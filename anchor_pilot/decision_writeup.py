"""Build a source-linked result note from the audited numerical outputs."""
import argparse
import json
from pathlib import Path


LABELS={'PROCEED_WITH_BOUNDED_SAE_CONFIRMATION':'Proceed to a bounded SAE confirmation.',
        'PIVOT_TESTED_SPARSE_RECIPE':'Pivot the tested sparse SAE recipe; the matched dense vector passed.',
        'PIVOT_TESTED_CONSTANT_VECTOR_FORMAT':'Pivot this constant-vector steering recipe; the LoRA passed but both constrained methods failed.',
        'INCONCLUSIVE_EVALUATION_OR_ANCHOR_TRANSFER':'The full go/pivot verdict is inconclusive because the anchor or evaluation prerequisite failed.',
        'INCONCLUSIVE_FOR_STRONG_NEGATIVE_CLAIM':'The tested methods did not establish a robust positive, but the evidence is insufficient for a strong negative.'}
LABELS['INCONCLUSIVE_TARGET_CONTROL_WITH_PREFERENCE_LIKE_SIGNAL']='Target control failed, but a replicated preference-like pattern prevents a negative claim about preference capacity.'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args();root=args.root.resolve()
    read=lambda name:json.loads((root/name).read_text())
    result=read('decision_analysis.json');lock=read('selection_lock.json');plan=read('plan.json');audit=read('delivery_audit.json')
    prior=read('prior_anchor_rule_checks.json');session=json.loads(Path('anchor_pilot/outputs/decision-session.json').read_text())
    lines=['# SAE steering decision experiment','',LABELS[result['verdict']],
           '',f"**Operational verdict:** `{result['verdict']}`. This applies to the fixed candidate set, layer, doses, token scopes and optimization budget below. It is not a universal result about SAEs.",
           '',f"The new rule classified the LoRA anchor as passing: **{result['loRA_anchor_passed']}**. A valid raw readout control was classified as action-like: **{result['action_anchor_passed']}**.",
           '', '## What was tested','',
           'A pinned bf16 Llama-3.3-70B and its released layer-50 SAE; the saved combined-CPT LoRA; 37 candidate features at both signs and two token scopes; 16 initial fits covering two targets, two methods, two scopes and two seeds. Each initial fit used 160 updates. The eight fits in the jointly selected scopes then received 480 additional updates. No LoRA was retrained.',
           '', 'The ten SAE features were chosen by intervention performance across the discovery reward grid. Coefficients were then trained on discovery prompts. Both dense and sparse methods shared the selected norm and scope for each target. None used adapted activations from frozen prompts. Extra optimization was declared during stage-one training, before frozen outputs were inspected; stage-one frozen scores were sealed and excluded from refinement and selection.',
           '', 'Discovery had 216 prompts and selection 96. The frozen set had 108 new economic scenarios, each tested with both answer orders and two wording templates (432 prompts per condition). Forty-eight separate elementary comprehension questions were also evaluated.',
           '', '## Held-out target error','',
           'RMSE of risky-choice probabilities against the planted target; lower is better. The declared limit was 0.060. Ranges show the two independently fitted vectors, not uncertainty intervals.',
           '', '| Target | Intervention | Original wording | New wording |', '|---|---|---:|---:|']
    results=result['conditions']
    for target in ('combined','neutral'):
        for method in ('baseline','lora','dense','sae10'):
            if method=='lora' and target=='neutral':continue
            names=[method] if method in ('baseline','lora') else result['methods'][method]['conditions']
            if method in ('dense','sae10'):names=[n for n in names if n.startswith(target+'_')]
            vals=[]
            for template in ('original','transfer'):
                x=[results[n]['templates'][template]['targets'][target]['teacher_rmse'] for n in names]
                vals.append(f'{x[0]:.3f}' if len(x)==1 else f'{min(x):.3f}–{max(x):.3f}')
            lines.append(f'| {target} | {method} | {vals[0]} | {vals[1]} |')
    lines+=['', '## Decision checks','']
    for method,details in result['methods'].items():
        lines.append(f"- **{method}:** {details['passed_cells']}/{details['total_cells']} target × seed × template cells passed all criteria. In {details['accuracy_excluded_cells']}/{details['total_cells']} cells, the scenario-bootstrap lower bound on teacher RMSE exceeded 0.060.")
        lines.append(f"  Preference-like behavior without requiring the exact planted parameters: {details['preference_like_cells']}/{details['total_cells']} cells; replicated across both seeds and wordings for a target: {details['robust_preference_like_state']}.")
    for target,choice in lock['choices'].items():
        c=choice['selected'];lines.append(f"- **{target} matched comparison:** scope `{c['scope']}`, per-position norm {c['dose']:g}.")
    lines+=['', 'The complete checks include held-out CPT prediction, comparison with frame-specific answer-bias/temperature models, parameter recovery, answer-order sensitivity, dominance, answer mass, elementary comprehension and realized bf16 displacement norms. See the numerical table for every condition; failed checks are retained.',
            '', '## Anchor recovery and generalization','', '| Wording | α curvature | γ weighting | λ loss aversion | β temperature | Earlier strict repair rule |', '|---|---:|---:|---:|---:|---|']
    for template in ('original','transfer'):
        params=prior[template]['fit']['parameters']
        lines.append(f"| {template} | {params['curvature']:.3f} | {params['weighting']:.3f} | {params['loss_aversion']:.3f} | {params['inverse_temperature']:.3f} | {'Pass' if prior[template]['passed_operational_recovery_target'] else 'Fail'} |")
    lines+=['', 'Planted combined values: α=0.8, γ=0.72, λ=2, β=3, A-label bias=0. The earlier strict repair rule used teacher RMSE ≤0.04 and tighter parameter tolerances. It is reported separately from this predeclared operational comparison; the two rules must not be conflated.',
            '', '## Qualifications','',
            '- This tests one constant signed decoder combination per target. It does not test prompt-conditioned SAE controllers, larger feature sets, other layers or all dictionaries.',
            '- Failure to recover the particular planted agent is not itself proof of absent preference-like behavior. The separate preference-like check omits teacher accuracy and planted-parameter tolerances; a replicated passing pattern blocks a strong negative capacity interpretation.',
            '- A failed optimizer/candidate budget is not a proof that no vector exists. Checkpoint histories and both seeds are included so optimization limits remain visible.',
            '- The single saved LoRA training seed remains a limitation; no matched neutral LoRA was trained. Two planted steering targets help test specificity but do not establish a preference-only mechanism.',
            '- The action model covers the declared frame, label and temperature shortcuts. It does not cover every possible shortcut. Synthetic calibration detected 7/7 preference alternatives and rejected 20/20 specified action nulls; this is not a population error-rate guarantee.',
            '- Bootstrap intervals resample the designed economic scenarios while keeping answer orders and templates together. They do not establish generalization to every possible wording, task or model.',
            '- The collaborator’s full scientific go/pivot rule was unavailable. These are explicitly declared operational thresholds.',
            '', '## Execution and evidence','',
            f"The run completed all {audit['frozen_conditions']} frozen conditions. {audit['remote_files_sha256_verified']} remote files were verified locally by SHA-256. Provider shutdown was confirmed; the pod has been stopped."]
    if 'estimated_session_cost' in session:lines.append(f"Estimated new session cost: **${session['estimated_session_cost']:.2f}**, within the $20/two-hour ceiling. Previously retained storage is separate.")
    lines+=['',f'[Complete comparison table]({root}/decision_comparison.csv) · [Machine-readable decisions and failed gates]({root}/decision_analysis.json) · [Delivery audit]({root}/delivery_audit.json)',
            '',f'![Fresh original wording]({root}/decision_curves_original.png)',
            '',f'![Fresh alternative wording]({root}/decision_curves_transfer.png)','']
    text='\n'.join(lines);(root/'DECISION_RESULTS.md').write_text(text);Path('anchor_pilot/DECISION_RESULTS.md').write_text(text)
    print(str(root/'DECISION_RESULTS.md'))


if __name__=='__main__':main()
