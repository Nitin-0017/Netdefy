"""NETDEFY — Behavioral & Temporal Engine Integration Tests (Phase 5).

Verifies end-to-end integration of Phase 5 Behavioral Intelligence with Phase 4D Hybrid Pipeline,
graceful fallback on benchmark data lacking 5-tuple context, and simulated streaming analysis.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from netdefy.behaviour.feature_builder import BehavioralFeatureBuilder
from netdefy.behaviour.pipeline_adapter import BehavioralHybridPipeline
from netdefy.behaviour.schema import (
    BehavioralDecisionCategory,
    EnhancedHybridPrediction,
    NetworkEvent,
)
from netdefy.hybrid.inference_pipeline import HybridInferencePipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def behavioural_pipeline() -> BehavioralHybridPipeline:
    """Fixture providing an initialized BehavioralHybridPipeline."""
    config_path = PROJECT_ROOT / "configs" / "hybrid.yaml"
    hybrid_pipe = HybridInferencePipeline.from_config(config_path)
    scaler_path = PROJECT_ROOT / "artifacts" / "preprocessing" / "standard_scaler.joblib"
    builder = BehavioralFeatureBuilder(
        scaler_path=scaler_path, feature_names=hybrid_pipe.feature_names
    )
    return BehavioralHybridPipeline(hybrid_pipeline=hybrid_pipe, feature_builder=builder)


def test_behavioural_pipeline_graceful_fallback_on_benchmark_row(
    behavioural_pipeline: BehavioralHybridPipeline,
) -> None:
    """Verify that benchmark data lacking 5-tuple timestamp/IP gracefully degrades without error."""
    val_path = PROJECT_ROOT / "data" / "benchmark" / "v1" / "validation.parquet"
    if not val_path.exists():
        pytest.skip("Benchmark validation.parquet not available for integration test.")

    df = pd.read_parquet(val_path, columns=behavioural_pipeline.feature_names).head(5)

    # Predict single flow without temporal event
    pred: EnhancedHybridPrediction = behavioural_pipeline.predict_flow(
        flow=df.iloc[0], flow_id="bench_0", is_scaled=True
    )

    assert pred.flow_id == "bench_0"
    assert pred.final_decision in (
        "NORMAL",
        "SUSPICIOUS_KNOWN",
        "SUSPICIOUS_UNKNOWN",
        "REVIEW_REQUIRED",
    )
    # Since 5-tuple is absent, multi_flow is None and category is INSUFFICIENT_CONTEXT (or SCANNING if RST signature)
    assert pred.behavioral_evidence.multi_flow is None
    assert pred.behavioral_decision in (
        BehavioralDecisionCategory.INSUFFICIENT_CONTEXT,
        BehavioralDecisionCategory.SCANNING_BEHAVIOUR,
        BehavioralDecisionCategory.NORMAL,
        BehavioralDecisionCategory.SUSPICIOUS_BEHAVIOUR,
    )
    # Tier A metrics are properly computed
    intra = pred.behavioral_evidence.intra_flow
    assert intra.directional_packet_ratio >= 0.0
    assert intra.directional_byte_ratio >= 0.0
    assert not np.isnan(intra.burstiness_index)
    assert not np.isnan(intra.window_disparity)


def test_behavioural_pipeline_with_streaming_temporal_events(
    behavioural_pipeline: BehavioralHybridPipeline,
) -> None:
    """Verify sequential streaming multi-flow context accumulation and scan elevation."""
    feature_names = behavioural_pipeline.feature_names
    flow_zero = dict.fromkeys(feature_names, 0.0)

    # Simulate 10 sequential events from a scanning host targeting different destination ports
    events = [
        NetworkEvent(
            timestamp=1000.0 + i,
            source_ip="192.168.1.100",
            destination_ip="10.0.0.1",
            destination_port=1024 + i,
            features={
                "Total Fwd Packets": 1.0,
                "Total Backward Packets": 1.0,
                "Total Length of Bwd Packets": 6.0,
            },
        )
        for i in range(12)
    ]

    preds: list[EnhancedHybridPrediction] = []
    for i, ev in enumerate(events):
        p = behavioural_pipeline.predict_flow(flow=flow_zero, event=ev, flow_id=f"seq_{i}")
        preds.append(p)

    final_pred = preds[-1]
    # By event 12, multi_flow context is active
    assert final_pred.behavioral_evidence.multi_flow is not None
    assert final_pred.behavioral_evidence.multi_flow.connection_count == 12
    # Vertical scan detected across ports
    assert final_pred.behavioral_decision == BehavioralDecisionCategory.SCANNING_BEHAVIOUR
    assert final_pred.final_decision == "SUSPICIOUS_KNOWN"
    assert "Scanning" in final_pred.decision_reason or "PortScan" in final_pred.decision_reason
