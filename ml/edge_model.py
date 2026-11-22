"""Small PyTorch sequence classifier for the XAUUSD edge filter.

The model is deliberately a filter, not a trade generator. The deterministic
SMC/liquidity module supplies candidate setups; this model estimates the
probability that the setup reaches a configurable favorable move before the
adverse move within a future horizon.

Expected input: a chronological DataFrame with numeric feature columns and a
binary target column. Rows must not be shuffled before the split.

The implementation follows common sequence-modeling patterns from the
PyTorch/deep-learning projects listed in TopDeepLearning, but is original code
for this repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset


@dataclass(frozen=True)
class ModelConfig:
    seq_len: int = 64
    hidden_size: int = 64
    num_layers: int = 2
    dropout: float = 0.10
    batch_size: int = 64
    epochs: int = 30
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    threshold: float = 0.60
    seed: int = 42


class SequenceDataset(Dataset):
    def __init__(self, x: np.ndarray, y: np.ndarray) -> None:
        if len(x) != len(y):
            raise ValueError("x and y must have the same number of rows")
        self.x = torch.as_tensor(x, dtype=torch.float32)
        self.y = torch.as_tensor(y, dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, idx: int):
        return self.x[idx], self.y[idx]


class LSTMEdgeClassifier(nn.Module):
    def __init__(self, n_features: int, config: ModelConfig) -> None:
        super().__init__()
        self.encoder = nn.LSTM(
            input_size=n_features,
            hidden_size=config.hidden_size,
            num_layers=config.num_layers,
            dropout=config.dropout if config.num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.norm = nn.LayerNorm(config.hidden_size)
        self.head = nn.Sequential(
            nn.Linear(config.hidden_size, config.hidden_size // 2),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_size // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.encoder(x)
        last = self.norm(out[:, -1, :])
        return self.head(last).squeeze(-1)


def chronological_windows(
    frame: pd.DataFrame,
    feature_columns: Iterable[str],
    target_column: str,
    seq_len: int,
) -> tuple[np.ndarray, np.ndarray]:
    cols = list(feature_columns)
    missing = [c for c in [*cols, target_column] if c not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    if len(frame) <= seq_len:
        raise ValueError("Not enough rows for the requested sequence length")

    values = frame[cols].astype(float).to_numpy()
    target = frame[target_column].astype(float).to_numpy()

    xs, ys = [], []
    for end in range(seq_len, len(frame)):
        xs.append(values[end - seq_len:end])
        ys.append(target[end])

    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.float32)


def fit_standardizer(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = x.reshape(-1, x.shape[-1]).mean(axis=0)
    std = x.reshape(-1, x.shape[-1]).std(axis=0)
    std = np.where(std < 1e-8, 1.0, std)
    return mean, std


def standardize(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return (x - mean.reshape(1, 1, -1)) / std.reshape(1, 1, -1)


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)


def train_model(
    train_x: np.ndarray,
    train_y: np.ndarray,
    val_x: np.ndarray,
    val_y: np.ndarray,
    config: ModelConfig,
) -> tuple[LSTMEdgeClassifier, dict]:
    set_seed(config.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LSTMEdgeClassifier(train_x.shape[-1], config).to(device)

    pos = float(train_y.sum())
    neg = float(len(train_y) - pos)
    pos_weight = torch.tensor([neg / max(pos, 1.0)], device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )

    train_loader = DataLoader(
        SequenceDataset(train_x, train_y),
        batch_size=config.batch_size,
        shuffle=False,
    )

    best_state = None
    best_val = float("inf")
    history = []

    for epoch in range(config.epochs):
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += float(loss.item()) * len(yb)

        model.eval()
        with torch.no_grad():
            vx = torch.as_tensor(val_x, dtype=torch.float32, device=device)
            vy = torch.as_tensor(val_y, dtype=torch.float32, device=device)
            val_loss = float(loss_fn(model(vx), vy).item())

        train_loss /= max(len(train_y), 1)
        history.append({
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "val_loss": val_loss,
        })

        if val_loss < best_val:
            best_val = val_loss
            best_state = {
                k: v.detach().cpu().clone()
                for k, v in model.state_dict().items()
            }

    if best_state is None:
        raise RuntimeError("No model checkpoint was produced")
    model.load_state_dict(best_state)

    return model, {
        "device": str(device),
        "best_val_loss": best_val,
        "history": history,
    }


def predict_probability(model: nn.Module, x: np.ndarray) -> np.ndarray:
    device = next(model.parameters()).device
    model.eval()
    with torch.no_grad():
        logits = model(torch.as_tensor(x, dtype=torch.float32, device=device))
        return torch.sigmoid(logits).cpu().numpy()


def save_checkpoint(
    path: str | Path,
    model: LSTMEdgeClassifier,
    feature_columns: list[str],
    mean: np.ndarray,
    std: np.ndarray,
    config: ModelConfig,
) -> None:
    payload = {
        "state_dict": model.state_dict(),
        "feature_columns": feature_columns,
        "mean": mean,
        "std": std,
        "config": config.__dict__,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
