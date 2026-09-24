"""The Fehr-Schmidt responder (BD54).

The trap this file exists to catch: `social.py` renders the responder as two
degenerate lotteries, so every risk-side code path runs on these trials without
raising. A social agent that is wired into `latent_z` but not into
`latent_z_packed` would therefore be silently ignored by everything that packs,
which is the estimator and the LoRA target builder.
"""
import numpy as np
import pytest

from cv_bench.estimator import agents as A
from cv_bench.tasks import core, social


def responder_trials(pies=(100.0,)):
    content = [t for t in social.generate_responder(splits=("cal",), pies=pies)]
    return list(core.expand_formats(content, response_formats=("mc",),
                                    label_sets=("neutral",)))


def test_responder_trials_exist():
    assert len(responder_trials()) > 0


def test_packed_and_unpacked_agree():
    trials = responder_trials(pies=(20.0, 100.0, 1000.0))
    par = A.AgentParams(tau=0.1186)
    one = A.latent_z_batch(trials, par)
    many = A.latent_z_packed(A.pack(trials), par)
    assert np.allclose(one, many, atol=1e-9)


def test_risk_path_is_untouched_by_the_social_branch():
    from cv_bench.tasks import risk
    content = list(risk.generate_risk(splits=("cal",), families=("sure_gain",)))
    trials = list(core.expand_formats(content, response_formats=("mc",),
                                      label_sets=("legacy",)))
    par = A.AgentParams(tau=0.1186)
    pk = A.pack(trials)
    assert not pk.is_social.any()
    assert np.allclose(A.latent_z_batch(trials, par),
                       A.latent_z_packed(pk, par), atol=1e-9)


def test_threshold_matches_the_closed_form():
    """z crosses zero at the offer share the formula predicts."""
    par = A.AgentParams(tau=0.1186)
    pie = 100.0
    want = A.social_threshold(par)
    offers = np.linspace(0.0, 50.0, 5001)
    z = A.fehr_schmidt_z(np.full_like(offers, pie), offers, par)
    crossing = offers[np.argmin(np.abs(z))] / pie
    assert crossing == pytest.approx(want, abs=1e-3)


def test_a_prospect_theory_agent_would_accept_everything():
    """Why the new model is needed, stated as a test.

    With the social branch disabled the responder is a sure `offer` against a
    sure 0, so the risk agent takes every positive offer and has no threshold.
    """
    trials = [t for t in responder_trials() if t.param_dict["offer"] > 0]
    par = A.AgentParams(tau=0.1186)
    risk_like = np.array([
        (A.utility(t.canonical[1], par) - A.utility(t.canonical[0], par))
        for t in trials])
    assert (risk_like > 0).all()


def test_scale_invariance_across_pies():
    """The same offer share gives the same z whatever the pie."""
    par = A.AgentParams(tau=0.1186)
    for frac in (0.05, 0.2, 0.35, 0.5):
        z = [float(A.fehr_schmidt_z(np.array(p), np.array(p * frac), par))
             for p in (20.0, 100.0, 1000.0)]
        assert np.allclose(z, z[0], atol=1e-9)


def test_less_inequity_aversion_lowers_the_threshold():
    base = A.AgentParams(tau=0.1186)
    softer = A.AgentParams(tau=0.1186, beta_adv=A.BETA0 - 0.2)
    assert A.social_threshold(softer) < A.social_threshold(base)


def test_the_two_implants_differ_in_kind():
    """A bias is a constant offset; a preference change is not.

    This is the social counterpart of the property the whole anchor contrast
    rests on, so it is asserted rather than assumed.
    """
    par = A.AgentParams(tau=0.1186)
    pref = A.AgentParams(tau=0.1186, beta_adv=A.BETA0 - 0.2)
    bias = A.AgentParams(tau=0.1186, action=0.6)
    pie = np.full(11, 100.0)
    offer = np.linspace(0.0, 50.0, 11)
    z0 = A.fehr_schmidt_z(pie, offer, par)
    d_pref = A.fehr_schmidt_z(pie, offer, pref) - z0
    d_bias = (A.fehr_schmidt_z(pie, offer, bias) + bias.action) - z0
    assert np.allclose(d_bias, 0.6, atol=1e-9)
    assert d_pref.std() > 1e-3
    assert d_pref[-1] == pytest.approx(0.0, abs=1e-9)   # nothing to be behind by at half
