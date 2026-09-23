from collections import Counter
from dataclasses import asdict

import pytest
import torch

from anchor_pilot.cpt import probabilities
from anchor_pilot.design import AGENTS, build_rows
from anchor_pilot.modeling import (add_lora, batched_answer_loss, load_stack,
                                  prepare_inputs)
from anchor_pilot.pilot import evaluate
from anchor_pilot.repair import paired_batches, valid
from anchor_pilot.repair_design import MODULES, RATIOS, build_repair_rows, recovery_check


def test_repair_splits_are_disjoint_and_test_is_new():
    rows = build_repair_rows()
    assert Counter(r['split'] for r in rows) == {'discovery':2160, 'selection':540, 'frozen':540}
    assert len({r['id'] for r in rows}) == len(rows)
    assert len({r['text'] for r in rows}) == len(rows)
    old = {r['text'] for r in build_rows()}
    assert not old & {r['text'] for r in rows if r['split'] == 'frozen'}
    assert not set(RATIOS['frozen']) & {.55, 1.25, 2.3, 3.3, 6.5}
    owners = {}
    for row in rows:
        assert owners.setdefault(row['economic_id'], row['split']) == row['split']


def test_training_batches_keep_pairs_and_exclude_validation_and_frozen():
    rows = build_repair_rows()
    batches = list(paired_batches(rows, 8, 2, 3))
    assert batches == list(paired_batches(rows, 8, 2, 3))
    counts = Counter()
    for micros in batches:
        assert len(micros) == 2
        for indices in micros:
            assert len(indices) == 8
            for i,j in zip(indices[::2], indices[1::2]):
                a,b = rows[i],rows[j]
                assert a['split'] == b['split'] == 'discovery'
                assert a['economic_id'] == b['economic_id']
                assert {a['risky_label'],b['risky_label']} == {'A','B'}
                counts[a['frame']] += 1
    assert counts == {'gain':8,'loss':8,'mixed':8}
    with pytest.raises(ValueError):
        next(paired_batches(rows, 3, 1, 1))


def test_recovery_requires_parameters_probabilities_and_answer_validity():
    rows = [r for r in build_repair_rows() if r['split']=='frozen']
    records = [{'p_risky':float(p),'answer_mass':1.} for p in probabilities(rows, AGENTS['combined'])]
    good = recovery_check(rows, records)
    assert good['passed_operational_recovery_target']
    assert good['scientific_go_pivot'] is None
    wrong_target = {**asdict(AGENTS['combined']), 'curvature':1.5}
    wrong = [{'p_risky':float(p),'answer_mass':1.} for p in probabilities(rows, wrong_target)]
    assert not recovery_check(rows, wrong)['passed_operational_recovery_target']
    records[0]['answer_mass'] = .98
    assert not recovery_check(rows, records)['passed_operational_recovery_target']


def test_expanded_adapter_first_layer_and_mlp_receive_gradients():
    model, tokenizer, _, _, _, _ = load_stack(fixture=True)
    inputs = prepare_inputs(model, tokenizer, build_repair_rows(True)[:2])
    add_lora(model, 0, 2, rank=2, target_modules=MODULES)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    model.train()
    loss = batched_answer_loss(model, inputs, [.8,.2]);loss.backward()
    for module in MODULES:
        gradients = [p.grad for n,p in model.named_parameters()
                     if f'layers.0.' in n and f'.{module}.' in n and '.lora_B.' in n]
        assert len(gradients)==1
        assert gradients[0] is not None and torch.isfinite(gradients[0]).all() and gradients[0].norm()>0
    assert all(p.grad is None for n,p in model.named_parameters() if 'lora_' not in n)
    assert all(not p.requires_grad for p in model.model.layers[3].parameters())


def test_additive_records_preserve_position_count_and_norm_gate():
    model, tokenizer, decoder, _, layers, _ = load_stack(fixture=True)
    inputs = prepare_inputs(model, tokenizer, build_repair_rows(True)[:2])
    records,_ = evaluate(model, inputs, 2, direction=decoder[:,0], layer=layers[-1],rho=1.)
    assert all(r['positions_per_prompt']==1 for r in records)
    assert valid(records, minimum=0.)['passed']
    records[0]['actual_norm'] *= 1.1
    assert not valid(records, minimum=0.)['passed']


def test_early_stop_report_does_not_claim_test_results(tmp_path):
    import json
    from anchor_pilot.repair_report import build_report
    (tmp_path/'report.json').write_text(json.dumps({
        'status':'validation_recovery_failed','frozen_responses_opened':False,
        'fixture':False,'plan':{'target':asdict(AGENTS['combined'])}}))
    assert build_report(tmp_path, bootstrap=0)==0
    assert 'No frozen response scores were produced' in (tmp_path/'REPORT.md').read_text()
    assert not (tmp_path/'comparison.csv').exists()
    assert json.loads((tmp_path/'analysis_status.json').read_text())['scientific_go_pivot'] is None
