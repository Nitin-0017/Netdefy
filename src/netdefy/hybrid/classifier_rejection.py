"""NETDEFY — Supervised Classifier Confidence & Open-Set Rejection Engine.

Evaluates softmax probability vectors for confidence, decision margin, and entropy
to safely reject low-confidence, ambiguous, or out-of-distribution network attack predictions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from netdefy.hybrid.schemas import ClassifierEvidence


@dataclass(frozen=True)
class ClassifierRejectionConfig:
    """Threshold configuration for supervised classification rejection."""

    min_confidence: float = 0.50
    min_margin: float = 0.10
    max_entropy: float = 2.00
    benign_label: str = "BENIGN"
    unknown_label: str = "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClassifierRejectionConfig:
        return cls(
            min_confidence=float(data.get("min_confidence", 0.50)),
            min_margin=float(data.get("min_margin", 0.10)),
            max_entropy=float(data.get("max_entropy", 2.00)),
            benign_label=str(data.get("benign_label", "BENIGN")),
            unknown_label=str(data.get("unknown_label", "UNKNOWN")),
        )


class ClassifierRejectionEngine:
    """Evaluates classifier output vectors and identifies out-of-distribution or ambiguous flows."""

    def __init__(self, config: ClassifierRejectionConfig | None = None) -> None:
        self.config = config or ClassifierRejectionConfig()

    def evaluate_batch(
        self,
        probabilities: np.ndarray,
        class_mapping: dict[int, str],
    ) -> list[ClassifierEvidence]:
        """Evaluate a batch of class probabilities and determine rejection state.

        Args:
            probabilities: 2D array of shape [N, num_classes] of float32 probabilities.
            class_mapping: Mapping from class integer index to class label string.

        Returns:
            List of ClassifierEvidence dataclasses.
        """
        probs = np.asarray(probabilities, dtype=np.float32)
        if probs.ndim != 2:
            raise ValueError(f"Probabilities must be 2D array [N, num_classes], got {probs.shape}")
        if np.isnan(probs).any() or np.isinf(probs).any():
            raise ValueError("Input probabilities contain NaN or Inf values!")

        n_samples, n_classes = probs.shape
        if n_samples == 0:
            return []

        # Sort probabilities descending per row
        sorted_indices = np.argsort(-probs, axis=1)
        sorted_probs = np.take_along_axis(probs, sorted_indices, axis=1)

        top_indices = sorted_indices[:, 0]
        top_probs = sorted_probs[:, 0]
        second_probs = (
            sorted_probs[:, 1] if n_classes > 1 else np.zeros(n_samples, dtype=np.float32)
        )
        margins = top_probs - second_probs

        # Compute Shannon Entropy H(p) = -sum(p * log2(p)) in bits
        clipped_probs = np.clip(probs, 1e-12, 1.0)
        entropies = -np.sum(probs * np.log2(clipped_probs), axis=1)

        evidence_list: list[ClassifierEvidence] = []
        for i in range(n_samples):
            idx = int(top_indices[i])
            pred_class = class_mapping.get(idx, f"Class_{idx}")
            top_p = float(top_probs[i])
            sec_p = float(second_probs[i])
            margin = float(margins[i])
            ent = float(entropies[i])

            # Evaluate rejection criteria
            rejection_reasons: list[str] = []
            if top_p < self.config.min_confidence:
                rejection_reasons.append(
                    f"Confidence {top_p:.4f} < {self.config.min_confidence:.4f}"
                )
            if margin < self.config.min_margin:
                rejection_reasons.append(f"Margin {margin:.4f} < {self.config.min_margin:.4f}")
            if ent > self.config.max_entropy:
                rejection_reasons.append(f"Entropy {ent:.4f} > {self.config.max_entropy:.4f}")

            is_rejected = len(rejection_reasons) > 0
            reason_str = "; ".join(rejection_reasons) if is_rejected else None

            # Build class probability dict
            prob_dict = {
                class_mapping.get(c, f"Class_{c}"): float(probs[i, c]) for c in range(n_classes)
            }

            evidence_list.append(
                ClassifierEvidence(
                    predicted_class=pred_class,
                    top_probability=top_p,
                    second_probability=sec_p,
                    probability_margin=margin,
                    entropy=ent,
                    rejected=is_rejected,
                    rejection_reason=reason_str,
                    class_probabilities=prob_dict,
                )
            )

        return evidence_list

    def save(self, filepath: Path | str) -> str:
        """Save rejection configuration and return SHA-256."""
        path = Path(filepath).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = self.config.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def load(cls, filepath: Path | str) -> ClassifierRejectionEngine:
        """Load rejection engine from JSON configuration."""
        path = Path(filepath).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Rejection config not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        config = ClassifierRejectionConfig.from_dict(data)
        return cls(config=config)
