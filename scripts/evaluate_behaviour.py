"""NETDEFY — Phase 5 Behavioral Engine Evaluation Script.

Evaluates intra-flow Tier A behavioral metrics, PortScan closed-port RST signature detection,
inference latency overhead, and decision alignment on the benchmark test holdout dataset.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from netdefy.behaviour.feature_builder import BehavioralFeatureBuilder
from netdefy.behaviour.pipeline_adapter import BehavioralHybridPipeline
from netdefy.hybrid.inference_pipeline import HybridInferencePipeline
from netdefy.utils.logging import setup_logging

logger = logging.getLogger(__name__)


def run_evaluation() -> dict[str, Any]:
    """Execute scientific evaluation of Phase 5 behavioral engine."""
    setup_logging(level=logging.INFO)
    logger.info("Starting NETDEFY Phase 5 Behavioral Intelligence Evaluation...")

    root_dir = Path(__file__).resolve().parent.parent
    config_path = root_dir / "configs" / "hybrid.yaml"
    scaler_path = root_dir / "artifacts" / "preprocessing" / "standard_scaler.joblib"
    test_path = root_dir / "data" / "benchmark" / "v1" / "test.parquet"

    if not test_path.exists():
        logger.error("Benchmark test partition not found at %s", test_path)
        sys.exit(1)

    # 1. Load pipeline
    logger.info("Initializing Hybrid and Behavioral pipelines...")
    hybrid_pipe = HybridInferencePipeline.from_config(config_path)
    feature_builder = BehavioralFeatureBuilder(
        scaler_path=scaler_path, feature_names=hybrid_pipe.feature_names
    )
    pipe = BehavioralHybridPipeline(hybrid_pipeline=hybrid_pipe, feature_builder=feature_builder)

    # 2. Load test set
    logger.info("Loading test dataset from %s...", test_path)
    df_test = pd.read_parquet(test_path)
    total_samples = len(df_test)
    y_true_class = df_test["Label"].to_numpy()

    logger.info("Total test flows: %d", total_samples)

    # 3. Evaluate Tier A Intra-Flow Behavioral Metrics across test set
    logger.info("Extracting intra-flow behavioral features across test set...")
    t0 = time.perf_counter()
    intra_behaviors = [
        feature_builder.compute_intra_flow(row, is_scaled=True)
        for _, row in df_test[pipe.feature_names].iterrows()
    ]
    t_intra_elapsed = time.perf_counter() - t0
    intra_latency_us = (t_intra_elapsed / total_samples) * 1e6

    logger.info(
        "Tier A extraction complete in %.2fs (%.1f µs/flow)",
        t_intra_elapsed,
        intra_latency_us,
    )

    # 4. PortScan Closed-Port Signature Performance
    portscan_mask = y_true_class == "PortScan"
    benign_mask = y_true_class == "BENIGN"
    total_portscan = int(np.sum(portscan_mask))
    total_benign = int(np.sum(benign_mask))

    scan_sig_flags = np.array([b.is_scan_signature for b in intra_behaviors])

    portscan_detected = int(np.sum(scan_sig_flags & portscan_mask))
    benign_false_positives = int(np.sum(scan_sig_flags & benign_mask))

    portscan_recall = float(portscan_detected / total_portscan) if total_portscan > 0 else 0.0
    benign_fpr = float(benign_false_positives / total_benign) if total_benign > 0 else 0.0

    logger.info(
        "PortScan Closed-Port RST Signature Analysis: Detected %d / %d (Recall: %.4f | FPR: %.4f)",
        portscan_detected,
        total_portscan,
        portscan_recall,
        benign_fpr,
    )

    # 5. Measure End-to-End Inference Latency on a Sample
    sample_size = min(2000, total_samples)
    df_sample = df_test.iloc[:sample_size]

    logger.info("Benchmarking end-to-end inference on %d flows...", sample_size)
    t0_sample = time.perf_counter()
    preds = pipe.predict_batch(df_sample[pipe.feature_names], is_scaled=True)
    t_sample_elapsed = time.perf_counter() - t0_sample
    e2e_latency_us = (t_sample_elapsed / sample_size) * 1e6

    # 6. Final Decision Aggregations
    final_decisions = [p.final_decision for p in preds]
    decision_counts = pd.Series(final_decisions).value_counts().to_dict()

    metrics = {
        "dataset": "data/benchmark/v1/test.parquet",
        "total_test_flows": total_samples,
        "sample_evaluated_flows": sample_size,
        "tier_a_extraction_latency_us_per_flow": round(intra_latency_us, 2),
        "end_to_end_latency_us_per_flow": round(e2e_latency_us, 2),
        "portscan_evaluation": {
            "total_portscan_flows": total_portscan,
            "detected_by_rst_signature": portscan_detected,
            "portscan_recall": round(portscan_recall, 4),
            "benign_flows": total_benign,
            "benign_false_positives": benign_false_positives,
            "benign_false_positive_rate": round(benign_fpr, 4),
        },
        "sample_decision_distribution": decision_counts,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # 7. Save metrics artifact
    artifact_dir = root_dir / "artifacts" / "models" / "behaviour" / "v1"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    out_file = artifact_dir / "evaluation_metrics.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    logger.info("Saved Phase 5 evaluation metrics to %s", out_file)
    return metrics


if __name__ == "__main__":
    results = run_evaluation()
    print(json.dumps(results, indent=2))
