"""Probe training, scoring, and steering-direction extraction.

`l2`-regularized logistic regression. CV over (layer, C). Final probe is a
single (weight_vector, bias) pair plus the picked layer.

Cross-validation is grouped by prompt. Every generation sampled from one prompt
shares that prompt's activation vector: the activation is captured from the
prompt, before any answer is produced, so the eight trials at one reward level
are eight copies of one vector with labels that differ only through sampling.
Folds are therefore built over prompts, so that a validation fold holds only
prompts the probe did not train on and its score speaks to generalization.

`train_probe` requires `groups`, one id per row naming the prompt the row came
from. `Probe.cv_accuracy` is the prompt-held-out estimate. `Probe.label_ceiling`
is the best accuracy any function of the activation can reach on this data: rows
that share a vector must receive one answer, so the ceiling is the
group-majority rate.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneGroupOut, StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler


@dataclass
class Probe:
    weight: np.ndarray              # shape (d,)
    bias: float
    layer: int
    cv_accuracy: float              # prompt-held-out
    scaler_mean: np.ndarray
    scaler_scale: np.ndarray
    label_low: str = "low"
    label_high: str = "high"
    meta: Dict = field(default_factory=dict)
    # How cv_accuracy was estimated: "prompt_grouped" (StratifiedGroupKFold over
    # prompts) or "leave_one_prompt_out" (fewer prompts than folds).
    cv_scheme: str = "prompt_grouped"
    n_groups: int = 0
    n_folds_used: int = 0
    label_ceiling: float = float("nan")

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


# =========================================================================
# Grouped cross-validation
# =========================================================================
def label_ceiling(labels: Sequence[int], groups: Sequence) -> float:
    """Highest accuracy reachable when rows in a group share one activation.

    A classifier is a function of the activation, so it must give every row in
    a group the same answer; the best it can do is the group's majority label.
    """
    y = np.asarray(labels)
    g = np.asarray(groups)
    if y.size == 0:
        return float("nan")
    correct = 0
    for gid in np.unique(g):
        yy = y[g == gid]
        correct += int(max(np.sum(yy == c) for c in np.unique(yy)))
    return correct / y.size


def make_cv(labels: Sequence[int], groups: Sequence, n_folds: int,
            random_state: int) -> Tuple[object, str, int]:
    """Choose the fold splitter. Returns (splitter, scheme, n_folds_used).

    No prompt ever appears in both the training and the validation side of a
    split. If there are at least `n_folds` distinct prompts, folds are
    stratified by label over whole prompts; with fewer prompts each one is held
    out in turn.
    """
    y = np.asarray(labels)
    if groups is None:
        raise ValueError("groups is required: one prompt id per row")
    g = np.asarray(groups)
    if g.shape[0] != y.shape[0]:
        raise ValueError(f"groups has {g.shape[0]} rows, labels has {y.shape[0]}")
    n_groups = int(np.unique(g).size)
    if n_groups < 2:
        raise ValueError(
            "Prompt-held-out cross-validation needs at least two distinct prompts; "
            f"got {n_groups}. Vary the prompt (reward level, object, wording) so the "
            "probe can be tested on a prompt it has not seen.")
    if n_groups >= n_folds:
        return (StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=random_state),
                "prompt_grouped", n_folds)
    return LeaveOneGroupOut(), "leave_one_prompt_out", n_groups


def _fold_accuracy(X: np.ndarray, y: np.ndarray, tr: np.ndarray, va: np.ndarray,
                   C: float, random_state: int) -> float:
    """Standardize on the training rows only, fit, score the validation rows."""
    classes = np.unique(y[tr])
    if classes.size < 2:
        # A single-class training fold can only predict that class.
        return float(np.mean(y[va] == classes[0]))
    scaler = StandardScaler().fit(X[tr])
    clf = LogisticRegression(
        penalty="l2", C=C, solver="lbfgs", max_iter=1000, random_state=random_state
    )
    clf.fit(scaler.transform(X[tr]), y[tr])
    return float(clf.score(scaler.transform(X[va]), y[va]))


def cv_fold_accuracies(X: np.ndarray, y: np.ndarray, groups: Sequence,
                       C: float, n_folds: int, random_state: int) -> Tuple[List[float], str, int]:
    """Per-fold prompt-held-out accuracies. Returns (scores, scheme, n_folds_used)."""
    y = np.asarray(y)
    splitter, scheme, used = make_cv(y, groups, n_folds, random_state)
    g = np.asarray(groups)
    scores = [_fold_accuracy(X, y, tr, va, C, random_state)
              for tr, va in splitter.split(X, y, g)]
    return scores, scheme, used


def cv_accuracy(X: np.ndarray, y: np.ndarray, groups: Sequence,
                C: float, n_folds: int, random_state: int) -> Tuple[float, str, int]:
    """Mean validation accuracy over folds. Returns (accuracy, scheme, n_folds_used)."""
    scores, scheme, used = cv_fold_accuracies(X, y, groups, C, n_folds, random_state)
    return float(np.mean(scores)), scheme, used


def train_probe(
    activations_by_layer: Dict[int, np.ndarray],   # {layer: (N, d)}
    labels: np.ndarray,                            # (N,)
    candidate_layers: Sequence[int],
    candidate_C: Sequence[float] = (0.01, 0.1, 1.0, 10.0),
    n_folds: int = 5,
    random_state: int = 0,
    groups: Optional[Sequence] = None,             # (N,) prompt id per row; required
) -> Probe:
    """CV-pick best layer + regularization, then fit final probe on full data.

    `groups` names the prompt each row was generated from and is required. Rows
    from one prompt share an activation, so the folds are built over prompts;
    see the module docstring.
    """
    labels = np.asarray(labels)
    if groups is None:
        raise ValueError(
            "train_probe requires `groups`, one prompt id per row, so that folds are "
            "built over prompts. For the lottery and ultimatum probes the group is the "
            "reward or offer level; for the capability probe it is the distinct prompt "
            "text.")
    groups = np.asarray(groups)
    if groups.shape[0] != labels.shape[0]:
        raise ValueError(f"groups has {groups.shape[0]} rows, labels has {labels.shape[0]}")
    best = None
    scheme, used = "prompt_grouped", n_folds
    for layer in candidate_layers:
        X = activations_by_layer[layer]
        for C in candidate_C:
            cv_mean, scheme, used = cv_accuracy(X, labels, groups, C, n_folds, random_state)
            if best is None or cv_mean > best["cv"]:
                best = dict(cv=cv_mean, layer=layer, C=C)

    X = activations_by_layer[best["layer"]]
    n_groups = int(np.unique(groups).size)
    ceiling = label_ceiling(labels, groups)

    # Refit on full data at the chosen (layer, C)
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
        cv_scheme=scheme,
        n_groups=n_groups,
        n_folds_used=int(used),
        label_ceiling=float(ceiling),
    )


def shared_activation_rows(train_X: np.ndarray, test_X: np.ndarray) -> int:
    """How many test rows are byte-identical to some training row.

    Rows generated from the same prompt carry the same activation vector, so a
    test row that equals a training row is a prompt the probe has already seen.
    """
    seen = {np.ascontiguousarray(r).tobytes() for r in np.asarray(train_X)}
    return int(sum(np.ascontiguousarray(r).tobytes() in seen for r in np.asarray(test_X)))


def _require_disjoint_prompts(train_X: np.ndarray, test_X: np.ndarray, where: str) -> None:
    n = shared_activation_rows(train_X, test_X)
    if n:
        raise ValueError(
            f"{where}: {n} of {len(test_X)} test rows share their activation vector "
            "with a training row, so they come from prompts the probe was trained on "
            "and the test accuracy would not be a held-out estimate. Split by prompt.")


def fit_and_score(
    train_X: np.ndarray, train_y: np.ndarray,
    test_X: np.ndarray, test_y: np.ndarray,
    C: float = 1.0,
    random_state: int = 0,
) -> Tuple[float, float]:
    """Fit one standardized L2-logistic probe; return (train_acc, test_acc).

    Used by the cross-object generalization runner so each seed's fit quality
    can be inspected (to drop ill-posed seeds) rather than averaged blindly.
    The test set must not share any activation vector with the training set.
    """
    _require_disjoint_prompts(train_X, test_X, "fit_and_score")
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
    Used for the cross-object generalization figures (13 / 19). The test set
    must not share any activation vector with the training set.
    """
    _require_disjoint_prompts(train_X, test_X, "eval_probe_split")
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
