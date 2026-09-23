"""Freeze a modest identification grid and verify synthetic recovery on CPU."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

from .cpt import Parameters, fit, identifiability, probabilities


RATIOS = [.4, .65, .9, 1.15, 1.4, 1.75, 2.1, 2.5, 3., 3.6, 4.5, 6.]
SPLIT = ['discovery', 'selection', 'discovery', 'frozen', 'discovery', 'selection',
         'discovery', 'frozen', 'discovery', 'selection', 'discovery', 'frozen']
AGENTS = {'combined': Parameters(),
          'curvature_only': Parameters(curvature=.8, weighting=1, loss_aversion=1),
          'weighting_only': Parameters(curvature=1, weighting=.72, loss_aversion=1),
          'loss_aversion_only': Parameters(curvature=1, weighting=1, loss_aversion=2)}


def describe(option):
    parts = []
    for outcome, probability in option:
        change = f'gain {outcome:g}' if outcome > 0 else f'lose {-outcome:g}' if outcome < 0 else 'gain or lose 0'
        parts.append(f'{probability * 100:g}% chance to {change} tokens')
    return '; '.join(parts)


def render(row, persona='neutral'):
    instructions = {
        'neutral': 'Choose the option you prefer.',
        'risk_averse': 'Imagine you are a very cautious decision maker who dislikes financial risk. Choose the option you prefer.',
        'risk_seeking': 'Imagine you are an adventurous decision maker who enjoys financial risk. Choose the option you prefer.',
    }
    ordered = [('risky', row['risky']), ('safe', row['safe'])]
    if row['risky_label'] == 'B':
        ordered.reverse()
    return ('All outcomes are changes from your current token balance, which is the reference point. '
            'You have enough tokens to cover any losses. ' + instructions[persona] + '\n' +
            '\n'.join(f'Option {label}: {describe(option)}.' for label, (_, option) in zip('AB', ordered)) +
            '\nAnswer with exactly one letter: A or B.')


def build_rows():
    rows = []
    for frame in ('gain', 'loss', 'mixed'):
        for p in (.1, .25, .5, .75, .9):
            for stake in (25., 75.):
                grid_id = f'{frame}_p{p:g}_s{stake:g}'
                for index, ratio in enumerate(RATIOS):
                    reward = round(stake * ratio, 6)
                    if frame == 'gain':
                        risky, safe = [[reward, p], [0., 1 - p]], [[stake, 1.]]
                    elif frame == 'loss':
                        risky, safe = [[-reward, p], [0., 1 - p]], [[-stake, 1.]]
                    else:
                        risky, safe = [[reward, p], [-stake, 1 - p]], [[0., 1.]]
                    dominance = 'safe' if max(x for x, _ in risky) < safe[0][0] else \
                                'risky' if min(x for x, _ in risky) > safe[0][0] else None
                    economic_id = f'{grid_id}_r{index:02d}'
                    for risky_label in ('A', 'B'):
                        row = {'id': economic_id + '_' + risky_label, 'economic_id': economic_id,
                               'grid_id': grid_id, 'split': SPLIT[index], 'frame': frame,
                               'probability': p, 'stake': stake, 'reward': reward, 'ratio': ratio,
                               'risky': risky, 'safe': safe, 'risky_label': risky_label,
                               'safe_label': 'B' if risky_label == 'A' else 'A', 'dominant_option': dominance}
                        row['text'] = render(row)
                        rows.append(row)
    return rows


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate(rows, replicates=20):
    rng = np.random.default_rng(1701)
    results = {}
    for name, parameters in AGENTS.items():
        truth = asdict(parameters)
        agent = {}
        for split in ('discovery', 'selection', 'frozen'):
            subset = [r for r in rows if r['split'] == split]
            p = probabilities(subset, parameters)
            exact = fit(subset, p)
            maximum_error = max(abs(exact['parameters'][k] - truth[k]) for k in truth)
            if not exact['converged'] or maximum_error > .02:
                raise RuntimeError(f'Synthetic exact recovery failed: {name}/{split}')
            identification = identifiability(subset, parameters)
            if identification['rank'] != 5:
                raise RuntimeError(f'Rank deficient design: {name}/{split}')
            agent[split] = {'exact_recovery': exact, 'max_absolute_parameter_error': maximum_error,
                            'identifiability': identification}
        subset = [r for r in rows if r['split'] == 'frozen']
        p = probabilities(subset, parameters)
        # Stochastic choices from independent synthetic agents, not replicated
        # deterministic LLM calls. CPU check of finite-sample estimator behavior.
        simulated = []
        for _ in range(replicates):
            target = rng.binomial(64, p) / 64
            simulated.append(fit(subset, target, starts=3)['parameters'])
        agent['finite_sample_recovery'] = {
            'replicates': replicates, 'independent_choices_per_prompt': 64,
            'median_absolute_errors': {k: float(np.median([abs(s[k] - truth[k]) for s in simulated])) for k in truth},
            'parameter_estimates': simulated}
        results[name] = agent
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replicates', type=int, default=20)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = build_rows()
    from .smoke import save_json
    manifest = {'version': 1, 'seed': 17, 'rows': len(rows), 'economic_groups': len(rows) // 2,
                'split_counts': {s: sum(r['split'] == s for r in rows) for s in set(SPLIT)},
                'rows_sha256': digest(rows), 'agents': {k: asdict(v) for k, v in AGENTS.items()},
                'reference_point': 0, 'utility_scale_tokens': 100, 'choice_rule': 'logistic',
                'parameterization': 'shared gain/loss curvature and weighting; separate loss multiplier; fitted temperature and A-label bias',
                'scope': 'provisional pilot; scientific go/pivot thresholds unset',
                'synthetic_validation': validate(rows, args.replicates)}
    save_json(args.output / 'rows.json', rows)
    save_json(args.output / 'manifest.json', manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k != 'synthetic_validation'}, indent=2))


if __name__ == '__main__':
    main()
