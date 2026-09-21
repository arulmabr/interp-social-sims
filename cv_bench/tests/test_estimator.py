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
    d5 = FP.d5_format_transfer(one_format, np.zeros(len(one_format)))
    assert d5.get("no_format_variation") == 1.0
    with pytest.raises(ValueError, match="format variation"):
        DEC.decide({}, {"D5_format": d5, "D1_dominance": 0.0, "D4_ce": {},
                        "D6_recall": {}}, 0.0, {})


def _good_gate_inputs():
    """Keys are base/intervention (author item 3)."""
    rmse = {"alpha": 0.01, "gamma": 0.01, "lambda": 0.01}
    cls = {
        "cpt/preference_alpha": [True] * 20,
        "cpt/preference_gamma": [True] * 20,
        "cpt/preference_lambda": [True] * 20,
        "cpt/action": [False] * 20, "cpt/belief": [False] * 20,
        "cpt/noise": [False] * 20, "cpt/format": [False] * 20,
    }
    mf = {f"{b}/{iv}": 1.0 for b in A.MISSPECIFIED_BASES for iv in A.INTERVENTIONS}
    return rmse, cls, mf


def test_gate_b2_needs_every_condition():
    rmse, cls, mf = _good_gate_inputs()
    assert DEC.gate_b2(rmse, cls, mf)["PASS"]

    # a preference cell below the bar sinks it
    bad = dict(cls, **{"cpt/preference_alpha": [True] * 18 + [False] * 2})
    assert not DEC.gate_b2(rmse, bad, mf)["PASS"]

    # a non-preference intervention called preference-like sinks it
    bad = dict(cls, **{"cpt/action": [True] * 20})
    assert not DEC.gate_b2(rmse, bad, mf)["PASS"]

    # the model-free layer failing on a misspecified base sinks it
    bad_mf = dict(mf, **{"mean_variance/format": 0.5})
    assert not DEC.gate_b2(rmse, cls, bad_mf)["PASS"]

    # alpha RMSE over its bar sinks it
    assert not DEC.gate_b2(dict(rmse, alpha=0.9), cls, mf)["PASS"]


def test_gate_b2_no_longer_depends_on_lambda():
    """Author item 2: lambda moved to its own gate; its bar is unchanged."""
    rmse, cls, mf = _good_gate_inputs()
    assert DEC.GATE_B2_PARAMS == ("alpha", "gamma")
    assert DEC.gate_b2(dict(rmse, **{"lambda": 99.0}), cls, mf)["PASS"]
    # but lambda's own gate still fails, at the same 0.15 bar
    lam = DEC.gate_lambda(dict(rmse, **{"lambda": 99.0}))
    assert not lam["PASS"]
    assert lam["limit"] == pytest.approx(0.5 * A.MDC["lambda"])
    assert DEC.gate_lambda({"lambda": 0.01})["PASS"]


def test_parametric_contradiction_is_reported_not_gated():
    """On a misspecified base the parametric layer may be wrong (item 3)."""
    rmse, cls, mf = _good_gate_inputs()
    contra = {f"{b}/{iv}": 1.0 for b in A.MISSPECIFIED_BASES for iv in A.INTERVENTIONS}
    g = DEC.gate_b2(rmse, cls, mf, contra)
    assert g["PASS"], "a contradiction rate must not by itself fail the gate"
    assert g["parametric_contradiction_rate"] == contra


def test_gate_thresholds_are_plan_v4():
    assert DEC.PREFERENCE_SHARE_MIN == 0.80
    assert DEC.GATE_CLASSIFICATION_MIN == 0.95
    assert DEC.GATE_RMSE_FRACTION == 0.5
    assert A.MDC == {"alpha": 0.10, "gamma": 0.10, "lambda": 0.30}


def test_d5_uses_dz_not_probability_differences(trials):
    """A ratio of two squashed probability differences swings on noise alone."""
    dz = np.full(len(trials), 0.3)
    d5 = FP.d5_format_transfer(trials, dz)
    assert d5["ratio_label"] == pytest.approx(1.0, abs=1e-9)
    assert d5["ratio_order"] == pytest.approx(1.0, abs=1e-9)
    assert d5["in_band"] == 1.0


def test_d5_calls_a_zero_effect_perfect_transfer():
    """No effect in either format is not a transfer failure."""
    ts = list(core.expand_formats(list(risk.generate_risk())))
    d5 = FP.d5_format_transfer(ts, np.zeros(len(ts)))
    assert d5["in_band"] == 1.0


def test_d5_catches_a_label_dependent_effect(trials):
    """An effect present only under legacy labels must leave the band."""
    dz = np.array([0.3 if t.fmt.label_set == "legacy" else 0.0 for t in trials])
    d5 = FP.d5_format_transfer(trials, dz)
    assert d5["in_band"] == 0.0


def test_logit_mode_beats_choice_mode_at_recovering_alpha(trials):
    """The readout returns z; fitting binary choices throws most of it away."""
    truth = replace(A.AgentParams(), alpha=A.ALPHA0 + A.MDC["alpha"])
    rng = np.random.default_rng(17)
    sim = A.simulate(trials, truth, rng, 0.0, 0.1)
    fit_logit, _, _ = F.fit(trials, sim["z"], ("alpha",), A.AgentParams(),
                            observe="logit", sigma=0.1, seed=0)
    fit_choice, _, _ = F.fit(trials, sim["choice"], ("alpha",), A.AgentParams(),
                             observe="choice", seed=0)
    err_logit = abs(fit_logit.alpha - truth.alpha)
    err_choice = abs(fit_choice.alpha - truth.alpha)
    assert err_logit < err_choice
    assert err_logit < 0.5 * A.MDC["alpha"]


def test_template_intercepts_improve_parameter_recovery(trials):
    """Unmodelled template offsets are misfit that decides model comparison.

    The intercepts are not separately identified -- B1 gives each split its own
    two templates, so a template effect is confounded with that split's reward
    levels, and only differences matter anyway. What must hold is the reason
    they were added: with them, the preference parameters come back closer to
    the truth.
    """
    rng = np.random.default_rng(23)
    truth = replace(A.AgentParams(), alpha=A.ALPHA0 + A.MDC["alpha"])
    offsets = A.draw_template_offsets(trials, 0.8, rng)
    sim = A.simulate(trials, truth, rng, 0.8, 0.05, template_offsets=offsets)

    without, _, _ = F.fit(trials, sim["z"], ("alpha", "gamma"), A.AgentParams(),
                          free_templates=False, observe="logit", sigma=0.05, seed=0)
    with_tpl, _, _ = F.fit(trials, sim["z"], ("alpha", "gamma"), A.AgentParams(),
                           free_templates=True, observe="logit", sigma=0.05, seed=0)
    err_without = abs(without.alpha - truth.alpha)
    err_with = abs(with_tpl.alpha - truth.alpha)
    assert err_with < err_without, (err_with, err_without)
    assert err_with < 0.5 * A.MDC["alpha"]


# -- bases crossed with interventions (author item 3) ----------------------

def test_crossed_zoo_covers_every_base_and_intervention(trials):
    sub = trials[::9]
    crossed, bases, effects = A.build_crossed_zoo(sub)
    assert set(bases) == set(A.BASES)
    for b in A.BASES:
        ivs = {iv for (bb, iv) in crossed if bb == b}
        if b == "cpt":
            assert set(A.CPT_PREFERENCE_CELLS) <= ivs
            assert "preference" not in ivs
        else:
            assert "preference" in ivs
        assert {"action", "belief", "noise", "format"} <= ivs


def test_each_base_keeps_its_own_family(trials):
    sub = trials[::9]
    crossed, bases, _ = A.build_crossed_zoo(sub)
    for (b, iv), par in crossed.items():
        assert par.kind == bases[b].kind, (b, iv)


def test_modelfree_classifier_names_belief_and_format_first():
    """Those two announce themselves on dedicated diagnostics."""
    fp = {"D6_recall": {"intact": 0.0}, "D5_format": {"in_band": 1.0},
          "D2_variance": {"action_share": 1.0, "payoff_share": 0.0, "scale_share": 0.0}}
    assert FP.modelfree_classify(fp) == "belief"
    fp = {"D6_recall": {"intact": 1.0}, "D5_format": {"in_band": 0.0},
          "D2_variance": {"action_share": 1.0, "payoff_share": 0.0, "scale_share": 0.0}}
    assert FP.modelfree_classify(fp) == "format"


def test_modelfree_classifier_sorts_the_rest_by_where_the_variance_went():
    base = {"D6_recall": {"intact": 1.0}, "D5_format": {"in_band": 1.0}}
    for top, expected in (("action_share", "action"), ("payoff_share", "preference"),
                          ("scale_share", "noise")):
        shares = {"action_share": 0.1, "payoff_share": 0.1, "scale_share": 0.1}
        shares[top] = 0.8
        assert FP.modelfree_classify({**base, "D2_variance": shares}) == expected


def test_d2_scale_term_separates_a_temperature_change(trials):
    """Raising tau rescales z toward zero, so dz loads on z itself."""
    sub = trials[::7]
    base = A.AgentParams()
    z0 = A.latent_z_packed(A.pack(sub), base)
    hotter = replace(base, tau=A.TAU0 * 2.0)
    dz = A.latent_z_packed(A.pack(sub), hotter) - z0
    v = FP.d2_variance_decomposition(sub, dz, z_base=z0)
    assert v["scale_share"] > v["payoff_share"]
    assert v["scale_share"] > v["action_share"]


def test_no_base_agent_is_degenerate(trials):
    """A base that is indifferent everywhere tests nothing.

    Regression: the contextual-utility range was measured in dollars for every
    family, but the monotone family's utility is a bounded tanh, so its z had
    an SD of 0.0073 and a P(risky) spread of 0.01 -- it could not express a
    preference, let alone have one detected.
    """
    # Stride, not head: the first rows of the expanded grid are one content in
    # many formats, which has almost no spread in z by construction.
    sub = [t for t in trials if t.family == "sure_gain"][::17]
    assert len({t.content_id for t in sub}) > 50
    pk = A.pack(sub)
    for base in A.BASES:
        z = A.latent_z_packed(pk, A.base_params(base))
        p = A.choice_prob(z)
        assert z.std() > 0.5, f"{base} is nearly flat in z (sd {z.std():.4f})"
        assert p.max() - p.min() > 0.5, f"{base} barely moves P(risky)"


def test_utility_range_is_measured_in_each_family_own_units(trials):
    t = next(x for x in trials if x.family == "sure_gain")
    mono = A.base_params("monotone")
    rng = A.utility_range(t, mono)
    # a tanh-valued utility has a range inside [0, 2], never in dollars
    assert 0.0 < rng <= 2.0


def test_every_crossed_cell_matches_the_target_effect(trials):
    """The matching is what makes Gate B2's rejection requirement fair."""
    sub = trials[::5]
    crossed, bases, effects = A.build_crossed_zoo(sub)
    target = effects["_target"]
    for (b, iv) in crossed:
        if iv == "preference_lambda":
            continue          # lambda is not identified on this grid (BD10)
        got = effects[f"{b}/{iv}"]
        assert got > 0.4 * target, f"{b}/{iv} effect {got:.4f} vs target {target:.4f}"
