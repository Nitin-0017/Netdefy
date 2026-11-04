"""NETDEFY — Autoencoder Evaluation and Forensic Analysis Engine.

Coordinates full test holdout scoring, ambiguity disaggregation,
per-attack detection recall, latency benchmarking, and error analysis.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from netdefy.evaluation.error_analysis import (
    analyze_ambiguity_impact,
    analyze_false_negatives,
    analyze_false_positives,
)
from netdefy.evaluation.metrics import AnomalyEvaluationReport, evaluate_anomaly_detector
from netdefy.models.autoencoder import AutoencoderDetector

logger = logging.getLogger(__name__)


@dataclass
class AutoencoderEvaluationBundle:
    """Complete evaluation results across all test protocols."""

    full_report: AnomalyEvaluationReport
    disambiguated_report: AnomalyEvaluationReport
    ambiguity_comparison: dict[str, Any]
    false_positive_analysis: dict[str, Any]
    false_negative_analysis: dict[str, Any]
    latency_ms_per_flow: float
    throughput_flows_per_second: float
    total_test_samples: int
    unambiguous_samples: int
    ambiguous_samples: int

    def to_test_metrics_dict(self) -> dict[str, Any]:
        """Format metrics for test_metrics.json."""
        return {
            "model_type": "deep_autoencoder",
            "full_test_report": self.full_report.to_dict(),
            "disambiguated_test_report": self.disambiguated_report.to_dict(),
            "latency_ms_per_flow": round(self.latency_ms_per_flow, 4),
            "throughput_flows_per_second": round(self.throughput_flows_per_second, 1),
            "sample_counts": {
                "total": self.total_test_samples,
                "unambiguous": self.unambiguous_samples,
                "ambiguous": self.ambiguous_samples,
            },
        }

    def to_error_analysis_dict(
        self,
        default_th_key: str,
        default_th_val: float,
    ) -> dict[str, Any]:
        """Format error analysis for error_analysis.json."""
        return {
            "evaluation_threshold": {
                "key": default_th_key,
                "value": default_th_val,
            },
            "false_positive_analysis": self.false_positive_analysis,
            "false_negative_analysis": self.false_negative_analysis,
            "ambiguity_comparison_by_threshold": self.ambiguity_comparison,
        }


class AutoencoderEvaluator:
    """Orchestrates comprehensive multi-protocol evaluation for AutoencoderDetector."""

    def __init__(
        self,
        detector: AutoencoderDetector,
        feature_columns: list[str],
        label_column: str = "Label",
        benign_label: str = "BENIGN",
    ) -> None:
        self.detector = detector
        self.feature_columns = feature_columns
        self.label_column = label_column
        self.benign_label = benign_label

    def evaluate_test_holdout(
        self,
        test_df: pd.DataFrame,
        thresholds: dict[str, float],
        is_ambiguous_flags: list[bool],
        default_threshold_key: str = "p99.0",
        batch_size: int = 1024,
    ) -> AutoencoderEvaluationBundle:
        """Execute full evaluation protocol on the chronological test holdout."""
        logger.info("Scoring %d final test flows with Autoencoder...", len(test_df))
        test_features = test_df[self.feature_columns].to_numpy(dtype=np.float32)

        start_time = time.perf_counter()
        test_scores = self.detector.score_samples(test_features, batch_size=batch_size)
        score_duration = time.perf_counter() - start_time

        latency_ms_per_flow = (score_duration / len(test_df)) * 1000.0
        throughput_flows_sec = len(test_df) / score_duration

        logger.info(
            "Scored %d test flows in %.3f s (%.4f ms/flow, %.1f flows/s)",
            len(test_df),
            score_duration,
            latency_ms_per_flow,
            throughput_flows_sec,
        )

        # 1. Full Protocol (all flows)
        full_report = evaluate_anomaly_detector(
            y_true_labels=test_df[self.label_column],
            anomaly_scores=test_scores,
            thresholds=thresholds,
            dataset_name="test_v1_full",
            benign_label=self.benign_label,
        )

        # 2. Ambiguity Breakdown
        is_ambig_arr = np.asarray(is_ambiguous_flags, dtype=bool)
        unambig_mask = ~is_ambig_arr

        ambiguity_comparison: dict[str, Any] = {}
        for th_key, th_val in thresholds.items():
            ambiguity_comparison[th_key] = analyze_ambiguity_impact(
                df=test_df,
                anomaly_scores=test_scores,
                threshold=th_val,
                is_ambiguous_flags=is_ambiguous_flags,
                label_column=self.label_column,
                benign_label=self.benign_label,
            )

        # 3. Disambiguated Protocol (unambiguous only)
        disambiguated_report = evaluate_anomaly_detector(
            y_true_labels=test_df.iloc[unambig_mask][self.label_column],
            anomaly_scores=test_scores[unambig_mask],
            thresholds=thresholds,
            dataset_name="test_v1_disambiguated",
            benign_label=self.benign_label,
        )

        # 4. Error Analysis at default threshold
        default_th_val = thresholds[default_threshold_key]
        fp_analysis = analyze_false_positives(
            df=test_df,
            anomaly_scores=test_scores,
            threshold=default_th_val,
            feature_columns=self.feature_columns,
            label_column=self.label_column,
            benign_label=self.benign_label,
            top_k=10,
        )

        fn_analysis = analyze_false_negatives(
            df=test_df,
            anomaly_scores=test_scores,
            threshold=default_th_val,
            label_column=self.label_column,
            benign_label=self.benign_label,
        )

        return AutoencoderEvaluationBundle(
            full_report=full_report,
            disambiguated_report=disambiguated_report,
            ambiguity_comparison=ambiguity_comparison,
            false_positive_analysis=fp_analysis,
            false_negative_analysis=fn_analysis,
            latency_ms_per_flow=latency_ms_per_flow,
            throughput_flows_per_second=throughput_flows_sec,
            total_test_samples=len(test_df),
            unambiguous_samples=int(unambig_mask.sum()),
            ambiguous_samples=int(is_ambig_arr.sum()),
        )
