"""Tests for the Track B trial generators (ICLR_PLAN.md B1).

The three that matter most are the invariants core.py claims to enforce: the
chat template is never bypassed, the test split cannot be materialised, and the
transfer battery cannot be used for selection.
"""

import math

import pytest

from cv_bench.tasks import core, risk, social, transfer


# -- lotteries -------------------------------------------------------------

def test_lottery_rejects_bad_probabilities():
    with pytest.raises(ValueError):
        core.Lottery(((0.5, 10.0), (0.4, 0.0)))
    with pytest.raises(ValueError):
        core.Lottery(((1.5, 10.0), (-0.5, 0.0)))


def test_lottery_ev_and_support():
    lot = core.Lottery(((0.25, 100.0), (0.75, 0.0)))
    assert lot.ev == pytest.approx(25.0)
    assert lot.support == (0.0, 100.0)
    assert not lot.is_sure
    assert core.Lottery(((1.0, 50.0),)).is_sure


def test_statewise_dominance():
    sure50 = core.Lottery(((1.0, 50.0),))
    gamble_worse = core.Lottery(((0.5, 40.0), (0.5, 0.0)))
    gamble_better = core.Lottery(((0.5, 80.0), (0.5, 60.0)))
    assert core.statewise_dominates(sure50, gamble_worse)
    assert core.statewise_dominates(gamble_better, sure50)
    assert not core.statewise_dominates(sure50, gamble_better)
    # Overlapping supports dominate in neither direction.
    assert not core.statewise_dominates(sure50, core.Lottery(((0.5, 100.0), (0.5, 10.0))))


# -- splits ----------------------------------------------------------------

def test_split_assignment_is_mod_four():
    assert [core.assign_split(i) for i in range(5)] == \
        ["disc", "sel", "cal", "test", "disc"]


def test_frame_role_core_is_sure_gain_at_three_probabilities():
    assert core.frame_role("sure_gain", {"p": 0.5}) == "core"
    assert core.frame_role("sure_gain", {"p": 0.25}) == "core"
    assert core.frame_role("sure_gain", {"p": 0.9}) == "heldout"
    assert core.frame_role("sure_loss", {"p": 0.5}) == "heldout"
    assert core.frame_role("paired", {"m": 50.0}) == "heldout"


def test_split_is_a_pure_function_of_content():
    """The same cell lands in the same split across independent generator runs."""
    a = {t.content_id: t.split for t in risk.generate_risk(splits=("disc", "sel", "cal"))}
    b = {t.content_id: t.split for t in risk.generate_risk(splits=("disc", "sel", "cal"))}
    assert a == b and len(a) > 100


# -- the grid --------------------------------------------------------------

def test_legacy_cell_is_always_present_and_exact():
    grid = risk.x_grid(0.5, 50.0)
    assert grid == tuple(float(n) for n in range(10, 245, 5))
    assert len(grid) == 47


def test_x_grid_is_log_spaced_around_the_risk_neutral_point():
    grid = risk.x_grid(0.25, 100.0)          # centre = 400
    assert len(grid) == risk.N_LEVELS
    assert grid[0] == pytest.approx(400 * risk.X_LO, abs=1.0)
    assert grid[-1] == pytest.approx(400 * risk.X_HI, abs=1.0)
    ratios = [grid[i + 1] / grid[i] for i in range(len(grid) - 1)]
    assert max(ratios) - min(ratios) < 0.05   # constant ratio, up to rounding


def test_every_risk_family_is_generated():
    families = {t.family for t in risk.generate_risk()}
    assert {"sure_gain", "sure_loss", "mixed", "paired",
            "catch_sure_gain", "catch_sure_loss", "catch_paired"} <= families


def test_catch_trials_really_have_a_dominant_option():
    for t in risk.generate_catch():
        assert t.is_catch
        assert t.dominant is not None, f"{t.family} {t.param_dict} has no dominant option"
        other = 1 - t.dominant
        assert core.statewise_dominates(t.canonical[t.dominant], t.canonical[other])


def test_dominated_preference_cells_are_only_at_the_low_end_and_are_flagged():
    """The plan's grid starts at 0.3 x s/p, so its bottom levels are dominated.

    They are kept deliberately (BD5). What must hold is that dominance never
    appears anywhere else, and that every dominated cell is flagged so the
    estimator and the dominated-choice rate can see it.
    """
    dominated = [t for t in risk.generate_risk(include_catch=False)
                 if t.dominant is not None]
    assert dominated, "expected the low end of the grid to contain dominated cells"
    for t in dominated:
        params = t.param_dict
        assert t.family in ("sure_gain", "sure_loss"), \
            f"unexpected dominance in {t.family}"
        # Dominated exactly when the gamble cannot beat the sure amount.
        assert params["x"] <= params["s"], \
            f"dominance away from the low end: x={params['x']} s={params['s']}"
        # In a gain frame the sure amount dominates; in a loss frame the gamble
        # does, since it risks losing at most x <= s.
        assert t.dominant == (0 if t.family == "sure_gain" else 1)


def test_paired_and_mixed_families_are_never_dominated():
    """These have no sure option to dominate, so any dominance would be a bug."""
    bad = [t for t in risk.generate_risk(include_catch=False)
           if t.family in ("paired", "mixed") and t.dominant is not None]
    assert not bad, f"{len(bad)} paired/mixed trials are dominated, e.g. {bad[:1]}"


# -- formats ---------------------------------------------------------------

def test_option_order_swaps_presentation_but_not_meaning():
    trial = next(t for t in risk.generate_risk() if t.family == "sure_gain")
    canonical = trial.fmt
    swapped = core.Format(1, canonical.label_set, canonical.response_format,
                          canonical.template_id)
    a = trial
    b = core.Trial(**{**trial.__dict__, "fmt": swapped})
    assert a.presented == tuple(reversed(b.presented))
    # The risky label follows the risky lottery through the swap.
    assert a.risky_label != a.safe_label
    assert b.risky_label != b.safe_label
    assert a.labels == b.labels


def test_content_id_is_format_free_and_trial_id_is_not():
    trial = next(iter(risk.generate_risk()))
    variants = list(core.expand_formats([trial]))
    assert len({t.content_id for t in variants}) == 1
    assert len({t.trial_id for t in variants}) == len(variants)


def test_expand_formats_covers_order_labels_and_response_format():
    trial = next(iter(risk.generate_risk()))
    variants = list(core.expand_formats([trial], label_sets=("legacy", "neutral")))
    assert {v.fmt.option_order for v in variants} == {0, 1}
    assert {v.fmt.label_set for v in variants} == {"legacy", "neutral"}
    assert {v.fmt.response_format for v in variants} == {"mc", "freetext"}
    assert len({v.fmt.template_id for v in variants}) == 2   # two templates per split


# -- the chat template -----------------------------------------------------

def test_raw_rendering_refuses_without_an_explicit_acknowledgement():
    trial = next(iter(risk.generate_risk()))
    with pytest.raises(RuntimeError, match="88.3%"):
        core.render_raw_unsafe(trial)
    assert core.render_raw_unsafe(trial, acknowledge_no_chat_template=True)


def test_trial_spec_requests_the_chat_template_and_orders_labels_safe_then_risky():
    trial = next(t for t in risk.generate_risk() if t.family == "sure_gain")
    spec = core.to_trial_spec(trial)
    assert spec.use_chat_template is True
    assert spec.labels == (trial.safe_label, trial.risky_label)
    assert spec.negative == trial.safe_label and spec.positive == trial.risky_label


def test_prompt_mentions_both_options_and_their_amounts():
    trial = next(t for t in risk.generate_risk() if t.family == "sure_gain")
    text = core.prompt_text(trial)
    for label in trial.labels:
        assert label in text
    params = trial.param_dict
    assert f"{params['s']:,.0f}" in text
    assert f"{params['p']:.0%}" in text


def test_describe_wording():
    assert core.describe(core.Lottery(((1.0, 50.0),))) == "$50 for sure"
    assert core.describe(core.Lottery(((1.0, -50.0),))) == "lose $50 for sure"
    # "p chance of x, otherwise 0" is the plan's own wording for these.
    assert core.describe(core.Lottery(((0.1, 60.0), (0.9, 0.0)))) == \
        "a 10% chance of $60 and otherwise nothing"
    # Two live payoffs keep both clauses, larger magnitude first.
    mixed = core.describe(core.Lottery(((0.5, 100.0), (0.5, -50.0))))
    assert mixed == "a 50% chance of $100 and a 50% chance of losing $50"
    assert core.describe(core.Lottery(((1.0, 0.0),))) == "nothing"


# -- the test lock ---------------------------------------------------------

def test_test_split_is_locked(tmp_path):
    with pytest.raises(core.TestSplitLocked):
        core.check_test_access("test", None, "unit-test", log_path=tmp_path / "a.log")
    with pytest.raises(core.TestSplitLocked):
        core.check_test_access("test", "not-a-sha", "unit-test", log_path=tmp_path / "a.log")
    # Non-test splits pass without a token.
    core.check_test_access("disc", None, "unit-test", log_path=tmp_path / "a.log")


def test_test_access_attempts_are_logged(tmp_path):
    log = tmp_path / "TEST_ACCESS.log"
    with pytest.raises(core.TestSplitLocked):
        core.check_test_access("test", "whatever", "unit-test", log_path=log)
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 1 and '"granted": false' in lines[0]


def test_generators_refuse_the_test_split():
    for gen in (risk.generate_risk, risk.generate_catch, social.generate_social):
        with pytest.raises(core.TestSplitLocked):
            list(gen(splits=("test",)))


def test_no_generator_emits_a_test_trial_by_default():
    produced = (list(risk.generate_risk()) + list(social.generate_social())
                + list(transfer.generate_transfer("unmodified")))
    assert produced
    assert not [t for t in produced if t.split == "test"]


def test_test_templates_are_absent_until_an_author_writes_them():
    assert core.TEMPLATES["test"] == {}
    for split in ("disc", "sel", "cal"):
        assert len(core.TEMPLATES[split]) == 2


# -- social ----------------------------------------------------------------

def test_responder_offers_at_or_above_half_are_catch_trials():
    trials = [t for t in social.generate_responder() if t.family == "responder"]
    assert trials
    for t in trials:
        assert t.is_catch == (t.param_dict["offer_frac"] >= 0.5)


def test_mini_ultimatum_holds_the_offer_fixed_and_varies_the_alternative():
    trials = list(social.generate_mini_ultimatum())
    assert trials
    assert {t.param_dict["responder_gets"] for t in trials} == {2.0}
    assert any(t.param_dict["has_alternative"] == 0.0 for t in trials)


def test_accept_bias_control_items_have_a_correct_answer():
    trials = list(social.generate_accept_bias_control())
    assert trials
    for t in trials:
        assert t.is_catch and t.dominant is not None


def test_social_uses_accept_reject_labels():
    trial = next(iter(social.generate_responder()))
    assert trial.fmt.label_set in ("accept_reject", "neutral")
    assert core.LABEL_SETS["accept_reject"] == ("Reject", "Accept")


# -- transfer --------------------------------------------------------------

def test_transfer_refuses_selection_and_calibration_splits():
    for split in ("sel", "cal"):
        with pytest.raises(transfer.TransferMisuse, match="never be used for selection"):
            list(transfer.generate_transfer("unmodified", splits=(split,)))


def test_transfer_battery_has_all_three_instruments():
    families = {t.family for t in transfer.generate_transfer("unmodified")}
    assert families == {"holt_laury", "gneezy_potters", "eckel_grossman"}


def test_holt_laury_switching_point_is_where_it_should_be():
    """Risk neutrality switches at decision 5 of 10 in the standard instrument."""
    trials = sorted(transfer.generate_holt_laury("unmodified", splits=("disc",)),
                    key=lambda t: t.param_dict["decision"])
    for t in transfer.generate_holt_laury("unmodified", splits=("disc",)):
        safe, risky = t.canonical
        p = t.param_dict["p"]
        if p < 0.5:
            assert safe.ev > risky.ev
        elif p > 0.5:
            assert risky.ev > safe.ev
    assert trials


def test_gneezy_potters_risky_option_has_the_higher_mean():
    for t in transfer.generate_gneezy_potters("unmodified", splits=("disc",)):
        keep, risky = t.canonical
        assert risky.ev > keep.ev
        assert risky.worst < keep.worst        # and strictly more spread


# -- design conditions must not be confounded with splits ------------------

def test_holt_laury_ladder_is_complete_in_every_split():
    """A ladder split across splits has no switching point in any of them."""
    for split in ("disc",):
        rungs = [t.param_dict["decision"]
                 for t in transfer.generate_holt_laury("unmodified", splits=(split,))]
        assert sorted(rungs) == [float(i) for i in range(1, 11)], \
            f"split {split} has {len(rungs)} of 10 Holt-Laury decisions"


def test_every_transfer_instrument_is_whole():
    counts = {}
    for t in transfer.generate_transfer("unmodified", splits=("disc",)):
        counts[t.family] = counts.get(t.family, 0) + 1
    assert counts == {"holt_laury": 10, "gneezy_potters": 10, "eckel_grossman": 5}


def test_mini_ultimatum_conditions_appear_in_every_split():
    by_split = {}
    for t in social.generate_mini_ultimatum(splits=("disc", "sel", "cal")):
        by_split.setdefault(t.split, set()).add(t.param_dict["has_alternative"])
    assert set(by_split) == {"disc", "sel", "cal"}
    for split, conditions in by_split.items():
        assert conditions == {0.0, 1.0}, f"split {split} is missing a condition"


def test_no_condition_is_lost_to_the_locked_test_split():
    """Any family whose levels are conditions must be complete outside `test`.

    This is the bug that motivated BD5: with four conditions and a mod-4 split
    rule, one condition lands in `test` and silently vanishes from the dataset.
    """
    produced = list(social.generate_mini_ultimatum()) + list(transfer.generate_transfer("unmodified"))
    assert {t.param_dict["has_alternative"] for t in produced
            if t.family == "mini_ultimatum"} == {0.0, 1.0}
    assert len({t.param_dict["decision"] for t in produced
                if t.family == "holt_laury"}) == 10


def test_social_dominance_is_recorded_only_on_catch_trials():
    """Rejecting a low offer is inequity aversion, not a dominance violation."""
    for t in social.generate_social():
        if not t.is_catch:
            assert t.dominant is None, \
                f"{t.family} {t.param_dict} would score a preference as dominated"
    catches = [t for t in social.generate_social() if t.is_catch]
    assert catches and all(t.dominant is not None for t in catches)


# -- the transfer lock (evaluation-only until B9's predictions are committed) --

def test_transfer_battery_is_evaluation_only():
    for role in ("unmodified", "anchor"):
        assert list(transfer.generate_transfer(role))
    for role in ("probe", "sae", "persona", "prompt_family", "lora"):
        with pytest.raises(core.TransferLocked, match="evaluation-only"):
            list(transfer.generate_transfer(role))


def test_transfer_role_has_no_default():
    """A caller must say who is looking; there is no way to omit it."""
    import inspect
    for fn in (transfer.generate_transfer, transfer.generate_holt_laury,
               transfer.generate_gneezy_potters, transfer.generate_eckel_grossman):
        assert inspect.signature(fn).parameters["role"].default is inspect.Parameter.empty


def test_transfer_access_is_logged(tmp_path):
    log = tmp_path / "B_TRANSFER_ACCESS.log"
    core.check_transfer_access("unmodified", "unit-test", log_path=log)
    with pytest.raises(core.TransferLocked):
        core.check_transfer_access("probe", "unit-test", log_path=log)
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 2
    assert '"granted": true' in lines[0] and '"granted": false' in lines[1]


def test_uncommitted_predictions_do_not_unlock_the_battery(tmp_path):
    """A file in the working tree is not committed, so it must not unlock."""
    preds = tmp_path / "b9_transfer_predictions.json"
    preds.write_text("{}")
    with pytest.raises(core.TransferLocked):
        core.check_transfer_access("probe", "unit-test", predictions_path=preds,
                                   log_path=tmp_path / "log")


# -- label sets must suit the trial ----------------------------------------

def test_label_sets_suit_the_domain():
    """A lottery must never be labelled Reject/Accept, nor an offer Safe/Risky."""
    for t in core.expand_formats(list(risk.generate_risk())):
        assert t.fmt.label_set in ("legacy", "neutral"), t.family
    for t in core.expand_formats(list(social.generate_social())):
        assert t.fmt.label_set in ("accept_reject", "neutral", "yes_no"), t.family
        assert t.fmt.label_set != "legacy"
    for t in core.expand_formats(list(transfer.generate_transfer("unmodified"))):
        assert t.fmt.label_set in ("legacy", "neutral")


def test_accept_bias_control_uses_yes_no():
    sets = {t.fmt.label_set for t in core.expand_formats(list(social.generate_social()))
            if t.family == "accept_bias_control"}
    assert sets == {"accept_reject", "yes_no"}


def test_no_prompt_mislabels_its_options():
    """Regression: the expansion once produced 'Reject: $20 for sure'."""
    for t in core.expand_formats(list(risk.generate_risk())):
        text = core.prompt_text(t)
        assert "Reject:" not in text and "Accept:" not in text


def test_every_label_pair_differs_at_its_scored_token():
    """A pair sharing a first token makes z identically zero, silently.

    "Option A" and "Option B" both begin with "Option", so under a bare stem the
    readout computes log p(Option) - log p(Option) = 0 on every trial. That is
    what made half the B3.1 dry run's prompts contribute exactly zero gradient.
    The stem has to move the scored position onto the part that differs.
    """
    for label_set, (neg, pos) in core.LABEL_SETS.items():
        stem = core.STEM_BY_LABEL_SET[label_set]
        if neg.split()[0] == pos.split()[0]:
            # the labels share a leading word, so the stem must consume it
            assert stem.rstrip().endswith(neg.split()[0]), \
                f"{label_set}: labels share {neg.split()[0]!r} but stem is {stem!r}"
        else:
            assert not stem.rstrip().endswith(neg.split()[0])


def test_stem_for_picks_by_label_set():
    t = next(x for x in core.expand_formats(list(risk.generate_risk()))
             if x.fmt.label_set == "legacy")
    assert core.stem_for(t) == "Answer:"
    t2 = next(x for x in core.expand_formats(list(risk.generate_risk()))
              if x.fmt.label_set == "neutral")
    assert core.stem_for(t2) == "Answer: Option"
