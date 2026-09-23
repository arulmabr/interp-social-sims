"""Honest pilot diagnostics; no invented confirmatory go/pivot threshold."""
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from .cpt import fit, group_bootstrap, probabilities


def switches(rows, target):
    grouped = defaultdict(list)
    for row, p in zip(rows, target):
        grouped[row['grid_id']].append((row['reward'], float(p)))
    result = {}
    for key, values in grouped.items():
        by_reward = defaultdict(list)
        for reward, p in values:
            by_reward[reward].append(p)
        curve = sorted((r, float(np.mean(p))) for r, p in by_reward.items())
        crossings = []
        for (x1, y1), (x2, y2) in zip(curve, curve[1:]):
            if (y1 - .5) * (y2 - .5) < 0:
                crossings.append(x1 + (.5 - y1) * (x2 - x1) / (y2 - y1))
            elif y1 == .5:
                crossings.append(x1)
        if curve[-1][1] == .5:
            crossings.append(curve[-1][0])
        result[key] = {'crossings': crossings, 'curve': curve,
                       'status': 'unique' if len(crossings) == 1 else 'none_in_grid' if not crossings else 'nonmonotone_multiple'}
    return result


def cross_entropy(targets, predictions):
    p = np.clip(predictions, 1e-7, 1 - 1e-7)
    q = np.asarray(targets)
    return float(-np.mean(q * np.log(p) + (1 - q) * np.log1p(-p)))


def condition_summary(rows, records, baseline, bootstrap=0, planted=None):
    p = np.array([r['p_risky'] for r in records])
    test = [i for i, r in enumerate(rows) if r['split'] == 'frozen']
    train = [i for i, r in enumerate(rows) if r['split'] != 'frozen']
    result = {'n': len(rows), 'scientific_classification': None,
              'reason': 'Full externally specified go/pivot rule unavailable; diagnostic comparisons only.',
              'min_answer_mass': min(r['answer_mass'] for r in records),
              'mean_answer_mass': float(np.mean([r['answer_mass'] for r in records]))}
    for split in ('discovery', 'selection', 'frozen'):
        indices = [i for i, r in enumerate(rows) if r['split'] == split]
        if not indices:
            continue
        subset = [rows[i] for i in indices]
        ps = p[indices]
        result[split] = fit(subset, ps, starts=4)
        result[split]['switching_points'] = switches(subset, ps)
        if split == 'frozen' and bootstrap:
            result[split]['bootstrap'] = group_bootstrap(subset, ps, replicates=bootstrap)
    if test and train:
        trained = fit([rows[i] for i in train], p[train], starts=4)
        predicted = probabilities([rows[i] for i in test], trained['parameters'])
        # A simple action comparator: constant risky-label and A-label offsets
        # applied to the actual baseline logits. Fit without frozen responses.
        base = np.array([r['margin'] for r in baseline])
        signs = np.array([1 if r['risky_label'] == 'A' else -1 for r in rows])
        def objective(theta):
            m = base[train] + theta[0] + theta[1] * signs[train]
            return np.mean(np.logaddexp(0, m) - p[train] * m)
        action = minimize(objective, [0, 0], method='L-BFGS-B', bounds=[(-40, 40)] * 2)
        action_pred = expit(base[test] + action.x[0] + action.x[1] * signs[test])
        result['frozen_predictive_comparison'] = {
            'cpt_cross_entropy': cross_entropy(p[test], predicted),
            'cpt_rmse': float(np.sqrt(np.mean((p[test] - predicted)**2))),
            'action_offset_cross_entropy': cross_entropy(p[test], action_pred),
            'action_offset_rmse': float(np.sqrt(np.mean((p[test] - action_pred)**2))),
            'action_offsets_risky_A': action.x.tolist(), 'action_fit_converged': bool(action.success),
            'training_cpt': trained,
            'caveat': 'This two-offset comparator does not span every possible action shortcut.'}
    paired = defaultdict(dict)
    for row, value in zip(rows, p):
        paired[row['economic_id']][row['risky_label']] = value
    gaps = [abs(v['A'] - v['B']) for v in paired.values() if len(v) == 2]
    result['label_order_mean_absolute_probability_gap'] = float(np.mean(gaps)) if gaps else None
    reflected = defaultdict(dict)
    for row, value in zip(rows, p):
        if row['frame'] in ('gain', 'loss'):
            key = (row['probability'], row['stake'], row['ratio'], row['risky_label'])
            reflected[key][row['frame']] = float(value)
    mirror_pairs = [v for v in reflected.values() if len(v) == 2]
    result['gain_loss_reflection'] = {
        'matched_pairs': len(mirror_pairs),
        'opposite_argmax_fraction': float(np.mean([(v['gain'] - .5) * (v['loss'] - .5) < 0 for v in mirror_pairs])) if mirror_pairs else None,
        'pairs': [{'probability': k[0], 'stake': k[1], 'ratio': k[2], 'risky_label': k[3], **v}
                  for k, v in reflected.items() if len(v) == 2],
        'interpretation': 'Matched gain/loss lotteries under a fixed zero reference point; report alongside planted predictions and label-order sensitivity.'}
    dominant = [(r, value) for r, value in zip(rows, p) if r['dominant_option']]
    result['dominance'] = {'rows': len(dominant),
        'argmax_violation_rate': float(np.mean([value <= .5 if r['dominant_option'] == 'risky' else value >= .5
                                               for r, value in dominant])) if dominant else None,
        'note': 'A stochastic CPT agent can choose a dominated option with nonzero probability; argmax consistency is reported.'}
    if planted is not None and test:
        target = probabilities([rows[i] for i in test], planted)
        result['planted_recovery'] = {'truth': planted,
            'parameter_errors': {k: result['frozen']['parameters'][k] - v for k, v in planted.items()},
            'frozen_probability_rmse': float(np.sqrt(np.mean((p[test] - target)**2))),
            'frozen_cross_entropy': cross_entropy(target, p[test])}
    return result
