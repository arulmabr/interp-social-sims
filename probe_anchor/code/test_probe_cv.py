"""probe_cv: prompt-held-out accuracy and the label ceiling. No GPU, no run tree."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location(
    "probe_cv", Path(__file__).resolve().parent / "lib" / "probe_cv.py")
probe_cv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_cv)


def repeated_level_data(n_levels=45, per_level=8, d=64, signal=False, seed=0):
    """G4's design: one vector per reward level, PROBE_SAMPLES rows each."""
    rng = np.random.default_rng(seed)
    vectors = rng.normal(size=(n_levels, d))
    X, y, g = [], [], []
    for lvl in range(n_levels):
        # each level has a clear tendency, tied to the vector only when signal
        if signal:
            p_high = 0.85 if vectors[lvl, 0] > 0 else 0.15
        else:
            p_high = 0.85 if rng.random() < 0.5 else 0.15
        for _ in range(per_level):
            X.append(vectors[lvl])
            y.append(int(rng.random() < p_high))
            g.append(lvl)
    return np.asarray(X), np.asarray(y), np.asarray(g)


def test_ceiling():
    y = np.array([1, 1, 0, 0, 0, 0, 1, 0])
    g = np.array([0, 0, 0, 1, 1, 1, 2, 2])
    assert probe_cv.label_ceiling(y, g) == pytest.approx(6 / 8)


def test_folds_never_split_a_level():
    X, y, g = repeated_level_data()
    splits, scheme, used = probe_cv.grouped_splits(y, g, n_folds=5, seed=0)
    assert scheme == "prompt_grouped" and used == 5 and len(splits) == 5
    for tr, va in splits:
        assert not (set(g[tr]) & set(g[va]))


def test_training_accuracy_exceeds_held_out_on_pure_noise():
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    X, y, g = repeated_level_data(signal=False)
    sc = StandardScaler().fit(X)
    train_acc = LogisticRegression(penalty="l2", C=1.0, max_iter=2000).fit(
        sc.transform(X), y).score(sc.transform(X), y)
    out = probe_cv.grouped_cv_accuracy(X, y, g, n_folds=5, seed=0)
    assert train_acc > 0.75                  # the fit scored on its own rows
    assert abs(out["accuracy"] - 0.5) < 0.1   # what an unseen level gets
    assert train_acc - out["accuracy"] > 0.15
    assert out["n_groups"] == 45 and len(out["per_fold"]) == 5


def test_held_out_keeps_real_signal():
    X, y, g = repeated_level_data(d=16, signal=True)
    out = probe_cv.grouped_cv_accuracy(X, y, g)
    assert out["accuracy"] > 0.65


def test_few_levels_use_leave_one_out():
    X, y, g = repeated_level_data(n_levels=3, per_level=6, d=8, signal=True)
    out = probe_cv.grouped_cv_accuracy(X, y, g, n_folds=5)
    assert out["scheme"] == "leave_one_prompt_out" and out["n_folds"] == 3
