"""NETDEFY — Integration & Research Integrity Tests for Phase 4D Hybrid Pipeline.

Verifies end-to-end model integration, input sanitation, numerical determinism,
artifact manifest verification, and research integrity constraints.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from netdefy.hybrid.inference_pipeline import HybridInferencePipeline
from netdefy.hybrid.model_registry import ModelRegistry
from netdefy.hybrid.schemas import DecisionCategory, HybridFlowPrediction

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def hybrid_pipeline() -> HybridInferencePipeline:
    config_path = PROJECT_ROOT / "configs" / "hybrid.yaml"
    return HybridInferencePipeline.from_config(config_path)


def test_hybrid_model_loading_and_bundle_integrity() -> None:
    """Verify that all three component models load simultaneously with identical schemas."""
    if_path = PROJECT_ROOT / "artifacts" / "models" / "isolation_forest" / "v1" / "model.joblib"
    ae_path = PROJECT_ROOT / "artifacts" / "models" / "autoencoder" / "v1" / "best_model.pt"
    clf_path = PROJECT_ROOT / "artifacts" / "models" / "xgboost_classifier" / "v1" / "model.json"

    bundle = ModelRegistry.load_bundle(if_path, ae_path, clf_path, device="cpu")

    assert len(bundle.feature_names) == 76
    assert bundle.isolation_forest.is_fitted
    assert bundle.autoencoder.is_fitted
    assert bundle.classifier.is_fitted
    assert "isolation_forest" in bundle.artifact_checksums
    assert "autoencoder" in bundle.artifact_checksums
    assert "classifier_booster" in bundle.artifact_checksums


def test_single_flow_prediction_and_schema_contract(
    hybrid_pipeline: HybridInferencePipeline,
) -> None:
    """Verify single-flow inference, schema compliance, and structured evidence."""
    flow = dict.fromkeys(hybrid_pipeline.feature_names, 0.0)
    flow_id = "test_flow_001"

    prediction: HybridFlowPrediction = hybrid_pipeline.predict(flow, flow_id=flow_id)

    assert prediction.flow_id == flow_id
    assert isinstance(prediction.decision, DecisionCategory)
    assert 0.0 <= prediction.anomaly.fused_score <= 1.0
    assert 0.0 <= prediction.classifier.top_probability <= 1.0
    assert len(prediction.explanation.evidence_summary) > 0
    assert len(prediction.model_versions) == 4

    # Serialization roundtrip test
    pred_dict = prediction.to_dict()
    assert pred_dict["decision"] in [c.value for c in DecisionCategory]
    assert "anomaly" in pred_dict
    assert "classifier" in pred_dict


def test_batch_prediction_and_determinism(hybrid_pipeline: HybridInferencePipeline) -> None:
    """Verify batch inference execution and bitwise determinism across repeated passes."""
    rng = np.random.default_rng(12345)
    X_synthetic = rng.normal(loc=0.0, scale=1.0, size=(25, 76)).astype(np.float32)

    pass1 = hybrid_pipeline.predict_batch(X_synthetic, batch_size=10, include_explanations=True)
    pass2 = hybrid_pipeline.predict_batch(X_synthetic, batch_size=10, include_explanations=True)

    assert pass1.total_flows == 25
    assert pass2.total_flows == 25

    # Verify bitwise determinism for fused anomaly scores and decisions
    scores1 = [p.anomaly.fused_score for p in pass1.predictions]
    scores2 = [p.anomaly.fused_score for p in pass2.predictions]
    np.testing.assert_allclose(scores1, scores2, rtol=1e-6)

    decisions1 = [p.decision for p in pass1.predictions]
    decisions2 = [p.decision for p in pass2.predictions]
    assert decisions1 == decisions2


def test_input_validation_and_error_handling(hybrid_pipeline: HybridInferencePipeline) -> None:
    """Verify that malformed inputs, NaNs, Infs, and missing features are safely rejected."""
    # 1. Missing required features
    partial_dict = {hybrid_pipeline.feature_names[0]: 1.0}
    with pytest.raises(ValueError, match="missing .* required features"):
        hybrid_pipeline.predict(partial_dict)

    # 2. NaN values in DataFrame
    df_nan = pd.DataFrame(
        np.full((5, 76), np.nan, dtype=np.float32),
        columns=hybrid_pipeline.feature_names,
    )
    with pytest.raises(ValueError, match="contains NaN or Inf"):
        hybrid_pipeline.predict_batch(df_nan)

    # 3. Inf values in numpy array
    arr_inf = np.zeros((3, 76), dtype=np.float32)
    arr_inf[0, 0] = np.inf
    with pytest.raises(ValueError, match="contains NaN or Inf"):
        hybrid_pipeline.predict_batch(arr_inf)

    # 4. Dimension mismatch
    arr_wrong_dim = np.zeros((3, 50), dtype=np.float32)
    with pytest.raises(ValueError, match="Feature count mismatch"):
        hybrid_pipeline.predict_batch(arr_wrong_dim)


def test_research_integrity_artifact_manifest_hashes() -> None:
    """Verify that all model artifact hashes match the recorded hybrid manifest."""
    manifest_path = PROJECT_ROOT / "artifacts" / "models" / "hybrid" / "v1" / "model_manifest.json"
    assert manifest_path.exists(), "Hybrid model manifest is missing!"

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    recorded_hashes = manifest["artifact_hashes"]

    for name, key_path in [
        (
            "isolation_forest",
            PROJECT_ROOT / "artifacts" / "models" / "isolation_forest" / "v1" / "model.joblib",
        ),
        (
            "autoencoder",
            PROJECT_ROOT / "artifacts" / "models" / "autoencoder" / "v1" / "best_model.pt",
        ),
        (
            "classifier_booster",
            PROJECT_ROOT / "artifacts" / "models" / "xgboost_classifier" / "v1" / "model.ubj",
        ),
        ("feature_schema", PROJECT_ROOT / "artifacts" / "preprocessing" / "feature_schema.json"),
        (
            "standard_scaler",
            PROJECT_ROOT / "artifacts" / "preprocessing" / "standard_scaler.joblib",
        ),
    ]:
        current_hash = ModelRegistry.compute_sha256(key_path)
        assert current_hash == recorded_hashes[name], f"Cryptographic hash mismatch for {name}!"
