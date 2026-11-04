"""NETDEFY — Anomaly Score Fusion Engine.

Combines calibrated anomaly scores from Isolation Forest and Deep Autoencoder
into a unified anomaly score under configurable, scientifically validated fusion policies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

FusionStrategyType = Literal[
    "isolation_forest_only",
    "autoencoder_only",
    "max",
    "mean",
    "weighted",
]


@dataclass(frozen=True)
class ScoreFusionConfig:
    """Configuration for calibrated score fusion."""

    strategy: FusionStrategyType = "mean"
    weight_if: float = 0.5
    weight_ae: float = 0.5
    description: str = "Equal-weight average of calibrated scores"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScoreFusionConfig:
        return cls(
            strategy=data.get("strategy", "mean"),
            weight_if=float(data.get("weight_if", 0.5)),
            weight_ae=float(data.get("weight_ae", 0.5)),
            description=str(data.get("description", "")),
        )


class ScoreFusionEngine:
    """Executes multi-detector anomaly score fusion under validated mathematical policies."""

    def __init__(self, config: ScoreFusionConfig | None = None) -> None:
        self.config = config or ScoreFusionConfig()
        # Verify valid weights for weighted fusion
        if self.config.strategy == "weighted":
            total_w = self.config.weight_if + self.config.weight_ae
            if abs(total_w - 1.0) > 1e-5:
                raise ValueError(f"Weights must sum to 1.0 for weighted fusion (got {total_w})!")

    def fuse(
        self,
        c_if: np.ndarray | float,
        c_ae: np.ndarray | float,
    ) -> np.ndarray:
        """Fuse calibrated anomaly scores.

        Args:
            c_if: Calibrated Isolation Forest score(s) in [0, 1].
            c_ae: Calibrated Autoencoder score(s) in [0, 1].

        Returns:
            1D array of fused float32 anomaly scores in [0, 1].
        """
        arr_if = np.asarray(c_if, dtype=np.float32)
        arr_ae = np.asarray(c_ae, dtype=np.float32)

        if arr_if.shape != arr_ae.shape:
            raise ValueError(
                f"Shape mismatch in score fusion: IF {arr_if.shape} vs AE {arr_ae.shape}"
            )
        if np.isnan(arr_if).any() or np.isnan(arr_ae).any():
            raise ValueError("NaN values detected in calibrated input scores!")

        strategy = self.config.strategy
        if strategy == "isolation_forest_only":
            fused = arr_if.copy()
        elif strategy == "autoencoder_only":
            fused = arr_ae.copy()
        elif strategy == "max":
            fused = np.maximum(arr_if, arr_ae)
        elif strategy == "mean":
            fused = 0.5 * (arr_if + arr_ae)
        elif strategy == "weighted":
            fused = self.config.weight_if * arr_if + self.config.weight_ae * arr_ae
        else:
            raise ValueError(f"Unsupported fusion strategy: {strategy}")

        return np.clip(fused, 0.0, 1.0).astype(np.float32)

    def save(self, filepath: Path | str) -> str:
        """Save fusion configuration and return SHA-256."""
        path = Path(filepath).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = self.config.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def load(cls, filepath: Path | str) -> ScoreFusionEngine:
        """Load fusion engine from JSON configuration."""
        path = Path(filepath).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Fusion config not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        config = ScoreFusionConfig.from_dict(data)
        return cls(config=config)
