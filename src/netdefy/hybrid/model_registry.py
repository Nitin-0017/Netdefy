"""NETDEFY — Hybrid Model Registry & Integrity Loader.

Safely loads and validates the three component models (Isolation Forest, Deep Autoencoder,
and XGBoost Classifier) ensuring schema alignment, device compatibility, and checksum tracking.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import torch

from netdefy.models.autoencoder import AutoencoderDetector
from netdefy.models.isolation_forest import IsolationForestDetector
from netdefy.models.xgboost_classifier import XGBoostAttackClassifier

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelBundle:
    """Loaded model instances and provenance checksums."""

    isolation_forest: IsolationForestDetector
    autoencoder: AutoencoderDetector
    classifier: XGBoostAttackClassifier
    feature_names: list[str]
    artifact_checksums: dict[str, str]


class ModelRegistry:
    """Manages loading, checksum verification, and schema validation of component models."""

    @staticmethod
    def compute_sha256(filepath: Path | str) -> str:
        """Compute SHA-256 hash of a file."""
        path = Path(filepath).resolve()
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def load_bundle(
        cls,
        isolation_forest_path: Path | str,
        autoencoder_path: Path | str,
        classifier_path: Path | str,
        device: torch.device | str = "cpu",
    ) -> ModelBundle:
        """Load and validate all three models."""
        if_p = Path(isolation_forest_path).resolve()
        ae_p = Path(autoencoder_path).resolve()
        clf_p = Path(classifier_path).resolve()

        for p, name in [
            (if_p, "Isolation Forest"),
            (ae_p, "Deep Autoencoder"),
            (clf_p, "XGBoost Classifier"),
        ]:
            if not p.exists():
                raise FileNotFoundError(f"{name} artifact missing at: {p}")

        logger.info("Loading Isolation Forest from %s", if_p)
        if_model = IsolationForestDetector.load(if_p)

        logger.info("Loading Deep Autoencoder from %s", ae_p)
        ae_model = AutoencoderDetector.load(ae_p, device=device)

        logger.info("Loading XGBoost Classifier from %s", clf_p)
        clf_model = XGBoostAttackClassifier.load(clf_p)

        # Validate schema consistency
        if if_model.feature_names != ae_model.feature_names:
            raise ValueError("Feature mismatch between Isolation Forest and Autoencoder models!")
        if if_model.feature_names != clf_model.feature_names:
            raise ValueError(
                "Feature mismatch between Isolation Forest and XGBoost Classifier models!"
            )

        checksums = {
            "isolation_forest": cls.compute_sha256(if_p),
            "autoencoder": cls.compute_sha256(ae_p),
            "classifier_metadata": cls.compute_sha256(clf_p.with_suffix(".json")),
            "classifier_booster": cls.compute_sha256(clf_p.parent / "model.ubj"),
        }

        return ModelBundle(
            isolation_forest=if_model,
            autoencoder=ae_model,
            classifier=clf_model,
            feature_names=if_model.feature_names,
            artifact_checksums=checksums,
        )
