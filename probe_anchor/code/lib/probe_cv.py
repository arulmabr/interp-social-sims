"""Prompt-held-out accuracy for probes fitted on repeated prompt activations.

Every row generated from one prompt shares that prompt's activation vector,
because the vector is captured from the prompt before the answer is sampled.
An accuracy computed on the training rows, or on a trial-level split, therefore
scores the probe on vectors it has already seen. The functions here hold whole
prompts out instead, and report the label ceiling that shared vectors impose.

Pure numpy and scikit-learn; no model, no run tree.
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

import numpy as np


def label_ceiling(labels: Sequence[int], groups: Sequence) -> float:
    """Best accuracy any function of the activation can reach on this data.

    Rows in a group share a vector and so must receive one answer; the best
    answer is the group's majority label.
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


def grouped_splits(labels: Sequence[int], groups: Sequence, n_folds: int = 5,
                   seed: int = 0) -> Tuple[list, str, int]:
    """Folds in which no group appears on both sides. Returns (splits, scheme, n)."""
    from sklearn.model_selection import LeaveOneGroupOut, StratifiedGroupKFold

    y = np.asarray(labels)
    g = np.asarray(groups)
    if g.shape[0] != y.shape[0]:
        raise ValueError(f"groups has {g.shape[0]} rows, labels has {y.shape[0]}")
    n_groups = int(np.unique(g).size)
    if n_groups < 2:
        raise ValueError("prompt-held-out accuracy needs at least two distinct prompts")
    X = np.zeros((y.shape[0], 1))
    if n_groups >= n_folds:
        sp = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
        return list(sp.split(X, y, g)), "prompt_grouped", n_folds
    sp = LeaveOneGroupOut()
    return list(sp.split(X, y, g)), "leave_one_prompt_out", n_groups


def grouped_cv_accuracy(X: np.ndarray, labels: Sequence[int], groups: Sequence,
                        n_folds: int = 5, seed: int = 0, C: float = 1.0,
                        max_iter: int = 2000) -> Dict[str, object]:
    """Mean held-out accuracy of a standardized L2 logistic probe over grouped folds.

    The scaler is fitted on the training rows of each fold. A training fold with
    one class predicts that class. Returns accuracy, the scheme used, fold count,
    group count and the per-fold scores.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    y = np.asarray(labels, dtype=int)
    splits, scheme, used = grouped_splits(y, groups, n_folds, seed)
    scores = []
    for tr, va in splits:
        classes = np.unique(y[tr])
        if classes.size < 2:
            scores.append(float(np.mean(y[va] == classes[0])))
            continue
        sc = StandardScaler().fit(X[tr])
        lr = LogisticRegression(penalty="l2", C=C, max_iter=max_iter).fit(
            sc.transform(X[tr]), y[tr])
        scores.append(float(lr.score(sc.transform(X[va]), y[va])))
    return dict(accuracy=float(np.mean(scores)), scheme=scheme, n_folds=int(used),
                n_groups=int(np.unique(np.asarray(groups)).size),
                per_fold=[round(s, 4) for s in scores])
