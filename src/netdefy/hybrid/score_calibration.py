"""NETDEFY — Anomaly Score Calibration Engine.

Implements leakage-safe, monotonic score calibration algorithms to project
heterogeneous anomaly detector outputs (Isolation Forest path lengths and
Autoencoder reconstruction errors) onto a unified, comparable [0, 1] scale.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np


class BaseScoreCalibrator(ABC):
    """Abstract base class for univariate anomaly score calibrators."""

    def __init__(self) -> None:
        self.is_fitted: bool = False
        self.reference_name: str = "benign_validation"

    @abstractmethod
    def fit(
        self, scores: np.ndarray, reference_name: str = "benign_validation"
    ) -> BaseScoreCalibrator:
        """Fit calibrator parameters on permitted reference anomaly scores."""

    @abstractmethod
    def transform(self, scores: np.ndarray) -> np.ndarray:
        """Transform raw anomaly scores into calibrated [0, 1] anomaly scores.

        Orientation Guarantee:
            Higher raw score -> Higher calibrated score.
        """

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize calibrator configuration and fitted parameters to dictionary."""

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseScoreCalibrator:
        """Instantiate calibrator from dictionary."""

    def save(self, filepath: Path | str) -> str:
        """Save calibrator JSON bundle and return SHA-256 checksum."""
        if not self.is_fitted:
            raise RuntimeError("Cannot save unfitted score calibrator!")

        path = Path(filepath).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = self.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def load(cls, filepath: Path | str) -> BaseScoreCalibrator:
        """Load calibrator from JSON bundle."""
        path = Path(filepath).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Calibrator file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        calibrator_type = data.get("calibrator_type")
        if calibrator_type == "percentile":
            return PercentileCalibrator.from_dict(data)
        if calibrator_type == "robust_sigmoid":
            return RobustScalerCalibrator.from_dict(data)
        raise ValueError(f"Unknown calibrator type: {calibrator_type}")


class PercentileCalibrator(BaseScoreCalibrator):
    """Calibrates raw scores to empirical percentile ranks via a reference distribution.

    Uses high-resolution quantile interpolation (1,001 points from 0.0 to 1.0)
    fitted strictly on permitted reference data (e.g. benign validation flows).
    Values strictly above the reference maximum extrapolate smoothly to 1.0;
    values strictly below the reference minimum extrapolate to 0.0.
    """

    def __init__(self, num_quantiles: int = 1001) -> None:
        super().__init__()
        self.num_quantiles = num_quantiles
        self.quantile_levels: np.ndarray = np.linspace(0.0, 1.0, num_quantiles, dtype=np.float64)
        self.quantile_values: np.ndarray = np.array([], dtype=np.float64)
        self.sample_count: int = 0
        self.min_score: float = 0.0
        self.max_score: float = 0.0

    def fit(
        self, scores: np.ndarray, reference_name: str = "benign_validation"
    ) -> PercentileCalibrator:
        """Fit quantile grid on 1D reference scores."""
        arr = np.asarray(scores, dtype=np.float64).ravel()
        if len(arr) == 0:
            raise ValueError("Cannot fit PercentileCalibrator on empty score array!")
        if np.isnan(arr).any() or np.isinf(arr).any():
            raise ValueError("Reference score array contains NaN or Inf values!")

        self.sample_count = len(arr)
        self.reference_name = reference_name
        self.min_score = float(np.min(arr))
        self.max_score = float(np.max(arr))

        # Compute empirical quantiles
        self.quantile_values = np.quantile(arr, self.quantile_levels, method="linear")
        # Ensure strict monotonicity for interpolation
        self.quantile_values = np.maximum.accumulate(self.quantile_values)
        self.is_fitted = True
        return self

    def transform(self, scores: np.ndarray) -> np.ndarray:
        """Transform raw anomaly scores into calibrated empirical percentiles in [0.0, 1.0]."""
        if not self.is_fitted:
            raise RuntimeError("PercentileCalibrator is not fitted!")

        arr = np.asarray(scores, dtype=np.float64)
        if np.isnan(arr).any() or np.isinf(arr).any():
            raise ValueError("Input score array contains NaN or Inf values!")

        # Monotonic linear interpolation with boundary clamping
        calibrated: np.ndarray = np.interp(
            arr,
            self.quantile_values,
            self.quantile_levels,
            left=0.0,
            right=1.0,
        )
        return np.asarray(calibrated, dtype=np.float32)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibrator_type": "percentile",
            "num_quantiles": self.num_quantiles,
            "sample_count": self.sample_count,
            "reference_name": self.reference_name,
            "min_score": self.min_score,
            "max_score": self.max_score,
            "quantile_levels": self.quantile_levels.tolist(),
            "quantile_values": self.quantile_values.tolist(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PercentileCalibrator:
        calibrator = cls(num_quantiles=int(data.get("num_quantiles", 1001)))
        calibrator.sample_count = int(data.get("sample_count", 0))
        calibrator.reference_name = data.get("reference_name", "benign_validation")
        calibrator.min_score = float(data.get("min_score", 0.0))
        calibrator.max_score = float(data.get("max_score", 1.0))
        calibrator.quantile_levels = np.array(data["quantile_levels"], dtype=np.float64)
        calibrator.quantile_values = np.array(data["quantile_values"], dtype=np.float64)
        calibrator.is_fitted = True
        return calibrator


class RobustScalerCalibrator(BaseScoreCalibrator):
    """Calibrates raw scores via Median and Interquartile Range (IQR) with logistic squashing.

    Transformation:
        z = (score - median) / (IQR + epsilon)
        calibrated = 1 / (1 + exp(-z))
    Guarantees output in (0.0, 1.0) with robust resilience against extreme outliers.
    """

    def __init__(self, epsilon: float = 1e-7) -> None:
        super().__init__()
        self.epsilon = epsilon
        self.median: float = 0.0
        self.iqr: float = 1.0
        self.q25: float = 0.0
        self.q75: float = 1.0
        self.sample_count: int = 0

    def fit(
        self, scores: np.ndarray, reference_name: str = "benign_validation"
    ) -> RobustScalerCalibrator:
        """Fit robust statistics on reference scores."""
        arr = np.asarray(scores, dtype=np.float64).ravel()
        if len(arr) == 0:
            raise ValueError("Cannot fit RobustScalerCalibrator on empty score array!")
        if np.isnan(arr).any() or np.isinf(arr).any():
            raise ValueError("Reference score array contains NaN or Inf values!")

        self.sample_count = len(arr)
        self.reference_name = reference_name
        self.median = float(np.median(arr))
        self.q25 = float(np.percentile(arr, 25.0))
        self.q75 = float(np.percentile(arr, 75.0))
        self.iqr = max(self.q75 - self.q25, self.epsilon)
        self.is_fitted = True
        return self

    def transform(self, scores: np.ndarray) -> np.ndarray:
        """Transform raw anomaly scores into calibrated robust probabilities in (0, 1)."""
        if not self.is_fitted:
            raise RuntimeError("RobustScalerCalibrator is not fitted!")

        arr = np.asarray(scores, dtype=np.float64)
        if np.isnan(arr).any() or np.isinf(arr).any():
            raise ValueError("Input score array contains NaN or Inf values!")

        # Robust z-score
        z = (arr - self.median) / self.iqr
        # Numerical stability clamp for sigmoid
        z_clamped = np.clip(z, -30.0, 30.0)
        calibrated = 1.0 / (1.0 + np.exp(-z_clamped))
        return np.asarray(calibrated, dtype=np.float32)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibrator_type": "robust_sigmoid",
            "epsilon": self.epsilon,
            "sample_count": self.sample_count,
            "reference_name": self.reference_name,
            "median": self.median,
            "q25": self.q25,
            "q75": self.q75,
            "iqr": self.iqr,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RobustScalerCalibrator:
        calibrator = cls(epsilon=float(data.get("epsilon", 1e-7)))
        calibrator.sample_count = int(data.get("sample_count", 0))
        calibrator.reference_name = data.get("reference_name", "benign_validation")
        calibrator.median = float(data.get("median", 0.0))
        calibrator.q25 = float(data.get("q25", 0.0))
        calibrator.q75 = float(data.get("q75", 1.0))
        calibrator.iqr = float(data.get("iqr", 1.0))
        calibrator.is_fitted = True
        return calibrator
