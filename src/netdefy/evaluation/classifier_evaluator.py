"""NETDEFY — Supervised Attack Classifier Evaluation Coordinator.

Coordinates full validation evaluation, test holdout evaluation, open-set unknown attack
rejection, ambiguity partitioning, and latency/throughput benchmarking.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from netdefy.evaluation.classification_error_analysis import (
    analyze_ambiguity_classification_impact,
    analyze_confidence_rejection_curve,
    analyze_confused_classes,
)
from netdefy.evaluation.classification_metrics import (
    MulticlassClassificationReport,
    evaluate_multiclass_classifier,
)
from netdefy.models.xgboost_classifier import XGBoostAttackClassifier

logger = logging.getLogger(__name__)


@dataclass
class ClassifierEvaluationBundle:
    """Complete evaluation bundle across validation, test, and ambiguity protocols."""

    full_test_report_closed: MulticlassClassificationReport
    full_test_report_open: MulticlassClassificationReport
    disambiguated_test_report: MulticlassClassificationReport
    top_confused_pairs: list[dict[str, Any]]
    confidence_curve: list[dict[str, Any]]
    ambiguity_analysis: dict[str, Any]
    latency_ms_per_flow: float
    throughput_flows_per_second: float

    def to_test_metrics_dict(self) -> dict[str, Any]:
        return {
            "model_type": "xgboost_classifier",
            "full_test_report_closed_set": self.full_test_report_closed.to_dict(),
            "full_test_report_open_set": self.full_test_report_open.to_dict(),
            "disambiguated_test_report": self.disambiguated_test_report.to_dict(),
            "latency_ms_per_flow": round(self.latency_ms_per_flow, 4),
            "throughput_flows_per_second": round(self.throughput_flows_per_second, 1),
        }

    def to_error_analysis_dict(self) -> dict[str, Any]:
        return {
            "top_confused_class_pairs": self.top_confused_pairs,
            "confidence_rejection_curve": self.confidence_curve,
            "ambiguity_classification_impact": self.ambiguity_analysis,
        }


class ClassifierEvaluator:
    """High-level evaluator for XGBoostAttackClassifier."""

    def __init__(
        self,
        classifier: XGBoostAttackClassifier,
        feature_columns: list[str],
        label_column: str = "Label",
    ) -> None:
        self.classifier = classifier
        self.feature_columns = feature_columns
        self.label_column = label_column
        self.known_classes = [
            self.classifier.class_mapping[i] for i in sorted(self.classifier.class_mapping.keys())
        ]

    def evaluate_validation(
        self,
        val_df: pd.DataFrame,
    ) -> tuple[MulticlassClassificationReport, list[dict[str, Any]]]:
        """Evaluate classifier on validation partition where all classes are known."""
        val_features = val_df[self.feature_columns].to_numpy(dtype=np.float32)
        val_true = val_df[self.label_column].to_numpy()

        val_probs = self.classifier.predict_proba(val_features)
        val_preds_closed = self.classifier.predict(val_features, reject_threshold=0.0)

        report = evaluate_multiclass_classifier(
            y_true=val_true,
            y_pred=val_preds_closed,
            y_prob=val_probs,
            classes=self.known_classes,
            dataset_name="validation_v1",
        )

        conf_curve = analyze_confidence_rejection_curve(
            y_true=val_true,
            y_prob=val_probs,
            classes=self.known_classes,
        )

        return report, conf_curve

    def evaluate_test_holdout(
        self,
        test_df: pd.DataFrame,
        is_ambiguous_flags: list[bool],
        reject_threshold: float = 0.50,
    ) -> ClassifierEvaluationBundle:
        """Evaluate classifier on holdout test partition containing unseen attack families."""
        test_features = test_df[self.feature_columns].to_numpy(dtype=np.float32)
        test_true = test_df[self.label_column].to_numpy()

        start_time = time.perf_counter()
        test_probs = self.classifier.predict_proba(test_features)
        score_duration = time.perf_counter() - start_time

        latency_ms_per_flow = (score_duration / len(test_df)) * 1000.0
        throughput_flows_sec = len(test_df) / score_duration

        # 1. Closed-set prediction (forced assignment to 1 of 8 known classes)
        test_preds_closed = self.classifier.predict(test_features, reject_threshold=0.0)
        report_closed = evaluate_multiclass_classifier(
            y_true=test_true,
            y_pred=test_preds_closed,
            classes=self.known_classes,
            dataset_name="test_v1_closed_set",
        )

        # 2. Open-set prediction (rejects max_prob < reject_threshold as UNKNOWN)
        test_preds_open = self.classifier.predict(
            test_features, reject_threshold=reject_threshold, unknown_label="UNKNOWN"
        )
        report_open = evaluate_multiclass_classifier(
            y_true=test_true,
            y_pred=test_preds_open,
            classes=self.known_classes,
            dataset_name="test_v1_open_set",
            unknown_label="UNKNOWN",
        )

        # 3. Disambiguated Test (unambiguous rows only)
        unambig_mask = ~np.asarray(is_ambiguous_flags, dtype=bool)
        test_df_unambig = test_df.iloc[unambig_mask]
        preds_unambig = test_preds_open[unambig_mask]
        report_unambig = evaluate_multiclass_classifier(
            y_true=test_df_unambig[self.label_column],
            y_pred=preds_unambig,
            classes=self.known_classes,
            dataset_name="test_v1_disambiguated",
            unknown_label="UNKNOWN",
        )

        # 4. Error Analysis
        top_confused = analyze_confused_classes(
            y_true=test_true,
            y_pred=test_preds_open,
            top_k=10,
        )

        conf_curve = analyze_confidence_rejection_curve(
            y_true=test_true,
            y_prob=test_probs,
            classes=self.known_classes,
        )

        ambig_analysis = analyze_ambiguity_classification_impact(
            df=test_df,
            y_pred=test_preds_open,
            is_ambiguous_flags=is_ambiguous_flags,
            label_column=self.label_column,
        )

        return ClassifierEvaluationBundle(
            full_test_report_closed=report_closed,
            full_test_report_open=report_open,
            disambiguated_test_report=report_unambig,
            top_confused_pairs=top_confused,
            confidence_curve=conf_curve,
            ambiguity_analysis=ambig_analysis,
            latency_ms_per_flow=latency_ms_per_flow,
            throughput_flows_per_second=throughput_flows_sec,
        )
