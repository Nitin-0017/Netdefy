"""NETDEFY — User-Facing Network Threat Detection Endpoints.

Provides primary operational analysis interfaces:
1. Single-flow interactive manual analysis.
2. Vectorized multi-flow batch inference.
3. CSV file upload and validation engine with automatic schema alignment.
4. Sample network traffic benchmark downloads.
5. Persistent detection session history and aggregate threat stats.
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from netdefy.api.dependencies import get_raw_hybrid_pipeline
from netdefy.storage.detection_history import get_history_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/detection", tags=["Threat Detection Console"])

SAMPLE_CSV_PATH = Path("artifacts/research/sample_network_traffic.csv")
SCALER_PATH = Path("artifacts/preprocessing/standard_scaler.joblib")


class SingleFlowAnalyzeRequest(BaseModel):
    """Payload for analyzing an individual network flow."""

    features: dict[str, float] = Field(
        ..., description="Dictionary mapping all 76 continuous features to their float32 values."
    )
    flow_id: str | None = Field(
        default=None, description="Optional identifier for tracking this flow."
    )
    source: str | None = Field(
        default="Manual Input", description="Traffic provenance description."
    )
    is_synthetic: bool = Field(
        default=False, description="Flag indicating if features were artificially set/modified."
    )


class BatchFlowItem(BaseModel):
    """Single flow item inside a batch submission."""

    flow_id: str | int | None = None
    features: dict[str, float]
    label: str | None = None


class BatchAnalyzeRequest(BaseModel):
    """Payload for submitting a batch of flows for inference."""

    flows: list[BatchFlowItem] = Field(..., max_length=2000, description="List of flows to score.")
    source_name: str | None = Field(default="Batch Submission", description="Batch source origin.")


def _get_feature_categories() -> dict[str, str]:
    """Return category assignment mapping for all 76 features."""
    categories: dict[str, str] = {
        # Timing
        "Flow Duration": "flow_timing",
        "Flow Bytes/s": "flow_timing",
        "Flow Packets/s": "flow_timing",
        # Forward Packets
        "Total Fwd Packets": "fwd_packets",
        "Total Length of Fwd Packets": "fwd_packets",
        "Fwd Packet Length Max": "fwd_packets",
        "Fwd Packet Length Min": "fwd_packets",
        "Fwd Packet Length Mean": "fwd_packets",
        "Fwd Packet Length Std": "fwd_packets",
        "Fwd Header Length": "fwd_packets",
        "Fwd Packets/s": "fwd_packets",
        "Avg Fwd Segment Size": "fwd_packets",
        "Subflow Fwd Packets": "fwd_packets",
        "Subflow Fwd Bytes": "fwd_packets",
        # Backward Packets
        "Total Backward Packets": "bwd_packets",
        "Total Length of Bwd Packets": "bwd_packets",
        "Bwd Packet Length Max": "bwd_packets",
        "Bwd Packet Length Min": "bwd_packets",
        "Bwd Packet Length Mean": "bwd_packets",
        "Bwd Packet Length Std": "bwd_packets",
        "Bwd Header Length": "bwd_packets",
        "Bwd Packets/s": "bwd_packets",
        "Avg Bwd Segment Size": "bwd_packets",
        "Subflow Bwd Packets": "bwd_packets",
        "Subflow Bwd Bytes": "bwd_packets",
        # IAT
        "Flow IAT Mean": "iat",
        "Flow IAT Std": "iat",
        "Flow IAT Max": "iat",
        "Flow IAT Min": "iat",
        "Fwd IAT Total": "iat",
        "Fwd IAT Mean": "iat",
        "Fwd IAT Std": "iat",
        "Fwd IAT Max": "iat",
        "Fwd IAT Min": "iat",
        "Bwd IAT Total": "iat",
        "Bwd IAT Mean": "iat",
        "Bwd IAT Std": "iat",
        "Bwd IAT Max": "iat",
        "Bwd IAT Min": "iat",
        # TCP Flags
        "Fwd PSH Flags": "tcp_flags",
        "Bwd PSH Flags": "tcp_flags",
        "Fwd URG Flags": "tcp_flags",
        "Bwd URG Flags": "tcp_flags",
        "FIN Flag Count": "tcp_flags",
        "SYN Flag Count": "tcp_flags",
        "RST Flag Count": "tcp_flags",
        "PSH Flag Count": "tcp_flags",
        "ACK Flag Count": "tcp_flags",
        "URG Flag Count": "tcp_flags",
        "CWE Flag Count": "tcp_flags",
        "ECE Flag Count": "tcp_flags",
        # Packet Distribution
        "Min Packet Length": "packet_distribution",
        "Max Packet Length": "packet_distribution",
        "Packet Length Mean": "packet_distribution",
        "Packet Length Std": "packet_distribution",
        "Packet Length Variance": "packet_distribution",
        "Down/Up Ratio": "packet_distribution",
        "Average Packet Size": "packet_distribution",
        # Bulk Transmission
        "Fwd Avg Bytes/Bulk": "bulk_transmission",
        "Fwd Avg Packets/Bulk": "bulk_transmission",
        "Fwd Avg Bulk Rate": "bulk_transmission",
        "Bwd Avg Bytes/Bulk": "bulk_transmission",
        "Bwd Avg Packets/Bulk": "bulk_transmission",
        "Bwd Avg Bulk Rate": "bulk_transmission",
        # Window & Buffer
        "Init_Win_bytes_forward": "window_and_segment",
        "Init_Win_bytes_backward": "window_and_segment",
        "act_data_pkt_fwd": "window_and_segment",
        "min_seg_size_forward": "window_and_segment",
        # Active / Idle
        "Active Mean": "active_idle",
        "Active Std": "active_idle",
        "Active Max": "active_idle",
        "Active Min": "active_idle",
        "Idle Mean": "active_idle",
        "Idle Std": "active_idle",
        "Idle Max": "active_idle",
        "Idle Min": "active_idle",
    }
    return categories


def _get_feature_units() -> dict[str, str]:
    """Return descriptive measurement units for features."""
    units: dict[str, str] = {
        "Flow Duration": "microseconds",
        "Flow Bytes/s": "bytes/sec",
        "Flow Packets/s": "packets/sec",
        "Total Fwd Packets": "packets",
        "Total Backward Packets": "packets",
        "Total Length of Fwd Packets": "bytes",
        "Total Length of Bwd Packets": "bytes",
        "Fwd Packet Length Max": "bytes",
        "Fwd Packet Length Min": "bytes",
        "Fwd Packet Length Mean": "bytes",
        "Fwd Packet Length Std": "bytes",
        "Bwd Packet Length Max": "bytes",
        "Bwd Packet Length Min": "bytes",
        "Bwd Packet Length Mean": "bytes",
        "Bwd Packet Length Std": "bytes",
        "Flow IAT Mean": "microseconds",
        "Flow IAT Std": "microseconds",
        "Flow IAT Max": "microseconds",
        "Flow IAT Min": "microseconds",
        "Fwd IAT Total": "microseconds",
        "Fwd IAT Mean": "microseconds",
        "Fwd IAT Std": "microseconds",
        "Fwd IAT Max": "microseconds",
        "Fwd IAT Min": "microseconds",
        "Bwd IAT Total": "microseconds",
        "Bwd IAT Mean": "microseconds",
        "Bwd IAT Std": "microseconds",
        "Bwd IAT Max": "microseconds",
        "Bwd IAT Min": "microseconds",
        "Fwd Header Length": "bytes",
        "Bwd Header Length": "bytes",
        "Fwd Packets/s": "packets/sec",
        "Bwd Packets/s": "packets/sec",
        "Min Packet Length": "bytes",
        "Max Packet Length": "bytes",
        "Packet Length Mean": "bytes",
        "Packet Length Std": "bytes",
        "Average Packet Size": "bytes",
        "Avg Fwd Segment Size": "bytes",
        "Avg Bwd Segment Size": "bytes",
        "Subflow Fwd Packets": "packets",
        "Subflow Fwd Bytes": "bytes",
        "Subflow Bwd Packets": "packets",
        "Subflow Bwd Bytes": "bytes",
        "Init_Win_bytes_forward": "bytes",
        "Init_Win_bytes_backward": "bytes",
        "act_data_pkt_fwd": "packets",
        "min_seg_size_forward": "bytes",
        "Active Mean": "microseconds",
        "Active Std": "microseconds",
        "Active Max": "microseconds",
        "Active Min": "microseconds",
        "Idle Mean": "microseconds",
        "Idle Std": "microseconds",
        "Idle Max": "microseconds",
        "Idle Min": "microseconds",
    }
    return units


@router.get("/schema")
def get_detection_schema() -> dict[str, Any]:
    """Return feature schema, groupings, units, and class architecture."""
    pipeline = get_raw_hybrid_pipeline()
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model pipeline not loaded",
        )

    categories_map = _get_feature_categories()
    units_map = _get_feature_units()

    category_labels = {
        "flow_timing": "Flow Timing & Duration",
        "fwd_packets": "Forward Packet Metrics",
        "bwd_packets": "Backward Packet Metrics",
        "iat": "Inter-Arrival Times (IAT)",
        "tcp_flags": "TCP Flags & Headers",
        "packet_distribution": "Packet Length Statistics",
        "bulk_transmission": "Bulk Transmission Rates",
        "window_and_segment": "Window Sizes & Buffer Bytes",
        "active_idle": "Active & Idle Times",
    }

    features_meta = []
    for f in pipeline.feature_names:
        cat_key = categories_map.get(f, "general")
        features_meta.append(
            {
                "name": f,
                "category": cat_key,
                "category_title": category_labels.get(cat_key, "General Metrics"),
                "unit": units_map.get(f, "metric"),
                "default_value": 0.0,
            }
        )

    categories_list = [
        {"id": k, "title": v, "feature_count": sum(1 for f in features_meta if f["category"] == k)}
        for k, v in category_labels.items()
    ]

    return {
        "total_features": len(pipeline.feature_names),
        "features": features_meta,
        "categories": categories_list,
        "trained_classes": [
            "BENIGN",
            "DoS GoldenEye",
            "DoS Hulk",
            "DoS Slowhttptest",
            "DoS slowloris",
            "FTP-Patator",
            "Heartbleed",
            "SSH-Patator",
        ],
        "absent_categories": [
            "PortScan",
            "DDoS",
            "Bot",
            "Infiltration",
            "Web Attack – Brute Force",
            "Web Attack – XSS",
            "Web Attack – Sql Injection",
        ],
    }


@router.post("/analyze-flow")
def analyze_single_flow(request: SingleFlowAnalyzeRequest) -> dict[str, Any]:
    """Run full tri-model inference on a single flow and record session."""
    pipeline = get_raw_hybrid_pipeline()
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hybrid inference engine unavailable",
        )

    expected = pipeline.feature_names
    missing = [f for f in expected if f not in request.features]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing {len(missing)} required features out of {len(expected)}. First missing: {missing[:5]}",
        )

    # Check for NaN / Inf
    for k, v in request.features.items():
        if np.isnan(v) or np.isinf(v):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Feature '{k}' contains non-finite numeric value ({v})",
            )

    flow_id = request.flow_id or f"flow_{uuid.uuid4().hex[:8]}"

    try:
        prediction = pipeline.predict(request.features, flow_id=flow_id)
        pred_dict = prediction.to_dict()
    except Exception as e:
        logger.exception("Inference failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference computation error: {e}",
        ) from e

    decision = pred_dict.get("decision", "NORMAL")

    # Record into history
    session_id = f"sess_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    session_data = {
        "id": session_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "source": request.source or "Manual Flow Analysis",
        "flow_count": 1,
        "normal_count": 1 if decision == "NORMAL" else 0,
        "suspicious_known_count": 1 if decision == "SUSPICIOUS_KNOWN" else 0,
        "suspicious_unknown_count": 1 if decision == "SUSPICIOUS_UNKNOWN" else 0,
        "review_required_count": 1 if decision == "REVIEW_REQUIRED" else 0,
        "status": "COMPLETED",
        "predictions": [pred_dict],
    }
    history_store = get_history_store()
    history_store.add_session(session_data)

    scientific_note = None
    if request.is_synthetic:
        scientific_note = (
            "Notice: Synthetic feature adjustments may create physically non-realizable or "
            "protocol-inconsistent network flow states. Benchmark samples represent validated physical packet captures."
        )

    return {
        "session_id": session_id,
        "prediction": pred_dict,
        "scientific_note": scientific_note,
        "is_synthetic": request.is_synthetic,
    }


@router.post("/analyze-batch")
def analyze_batch_flows(request: BatchAnalyzeRequest) -> dict[str, Any]:
    """Vectorized multi-flow analysis for up to 2,000 flows."""
    pipeline = get_raw_hybrid_pipeline()
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hybrid inference engine unavailable",
        )

    n_flows = len(request.flows)
    if n_flows == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Batch contains zero flows",
        )

    expected = pipeline.feature_names
    flow_ids: list[str | int | None] = []
    matrix_rows = []

    for idx, item in enumerate(request.flows):
        fid = item.flow_id or f"flow_{idx + 1}"
        flow_ids.append(fid)
        missing = [f for f in expected if f not in item.features]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Flow index {idx} ({fid}) missing {len(missing)} features: {missing[:3]}...",
            )
        row = [float(item.features[f]) for f in expected]
        matrix_rows.append(row)

    X_mat = np.array(matrix_rows, dtype=np.float32)

    try:
        batch_res = pipeline.predict_batch(
            X_mat,
            batch_size=512,
            flow_ids=flow_ids,
            include_explanations=True,
        )
        batch_dict = batch_res.to_dict()
    except Exception as e:
        logger.exception("Batch prediction failure: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch execution error: {e}",
        ) from e

    decision_counts = batch_dict.get("decision_counts", {})
    normal_count = decision_counts.get("NORMAL", 0)
    suspicious_known = decision_counts.get("SUSPICIOUS_KNOWN", 0)
    suspicious_unknown = decision_counts.get("SUSPICIOUS_UNKNOWN", 0)
    review_required = decision_counts.get("REVIEW_REQUIRED", 0)

    # Attach labels if provided
    for idx, p in enumerate(batch_dict.get("predictions", [])):
        if idx < len(request.flows):
            p["ground_truth_label"] = request.flows[idx].label

    session_id = f"batch_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    session_data = {
        "id": session_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "source": request.source_name or f"Batch Analysis ({n_flows} flows)",
        "flow_count": n_flows,
        "normal_count": normal_count,
        "suspicious_known_count": suspicious_known,
        "suspicious_unknown_count": suspicious_unknown,
        "review_required_count": review_required,
        "status": "COMPLETED",
        "predictions": batch_dict.get("predictions", []),
    }
    history_store = get_history_store()
    history_store.add_session(session_data)

    return {
        "session_id": session_id,
        "total_flows": n_flows,
        "normal_count": normal_count,
        "suspicious_known_count": suspicious_known,
        "suspicious_unknown_count": suspicious_unknown,
        "review_required_count": review_required,
        "decision_counts": decision_counts,
        "predictions": batch_dict.get("predictions", []),
    }


@router.post("/upload-csv")
async def upload_csv_file(
    file: UploadFile = File(...),
    max_rows: int = Form(default=500),
) -> dict[str, Any]:
    """Parse, validate, and execute batch inference on an uploaded CSV file."""
    pipeline = get_raw_hybrid_pipeline()
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hybrid inference engine unavailable",
        )

    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse uploaded CSV: {e}",
        ) from e

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded CSV file is completely empty",
        )

    # Clean whitespace from column headers
    df.columns = [str(c).strip() for c in df.columns]

    expected = pipeline.feature_names
    missing_columns = [f for f in expected if f not in df.columns]
    if missing_columns:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": f"CSV is missing {len(missing_columns)} required features.",
                "missing_columns": missing_columns,
                "found_columns": list(df.columns),
                "required_count": len(expected),
            },
        )

    # Isolate Label column if present
    ground_truth_labels: list[str | None] = []
    if "Label" in df.columns:
        ground_truth_labels = [str(x) if pd.notna(x) else None for x in df["Label"].iloc[:max_rows]]
    else:
        ground_truth_labels = [None] * min(len(df), max_rows)

    # Subsample to requested max_rows
    df_eval = df.iloc[:max_rows].copy()
    n_rows = len(df_eval)

    # Extract strictly the 76 features
    X_features = df_eval[expected].copy()

    # Drop non-finite rows or fill with median if tiny fraction
    invalid_mask = X_features.isna().any(axis=1) | np.isinf(X_features.to_numpy()).any(axis=1)
    invalid_count = int(invalid_mask.sum())
    if invalid_count > 0:
        logger.warning(
            "Found %d rows with non-finite values in uploaded CSV; replacing with 0.0",
            invalid_count,
        )
        X_features = X_features.fillna(0.0)
        X_features = X_features.replace([np.inf, -np.inf], 0.0)

    # Convert to float32
    X_mat = X_features.to_numpy(dtype=np.float32)

    # Generate flow identifiers
    flow_ids: list[int | str | None] = [f"row_{i + 1}" for i in range(n_rows)]

    try:
        batch_res = pipeline.predict_batch(
            X_mat,
            batch_size=512,
            flow_ids=flow_ids,
            include_explanations=True,
        )
        batch_dict = batch_res.to_dict()
    except Exception as e:
        logger.exception("CSV Batch inference failure: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error during CSV processing: {e}",
        ) from e

    # Attach ground truth labels to prediction records if available
    for idx, p in enumerate(batch_dict.get("predictions", [])):
        if idx < len(ground_truth_labels):
            p["ground_truth_label"] = ground_truth_labels[idx]

    decision_counts = batch_dict.get("decision_counts", {})
    normal_count = decision_counts.get("NORMAL", 0)
    suspicious_known = decision_counts.get("SUSPICIOUS_KNOWN", 0)
    suspicious_unknown = decision_counts.get("SUSPICIOUS_UNKNOWN", 0)
    review_required = decision_counts.get("REVIEW_REQUIRED", 0)

    session_id = f"csv_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    session_data = {
        "id": session_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "source": f"CSV Upload: {file.filename or 'traffic.csv'} ({n_rows} flows)",
        "flow_count": n_rows,
        "normal_count": normal_count,
        "suspicious_known_count": suspicious_known,
        "suspicious_unknown_count": suspicious_unknown,
        "review_required_count": review_required,
        "status": "COMPLETED",
        "predictions": batch_dict.get("predictions", []),
    }
    history_store = get_history_store()
    history_store.add_session(session_data)

    return {
        "session_id": session_id,
        "filename": file.filename,
        "total_rows_evaluated": n_rows,
        "total_csv_rows": len(df),
        "invalid_rows_cleaned": invalid_count,
        "has_ground_truth_labels": "Label" in df.columns,
        "normal_count": normal_count,
        "suspicious_known_count": suspicious_known,
        "suspicious_unknown_count": suspicious_unknown,
        "review_required_count": review_required,
        "decision_counts": decision_counts,
        "predictions": batch_dict.get("predictions", []),
    }


@router.get("/sample-csv")
def download_sample_benchmark_csv() -> FileResponse:
    """Download authentic benchmark sample CSV with validated CICIDS2017 flow headers."""
    if not SAMPLE_CSV_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample network traffic CSV not found",
        )
    return FileResponse(
        path=SAMPLE_CSV_PATH,
        filename="netdefy_sample_network_traffic.csv",
        media_type="text/csv",
    )


@router.get("/history")
def list_detection_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Retrieve historical analysis sessions."""
    store = get_history_store()
    sessions, total = store.list_sessions(limit=limit, offset=offset)
    return {
        "total_count": total,
        "limit": limit,
        "offset": offset,
        "sessions": sessions,
    }


@router.get("/history/{session_id}")
def get_detection_session(session_id: str) -> dict[str, Any]:
    """Retrieve full analysis session details including all flow predictions."""
    store = get_history_store()
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection session '{session_id}' not found",
        )
    return session


@router.delete("/history")
def clear_detection_history() -> dict[str, str]:
    """Reset and clear all stored detection analysis sessions."""
    store = get_history_store()
    store.clear()
    return {"message": "Detection history cleared successfully"}


@router.get("/stats")
def get_detection_stats() -> dict[str, Any]:
    """Return aggregated summary metrics across all analyzed network flows."""
    store = get_history_store()
    return store.get_aggregate_stats()
