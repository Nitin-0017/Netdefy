"""NETDEFY — Research and Playground API Unit Tests (Phase 6.1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from netdefy.api.app import app


@pytest.fixture
def client() -> TestClient:
    """Fixture providing TestClient instance."""
    return TestClient(app)


def test_research_overview_endpoint(client: TestClient) -> None:
    """Verify research overview returns correct benchmark metadata and class verification."""
    response = client.get("/api/v1/research/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["benchmark_version"] == "v1"
    assert data["feature_count"] == 76
    assert data["class_architecture"]["classifier_trained_classes_count"] == 8
    assert "BENIGN" in data["class_architecture"]["classifier_trained_classes"]
    assert "DoS Hulk" in data["class_architecture"]["classifier_trained_classes"]
    assert data["class_architecture"]["absent_unseen_classes_count"] == 7
    absent_names = [c["name"] for c in data["class_architecture"]["absent_unseen_classes"]]
    assert "PortScan" in absent_names
    assert "DDoS" in absent_names
    assert "Bot" in absent_names


def test_research_comparison_endpoint(client: TestClient) -> None:
    """Verify research model comparison returns all 4 models."""
    response = client.get("/api/v1/research/comparison")
    assert response.status_code == 200
    data = response.json()
    assert len(data["models"]) == 4
    model_ids = [m["id"] for m in data["models"]]
    assert "isolation_forest" in model_ids
    assert "autoencoder" in model_ids
    assert "xgboost_classifier" in model_ids
    assert "hybrid_engine" in model_ids


def test_research_thresholds_endpoint(client: TestClient) -> None:
    """Verify research threshold calibration returns p95, p99, and p99.5 tiers."""
    response = client.get("/api/v1/research/thresholds")
    assert response.status_code == 200
    data = response.json()
    tiers = [t["tier"] for t in data["threshold_tiers"]]
    assert "p95.0" in tiers
    assert "p99.0" in tiers
    assert "p99.5" in tiers


def test_research_confusion_matrix_endpoint(client: TestClient) -> None:
    """Verify confusion matrix returns validation 8x8 and test open-set matrices."""
    response = client.get("/api/v1/research/confusion-matrix")
    assert response.status_code == 200
    data = response.json()
    assert len(data["validation_closed_set"]["labels"]) == 8
    assert len(data["test_open_set"]["predicted_labels"]) == 8


def test_research_feature_importance_endpoint(client: TestClient) -> None:
    """Verify feature importance returns top ranked features by gain."""
    response = client.get("/api/v1/research/feature-importance")
    assert response.status_code == 200
    data = response.json()
    assert len(data["xgboost_feature_importance_gain"]) > 0
    top1 = data["xgboost_feature_importance_gain"][0]
    assert "feature" in top1
    assert "gain" in top1


def test_research_explainability_spec_endpoint(client: TestClient) -> None:
    """Verify explainability specification documents mathematical methods and limitations."""
    response = client.get("/api/v1/research/explainability-spec")
    assert response.status_code == 200
    data = response.json()
    assert len(data["methods"]) == 3
    assert "why_not_bruteforce_kernel_shap" in data


def test_playground_samples_endpoint(client: TestClient) -> None:
    """Verify playground samples endpoint returns curated benchmark samples."""
    response = client.get("/api/v1/playground/samples")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 10
    sample_ids = [s["id"] for s in data["samples"]]
    assert "benign_web" in sample_ids
    assert "portscan" in sample_ids
    assert "dos_hulk" in sample_ids


def test_playground_predict_endpoint(client: TestClient) -> None:
    """Verify live prediction against real benchmark sample."""
    samples_resp = client.get("/api/v1/playground/samples")
    sample = samples_resp.json()["samples"][0]

    payload = {
        "features": sample["features"],
        "flow_id": "test_flow_01",
        "is_synthetic": True,
    }
    response = client.post("/api/v1/playground/predict", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["flow_id"] == "test_flow_01"
    assert res["decision"] in [
        "NORMAL",
        "SUSPICIOUS_KNOWN",
        "SUSPICIOUS_UNKNOWN",
        "REVIEW_REQUIRED",
    ]
    assert "anomaly" in res
    assert "fused_score" in res["anomaly"]
    assert "classifier" in res
    assert len(res["classifier"]["class_probabilities"]) == 8
    assert "explanation" in res
    assert res["is_synthetic"] is True
    assert res["scientific_note"] is not None


def test_playground_predict_missing_features(client: TestClient) -> None:
    """Verify 422 error when features are missing."""
    response = client.post(
        "/api/v1/playground/predict",
        json={"features": {"Flow Duration": 1.0}},
    )
    assert response.status_code == 422
