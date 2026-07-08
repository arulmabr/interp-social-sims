"""Probe training, scoring, and steering-direction extraction.

`l2`-regularized logistic regression. CV over (layer, C). Final probe is a
single (weight_vector, bias) pair plus the picked layer.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler


@dataclass
class Probe:
    weight: np.ndarray              # shape (d,)
    bias: float
    layer: int
    cv_accuracy: float
    scaler_mean: np.ndarray
    scaler_scale: np.ndarray
    label_low: str = "low"
    label_high: str = "high"
    meta: Dict = field(default_factory=dict)

    @property
    def direction_unit(self) -> np.ndarray:
        w = self.weight
        return w / (np.linalg.norm(w) + 1e-12)

    def score(self, activation: np.ndarray) -> float:
        """Return signed projection s = w_hat^T h (unit-normalized)."""
        h_std = (activation - self.scaler_mean) / self.scaler_scale
        return float(np.dot(self.direction_unit, h_std))

    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: Path) -> "Probe":
        with open(path, "rb") as f:
            return pickle.load(f)


def median_split(values: Sequence[float]) -> np.ndarray:
    """Return binary labels (0/1) via median split: above-median -> 1.

    Use ONLY for metrics that increase with the target trait, so that the
    positive class is the "high" one -- e.g. the capability probe's creativity
    score (higher score = more creative). Do NOT feed a switching point here:
    a lower switching point means *more* risk-taking, so an above-median split
    would label the risk-averse trials as "high". Preference probes therefore
    label by the agent's observed choice (see build_preference_probe), not this
    helper.
    """
    arr = np.asarray(values, dtype=float)
    median = np.median(arr)
    return (arr > median).astype(int)


def train_probe(
    activations_by_layer: Dict[int, np.ndarray],   # {layer: (N, d)}
    labels: np.ndarray,                            # (N,)
    candidate_layers: Sequence[int],
    candidate_C: Sequence[float] = (0.01, 0.1, 1.0, 10.0),
    n_folds: int = 5,
    random_state: int = 0,
) -> Probe:
    """CV-pick best layer + regularization, then fit final probe on full data."""
    best = None
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=random_state)

    for layer in candidate_layers:
        X = activations_by_layer[layer]
        for C in candidate_C:
            fold_scores = []
            for tr, va in skf.split(X, labels):
                scaler = StandardScaler().fit(X[tr])
                Xtr = scaler.transform(X[tr])
                Xva = scaler.transform(X[va])
                clf = LogisticRegression(
                    penalty="l2", C=C, solver="lbfgs", max_iter=1000, random_state=random_state
                )
                clf.fit(Xtr, labels[tr])
                fold_scores.append(clf.score(Xva, labels[va]))
            cv_mean = float(np.mean(fold_scores))
            if best is None or cv_mean > best["cv"]:
                best = dict(cv=cv_mean, layer=layer, C=C)

    # Refit on full data at the chosen (layer, C)
    X = activations_by_layer[best["layer"]]
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    clf = LogisticRegression(
        penalty="l2", C=best["C"], solver="lbfgs", max_iter=2000, random_state=random_state
    )
    clf.fit(Xs, labels)
    return Probe(
        weight=clf.coef_.ravel().astype(np.float32),
        bias=float(clf.intercept_[0]),
        layer=int(best["layer"]),
        cv_accuracy=float(best["cv"]),
        scaler_mean=scaler.mean_.astype(np.float32),
        scaler_scale=scaler.scale_.astype(np.float32),
        meta=dict(best_C=best["C"], n_folds=n_folds),
    )


def fit_and_score(
    train_X: np.ndarray, train_y: np.ndarray,
    test_X: np.ndarray, test_y: np.ndarray,
    C: float = 1.0,
    random_state: int = 0,
) -> Tuple[float, float]:
    """Fit one standardized L2-logistic probe; return (train_acc, test_acc).

    Used by the cross-object generalization runner so each seed's fit quality
    can be inspected (to drop ill-posed seeds) rather than averaged blindly.
    """
    scaler = StandardScaler().fit(train_X)
    Xtr = scaler.transform(train_X)
    Xte = scaler.transform(test_X)
    clf = LogisticRegression(
        penalty="l2", C=C, solver="lbfgs", max_iter=2000, random_state=random_state
    )
    clf.fit(Xtr, train_y)
    return float(clf.score(Xtr, train_y)), float(clf.score(Xte, test_y))


def eval_probe_split(
    train_X: np.ndarray, train_y: np.ndarray,
    test_X: np.ndarray, test_y: np.ndarray,
    C: float = 1.0,
    n_seeds: int = 5,
) -> Tuple[float, float, int]:
    """Train + evaluate a fresh probe across multiple random seeds.

    Returns (mean_accuracy, std_accuracy, n_runs).
    Used for the cross-object generalization figures (13 / 19).
    """
    accs = []
    for seed in range(n_seeds):
        scaler = StandardScaler().fit(train_X)
        Xtr = scaler.transform(train_X)
        Xte = scaler.transform(test_X)
        clf = LogisticRegression(
            penalty="l2", C=C, solver="lbfgs", max_iter=2000, random_state=seed
        )
        clf.fit(Xtr, train_y)
        accs.append(clf.score(Xte, test_y))
    return float(np.mean(accs)), float(np.std(accs)), int(n_seeds)
