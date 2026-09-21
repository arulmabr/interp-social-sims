"""Tests for the B2 estimator (ICLR_PLAN.md B2)."""

from dataclasses import replace

import numpy as np
import pytest

from cv_bench.estimator import agents as A, decision as DEC, fingerprint as FP, fit as F
from cv_bench.tasks import core, risk


@pytest.fixture(scope="module")
def trials():
    return list(core.expand_formats(list(risk.generate_risk())))


# -- prospect theory --------------------------------------------------------

def test_weighting_function_endpoints_and_monotonicity():
    assert A.weight(np.array([0.0]), 0.61)[0] == pytest.approx(0.0, abs=1e-6)
    assert A.weight(np.array([1.0]), 0.61)[0] == pytest.approx(1.0, abs=1e-6)
    ps = np.linspace(0.01, 0.99, 50)
    w = A.weight(ps, 0.61)
    assert np.all(np.diff(w) > 0)
    # gamma = 1 is the identity
    assert np.allclose(A.weight(ps, 1.0), ps, atol=1e-9)


def test_value_function_signs_and_loss_aversion():
    v = A.value(np.array([100.0, -100.0]), 0.88, 2.25)
    assert v[0] > 0 > v[1]
    assert abs(v[1]) == pytest.approx(2.25 * v[0], rel=1e-9)


# -- the vectorised path ----------------------------------------------------

def test_packed_matches_scalar_for_every_agent(trials):
    sub = trials[::37]
    pk = A.pack(sub)
    for name, par in A.agent_zoo().items():
        a = A.latent_z_batch(sub, par)
        b = A.latent_z_packed(pk, par)
        assert np.max(np.abs(a - b)) < 1e-9, name


# -- identification facts (BD10 and the kappa bug) --------------------------

def test_lambda_cancels_on_single_sign_trials():
    """BD10: under contextual utility, lambda has no effect where signs agree."""
    base = A.AgentParams()
    hi = replace(base, lam=A.LAMBDA0 + A.MDC["lambda"])
    for family in ("sure_gain", "sure_loss"):
        ts = [t for t in risk.generate_risk(include_catch=False) if t.family == family]
        d = np.abs(A.latent_z_batch(ts, hi) - A.latent_z_batch(ts, base))
        assert np.max(d) < 1e-12, f"lambda moved z on {family}"
    mixed = [t for t in risk.generate_risk(include_catch=False) if t.family == "mixed"]
    assert np.max(np.abs(A.latent_z_batch(mixed, hi)
                         - A.latent_z_batch(mixed, base))) > 1e-3


def test_belief_distortion_actually_changes_behaviour():
    """Regression: kappa applied to every amount cancels and does nothing."""
    ts = [t for t in risk.generate_risk(include_catch=False)
          if t.family in ("sure_gain", "sure_loss")]
    base = A.AgentParams()
    belief = replace(base, kappa=1.35)
    assert A.behavioural_effect(ts, belief, base) > 0.01


def test_kappa_spares_the_sure_amount(trials):
    """The distortion is on the gamble's x, which is what B1 calls x."""
    t = next(x for x in trials if x.family == "sure_gain")
    par = A.AgentParams(kappa=2.0)
    pk = A.pack([t])
    _, s_hi, _ = A._utility_vec(pk.safe_hi, pk.safe_lo, pk.safe_phi, pk.safe_sure, par)
    _, r_hi, _ = A._utility_vec(pk.risky_hi, pk.risky_lo, pk.risky_phi, pk.risky_sure, par)
    assert s_hi[0] == pytest.approx(t.param_dict["s"])
    assert r_hi[0] == pytest.approx(2.0 * t.param_dict["x"])


# -- noise ------------------------------------------------------------------

def test_template_effects_are_shared_between_conditions(trials):
    """Redrawn template effects would appear as a constant shift, i.e. an action bias."""
    sub = trials[::53]
    rng = np.random.default_rng(11)
    base = A.AgentParams()
    offsets = A.draw_template_offsets(sub, 1.0, rng)
    a = A.simulate(sub, base, rng, 1.0, 0.0, template_offsets=offsets)
    b = A.simulate(sub, base, rng, 1.0, 0.0, template_offsets=offsets)
    assert np.allclose(a["z"], b["z"]), "shared offsets must cancel exactly"


def test_template_noise_is_shared_within_a_template(trials):
    sub = trials[::53]
    rng = np.random.default_rng(0)
    base = A.AgentParams()
    z0 = A.latent_z_packed(A.pack(sub), base)
    sim = A.simulate(sub, base, rng, template_noise_sd=1.0, numerical_noise_sd=0.0)
    offsets = sim["z"] - z0
    for tid in {t.fmt.template_id for t in sub}:
        vals = [o for o, t in zip(offsets, sub) if t.fmt.template_id == tid]
        assert np.std(vals) < 1e-9, "template noise must be one draw per template"


def test_numerical_noise_is_independent_per_trial(trials):
    sub = trials[::53]
    rng = np.random.default_rng(0)
    base = A.AgentParams()
    z0 = A.latent_z_packed(A.pack(sub), base)
    sim = A.simulate(sub, base, rng, template_noise_sd=0.0, numerical_noise_sd=0.25)
    offsets = sim["z"] - z0
    assert np.std(offsets) == pytest.approx(0.25, rel=0.25)
    tid = sorted({t.fmt.template_id for t in sub})[0]
    vals = [o for o, t in zip(offsets, sub) if t.fmt.template_id == tid]
    assert np.std(vals) > 0.05, "numerical noise must vary within a template"


# -- fitting ----------------------------------------------------------------

def test_fit_recovers_parameters_from_clean_data(trials):
    """No noise and probabilities as data: the optimiser must land on the truth."""
    truth = replace(A.AgentParams(), alpha=0.95, gamma=0.70)
    pk = A.pack(trials)
    z = A.latent_z_packed(pk, truth)
    rng = np.random.default_rng(3)
    choices = (rng.random(len(trials)) < A.choice_prob(z)).astype(int)
    fitted, lapse, _ = F.fit(trials, choices, ("alpha", "gamma"), A.AgentParams(), seed=0)
    assert abs(fitted.alpha - 0.95) < 0.05
    assert abs(fitted.gamma - 0.70) < 0.05


def test_shares_favour_the_true_model(trials):
    rng = np.random.default_rng(5)
    base = A.AgentParams()
    zoo = A.agent_zoo()
    offsets = A.draw_template_offsets(trials, 0.5, rng)
    sim_b = A.simulate(trials, base, rng, 0.5, 0.1, template_offsets=offsets)
    fb, _, _ = F.fit(trials, sim_b["choice"], ("alpha", "gamma", "tau"), base, seed=0)
    for agent, expected in (("pref_alpha", "preference"), ("action", "action")):
        sim_i = A.simulate(trials, zoo[agent], rng, 0.5, 0.1, template_offsets=offsets)
        fits = F.fit_all_models(trials, sim_i["choice"], fb, seed=0)
        shares = F.model_shares(fits)
        assert max(shares, key=shares.get) == expected, (agent, shares)


def test_dominated_policies_both_run(trials):
    sub = trials[::11]
    rng = np.random.default_rng(7)
    base = A.AgentParams()
    sim = A.simulate(sub, base, rng, 0.5, 0.1)
    for policy in ("exclude", "lapse"):
        par, lapse, ll = F.fit(sub, sim["choice"], ("alpha",), base,
                               dominated_policy=policy, seed=0)
        assert np.isfinite(ll)
    with pytest.raises(ValueError):
        F.fit(sub, sim["choice"], ("alpha",), base, dominated_policy="nonsense")


def test_heldout_mask_splits_alternate_reward_levels(trials):
    sub = [t for t in trials if t.family == "sure_gain"]
    held = F.heldout_mask(sub)
    assert 0.3 < held.mean() < 0.7


# -- the fingerprint and the decision rule ----------------------------------

def test_d1_counts_the_dominated_choice(trials):
    catch = [t for t in trials if t.is_catch and t.dominant is not None][:40]
    always_risky = np.ones(len(catch), dtype=int)
    rate = FP.d1_dominance_violations(catch, always_risky)
    expected = np.mean([t.dominant == 0 for t in catch])
    assert rate == pytest.approx(expected)


def test_decision_rule_refuses_to_run_without_format_variation():
    """A silent NaN here would read as 'nothing is preference-like'."""
    one_format = [t for t in core.expand_formats(list(risk.generate_risk()))
                  if t.fmt.label_set == "legacy" and t.fmt.option_order == 0]
    p = np.zeros(len(one_format))
    d5 = FP.d5_format_transfer(one_format, p, p)
    assert d5.get("no_format_variation") == 1.0
    with pytest.raises(ValueError, match="format variation"):
        DEC.decide({}, {"D5_format": d5, "D1_dominance": 0.0, "D4_ce": {},
                        "D6_recall": {}}, 0.0, {})


def test_gate_b2_needs_every_condition():
    good_rmse = {"alpha": 0.01, "gamma": 0.01, "lambda": 0.01}
    good_cls = {"pref_alpha": [True] * 20, "pref_gamma": [True] * 20,
                "pref_lambda": [True] * 20, "action": [False] * 20,
                "belief": [False] * 20, "noise": [False] * 20, "format": [False] * 20}
    good_miss = {"mean_variance": True, "monotone": True}
    assert DEC.gate_b2(good_rmse, good_cls, good_miss)["PASS"]
    # any single failure sinks it
    bad = dict(good_rmse, **{"lambda": 10.0})
    assert not DEC.gate_b2(bad, good_cls, good_miss)["PASS"]
    cls = dict(good_cls, **{"action": [True] * 20})
    assert not DEC.gate_b2(good_rmse, cls, good_miss)["PASS"]
    assert not DEC.gate_b2(good_rmse, good_cls, {"mean_variance": False,
                                                 "monotone": True})["PASS"]


def test_gate_thresholds_are_plan_v4():
    assert DEC.PREFERENCE_SHARE_MIN == 0.80
    assert DEC.GATE_CLASSIFICATION_MIN == 0.95
    assert DEC.GATE_RMSE_FRACTION == 0.5
    assert A.MDC == {"alpha": 0.10, "gamma": 0.10, "lambda": 0.30}
