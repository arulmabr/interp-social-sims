"""Recompute replay errors from saved readouts and deliver an audited report."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from .cpt import probabilities
from .design import digest
from .replay_plan import CONDITIONS
from .replay import identity_gate
from .smoke import save_json


LABELS={'baseline':'Base model','lora':'Full LoRA','raw_all_replace':'Raw: all positions, exact replacement',
        'raw_all_add':'Raw: all positions, additive difference','raw_final_replace':'Raw: final position, prompt-specific',
        'raw_context_replace':'Raw: context positions only','mean_final':'Raw: discovery mean, original magnitude',
        'mean_final_norm1':'Raw: discovery mean, norm 1','sae_encoder_all':'SAE encoder difference: all positions',
        'sae_encoder_final':'SAE encoder difference: final position','sae_subspace10_all':'SAE 10-feature subspace: all positions',
        'sae_subspace10_final':'SAE 10-feature subspace: final position','sae_subspace30_all':'SAE 30-feature subspace: all positions',
        'sae_subspace30_final':'SAE 30-feature subspace: final position','sae_mean10_final':'SAE 10-feature fixed mean: final position',
        'sae_mean30_final':'SAE 30-feature fixed mean: final position'}


def build(run,fixture=False):
    report=json.loads((run/'report.json').read_text());plan=json.loads((run/'plan.json').read_text())
    assert report['status']==('fixture_completed' if fixture else 'completed')
    assert bool(report['fixture'])==fixture
    rows=json.loads((run/'frozen_rows.json').read_text());n=len(rows)
    assert n==(6 if fixture else 540)
    all_rows=json.loads((run/'rows.json').read_text());assert digest(all_rows)==plan['rows_sha256']
    lock=json.loads((run/'selection_lock.json').read_text());assert lock['frozen_responses_opened'] is False
    assert lock['conditions']==CONDITIONS
    frozen={k:json.loads((run/f'frozen_scores_{k}.json').read_text()) for k in CONDITIONS}
    assert all(len(v)==n for v in frozen.values())
    selection={k:json.loads((run/f'selection_scores_{k}.json').read_text()) for k in CONDITIONS}
    assert all(len(v)==(6 if fixture else 36) for v in selection.values())
    assert identity_gate(selection)['passed'] and identity_gate(frozen)['passed']
    for records in frozen.values():
        for r in records:
            assert np.isfinite([r['margin'],r['p_risky'],r['answer_mass']]).all()
            assert 0<=r['p_risky']<=1 and 0<=r['answer_mass']<=1.00001
            assert abs(r['p_risky']-1/(1+np.exp(-r['margin'])))<1e-6
    reference=np.array([r['p_risky'] for r in frozen['lora']]);teacher=probabilities(rows,plan['target'])
    groups={}
    for i,r in enumerate(rows):groups.setdefault(r['economic_id'],[]).append(i)
    assert all(len(g)==2 for g in groups.values())
    group_array=np.array(list(groups.values()));rng=np.random.default_rng(918)
    samples=group_array[rng.integers(0,len(group_array),size=(1000,len(group_array)))].reshape(1000,-1)
    summary={}
    for name,records in frozen.items():
        p=np.array([r['p_risky'] for r in records]);error=p-reference;teacher_error=p-teacher
        rmse=float(np.sqrt(np.mean(error**2)));trmse=float(np.sqrt(np.mean(teacher_error**2)))
        assert abs(rmse-report['summary'][name]['rmse_to_lora'])<1e-12
        assert abs(trmse-report['summary'][name]['teacher_probability_rmse'])<1e-12
        summary[name]={**report['summary'][name],
                       'rmse_to_lora_scenario_interval':np.quantile(np.sqrt(np.mean(error[samples]**2,axis=1)),[.025,.975]).tolist(),
                       'teacher_rmse_scenario_interval':np.quantile(np.sqrt(np.mean(teacher_error[samples]**2,axis=1)),[.025,.975]).tolist()}
    contrasts={}
    for first,second in [('raw_all_replace','raw_final_replace'),('raw_final_replace','mean_final'),
                         ('mean_final','mean_final_norm1'),('raw_all_replace','sae_encoder_all'),
                         ('raw_all_replace','sae_subspace30_all'),('raw_final_replace','sae_subspace30_final')]:
        a=np.array([r['p_risky'] for r in frozen[first]])-reference
        b=np.array([r['p_risky'] for r in frozen[second]])-reference
        differences=np.sqrt(np.mean(b[samples]**2,axis=1))-np.sqrt(np.mean(a[samples]**2,axis=1))
        contrasts[first+' -> '+second]={'rmse_increase':summary[second]['rmse_to_lora']-summary[first]['rmse_to_lora'],
                                       'paired_scenario_interval':np.quantile(differences,[.025,.975]).tolist()}
    save_json(run/'replay_analysis.json',{'summary':summary,'contrasts':contrasts,'bootstrap':{
        'replicates':1000,'seed':918,'unit':'paired economic scenario','training_seed_uncertainty':False}})
    with (run/'comparison.csv').open('w') as file:
        writer=csv.writer(file);writer.writerow(['condition','rmse_to_lora','teacher_probability_rmse','min_answer_mass','dominance_violations','dominance_n','provisional_reproduction'])
        for k,v in summary.items():writer.writerow([k,v['rmse_to_lora'],v['teacher_probability_rmse'],v['min_answer_mass'],v['dominance_violations'],v['dominance_n'],v['passed_provisional_reproduction']])
    verified=0;manifest=run.parent.parent/'verified_remote_files.json'
    if manifest.exists():
        backup=manifest.parent
        for name,record in json.loads(manifest.read_text()).items():
            assert hashlib.sha256((backup/name).read_bytes()).hexdigest()==record['sha256'],name
            verified+=1
    elif not fixture:raise RuntimeError('Missing verified remote transfer manifest')
    if not fixture:
        session=json.loads(Path('anchor_pilot/outputs/replay-session.json').read_text())
        launch=Path('anchor_pilot/outputs')/('launch-'+session.get('execution_session',session['session'])+'.json')
        launched=json.loads(launch.read_text())['source_hashes']
        for f in (run/'execution_source').glob('*.py'):
            assert hashlib.sha256(f.read_bytes()).hexdigest()==launched['anchor_pilot/'+f.name],f.name
    audit={'status':'verified','fixture':fixture,'frozen_rows':n,'development_rows':len(selection['baseline']),
           'conditions':len(frozen),'frozen_readouts':n*len(frozen),'all_probability_metrics_recomputed':True,
           'all_state_identity':identity_gate(frozen),'remote_files_sha256_verified':verified,
           'rows_match_locked_manifest':True,'execution_source_matches_launched_source':not fixture}
    save_json(run/'replay_audit.json',audit)
    lines=['# Replay diagnostic results','',
           'This is a provisional representation diagnostic. The full external scientific go/pivot rule remains unavailable.','',
           f'{n} new frozen prompts, {len(frozen)} conditions; saved repair checkpoint 700; no retraining.','',
           '## Main comparison','',
           '| Intervention | RMSE to full LoRA | RMSE to planted teacher | Minimum A/B mass |',
           '|---|---:|---:|---:|']
    for k,v in summary.items():lines.append(f'| {LABELS[k]} | {v["rmse_to_lora"]:.5f} | {v["teacher_probability_rmse"]:.5f} | {v["min_answer_mass"]:.6f} |')
    lines +=['','## Interpretation limits','',
             'All-position raw replacement and addition are engineering identity controls. Prompt-specific raw and SAE replays use adapted activations from the same prompt; they do not establish independent steering.',
             'The encoder method uses all latent differences, with no top-k restriction. The 10/30-feature supports were selected geometrically from an earlier discovery mean. Their coefficients vary per prompt and token in the subspace conditions. Mean conditions use one fixed vector.',
             'Original magnitudes are retained, except the explicitly named norm-1 mean control. All-position and final-token comparisons change intervention scope and are not common-total-norm comparisons.',
             'Failure of these SAE methods does not establish that no sparse preference intervention exists. Causal feature reselection remains separate work.',
             'Bootstrap intervals in replay_analysis.json resample answer-order-paired scenarios, not training seeds. These are interpolated reward levels under the same prompt template, not task-family generalization.','',
             '## Full LoRA fitted parameters','', '| Parameter | Planted | Recovered |','|---|---:|---:|']
    for k,v in plan['target'].items():lines.append(f'| {k} | {v:.5f} | {summary["lora"]["cpt_fit"]["parameters"][k]:.5f} |')
    lines+=['','## Integrity','',f'All {verified} files listed in the remote transfer manifest verified. Raw-score metrics were recomputed locally; both development and frozen complete-state identity gates passed.',
            'See replay_audit.json, replay_analysis.json, comparison.csv, raw score files, and execution_source/.']
    (run/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(audit))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path);parser.add_argument('--fixture',action='store_true')
    args=parser.parse_args();build(args.run,args.fixture)
