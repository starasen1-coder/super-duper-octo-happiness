"""Chronological train/validation/test split with no shuffling."""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class WalkForwardParts:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame

def split_walk_forward(df: pd.DataFrame, train: float = 0.6, validation: float = 0.2) -> WalkForwardParts:
    if not 0 < train < 1 or not 0 < validation < 1 or train + validation >= 1:
        raise ValueError("train and validation fractions must be >0 and sum to <1")
    if len(df) < 3:
        raise ValueError("at least 3 rows are required")
    data = df.sort_values("time").reset_index(drop=True)
    n = len(data)
    i = int(n * train)
    j = i + int(n * validation)
    if i < 1 or j <= i or j >= n:
        raise ValueError("split fractions produce an empty partition")
    return WalkForwardParts(data.iloc[:i].copy(), data.iloc[i:j].copy(), data.iloc[j:].copy())
