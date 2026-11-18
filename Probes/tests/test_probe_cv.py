"""Prompt-held-out cross-validation for probes.

The data these tests build mirror the probe pipeline's design: one activation
vector per prompt, repeated once per sampled trial, with a label per trial.
"""
import numpy as np
import pytest
from sklearn.model_selection import StratifiedKFold

from Probes.probes import (cv_accuracy, eval_probe_split, fit_and_score, label_ceiling,
                           make_cv, shared_activation_rows, train_probe)


def repeated_prompt_data(n_groups=40, per_group=8, d=64, signal=False, seed=0):
    """One random vector per prompt, copied per trial.

    Each prompt has its own choice tendency, as a reward level does in the real
    data: most of its trials go one way. signal=False draws that tendency at
    random, unrelated to the vector, so nothing about the activation can predict
    an unseen prompt's labels, yet a probe that has seen a prompt's other trials
    can predict its held-out ones. signal=True ties the tendency to the vector.
    """
    rng = np.random.default_rng(seed)
    vectors = rng.normal(size=(n_groups, d))
    X, y, g = [], [], []
    for gid in range(n_groups):
        if signal:
            p_high = 0.85 if vectors[gid, 0] > 0 else 0.15
        else:
            p_high = 0.85 if rng.random() < 0.5 else 0.15
        for _ in range(per_group):
            X.append(vectors[gid])
            y.append(int(rng.random() < p_high))
            g.append(gid)
    return np.asarray(X), np.asarray(y), np.asarray(g)


def test_label_ceiling_is_group_majority_rate():
    y = np.array([1, 1, 0,   0, 0, 0,   1, 0])
    g = np.array([0, 0, 0,   1, 1, 1,   2, 2])
    # group 0: best 2/3, group 1: 3/3, group 2: 1/2 -> 6/8
    assert label_ceiling(y, g) == pytest.approx(6 / 8)


def test_no_prompt_straddles_a_grouped_fold():
    X, y, g = repeated_prompt_data()
    splitter, scheme, used = make_cv(y, g, n_folds=5, random_state=0)
    assert scheme == "prompt_grouped" and used == 5
    n_val = 0
    for tr, va in splitter.split(X, y, g):
        assert not (set(g[tr]) & set(g[va]))
        n_val += len(va)
    assert n_val == len(y)


def test_make_cv_requires_groups():
    X, y, g = repeated_prompt_data()
    with pytest.raises(ValueError, match="groups is required"):
        make_cv(y, None, n_folds=5, random_state=0)


def test_trial_level_split_scores_above_chance_on_pure_noise_and_grouped_split_does_not():
    """Why folds are built over prompts.

    Labels are coin flips, so no probe can know the label of a prompt it has not
    seen. A trial-level split still scores well above 0.5 because it has seen
    the validation prompt's other trials; the grouped split sits at chance.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    X, y, g = repeated_prompt_data(signal=False)
    # A trial-level split, built here only to show what grouping protects against.
    scores = []
    for tr, va in StratifiedKFold(n_splits=5, shuffle=True, random_state=0).split(X, y):
        assert set(g[tr]) & set(g[va])            # prompts sit on both sides
        sc = StandardScaler().fit(X[tr])
        clf = LogisticRegression(C=1.0, max_iter=1000).fit(sc.transform(X[tr]), y[tr])
        scores.append(clf.score(sc.transform(X[va]), y[va]))
    trial_level = float(np.mean(scores))
    held_out, scheme, _ = cv_accuracy(X, y, g, C=1.0, n_folds=5, random_state=0)
    ceiling = label_ceiling(y, g)
    assert scheme == "prompt_grouped"
    assert ceiling > 0.75                      # each prompt has a clear majority
    assert trial_level > 0.7                   # memorised the seen prompts
    assert abs(held_out - 0.5) < 0.1           # nothing to generalize
    assert trial_level - held_out > 0.15


def test_grouped_split_still_detects_real_signal():
    X, y, g = repeated_prompt_data(d=16, signal=True)
    held_out, _, _ = cv_accuracy(X, y, g, C=1.0, n_folds=5, random_state=0)
    assert held_out > 0.65                     # chance is 0.5; the 0.85 tendency caps it


def test_two_prompts_fall_back_to_leave_one_prompt_out():
    # The capability probe's design: one plain prompt, one persona prompt.
    X, y, g = repeated_prompt_data(n_groups=2, per_group=80, d=16, signal=False, seed=1)
    _, scheme, used = make_cv(y, g, n_folds=5, random_state=0)
    assert scheme == "leave_one_prompt_out" and used == 2


def test_one_prompt_is_refused():
    X, y, g = repeated_prompt_data(n_groups=1, per_group=16, d=8)
    with pytest.raises(ValueError, match="at least two distinct prompts"):
        make_cv(y, g, n_folds=5, random_state=0)


def test_train_probe_records_scheme_and_ceiling():
    X, y, g = repeated_prompt_data(signal=False)
    probe = train_probe({48: X, 50: X + 0.0}, y, candidate_layers=[48, 50],
                        candidate_C=(1.0,), groups=g)
    assert probe.cv_scheme == "prompt_grouped"
    assert probe.n_groups == 40 and probe.n_folds_used == 5
    assert probe.label_ceiling == pytest.approx(label_ceiling(y, g))
    assert abs(probe.cv_accuracy - 0.5) < 0.1
    assert probe.weight.shape == (X.shape[1],)


def test_train_probe_without_groups_is_refused():
    X, y, g = repeated_prompt_data(n_groups=10, per_group=4, d=8)
    with pytest.raises(ValueError, match="requires `groups`"):
        train_probe({48: X}, y, candidate_layers=[48], candidate_C=(1.0,))


def test_train_probe_with_mismatched_groups_is_refused():
    X, y, g = repeated_prompt_data(n_groups=10, per_group=4, d=8)
    with pytest.raises(ValueError, match="rows"):
        train_probe({48: X}, y, candidate_layers=[48], candidate_C=(1.0,), groups=g[:-1])


def test_fold_accuracies_are_per_fold():
    from Probes.probes import cv_fold_accuracies
    X, y, g = repeated_prompt_data()
    scores, scheme, used = cv_fold_accuracies(X, y, g, C=1.0, n_folds=5, random_state=0)
    assert scheme == "prompt_grouped" and used == 5 and len(scores) == 5
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_fit_and_score_refuses_a_test_set_that_shares_prompts_with_training():
    X, y, g = repeated_prompt_data(n_groups=10, per_group=8, d=16, signal=True)
    rng = np.random.default_rng(0)
    boot = rng.integers(0, len(y), size=len(y))
    oob = np.setdiff1d(np.arange(len(y)), np.unique(boot))
    # Row bootstrap: the out-of-bag rows come from prompts that are also in-bag.
    assert shared_activation_rows(X[boot], X[oob]) == len(oob)
    with pytest.raises(ValueError, match="share their activation vector"):
        fit_and_score(X[boot], y[boot], X[oob], y[oob])
    with pytest.raises(ValueError, match="share their activation vector"):
        eval_probe_split(X[boot], y[boot], X[oob], y[oob])


def test_fit_and_score_accepts_a_prompt_disjoint_split():
    X, y, g = repeated_prompt_data(n_groups=40, per_group=8, d=8, signal=True)
    train = g < 30
    assert shared_activation_rows(X[train], X[~train]) == 0
    tr, te = fit_and_score(X[train], y[train], X[~train], y[~train])
    assert te > 0.65                               # unseen prompts, real signal
