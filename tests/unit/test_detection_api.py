"""NETDEFY — Unit Tests for Detection Console API Endpoints."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from netdefy.api.app import app


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client instance."""
    return TestClient(app)


@pytest.fixture
def sample_features() -> dict[str, float]:
    """Load valid 76-feature sample from curated benchmark samples."""
    samples_path = Path("artifacts/research/curated_benchmark_samples.json")
    with open(samples_path, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    first_sample: dict[str, Any] = data["samples"][0]
    return dict(first_sample["features"])


def test_detection_schema_endpoint(client: TestClient) -> None:
    """Validate that /detection/schema returns all 76 features and 9 categories."""
    resp = client.get("/api/v1/detection/schema")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_features"] == 76
    assert len(data["features"]) == 76
    assert len(data["categories"]) == 9
    assert len(data["trained_classes"]) == 8
    assert len(data["absent_categories"]) == 7
    # Check first feature metadata
    f0 = data["features"][0]
    assert "name" in f0
    assert "category" in f0
    assert "unit" in f0


def test_analyze_single_flow_success(client: TestClient, sample_features: dict[str, float]) -> None:
    """Validate single-flow analysis against real ModelRegistry."""
    payload = {
        "features": sample_features,
        "flow_id": "test_flow_unit_01",
        "source": "Unit Test Flow",
        "is_synthetic": False,
    }
    resp = client.post("/api/v1/detection/analyze-flow", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    pred = data["prediction"]
    assert pred["flow_id"] == "test_flow_unit_01"
    assert pred["decision"] in [
        "NORMAL",
        "SUSPICIOUS_KNOWN",
        "SUSPICIOUS_UNKNOWN",
        "REVIEW_REQUIRED",
    ]
    assert "anomaly" in pred
    assert "classifier" in pred
    assert "explanation" in pred
    assert len(pred["explanation"]["top_contributing_features"]) > 0


def test_analyze_single_flow_missing_features(client: TestClient) -> None:
    """Validate 422 rejection when features are missing."""
    payload = {
        "features": {"Flow Duration": 12000.0, "Total Fwd Packets": 5.0},
        "flow_id": "bad_flow",
    }
    resp = client.post("/api/v1/detection/analyze-flow", json=payload)
    assert resp.status_code == 422
    err = resp.json()
    assert "Missing" in err["detail"]


def test_analyze_single_flow_nan_rejection(client: TestClient) -> None:
    """Validate rejection of invalid non-numeric values."""
    raw_payload = (
        '{"features": {"Flow Duration": "invalid_string_not_float"}, "flow_id": "bad_flow"}'
    )
    resp = client.post(
        "/api/v1/detection/analyze-flow",
        content=raw_payload,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


def test_analyze_batch_flows_success(client: TestClient, sample_features: dict[str, float]) -> None:
    """Validate vectorized batch inference endpoint."""
    batch_items = [
        {"flow_id": "flow_1", "features": sample_features, "label": "BENIGN"},
        {"flow_id": "flow_2", "features": sample_features, "label": "BENIGN"},
    ]
    resp = client.post(
        "/api/v1/detection/analyze-batch",
        json={"flows": batch_items, "source_name": "Unit Test Batch"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_flows"] == 2
    assert len(data["predictions"]) == 2
    assert "decision_counts" in data
    assert "session_id" in data


def test_analyze_batch_empty_rejected(client: TestClient) -> None:
    """Validate rejection of empty batch."""
    resp = client.post("/api/v1/detection/analyze-batch", json={"flows": []})
    assert resp.status_code == 422


def test_download_sample_csv(client: TestClient) -> None:
    """Validate download of sample network traffic CSV."""
    resp = client.get("/api/v1/detection/sample-csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    text = resp.text
    assert "Flow Duration" in text
    assert "Total Fwd Packets" in text


def test_upload_csv_success(client: TestClient) -> None:
    """Validate CSV upload and batch inference."""
    sample_csv = Path("artifacts/research/sample_network_traffic.csv")
    assert sample_csv.exists(), "Sample CSV must exist for upload test"

    with open(sample_csv, "rb") as f:
        csv_bytes = f.read()

    files = {"file": ("test_upload.csv", io.BytesIO(csv_bytes), "text/csv")}
    resp = client.post("/api/v1/detection/upload-csv", files=files, data={"max_rows": 15})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows_evaluated"] == 15
    assert data["has_ground_truth_labels"] is True
    assert len(data["predictions"]) == 15
    assert "session_id" in data
    # Confirm ground truth label attached
    assert data["predictions"][0].get("ground_truth_label") is not None


def test_upload_csv_missing_columns(client: TestClient) -> None:
    """Validate clear structured error when CSV has missing columns."""
    bad_csv = "Flow Duration,Total Fwd Packets\n12000,5\n34000,2\n"
    files = {"file": ("bad_traffic.csv", io.BytesIO(bad_csv.encode()), "text/csv")}
    resp = client.post("/api/v1/detection/upload-csv", files=files)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "missing_columns" in detail
    assert detail["required_count"] == 76


def test_detection_history_and_stats(client: TestClient) -> None:
    """Validate history listing, session retrieval, and aggregate stats."""
    # List history
    resp = client.get("/api/v1/detection/history")
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert "total_count" in data
    assert data["total_count"] > 0

    session_id = data["sessions"][0]["id"]
    # Get specific session details
    detail_resp = client.get(f"/api/v1/detection/history/{session_id}")
    assert detail_resp.status_code == 200
    session_detail = detail_resp.json()
    assert session_detail["id"] == session_id
    assert "predictions" in session_detail

    # Get aggregate stats
    stats_resp = client.get("/api/v1/detection/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_flows_analyzed"] > 0
    assert "normal_flows" in stats
    assert "suspicious_flows" in stats
    assert "review_required_flows" in stats
