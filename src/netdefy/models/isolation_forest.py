"""NETDEFY — Isolation Forest Baseline Anomaly Detection Engine.

Implements a reproducible, leakage-safe scikit-learn Isolation Forest wrapper
designed for unsupervised network flow anomaly detection.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


@dataclass(frozen=True)
class IsolationForestConfig:
    """Hyperparameter configuration for IsolationForestDetector."""

    n_estimators: int = 100
    max_samples: int | float | Literal["auto"] = "auto"
    contamination: float | Literal["auto"] = "auto"
    max_features: float = 1.0
    bootstrap: bool = False
    n_jobs: int = -1
    random_state: int = 42

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IsolationForestDetector:
    """Production-grade Isolation Forest anomaly detector for network traffic flows.

    Score Orientation:
        In scikit-learn, `score_samples(X)` returns the opposite of the anomaly score
        defined in Liu et al. (2008), where lower (more negative) values indicate anomalies.
        In NETDEFY, all anomaly detectors strictly adhere to:
            **HIGHER ANOMALY SCORE = MORE SUSPICIOUS / ANOMALOUS**
        Therefore, `score_samples(X)` computes:
            anomaly_score(x) = -sklearn_model.score_samples(x)
    """

    def __init__(self, config: IsolationForestConfig | None = None) -> None:
        self.config = config or IsolationForestConfig()
        self.model = IsolationForest(
            n_estimators=self.config.n_estimators,
            max_samples=self.config.max_samples,
            contamination=self.config.contamination,
            max_features=self.config.max_features,
            bootstrap=self.config.bootstrap,
            n_jobs=self.config.n_jobs,
            random_state=self.config.random_state,
        )
        self.feature_names: list[str] = []
        self.is_fitted: bool = False
        self.train_duration_seconds: float = 0.0
        self.train_sample_count: int = 0

    def fit(
        self,
        X: pd.DataFrame | np.ndarray,
        feature_names: list[str] | None = None,
    ) -> IsolationForestDetector:
        """Fit Isolation Forest exclusively on normal benign traffic.

        Args:
            X: Training feature matrix (float32, 2D).
            feature_names: Optional column names if X is a numpy array.

        Returns:
            Self (fitted detector).
        """
        start_time = time.perf_counter()

        if isinstance(X, pd.DataFrame):
            self.feature_names = list(X.columns)
            X_arr = X.to_numpy(dtype=np.float32)
        else:
            X_arr = np.asarray(X, dtype=np.float32)
            if feature_names is not None:
                self.feature_names = list(feature_names)
            else:
                self.feature_names = [f"feature_{i}" for i in range(X_arr.shape[1])]

        if np.isnan(X_arr).any() or np.isinf(X_arr).any():
            raise ValueError("Input feature matrix contains NaN or Inf values!")

        self.model.fit(X_arr)
        self.train_duration_seconds = time.perf_counter() - start_time
        self.train_sample_count = X_arr.shape[0]
        self.is_fitted = True
        return self

    def score_samples(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Compute anomaly scores for input samples.

        Returns:
            1D numpy array of float32 anomaly scores where HIGHER values
            indicate greater anomaly / deviation from normal training behaviour.
        """
        if not self.is_fitted:
            raise RuntimeError("Cannot score samples: IsolationForestDetector is not fitted!")

        if isinstance(X, pd.DataFrame):
            X_arr = X[self.feature_names].to_numpy(dtype=np.float32)
        else:
            X_arr = np.asarray(X, dtype=np.float32)

        if np.isnan(X_arr).any() or np.isinf(X_arr).any():
            raise ValueError("Input feature matrix contains NaN or Inf values!")

        # Invert scikit-learn score_samples so higher score = more anomalous
        raw_scores = self.model.score_samples(X_arr)
        anomaly_scores: np.ndarray = (-raw_scores).astype(np.float32)
        return anomaly_scores

    def predict(self, X: pd.DataFrame | np.ndarray, threshold: float) -> np.ndarray:
        """Predict binary anomaly labels given a calibrated decision threshold.

        Args:
            X: Feature matrix.
            threshold: Calibrated anomaly threshold. Scores >= threshold are flagged as anomalous (1).

        Returns:
            Binary numpy array of int32 (1 = Anomaly, 0 = Normal).
        """
        scores = self.score_samples(X)
        return (scores >= threshold).astype(np.int32)

    def save(self, filepath: Path | str) -> str:
        """Serialize fitted model bundle and return SHA-256 checksum."""
        if not self.is_fitted:
            raise RuntimeError("Cannot save unfitted model!")

        save_path = Path(filepath).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)

        bundle: dict[str, Any] = {
            "model": self.model,
            "config": self.config.to_dict(),
            "feature_names": self.feature_names,
            "train_duration_seconds": self.train_duration_seconds,
            "train_sample_count": self.train_sample_count,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        joblib.dump(bundle, save_path, compress=3)

        # Compute file checksum
        hasher = hashlib.sha256()
        with open(save_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def load(cls, filepath: Path | str) -> IsolationForestDetector:
        """Load serialized model bundle."""
        load_path = Path(filepath).resolve()
        if not load_path.exists():
            raise FileNotFoundError(f"Model file not found: {load_path}")

        bundle: dict[str, Any] = joblib.load(load_path)

        cfg_dict = bundle["config"]
        config = IsolationForestConfig(**cfg_dict)
        detector = cls(config=config)
        detector.model = bundle["model"]
        detector.feature_names = bundle["feature_names"]
        detector.train_duration_seconds = bundle.get("train_duration_seconds", 0.0)
        detector.train_sample_count = bundle.get("train_sample_count", 0)
        detector.is_fitted = True
        return detector
