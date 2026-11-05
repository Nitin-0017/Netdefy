"""NETDEFY — Adaptive Baseline & Drift Monitoring Engine (Phase 6).

Implements bounded, security-gated statistical baseline adaptation and drift
detection to track environment shifts without baseline poisoning.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from netdefy.hybrid.schemas import DecisionCategory

logger = logging.getLogger(__name__)


@dataclass
class BaselineSnapshot:
    """Statistical summary of reference or adaptive anomaly score distributions."""

    version_id: str
    created_at: datetime
    mean_score: float
    p95_score: float
    p99_score: float
    observations_count: int
    is_frozen_reference: bool = False
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "created_at": self.created_at.isoformat(),
            "mean_score": round(self.mean_score, 4),
            "p95_score": round(self.p95_score, 4),
            "p99_score": round(self.p99_score, 4),
            "observations_count": self.observations_count,
            "is_frozen_reference": self.is_frozen_reference,
            "description": self.description,
        }


class AdaptiveBaselinePolicy:
    """Security-gated adaptive baseline with strict anti-poisoning constraints."""

    def __init__(
        self,
        frozen_mean: float = 0.50,
        frozen_p95: float = 0.95,
        frozen_p99: float = 0.982,
        ema_alpha: float = 0.005,
        drift_z_threshold: float = 3.0,
        max_deviation_ratio: float = 0.25,
    ) -> None:
        self.ema_alpha = ema_alpha
        self.drift_z_threshold = drift_z_threshold
        self.max_deviation_ratio = max_deviation_ratio

        # Immutable reference baseline (never modified)
        self.frozen_reference = BaselineSnapshot(
            version_id="baseline-v1-frozen-ref",
            created_at=datetime.now(UTC),
            mean_score=frozen_mean,
            p95_score=frozen_p95,
            p99_score=frozen_p99,
            observations_count=50000,
            is_frozen_reference=True,
            description="Verified Phase 4D/5.1 frozen benign holdout reference",
        )

        # Active adaptive baseline initialized to frozen values
        self.active_baseline = BaselineSnapshot(
            version_id=f"adaptive-v1-{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(UTC),
            mean_score=frozen_mean,
            p95_score=frozen_p95,
            p99_score=frozen_p99,
            observations_count=0,
            is_frozen_reference=False,
            description="Active running exponential moving average baseline",
        )

        self.drift_detected: bool = False
        self.drift_reason: str = ""
        self.version_history: list[BaselineSnapshot] = [self.frozen_reference]

    def is_eligible_for_update(
        self,
        decision: str,
        anomaly_score: float,
        supervised_label: str = "BENIGN",
        has_behavioral_flag: bool = False,
    ) -> bool:
        """CRITICAL SECURITY GATE: Prevents adversarial baseline poisoning.

        Only high-confidence, verified BENIGN flows with no classifier ambiguity
        and zero behavioural triggers are permitted to update running statistics.
        """
        # Rule 1: Must be explicitly classified as NORMAL
        if decision != DecisionCategory.NORMAL.value:
            return False

        # Rule 2: Supervised class must be strictly BENIGN
        if supervised_label != "BENIGN":
            return False

        # Rule 3: Must not have any behavioural flags (scan or burst)
        if has_behavioral_flag:
            return False

        # Rule 4: Score must be well within normal boundary (< p95 reference)
        return anomaly_score < self.frozen_reference.p95_score

    def update(
        self,
        anomaly_score: float,
        decision: str,
        supervised_label: str = "BENIGN",
        has_behavioral_flag: bool = False,
    ) -> bool:
        """Apply bounded EMA update to active baseline if observation passes security gate."""
        if not self.is_eligible_for_update(
            decision=decision,
            anomaly_score=anomaly_score,
            supervised_label=supervised_label,
            has_behavioral_flag=has_behavioral_flag,
        ):
            return False

        # Bounded EMA update
        old_mean = self.active_baseline.mean_score
        new_mean = (1.0 - self.ema_alpha) * old_mean + self.ema_alpha * anomaly_score

        # Bound maximum deviation from frozen reference to prevent slow drift attacks
        ref_mean = self.frozen_reference.mean_score
        max_allowed_delta = ref_mean * self.max_deviation_ratio
        clamped_mean = max(
            ref_mean - max_allowed_delta, min(ref_mean + max_allowed_delta, new_mean)
        )

        self.active_baseline.mean_score = clamped_mean
        self.active_baseline.observations_count += 1

        # Check for distribution drift
        self._check_drift()
        return True

    def _check_drift(self) -> None:
        """Evaluate whether active baseline has drifted significantly from frozen reference."""
        ref_mean = self.frozen_reference.mean_score
        act_mean = self.active_baseline.mean_score
        delta = abs(act_mean - ref_mean)

        ratio = delta / max(1e-5, ref_mean)
        if ratio >= self.max_deviation_ratio:
            self.drift_detected = True
            self.drift_reason = (
                f"Significant baseline drift detected: Active mean ({act_mean:.4f}) deviates by "
                f"{ratio * 100:.1f}% from frozen reference ({ref_mean:.4f})"
            )
            logger.warning(self.drift_reason)
        else:
            self.drift_detected = False
            self.drift_reason = ""

    def rollback_to_frozen(self) -> None:
        """Emergency administrative reset restoring active baseline to frozen reference."""
        self.active_baseline.mean_score = self.frozen_reference.mean_score
        self.active_baseline.p95_score = self.frozen_reference.p95_score
        self.active_baseline.p99_score = self.frozen_reference.p99_score
        self.active_baseline.version_id = f"adaptive-rollback-{uuid.uuid4().hex[:8]}"
        self.active_baseline.created_at = datetime.now(UTC)
        self.active_baseline.description = "Rolled back to frozen reference baseline"
        self.drift_detected = False
        self.drift_reason = ""
        logger.info(
            "Rolled back active baseline to frozen reference: %s", self.active_baseline.version_id
        )

    def snapshot_version(self, description: str = "") -> BaselineSnapshot:
        """Create an immutable snapshot of current active baseline for audit persistence."""
        snap = BaselineSnapshot(
            version_id=f"snap-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
            created_at=datetime.now(UTC),
            mean_score=self.active_baseline.mean_score,
            p95_score=self.active_baseline.p95_score,
            p99_score=self.active_baseline.p99_score,
            observations_count=self.active_baseline.observations_count,
            is_frozen_reference=False,
            description=description
            or f"Snapshot after {self.active_baseline.observations_count} updates",
        )
        self.version_history.append(snap)
        return snap
