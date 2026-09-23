from dataclasses import asdict

import numpy as np
import pytest

from anchor_pilot.cpt import Parameters, fit, identifiability, margin, prepare, probabilities
from anchor_pilot.design import AGENTS, build_rows


def test_expected_value_special_case_and_dominance():
    rows = build_rows()
    p = Parameters(curvature=1, weighting=1, loss_aversion=1, inverse_temperature=1)
    observed = margin(prepare(rows), p)
    expected = [(sum(x*q for x,q in r['risky']) - sum(x*q for x,q in r['safe'])) / 100 for r in rows]
    assert np.allclose(observed, expected)
    cpt = probabilities(rows)
    for row, prob in zip(rows, cpt):
        if row['dominant_option'] == 'risky':
            assert prob > .5
        elif row['dominant_option'] == 'safe':
            assert prob < .5


def test_split_isolation_and_counterbalancing():
    rows = build_rows()
    for economic_id in {r['economic_id'] for r in rows}:
        group = [r for r in rows if r['economic_id'] == economic_id]
        assert len(group) == 2
        assert {r['risky_label'] for r in group} == {'A', 'B'}
        assert len({r['split'] for r in group}) == 1
    for grid in {r['grid_id'] for r in rows}:
        subset = [r for r in rows if r['grid_id'] == grid]
        sets = [{r['reward'] for r in subset if r['split'] == s} for s in ('discovery','selection','frozen')]
        assert not sets[0] & sets[1] and not sets[0] & sets[2] and not sets[1] & sets[2]


def test_loss_multiplier_cancels_deterministic_pure_loss_choice():
    rows = [r for r in build_rows() if r['frame'] == 'loss']
    first = margin(prepare(rows), Parameters(loss_aversion=1))
    second = margin(prepare(rows), Parameters(loss_aversion=3))
    assert np.allclose(second, 3 * first)
    assert np.array_equal(first > 0, second > 0)


@pytest.mark.parametrize('name', list(AGENTS))
def test_identification_and_exact_recovery(name):
    rows = [r for r in build_rows() if r['split'] == 'frozen']
    truth = AGENTS[name]
    assert identifiability(rows, truth)['rank'] == 5
    result = fit(rows, probabilities(rows, truth), starts=2)
    assert result['converged']
    for k, value in asdict(truth).items():
        assert result['parameters'][k] == pytest.approx(value, abs=.01)


def test_label_bias_changes_labels_not_economic_preference():
    rows = build_rows()[:2]
    margins = margin(prepare(rows), Parameters(label_bias=1.5))
    assert margins[0] - margins[1] == pytest.approx(3)
