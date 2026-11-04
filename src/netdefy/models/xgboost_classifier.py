"""NETDEFY — Supervised Attack Classification Engine using XGBoost.

Implements a configurable, leakage-safe XGBoost multiclass classifier for identifying
known network attack categories and rejecting low-confidence / unknown attack flows.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import xgboost as xgb

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class XGBoostClassifierConfig:
    """Hyperparameter and architectural configuration for XGBoostAttackClassifier."""

    n_estimators: int = 150
    max_depth: int = 6
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_weight: float = 1.0
    gamma: float = 0.1
    reg_alpha: float = 0.01
    reg_lambda: float = 1.0
    objective: str = "multi:softprob"
    eval_metric: str = "mlogloss"
    tree_method: str = "hist"
    random_state: int = 42
    n_jobs: int = 4
    early_stopping_rounds: int | None = 15
    confidence_threshold: float = 0.50

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> XGBoostClassifierConfig:
        return cls(
            n_estimators=int(data.get("n_estimators", 150)),
            max_depth=int(data.get("max_depth", 6)),
            learning_rate=float(data.get("learning_rate", 0.05)),
            subsample=float(data.get("subsample", 0.8)),
            colsample_bytree=float(data.get("colsample_bytree", 0.8)),
            min_child_weight=float(data.get("min_child_weight", 1.0)),
            gamma=float(data.get("gamma", 0.1)),
            reg_alpha=float(data.get("reg_alpha", 0.01)),
            reg_lambda=float(data.get("reg_lambda", 1.0)),
            objective=str(data.get("objective", "multi:softprob")),
            eval_metric=str(data.get("eval_metric", "mlogloss")),
            tree_method=str(data.get("tree_method", "hist")),
            random_state=int(data.get("random_state", 42)),
            n_jobs=int(data.get("n_jobs", -1)),
            early_stopping_rounds=(
                int(data["early_stopping_rounds"])
                if data.get("early_stopping_rounds") is not None
                else None
            ),
            confidence_threshold=float(data.get("confidence_threshold", 0.50)),
        )


class XGBoostAttackClassifier:
    """Production and evaluation wrapper for XGBoost multiclass network attack classification."""

    def __init__(
        self,
        config: XGBoostClassifierConfig | None = None,
        class_mapping: dict[int, str] | None = None,
    ) -> None:
        self.config = config or XGBoostClassifierConfig()
        self.class_mapping = class_mapping or {}
        self.inverse_class_mapping: dict[str, int] = {v: k for k, v in self.class_mapping.items()}
        self.feature_names: list[str] = []
        self.is_fitted: bool = False
        self.train_duration_seconds: float = 0.0
        self.train_sample_count: int = 0
        self.best_iteration: int | None = None

        self.model: xgb.XGBClassifier = xgb.XGBClassifier(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            learning_rate=self.config.learning_rate,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            min_child_weight=self.config.min_child_weight,
            gamma=self.config.gamma,
            reg_alpha=self.config.reg_alpha,
            reg_lambda=self.config.reg_lambda,
            objective=self.config.objective,
            eval_metric=self.config.eval_metric,
            tree_method=self.config.tree_method,
            random_state=self.config.random_state,
            n_jobs=self.config.n_jobs,
        )

    def fit(
        self,
        X_train: pd.DataFrame | np.ndarray,
        y_train: pd.Series | np.ndarray,
        X_val: pd.DataFrame | np.ndarray | None = None,
        y_val: pd.Series | np.ndarray | None = None,
        feature_names: list[str] | None = None,
        sample_weight: np.ndarray | None = None,
    ) -> XGBoostAttackClassifier:
        """Fit multiclass classifier with optional validation early stopping.

        Args:
            X_train: Training feature matrix.
            y_train: Training labels (strings or integer class indices).
            X_val: Optional validation feature matrix.
            y_val: Optional validation labels.
            feature_names: Optional feature names if X is numpy array.
            sample_weight: Optional per-sample weighting array.
        """
        start_time = time.perf_counter()

        # Handle features
        if isinstance(X_train, pd.DataFrame):
            self.feature_names = list(X_train.columns)
            X_arr = np.ascontiguousarray(X_train.to_numpy(dtype=np.float32))
        else:
            X_arr = np.ascontiguousarray(X_train, dtype=np.float32)
            if feature_names is not None:
                self.feature_names = list(feature_names)
            else:
                self.feature_names = [f"feature_{i}" for i in range(X_arr.shape[1])]

        if np.isnan(X_arr).any() or np.isinf(X_arr).any():
            raise ValueError("Training feature matrix contains NaN or Inf values!")

        # Handle label mapping
        if not self.class_mapping:
            unique_labels = sorted(pd.Series(y_train).unique())
            self.class_mapping = {i: str(lbl) for i, lbl in enumerate(unique_labels)}
            self.inverse_class_mapping = {v: k for k, v in self.class_mapping.items()}

        y_train_arr = np.ascontiguousarray(
            [self.inverse_class_mapping[str(lbl)] for lbl in pd.Series(y_train)],
            dtype=np.int32,
        )

        weights_arr: np.ndarray | None = None
        if sample_weight is not None:
            weights_arr = np.ascontiguousarray(sample_weight, dtype=np.float32)

        eval_set: list[tuple[np.ndarray, np.ndarray]] | None = None
        if X_val is not None and y_val is not None:
            if isinstance(X_val, pd.DataFrame):
                X_val_arr = np.ascontiguousarray(
                    X_val[self.feature_names].to_numpy(dtype=np.float32)
                )
            else:
                X_val_arr = np.ascontiguousarray(X_val, dtype=np.float32)

            y_val_arr = np.ascontiguousarray(
                [self.inverse_class_mapping[str(lbl)] for lbl in pd.Series(y_val)],
                dtype=np.int32,
            )
            eval_set = [(X_val_arr, y_val_arr)]
            if self.config.early_stopping_rounds is not None:
                self.model.set_params(early_stopping_rounds=self.config.early_stopping_rounds)
        else:
            self.model.set_params(early_stopping_rounds=None)

        if self.config.objective.startswith("multi:"):
            self.model.set_params(num_class=len(self.class_mapping))

        self.model.fit(
            X_arr,
            y_train_arr,
            sample_weight=weights_arr,
            eval_set=eval_set,
            verbose=False,
        )

        self.train_duration_seconds = time.perf_counter() - start_time
        self.train_sample_count = len(X_arr)
        self.best_iteration = getattr(self.model, "best_iteration", None)
        self.is_fitted = True

        return self

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Compute class probabilities for input flows.

        Returns:
            2D numpy array [N, num_classes] of float32 probabilities.
        """
        if not self.is_fitted:
            raise RuntimeError("Cannot predict: XGBoostAttackClassifier is not fitted!")

        if isinstance(X, pd.DataFrame):
            X_arr = X[self.feature_names].to_numpy(dtype=np.float32)
        else:
            X_arr = np.asarray(X, dtype=np.float32)

        if np.isnan(X_arr).any() or np.isinf(X_arr).any():
            raise ValueError("Input feature matrix contains NaN or Inf values!")

        probs: np.ndarray = self.model.predict_proba(X_arr).astype(np.float32)
        return probs

    def predict(
        self,
        X: pd.DataFrame | np.ndarray,
        reject_threshold: float | None = None,
        unknown_label: str = "UNKNOWN",
    ) -> np.ndarray:
        """Predict attack category labels with optional confidence-based rejection.

        Args:
            X: Input feature matrix.
            reject_threshold: If provided, flows with max class probability < threshold
                             are marked as `unknown_label`.
            unknown_label: Label string assigned to rejected low-confidence predictions.

        Returns:
            1D numpy array of string predicted labels.
        """
        probs = self.predict_proba(X)
        pred_indices = np.argmax(probs, axis=1)
        max_probs = np.max(probs, axis=1)

        threshold = (
            reject_threshold if reject_threshold is not None else self.config.confidence_threshold
        )

        preds: list[str] = []
        for idx, conf in zip(pred_indices, max_probs, strict=True):
            if threshold > 0.0 and conf < threshold:
                preds.append(unknown_label)
            else:
                preds.append(self.class_mapping[idx])

        return np.asarray(preds, dtype=object)

    def get_feature_importances(
        self,
        importance_type: Literal["gain", "weight", "cover", "total_gain", "total_cover"] = "gain",
    ) -> dict[str, float]:
        """Extract sorted feature importance values."""
        if not self.is_fitted:
            raise RuntimeError("Cannot extract importances: model is not fitted!")

        booster = self.model.get_booster()
        score_dict = booster.get_score(importance_type=importance_type)

        importances: dict[str, float] = {}
        for i, fname in enumerate(self.feature_names):
            key = f"f{i}"
            raw_val = score_dict.get(key, 0.0)
            score = float(raw_val[0]) if isinstance(raw_val, list) else float(raw_val)
            importances[fname] = score

        # Sort descending
        return dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))

    def save(self, filepath: Path | str) -> str:
        """Save model bundle and return SHA-256 checksum."""
        if not self.is_fitted:
            raise RuntimeError("Cannot save unfitted model!")

        save_path = Path(filepath).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)

        bundle: dict[str, Any] = {
            "config": self.config.to_dict(),
            "class_mapping": {str(k): v for k, v in self.class_mapping.items()},
            "feature_names": self.feature_names,
            "train_duration_seconds": self.train_duration_seconds,
            "train_sample_count": self.train_sample_count,
            "best_iteration": self.best_iteration,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Save metadata bundle
        metadata_path = save_path.with_suffix(".json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2)

        # Save native XGBoost booster
        model_native_path = save_path.parent / "model.ubj"
        self.model.save_model(model_native_path)

        # Compute file checksum
        hasher = hashlib.sha256()
        with open(model_native_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def load(cls, filepath: Path | str) -> XGBoostAttackClassifier:
        """Load serialized model bundle."""
        save_path = Path(filepath).resolve()
        metadata_path = save_path.with_suffix(".json")
        model_native_path = save_path.parent / "model.ubj"

        if not metadata_path.exists() or not model_native_path.exists():
            raise FileNotFoundError(f"Classifier files missing at: {save_path.parent}")

        with open(metadata_path, encoding="utf-8") as f:
            bundle = json.load(f)

        config = XGBoostClassifierConfig.from_dict(bundle["config"])
        class_mapping = {int(k): v for k, v in bundle["class_mapping"].items()}

        classifier = cls(config=config, class_mapping=class_mapping)
        classifier.feature_names = bundle["feature_names"]
        classifier.train_duration_seconds = bundle.get("train_duration_seconds", 0.0)
        classifier.train_sample_count = bundle.get("train_sample_count", 0)
        classifier.best_iteration = bundle.get("best_iteration")

        # Load native booster
        classifier.model.load_model(model_native_path)
        classifier.is_fitted = True
        return classifier
