"""NETDEFY — Connection Burst Detector.

Monitors connection arrival velocity and volume using rolling baselines and EWMA,
detecting anomalous traffic bursts, volumetric flooding, and automated rate spikes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BurstStatus:
    """Quantitative evaluation of traffic arrival rate and burst intensity."""

    is_burst: bool
    current_rate: float
    baseline_rate: float
    baseline_std: float
    rate_z_score: float
    severity: str


class BurstDetector:
    """Detects rapid surges in connection rates using online EWMA statistics."""

    def __init__(
        self,
        alpha: float = 0.1,
        z_threshold: float = 3.0,
        min_rate_for_burst: float = 20.0,
        initial_baseline_rate: float = 5.0,
        initial_baseline_std: float = 2.0,
    ) -> None:
        """Initialize BurstDetector.

        Args:
            alpha: Exponential smoothing factor (0 < alpha <= 1).
            z_threshold: Number of standard deviations above baseline to flag as burst.
            min_rate_for_burst: Minimum absolute connection rate (conns/sec) required to alert.
            initial_baseline_rate: Default starting expectation for connection rate.
            initial_baseline_std: Default starting standard deviation.
        """
        self.alpha = alpha
        self.z_threshold = z_threshold
        self.min_rate = min_rate_for_burst
        self.mean_rate = initial_baseline_rate
        self.var_rate = initial_baseline_std**2
        self.samples_seen = 0

    def update_and_check(self, observed_rate: float) -> BurstStatus:
        """Evaluate an observed connection rate against the running baseline and update statistics."""
        current_std = math.sqrt(max(1e-4, self.var_rate))
        z_score = float((observed_rate - self.mean_rate) / current_std)

        is_burst = bool(z_score >= self.z_threshold and observed_rate >= self.min_rate)

        # Categorize severity
        if z_score >= self.z_threshold * 1.5 and observed_rate >= self.min_rate * 2:
            severity = "CRITICAL"
        elif is_burst:
            severity = "BURST"
        elif z_score >= self.z_threshold * 0.7:
            severity = "ELEVATED"
        else:
            severity = "NORMAL"

        status = BurstStatus(
            is_burst=is_burst,
            current_rate=observed_rate,
            baseline_rate=self.mean_rate,
            baseline_std=current_std,
            rate_z_score=z_score,
            severity=severity,
        )

        # Update running EWMA mean and variance (Welford-style EWMA)
        diff = observed_rate - self.mean_rate
        incr = self.alpha * diff
        self.mean_rate += incr
        self.var_rate = (1.0 - self.alpha) * (self.var_rate + diff * incr)
        self.samples_seen += 1

        return status

    def reset(self, initial_rate: float = 5.0, initial_std: float = 2.0) -> None:
        """Reset internal statistical state."""
        self.mean_rate = initial_rate
        self.var_rate = initial_std**2
        self.samples_seen = 0
