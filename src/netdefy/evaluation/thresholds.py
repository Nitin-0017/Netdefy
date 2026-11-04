"""NETDEFY — Anomaly Threshold Calibration Module.

Implements pure-benign threshold calibration for unsupervised anomaly detectors,
ensuring strict adherence to the Validation Purity Principle.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ThresholdEntry:
    """Represents a single calibrated percentile threshold."""

    percentile: float
    threshold_value: float
    benign_fpr_nominal: float  # (100 - percentile) / 100


@dataclass
class ThresholdCalibrationResult:
    """Encapsulates the complete threshold calibration metadata."""

    strategy: str
    calibration_timestamp: str
    benign_sample_count: int
    score_statistics: dict[str, float]
    thresholds: dict[str, float]  # e.g., {"p95.0": 0.523, "p99.0": 0.551}
    threshold_entries: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, filepath: Path | str) -> None:
        """Save calibration result to JSON."""
        save_path = Path(filepath).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: Path | str) -> ThresholdCalibrationResult:
        """Load calibration result from JSON."""
        load_path = Path(filepath).resolve()
        with open(load_path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


class BenignThresholdCalibrator:
    """Calibrates anomaly thresholds strictly on BENIGN validation traffic.

    Adheres strictly to the Validation Purity Principle:
    Thresholds represent empirical upper-tail percentiles of benign flow scores.
    At no point are attack labels inspected during threshold selection.
    """

    def __init__(self, target_percentiles: list[float] | None = None) -> None:
        self.target_percentiles = target_percentiles or [95.0, 99.0, 99.5]
        for p in self.target_percentiles:
            if not 0.0 < p < 100.0:
                raise ValueError(f"Percentile must be in (0, 100), got {p}")

    def calibrate(self, benign_scores: np.ndarray) -> ThresholdCalibrationResult:
        """Calibrate thresholds from pure benign anomaly scores.

        Args:
            benign_scores: 1D array of float32 anomaly scores from benign flows.

        Returns:
            ThresholdCalibrationResult with calibrated thresholds and score statistics.
        """
        scores = np.asarray(benign_scores, dtype=np.float32).ravel()

        if len(scores) == 0:
            raise ValueError("Cannot calibrate thresholds on empty scores array!")
        if np.isnan(scores).any() or np.isinf(scores).any():
            raise ValueError("Benign scores array contains NaN or Inf values!")

        # Compute empirical statistics on benign baseline scores
        stats = {
            "min": float(np.min(scores)),
            "max": float(np.max(scores)),
            "mean": float(np.mean(scores)),
            "std": float(np.std(scores)),
            "median": float(np.median(scores)),
            "q25": float(np.percentile(scores, 25.0)),
            "q75": float(np.percentile(scores, 75.0)),
            "iqr": float(np.percentile(scores, 75.0) - np.percentile(scores, 25.0)),
        }

        thresholds: dict[str, float] = {}
        entries: list[dict[str, Any]] = []

        for p in sorted(self.target_percentiles):
            th_val = float(np.percentile(scores, p))
            key = f"p{p:.1f}"
            thresholds[key] = th_val
            entries.append(
                asdict(
                    ThresholdEntry(
                        percentile=p,
                        threshold_value=th_val,
                        benign_fpr_nominal=round((100.0 - p) / 100.0, 4),
                    )
                )
            )

        return ThresholdCalibrationResult(
            strategy="benign_validation_percentile",
            calibration_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            benign_sample_count=len(scores),
            score_statistics=stats,
            thresholds=thresholds,
            threshold_entries=entries,
        )

    def calibrate_from_validation(
        self,
        val_df: pd.DataFrame,
        anomaly_scores: np.ndarray,
        label_column: str = "Label",
        benign_label: str = "BENIGN",
    ) -> ThresholdCalibrationResult:
        """Filter validation set for pure BENIGN flows and calibrate thresholds.

        Raises:
            ValueError if no benign samples are found or lengths mismatch.
        """
        if len(val_df) != len(anomaly_scores):
            raise ValueError(
                f"Validation DataFrame length ({len(val_df)}) does not match scores length ({len(anomaly_scores)})!"
            )

        benign_mask = (val_df[label_column] == benign_label).to_numpy()
        benign_count = int(np.sum(benign_mask))

        if benign_count == 0:
            raise ValueError(f"No samples found with label '{benign_label}' in validation set!")

        benign_scores = anomaly_scores[benign_mask]
        return self.calibrate(benign_scores)
