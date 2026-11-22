"""Leakage-aware chronological validation for trading ML experiments.

This module intentionally does not shuffle observations. Each fold trains on
the past and validates on a later interval. A small embargo can be applied
between train and validation windows to reduce label overlap around the split.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np


@dataclass(frozen=True)
class Fold:
    train_start: int
    train_end: int
    valid_start: int
    valid_end: int


def expanding_walk_forward(
    n_rows: int,
    min_train: int,
    validation_size: int,
    step: int | None = None,
    embargo: int = 0,
) -> Iterator[Fold]:
    if min_train <= 0 or validation_size <= 0:
        raise ValueError("min_train and validation_size must be positive")
    if embargo < 0:
        raise ValueError("embargo cannot be negative")

    step = validation_size if step is None else step
    if step <= 0:
        raise ValueError("step must be positive")

    valid_start = min_train
    while valid_start + validation_size <= n_rows:
        train_end = max(0, valid_start - embargo)
        if train_end <= 0:
            break
        yield Fold(
            train_start=0,
            train_end=train_end,
            valid_start=valid_start,
            valid_end=valid_start + validation_size,
        )
        valid_start += step


def classification_report(
    y_true: np.ndarray,
    p: np.ndarray,
    threshold: float = 0.5,
) -> dict:
    y_true = np.asarray(y_true).astype(int)
    p = np.asarray(p)
    pred = (p >= threshold).astype(int)

    tp = int(((pred == 1) & (y_true == 1)).sum())
    tn = int(((pred == 0) & (y_true == 0)).sum())
    fp = int(((pred == 1) & (y_true == 0)).sum())
    fn = int(((pred == 0) & (y_true == 1)).sum())

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    accuracy = (tp + tn) / max(len(y_true), 1)

    return {
        "n": int(len(y_true)),
        "positive_rate": float(y_true.mean()) if len(y_true) else 0.0,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }
