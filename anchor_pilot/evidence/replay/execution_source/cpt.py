"""Cumulative prospect theory, TK92 weights, shared gain/loss curvature.

Outcomes are changes from reference wealth, in units of 100 tokens. Choice
noise is an explicit logistic rule; label bias favors displayed answer A.
This is a deliberately restricted CPT family, not a general identification
claim about every possible probability-weighting or reference-point model.
"""
from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit


@dataclass(frozen=True)
class Parameters:
    curvature: float = 0.8
    weighting: float = 0.72
    loss_aversion: float = 2.0
    inverse_temperature: float = 3.0
    label_bias: float = 0.0


NAMES = list(asdict(Parameters()))
BOUNDS = [(0.25, 1.5), (0.35, 1.5), (0.3, 4.0), (0.25, 12.0), (-8.0, 8.0)]


def weight(p, gamma):
    p = np.clip(np.asarray(p, dtype=float), 0, 1)
    return p**gamma / (p**gamma + (1 - p)**gamma)**(1 / gamma)


def prepare(rows):
    """Precompute rank-dependent cumulative probability intervals."""
    x = np.zeros((len(rows), 2, 2))
    high, low = np.zeros_like(x), np.zeros_like(x)
    for i, row in enumerate(rows):
        for j, option in enumerate((row['risky'], row['safe'])):
            if len(option) > 2 or abs(sum(p for _, p in option) - 1) > 1e-8:
                raise ValueError('Expected a valid prospect with at most two outcomes')
            ordered = sorted(option)
            for k, (outcome, probability) in enumerate(ordered):
                if probability < 0:
                    raise ValueError('Negative probability')
                x[i, j, k] = outcome / 100.0
                if outcome < 0:
                    high[i, j, k] = sum(p for o, p in ordered if o <= outcome)
                else:
                    high[i, j, k] = sum(p for o, p in ordered if o >= outcome)
                low[i, j, k] = high[i, j, k] - probability
    return x, high, low, np.array([1 if r['risky_label'] == 'A' else -1 for r in rows])


def margin(prepared, parameters):
    if isinstance(parameters, dict):
        parameters = [parameters[name] for name in NAMES]
    if isinstance(parameters, Parameters):
        parameters = list(asdict(parameters).values())
    alpha, gamma, lam, beta, bias = parameters
    x, high, low, label_sign = prepared
    values = np.sign(x) * np.abs(x)**alpha * np.where(x < 0, lam, 1)
    utilities = (values * (weight(high, gamma) - weight(low, gamma))).sum(axis=-1)
    return beta * (utilities[:, 0] - utilities[:, 1]) + bias * label_sign


def probabilities(rows, parameters=Parameters()):
    return expit(margin(prepare(rows), parameters))


def fit(rows, targets, starts=6, seed=17):
    targets = np.asarray(targets, dtype=float)
    if targets.shape != (len(rows),) or not np.isfinite(targets).all() or np.any((targets < 0) | (targets > 1)):
        raise ValueError('Targets must be finite risky-choice fractions in [0, 1]')
    inputs = prepare(rows)

    def loss(theta):
        logits = margin(inputs, theta)
        return np.mean(np.logaddexp(0, logits) - targets * logits)

    rng = np.random.default_rng(seed)
    initial = [[1, 1, 1, 2, 0]]
    initial += [rng.uniform([b[0] for b in BOUNDS], [b[1] for b in BOUNDS]) for _ in range(starts - 1)]
    results = [minimize(loss, x, method='L-BFGS-B', bounds=BOUNDS,
                        options={'maxiter': 800, 'ftol': 1e-12, 'gtol': 1e-7}) for x in initial]
    converged = [r for r in results if r.success and np.isfinite(r.fun)]
    best = min(converged or results, key=lambda r: r.fun)
    predictions = expit(margin(inputs, best.x))
    return {'parameters': dict(zip(NAMES, best.x.tolist())), 'cross_entropy': float(best.fun),
            'probability_rmse': float(np.sqrt(np.mean((predictions - targets)**2))),
            'converged': bool(best.success),
            'boundary_parameters': [name for name, v, (a, b) in zip(NAMES, best.x, BOUNDS)
                                    if min(v - a, b - v) < 0.001 * (b - a)],
            'starts': starts}


def identifiability(rows, parameters=Parameters()):
    theta = np.array(list(asdict(parameters).values()))
    inputs = prepare(rows)
    jacobian = []
    for j in range(len(theta)):
        delta = np.zeros_like(theta)
        delta[j] = 1e-5
        jacobian.append((margin(inputs, theta + delta) - margin(inputs, theta - delta)) / 2e-5)
    jacobian = np.array(jacobian).T
    p = expit(margin(inputs, theta))
    weighted = jacobian * np.sqrt(p * (1 - p))[:, None]
    singular = np.linalg.svd(weighted, compute_uv=False)
    return {'rank': int(np.linalg.matrix_rank(weighted)), 'parameter_count': len(theta),
            'singular_values': singular.tolist(), 'condition_number': float(singular[0] / singular[-1])}


def group_bootstrap(rows, targets, replicates=100, seed=913):
    groups = sorted({r['economic_id'] for r in rows})
    by_group = {g: [i for i, r in enumerate(rows) if r['economic_id'] == g] for g in groups}
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(replicates):
        indices = [i for g in rng.choice(groups, len(groups), replace=True) for i in by_group[g]]
        result = fit([rows[i] for i in indices], np.asarray(targets)[indices], starts=2)
        if result['converged']:
            samples.append([result['parameters'][n] for n in NAMES])
    return {'replicates': replicates, 'converged_replicates': len(samples),
            'intervals_95': {n: np.quantile(np.array(samples)[:, j], [.025, .975]).tolist()
                             for j, n in enumerate(NAMES)} if samples else {},
            'interpretation': 'Variation over economic scenarios, preserving both label orders; not a sampling CI for one deterministic LLM prompt.'}
