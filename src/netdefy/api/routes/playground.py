"""NETDEFY — Interactive ML Inference Playground API (Phase 6.1).

Serves curated benchmark samples and executes real-time single-flow inference
against the frozen multi-model hybrid pipeline with detailed decision,
anomaly calibration, classification probabilities, and feature explanations.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from netdefy.api.dependencies import get_raw_hybrid_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playground", tags=["Inference Playground"])

CURATED_SAMPLES_FILE = Path("artifacts/research/curated_benchmark_samples.json")


class PlaygroundPredictRequest(BaseModel):
    """Payload for interactive single-flow inference."""

    features: dict[str, float] = Field(
        ...,
        description="Dictionary mapping all 76 continuous features to their float32 values.",
    )
    flow_id: str | int | None = Field(
        default=None,
        description="Optional identifier for the flow.",
    )
    is_synthetic: bool = Field(
        default=False,
        description="Flag indicating if features were manually modified via playground sliders.",
    )


@router.get("/samples")
def get_curated_samples() -> dict[str, Any]:
    """Return authentic curated benchmark samples extracted directly from test/validation splits."""
    if not CURATED_SAMPLES_FILE.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curated benchmark samples artifact missing. Run sample extraction first.",
        )
    try:
        with open(CURATED_SAMPLES_FILE, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            raise ValueError("Curated samples artifact is not a JSON object")
    except Exception as e:
        logger.error("Failed to load curated samples: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read curated samples: {e}",
        ) from e


@router.post("/predict")
def predict_flow_sample(request: PlaygroundPredictRequest) -> dict[str, Any]:
    """Execute live inference on a single 76-feature flow vector using the actual saved models."""
    pipeline = get_raw_hybrid_pipeline()
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hybrid inference pipeline is not loaded or model artifacts are unavailable.",
        )

    # Validate required feature count
    expected_features = pipeline.feature_names
    missing_features = [f for f in expected_features if f not in request.features]
    if missing_features:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Missing {len(missing_features)} required features out of {len(expected_features)}. "
                f"First missing: {missing_features[:5]}"
            ),
        )

    try:
        prediction = pipeline.predict(request.features, flow_id=request.flow_id)
        pred_dict = prediction.to_dict()
    except Exception as e:
        logger.exception("Inference failed on flow: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference execution error: {e}",
        ) from e

    # Attach scientific advisory note if sliders were used
    scientific_note = None
    if request.is_synthetic:
        scientific_note = (
            "Notice: Synthetic feature adjustments may create physically non-realizable or "
            "protocol-inconsistent network flow states. Benchmark samples represent validated physical packet captures."
        )

    return {
        "flow_id": pred_dict.get("flow_id"),
        "decision": pred_dict.get("decision"),
        "decision_reason": pred_dict.get("decision_reason"),
        "anomaly": pred_dict.get("anomaly"),
        "classifier": pred_dict.get("classifier"),
        "explanation": pred_dict.get("explanation"),
        "model_versions": pred_dict.get("model_versions"),
        "scientific_note": scientific_note,
        "is_synthetic": request.is_synthetic,
    }
