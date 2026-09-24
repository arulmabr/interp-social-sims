import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from label_pilot.catalog import import_catalog, search
from label_pilot.common import read, write
from label_pilot.design import build_rows, assert_disjoint
from label_pilot.prepare import prepare, load_plan
from label_pilot.runtime import edit_hidden
from label_pilot.run import conditions, records, calibrate
from label_pilot.analyze import summarize, lock_selection
from label_pilot.interpret import score
from label_pilot.access import load_credentials


@pytest.fixture
def catalog_csv(tmp_path):
    path = tmp_path/'labels.csv'
    with path.open('w', newline='') as handle:
        writer = csv.writer(handle); writer.writerow(['id', 'label', 'index_in_sae'])
        for i, label in enumerate(['taking risks', 'taking risks', 'altruistic and selfless',
                                    'fairness and equality', 'creative innovation']):
            writer.writerow([f'uuid-{i}', label, i])
    return path


def test_duplicate_labels_preserve_distinct_feature_identity(catalog_csv, tmp_path):
    db = tmp_path/'catalog.sqlite'
    audit = import_catalog(catalog_csv, db)
    assert audit['rows'] == 5 and audit['unique_labels'] == 4
    assert {r['feature_id'] for r in search(db, 'taking risks')} == {0, 1}
    assert search(db, '" OR 1=1; --') == []


def test_duplicate_indices_rejected(catalog_csv, tmp_path):
    with catalog_csv.open('a') as handle: handle.write('other,some label,0\n')
    with pytest.raises(ValueError): import_catalog(catalog_csv, tmp_path/'bad.sqlite')


def test_scenario_splits_and_counterbalancing():
    rows = build_rows(); assert_disjoint(rows)
    groups = {}
    for row in rows:
        groups.setdefault(row['scenario_id'], []).append(row)
    for values in groups.values():
        assert len({v['split'] for v in values}) == 1
        if values[0]['kind'] == 'choice':
            assert {(v['template'], v['target_label']) for v in values} == {
                ('original','A'), ('original','B'), ('transfer','A'), ('transfer','B')}
    with pytest.raises(ValueError): assert_disjoint(rows + [dict(rows[0], id='changed', split='frozen')])


def test_plan_detects_input_changes(catalog_csv, tmp_path):
    out = tmp_path/'plan'; prepare(catalog_csv, out, 1)
    assert load_plan(out)['candidates_per_construct'] == 1
    data = read(out/'frozen.json'); data[0]['text'] += 'changed'; write(out/'frozen.json', data)
    with pytest.raises(ValueError, match='changed'): load_plan(out)


def test_ultimatum_games_share_prompts_and_preserve_payoffs_and_split_isolation():
    rows = build_rows()
    assert {r['construct'] for r in rows} == {'risk', 'altruism', 'fairness', 'creativity'}
    lookup = {}
    scenarios = {}
    for row in rows:
        if row['construct'] not in ('altruism', 'fairness'):
            continue
        cov = row['covariates']
        assert cov['offer'] + cov['proposer_payoff'] == cov['total']
        assert 0 < cov['offer'] < cov['total']
        assert cov['target_action'] == 'accept' and cov['role'] == 'responder'
        assert 'both of you receive zero' in row['text']
        assert f"{'Option ' if row['template']=='original' else ''}{row['target_label']}{':' if row['template']=='original' else ')'} Accept:" in row['text']
        key = (cov['total'], cov['offer'])
        assert scenarios.setdefault(key, row['split']) == row['split']
        lookup[(row['construct'], row['split'], row['scenario_id'], row['template'], row['target_label'])] = row
    for key, row in lookup.items():
        construct, *rest = key
        other = lookup[('fairness' if construct=='altruism' else 'altruism', *rest)]
        assert (row['text'], row['system']) == (other['text'], other['system'])
    discovery = {r['covariates']['offer'] for r in rows if r['construct']=='altruism' and r['split']=='discovery'}
    assert discovery == set(range(10, 91, 5))


@pytest.mark.parametrize('changes,expected', [
    ({'below_equal': -.2, 'equal': 0, 'above_equal': 0}, .2),
    ({'below_equal': -.2, 'equal': -.2, 'above_equal': -.2}, 0),
    ({'below_equal': 0, 'equal': -.2, 'above_equal': 0}, -.2),
])
def test_fairness_is_selective_rejection_not_blanket_rejection(changes, expected):
    rows = [r for r in build_rows() if r['construct']=='fairness' and r['split']=='discovery']
    scores = []
    for row in rows:
        for condition in ('baseline', 'test'):
            value = .5 + (changes[row['covariates']['offer_stratum']] if condition=='test' else 0)
            scores.append(dict(row_id=row['id'], construct='fairness', condition={'id':condition}, p_target=value, answer_mass=.99))
    entry = next(r for r in summarize(rows, scores, bootstrap=20) if r['condition']=='test')
    assert entry['paired_effect'] == pytest.approx(expected)
    assert len(entry['offer_curve']) == 17
    assert set(entry['offer_strata']) == {'below_equal', 'equal', 'above_equal'}
    assert entry['metric'] == 'below_equal_rejection_minus_equal_rejection'


def test_zero_edit_is_bitwise_identity():
    x = torch.randn(2, 3, 7).bfloat16()
    y, trace = edit_hidden(x, None, None, None, 0, 0)
    assert y is x and torch.equal(x, y) and trace['realized_norm_mean'] == 0


@pytest.mark.parametrize('delta', [-100.0, -.3, .7])
def test_sparse_update_matches_full_error_preserving_reconstruction(delta):
    torch.manual_seed(123)
    h, encoder, bias, decoder, dec_bias = torch.randn(2,3,7), torch.randn(11,7), torch.randn(11), torch.randn(7,11), torch.randn(7)
    z = torch.relu(h @ encoder.T + bias)
    reconstruction = z @ decoder.T + dec_bias
    edited = z.clone(); edited[...,4] = torch.clamp(edited[...,4]+delta, min=0)
    expected = edited @ decoder.T + dec_bias + h - reconstruction
    actual, trace = edit_hidden(h, encoder, bias, decoder, 4, delta)
    torch.testing.assert_close(actual, expected, atol=3e-6, rtol=2e-5)
    assert trace['after_mean'] >= 0


def test_random_control_matches_actual_feature_displacement_norm_float32():
    torch.manual_seed(19)
    h, encoder, bias, decoder = torch.randn(1,2,7), torch.randn(3,7), torch.randn(3), torch.randn(7,3)
    direction = torch.randn(7); direction /= direction.norm()
    normal, _ = edit_hidden(h, encoder, bias, decoder, 1, .7)
    random, _ = edit_hidden(h, encoder, bias, decoder, 1, .7, direction)
    torch.testing.assert_close((normal-h).norm(dim=-1), (random-h).norm(dim=-1))


def test_uncovered_features_are_not_assigned_invented_scales():
    c = {'risk': [{'feature_id': 1}, {'feature_id': 2}]}
    calibration = {'features': {'1': {'scale': None}, '2': {'scale': 3.0}}}
    result = conditions('risk', c, calibration, [-.5, .5])
    assert len(result) == 8
    assert not any(r['id'].startswith('f1_') for r in result)
    assert next(r for r in result if r['id']=='f2_d+0.5')['actual_delta'] == 1.5


def test_content_calibration_uses_prompt_maxima_excludes_special_tokens_and_selection():
    rows = [dict(split='discovery', final_position={'1':0}, examples=[
                dict(feature_id=1,activation=2,scope='user_content'),
                dict(feature_id=1,activation=4,scope='user_content'),
                dict(feature_id=1,activation=999,scope='special')]),
            dict(split='discovery', final_position={'1':0}, examples=[
                dict(feature_id=1,activation=6,scope='user_content')]),
            dict(split='selection', final_position={'1':999}, examples=[
                dict(feature_id=1,activation=999,scope='user_content')])]
    result=calibrate('plan','discovery',[1,2],rows,'user_content_prompt_max')
    assert result['features']['1']['scale']==pytest.approx(5.9)
    assert result['features']['1']['positive_prompt_count']==2
    assert result['features']['2']['scale'] is None
    old=calibrate('plan','discovery',[1],rows,'final_prompt_position')
    assert old['features']['1']['scale'] is None


def test_pairing_and_scenario_bootstrap_do_not_count_prompt_variants_as_scenarios():
    rows = [r for r in build_rows() if r['split']=='smoke' and r['construct']=='risk']
    scores = []
    for row in rows:
        for condition, probability in [('baseline', .2), ('test', .4)]:
            scores.append(dict(row_id=row['id'], construct='risk', condition={'id':condition},
                               p_target=probability, answer_mass=.99))
    report = summarize(rows, scores, bootstrap=20)
    test = next(r for r in report if r['condition']=='test')
    assert test['rows']==4 and test['scenarios']==1
    assert test['paired_effect']==pytest.approx(.2)
    assert test['order_gap_mean']==0


def test_frozen_results_cannot_select_conditions(catalog_csv, tmp_path):
    plan = tmp_path/'plan'; prepare(catalog_csv, plan, 1)
    run = tmp_path/'run'; write(run/'run.json', {'identity': {'stage':'confirm'},'status':'completed'})
    with pytest.raises(ValueError, match='selection-split'):
        lock_selection(plan, run, tmp_path/'calibration.json', tmp_path/'lock.json')


def test_partial_jsonl_does_not_silently_resume(tmp_path):
    path = tmp_path/'scores.jsonl'; path.write_text('{"row_id":"a"}\n{"row')
    with pytest.raises(ValueError, match='partial record'): records(path)


def test_interpretation_rejects_missing_predictions(tmp_path):
    write(tmp_path/'private_answer_key.json', {'a':{'feature_id':1,'active':True},'b':{'feature_id':1,'active':False}})
    write(tmp_path/'predictions.json', [{'id':'a','predicted_active':True}])
    with pytest.raises(ValueError, match='exactly one'): score(tmp_path, tmp_path/'predictions.json', tmp_path/'scores.json')


def test_credentials_file_requires_private_permissions(tmp_path):
    path=tmp_path/'credentials.json'; path.write_text('{}'); path.chmod(0o644)
    with pytest.raises(PermissionError): load_credentials(path)
