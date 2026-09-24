"""Export blinded explanation material; evaluate separately supplied predictions."""
import argparse
import collections
import json
import random
from pathlib import Path

from .common import digest, read, write
from .run import records


def export(run_path, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError('Choose a new blinded export directory')
    run = read(Path(run_path)/'run.json')
    if run['identity']['stage'] != 'harvest' or run['status'] != 'completed':
        raise ValueError('Interpretation export requires completed discovery/selection harvest')
    grouped = collections.defaultdict(lambda: collections.defaultdict(list))
    for record in records(Path(run_path)/'activation_rows.jsonl'):
        for example in record['examples']:
            grouped[example['feature_id']][example['split']].append(example)
    development, challenges, private = [], [], {}
    for number, (feature, splits) in enumerate(sorted(grouped.items())):
        alias = f'feature_{number:03d}'
        dev = splits['discovery']
        active = sorted((e for e in dev if e['activation'] > 0), key=lambda e: e['activation'], reverse=True)
        inactive = [e for e in dev if e['activation'] == 0 and e['sampling'] == 'uniform']
        rng = random.Random(feature)
        rng.shuffle(inactive)
        # Include both strong and moderate positives, not only maxima.
        chosen = active[:8] + active[len(active)//2:len(active)//2+8] + inactive[:8]
        chosen = list({(e['row_id'], e['token_position']): e for e in chosen}.values())
        development.append({'feature_alias': alias,
                            'instruction': 'Explain the activation pattern using only these contexts. State uncertainty and alternatives.',
                            'examples': [{k: e[k] for k in ('context', 'token', 'activation')} for e in chosen],
                            'coverage': {'positive_examples': len(active), 'sampled_inactive_examples': len(inactive)}})
        validation = splits['selection']
        positive = [e for e in validation if e['activation'] > 0]
        negative = [e for e in validation if e['activation'] == 0 and e['sampling'] == 'uniform']
        rng.shuffle(positive); rng.shuffle(negative)
        count = min(20, len(positive), len(negative))
        cases = positive[:count] + negative[:count]
        rng.shuffle(cases)
        for e in cases:
            cid = digest([alias, e['row_id'], e['token_position']])[:24]
            challenges.append(dict(id=cid, feature_alias=alias, context=e['context'], token=e['token']))
            private[cid] = {'feature_id': feature, 'active': e['activation'] > 0,
                            'scenario_id': e['scenario_id']}
    output.mkdir(parents=True)
    write(output/'explanation_inputs.json', development)
    write(output/'heldout_challenges.json', challenges)
    write(output/'private_answer_key.json', private)
    write(output/'instructions.json', {
        'source_run_plan_hash': run['identity']['plan_hash'],
        'steps': ['Generate descriptions from explanation_inputs.json without access to labels or the private answer key.',
                  'Lock descriptions before viewing heldout_challenges.json.',
                  'A separate evaluator predicts active=true/false from each description and heldout context.',
                  'Supply a JSON list of {id, predicted_active} to the score command.',
                  'Keep private_answer_key.json out of explainer/evaluator context.'],
        'limitations': ['This starter export uses task text only, not a general-text corpus.',
                        'Held-out scenarios are separate; benchmark both existing and new explanations on the same items.',
                        'This measures activation-label prediction, not causal steering.']})
    return {'features': len(development), 'heldout_items': len(challenges), 'directory': str(output)}


def score(export_path, predictions_path, output):
    key = read(Path(export_path)/'private_answer_key.json')
    predictions = read(predictions_path)
    by_id = {p['id']: p for p in predictions}
    if len(by_id) != len(predictions) or set(by_id) != set(key):
        raise ValueError('Provide exactly one prediction for every challenge; no duplicate, missing or unknown IDs')
    counts = collections.defaultdict(lambda: {'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0})
    for cid, truth in key.items():
        value = by_id[cid]['predicted_active']
        if not isinstance(value, bool):
            raise ValueError('predicted_active must be a JSON boolean')
        field = 'tp' if value and truth['active'] else 'fp' if value else 'fn' if truth['active'] else 'tn'
        counts[truth['feature_id']][field] += 1
    report = []
    for feature, c in sorted(counts.items()):
        positive, negative = c['tp']+c['fn'], c['tn']+c['fp']
        report.append({'feature_id': feature, **c,
                       'balanced_accuracy': .5*(c['tp']/positive+c['tn']/negative) if positive and negative else None})
    write(output, {'scores': report, 'note': 'Descriptive task-corpus accuracy; small samples and correlated examples limit precision.'})
    return {'features_scored': len(report), 'output': str(output)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['export', 'score'])
    p.add_argument('--run'); p.add_argument('--export'); p.add_argument('--predictions')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    if args.action == 'export':
        if not args.run: p.error('--run is required')
        result = export(args.run, args.output)
    else:
        if not args.export or not args.predictions: p.error('--export and --predictions are required')
        result = score(args.export, args.predictions, args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
