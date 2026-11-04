"""NETDEFY — Supervised Attack Classifier Training Engine.

Coordinates XGBoost training, class imbalance re-weighting, validation early stopping,
and feature importance extraction.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.utils.class_weight import compute_sample_weight

from netdefy.models.xgboost_classifier import (
    XGBoostAttackClassifier,
    XGBoostClassifierConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class ClassifierTrainingResult:
    """Summary of classifier training and optimization run."""

    classifier: XGBoostAttackClassifier
    train_duration_seconds: float
    train_sample_count: int
    val_sample_count: int
    best_iteration: int | None
    class_mapping: dict[int, str]
    feature_importances: dict[str, float]
    use_class_weights: bool

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "status": "SUCCESS",
            "model_type": "xgboost_classifier",
            "train_sample_count": self.train_sample_count,
            "val_sample_count": self.val_sample_count,
            "train_duration_seconds": round(self.train_duration_seconds, 2),
            "best_iteration": self.best_iteration,
            "class_count": len(self.class_mapping),
            "class_mapping": self.class_mapping,
            "use_class_weights": self.use_class_weights,
            "top_10_features_gain": dict(list(self.feature_importances.items())[:10]),
        }


class ClassifierTrainer:
    """Trains and optimizes XGBoostAttackClassifier on network traffic flows."""

    def __init__(
        self,
        config: XGBoostClassifierConfig | None = None,
        use_class_weights: bool = True,
    ) -> None:
        self.config = config or XGBoostClassifierConfig()
        self.use_class_weights = use_class_weights

    def train(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        feature_columns: list[str],
        label_column: str = "Label",
    ) -> ClassifierTrainingResult:
        """Fit classifier on training partition with optional sample weighting and validation early stopping."""
        start_time = time.perf_counter()

        X_train = train_df[feature_columns].to_numpy(dtype=np.float32)
        y_train = train_df[label_column].to_numpy()

        X_val = val_df[feature_columns].to_numpy(dtype=np.float32)
        y_val = val_df[label_column].to_numpy()

        # Handle class weighting if requested
        sample_weight: np.ndarray | None = None
        if self.use_class_weights:
            logger.info("Computing balanced class weights for training partition...")
            sample_weight = compute_sample_weight("balanced", y_train)

        # Build class mapping
        unique_classes = sorted(np.unique(y_train))
        class_mapping = {i: str(lbl) for i, lbl in enumerate(unique_classes)}
        logger.info("Established %d training classes: %s", len(class_mapping), class_mapping)

        classifier = XGBoostAttackClassifier(
            config=self.config,
            class_mapping=class_mapping,
        )

        logger.info(
            "Fitting XGBoost (%d estimators, max_depth=%d, lr=%.3f, class_weights=%s)...",
            self.config.n_estimators,
            self.config.max_depth,
            self.config.learning_rate,
            self.use_class_weights,
        )

        classifier.fit(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            feature_names=feature_columns,
            sample_weight=sample_weight,
        )

        duration = time.perf_counter() - start_time
        importances = classifier.get_feature_importances(importance_type="gain")

        logger.info(
            "Classifier training finished in %.2f s (best iteration: %s)",
            duration,
            classifier.best_iteration,
        )

        return ClassifierTrainingResult(
            classifier=classifier,
            train_duration_seconds=duration,
            train_sample_count=len(train_df),
            val_sample_count=len(val_df),
            best_iteration=classifier.best_iteration,
            class_mapping=class_mapping,
            feature_importances=importances,
            use_class_weights=self.use_class_weights,
        )
