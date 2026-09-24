"""Paired scenario bootstrap, engineering checks and a frozen selection lock.

No generated-text quality is inferred without blinded human/model ratings.
"""
import argparse
import collections
import json
import random
from pathlib import Path
from statistics import mean

from .common import digest, file_hash, read, write
from .design import metric
from .prepare import load_plan
from .run import conditions, records, quantile


def summarize(rows, scores, bootstrap=1000):
    by_id = {r['id']: r for r in rows}
    if len(by_id) != len(rows):
        raise ValueError('Duplicate row IDs')
    seen = set()
    for score in scores:
        key = score['row_id'], score['condition']['id']
        if key in seen or score['row_id'] not in by_id:
            raise ValueError('Duplicate or unknown score')
        seen.add(key)
    baseline = {s['row_id']: s for s in scores if s['condition']['id'] == 'baseline'}
    grouped = collections.defaultdict(list)
    for score in scores:
        grouped[(score['construct'], score['condition']['id'])].append(score)
    result = []
    for (construct, condition), values in sorted(grouped.items()):
        entry = dict(construct=construct, condition=condition, rows=len(values))
        if construct == 'creativity':
            entry.update(status='awaiting_blinded_quality_ratings',
                         generated_tokens_mean=mean(v['generated_tokens'] for v in values))
            result.append(entry)
            continue
        differences = collections.defaultdict(list)
        order_pairs = collections.defaultdict(dict)
        for value in values:
            row = by_id[value['row_id']]
            if value['row_id'] not in baseline:
                raise ValueError('Missing paired baseline')
            differences[row['scenario_id']].append(metric(row, value['p_target']) - metric(row, baseline[row['id']]['p_target']))
            order_pairs[(row['scenario_id'], row['template'])][row['target_label']] = value['p_target']
        cluster_means = [mean(v) for v in differences.values()]
        rng = random.Random(913)
        draws = [mean(rng.choices(cluster_means, k=len(cluster_means))) for _ in range(bootstrap)]
        effect = mean(cluster_means)
        metric_name = 'p_target' if construct == 'risk' else 'signed_p_target_index'
        if construct in ('altruism', 'fairness'):
            # Both feature families use accept as the target on the same game.
            strata = collections.defaultdict(list)
            offers = collections.defaultdict(list)
            scenario_strata = {}
            for value in values:
                cov = by_id[value['row_id']]['covariates']
                strata[cov['offer_stratum']].append(value)
                offers[(cov['total'], cov['offer'], cov['offer_percent'])].append(value)
                scenario_strata[by_id[value['row_id']]['scenario_id']] = cov['offer_stratum']
            def acceptance_summary(items):
                return {'rows': len(items), 'acceptance_mean': mean(v['p_target'] for v in items),
                        'baseline_acceptance_mean': mean(baseline[v['row_id']]['p_target'] for v in items),
                        'paired_acceptance_change': mean(v['p_target']-baseline[v['row_id']]['p_target'] for v in items)}
            entry['offer_strata'] = {name: acceptance_summary(items) for name, items in sorted(strata.items())}
            entry['offer_curve'] = [dict(total=total, offer=offer, offer_percent=percent, **acceptance_summary(items))
                                    for (total, offer, percent), items in sorted(offers.items())]
            metric_name = 'ultimatum_acceptance_probability'
            if construct == 'fairness':
                # Increased rejection of below-equal offers relative to equal
                # offers. Equal-weight stratum means prevent the many unequal
                # offers from turning blanket rejection into a fairness score.
                stratified = collections.defaultdict(list)
                for scenario, items in differences.items():
                    stratified[scenario_strata[scenario]].append(mean(items))
                low, equal = stratified['below_equal'], stratified['equal']
                if not low or not equal:
                    raise ValueError('Fairness contrast requires below-equal and equal offers')
                effect = mean(equal) - mean(low)
                draws = [mean(rng.choices(equal, k=len(equal)))-mean(rng.choices(low, k=len(low)))
                         for _ in range(bootstrap)]
                metric_name = 'below_equal_rejection_minus_equal_rejection'
                entry['bootstrap_strata'] = ['below_equal', 'equal']
        gaps = [abs(v['A']-v['B']) for v in order_pairs.values() if set(v) == {'A', 'B'}]
        entry.update(status='descriptive_pilot', scenarios=len(cluster_means),
                     metric=metric_name,
                     paired_effect=effect,
                     cluster_bootstrap_95=[quantile(draws, .025), quantile(draws, .975)],
                     answer_mass_min=min(v['answer_mass'] for v in values),
                     answer_mass_mean=mean(v['answer_mass'] for v in values),
                     order_gap_mean=mean(gaps) if gaps else None,
                     paired_order_groups=len(gaps))
        result.append(entry)
    return result


def analyze(plan_path, run_path, output):
    plan = load_plan(plan_path)
    run = read(Path(run_path)/'run.json')
    if run['identity']['plan_hash'] != plan['plan_hash']:
        raise ValueError('Run and plan differ')
    split = {'smoke': 'smoke', 'screen': 'discovery', 'selection': 'selection', 'confirm': 'frozen'}[run['identity']['stage']]
    scores = records(Path(run_path)/'scores.jsonl')
    rows = read(Path(plan_path)/f'{split}.json')
    table = summarize(rows, scores)
    lookup = {(s['row_id'], s['condition']['id']): s for s in scores}
    zero_checks = []
    for row in rows:
        base, zero = lookup.get((row['id'], 'baseline')), lookup.get((row['id'], 'zero_edit'))
        if base and zero:
            zero_checks.append(base.get('p_target', base.get('response')) == zero.get('p_target', zero.get('response')))
    report = {'plan_hash': plan['plan_hash'], 'run_stage': run['identity']['stage'],
              'run_status': run['status'], 'scores_sha256': file_hash(Path(run_path)/'scores.jsonl'),
              'zero_edit_checks': len(zero_checks), 'zero_edit_exact': bool(zero_checks) and all(zero_checks),
              'table': table, 'qualifications': ['Scenario bootstrap is conditional on the designed task set.',
                                                'A behavior change is not proof of a stable human-like trait.',
                                                'Ultimatum acceptance alone does not distinguish altruism from self-interest or efficiency preferences.',
                                                'Fairness is operationalized as differential rejection below equality; above-equal offers are reported separately.',
                                                'Creativity quality requires blinded ratings.']}
    write(output, report)
    return report


def lock_selection(plan_path, run_path, calibration_path, output):
    plan = load_plan(plan_path)
    run = read(Path(run_path)/'run.json')
    if run['identity']['stage'] != 'selection' or run['status'] != 'completed':
        raise ValueError('Only a completed selection-split run can choose frozen conditions')
    if run['identity']['plan_hash'] != plan['plan_hash'] or run['identity']['calibration_sha256'] != file_hash(calibration_path):
        raise ValueError('Plan or calibration mismatch')
    if Path(output).exists():
        raise FileExistsError('Selection locks are immutable')
    rows = read(Path(plan_path)/'selection.json')
    scores = records(Path(run_path)/'scores.jsonl')
    table = summarize(rows, scores)
    candidates, calibration = read(Path(plan_path)/'candidates.json'), read(calibration_path)
    expected = {(row['id'], c['id']) for row in rows for c in
                conditions(row['construct'], candidates, calibration, plan['dose_multipliers'])}
    observed = {(s['row_id'], s['condition']['id']) for s in scores}
    if observed != expected:
        raise ValueError('Selection scores do not cover exactly the prescribed rows and conditions')
    lookup = {(s['row_id'], s['condition']['id']): s for s in scores}
    for row in rows:
        base, zero = lookup[(row['id'], 'baseline')], lookup[(row['id'], 'zero_edit')]
        field = 'p_target' if row['kind'] == 'choice' else 'response'
        if base[field] != zero[field]:
            raise ValueError('Zero-edit invariance failed; resolve this before frozen evaluation')
    locked, decisions = {}, {}
    for construct in candidates:
        available = conditions(construct, candidates, calibration, plan['dose_multipliers'])
        names = {c['id'] for c in available}
        keep = ['baseline', 'zero_edit', 'prompt_simple', 'prompt_strong']
        # Pure label retrieval has a fixed rank-1 feature and fixed +0.5 dose.
        label_only = f"f{candidates[construct][0]['feature_id']}_d+0.5"
        if label_only in names:
            keep += [label_only, label_only+'_random']
        eligible = [r for r in table if r['construct'] == construct and r['condition'].startswith('f')
                    and not r['condition'].endswith('_random') and r['status'] == 'descriptive_pilot'
                    and r['answer_mass_min'] >= plan['min_answer_mass']]
        winner = max(eligible, key=lambda r: r['paired_effect'], default=None)
        if winner:
            keep += [winner['condition'], winner['condition']+'_random']
        # For creativity no response-length proxy is allowed to choose a winner.
        # Evaluate the predeclared label-only intervention; obtain ratings later.
        locked[construct] = sorted(set(keep))
        decisions[construct] = {'label_only': label_only if label_only in names else None,
                                'selection_winner': winner['condition'] if winner else None,
                                'selection_effect': winner['paired_effect'] if winner else None,
                                'note': 'No eligible measured winner' if not winner else 'Finite-budget selection; not a capacity claim'}
    value = {'plan_hash': plan['plan_hash'], 'calibration_sha256': file_hash(calibration_path),
             'selection_scores_sha256': file_hash(Path(run_path)/'scores.jsonl'),
             'conditions': locked, 'decisions': decisions}
    value['lock_hash'] = digest(value)
    write(output, value)
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['report', 'lock'])
    p.add_argument('--plan', required=True); p.add_argument('--run', required=True)
    p.add_argument('--output', required=True); p.add_argument('--calibration')
    args = p.parse_args()
    if args.action == 'lock':
        if not args.calibration:
            p.error('--calibration is required for selection locking')
        result = lock_selection(args.plan, args.run, args.calibration, args.output)
    else:
        result = analyze(args.plan, args.run, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != 'table'}, indent=2))


if __name__ == '__main__':
    main()
