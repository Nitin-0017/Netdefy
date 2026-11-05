"""NETDEFY — Phase 5.1 Independent Behavioural Validation Unit Tests.

Verifies external dataset schema mapping, chronological split integrity, zero temporal leakage,
out-of-order tolerance, missing event robustness, and host profile LRU eviction.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from netdefy.behaviour.behavioural_profiles import HostProfileManager
from netdefy.behaviour.destination_diversity import DestinationDiversityAnalyzer
from netdefy.behaviour.schema import NetworkEvent
from netdefy.behaviour.validation import TemporalValidator
from netdefy.behaviour.window_aggregator import WindowAggregator, WindowAggregatorConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_phase5_1_benchmark_partitions_exist_and_zero_leakage() -> None:
    """Verify that Phase 5.1 benchmark partitions exist and enforce strict chronological separation."""
    bench_dir = PROJECT_ROOT / "data" / "benchmark" / "phase5_1"
    cal_file = bench_dir / "calibration.parquet"
    val_file = bench_dir / "validation.parquet"
    test_file = bench_dir / "test.parquet"

    if not (cal_file.exists() and val_file.exists() and test_file.exists()):
        pytest.skip("Phase 5.1 benchmark parquet files not yet generated.")

    df_cal = pd.read_parquet(cal_file, columns=["epoch_timestamp", "Label"])
    df_val = pd.read_parquet(val_file, columns=["epoch_timestamp", "Label"])
    df_test = pd.read_parquet(test_file, columns=["epoch_timestamp", "Label"])

    max_cal = int(df_cal["epoch_timestamp"].max())
    min_val = int(df_val["epoch_timestamp"].min())
    max_val = int(df_val["epoch_timestamp"].max())
    min_test = int(df_test["epoch_timestamp"].min())

    # Strict chronological non-overlap: max_cal <= min_val and max_val <= min_test
    assert max_cal <= min_val, f"Temporal leakage: max cal ({max_cal}) > min val ({min_val})"
    assert max_val <= min_test, f"Temporal leakage: max val ({max_val}) > min test ({min_test})"

    # Validate monotonicity in test partition sample
    test_ts = [float(x) for x in df_test["epoch_timestamp"].head(5000)]
    assert (
        TemporalValidator.validate_monotonicity(test_ts, max_allowed_backward_seconds=1.0) is True
    )


def test_phase5_1_feature_schema_completeness() -> None:
    """Verify that external benchmark partitions contain all 76 continuous features required by Phase 4D."""
    bench_dir = PROJECT_ROOT / "data" / "benchmark" / "phase5_1"
    test_file = bench_dir / "test.parquet"
    scaler_file = PROJECT_ROOT / "artifacts" / "preprocessing" / "standard_scaler.joblib"

    if not (test_file.exists() and scaler_file.exists()):
        pytest.skip("Test parquet or scaler artifact not available.")

    import joblib

    scaler = joblib.load(scaler_file)
    expected_features = list(scaler.feature_names_in_)

    df_test = pd.read_parquet(test_file)
    missing = [c for c in expected_features if c not in df_test.columns]

    assert len(missing) == 0, f"Missing required features in Phase 5.1 benchmark: {missing}"
    assert "epoch_timestamp" in df_test.columns
    assert "Destination Port" in df_test.columns
    assert "Label" in df_test.columns


def test_missing_event_robustness_on_diversity_analyzer() -> None:
    """Verify that scan diversity detection is robust to realistic packet loss (up to 20% dropped events)."""
    analyzer = DestinationDiversityAnalyzer(
        min_connections_for_scan=10,
        vertical_scan_port_threshold=8,
        vertical_scan_fan_out=0.70,
    )

    # 20 sequential scan events probing 20 different ports
    events = [
        NetworkEvent(
            source_ip="10.0.0.99",
            destination_ip="192.168.1.1",
            destination_port=1000 + i,
        )
        for i in range(20)
    ]

    # Baseline 100% events: Vertical scan detected
    baseline_profile = analyzer.analyze(events)
    assert baseline_profile.is_vertical_scan is True

    # 20% events dropped (4 events removed randomly)
    rng = np.random.default_rng(seed=42)
    retained_indices = rng.choice(20, size=16, replace=False)
    dropped_events = [events[i] for i in sorted(retained_indices)]

    dropped_profile = analyzer.analyze(dropped_events)
    assert dropped_profile.total_connections == 16
    assert dropped_profile.unique_destination_ports == 16
    assert dropped_profile.is_vertical_scan is True


def test_out_of_order_event_tolerance_bounds() -> None:
    """Verify that WindowAggregator tolerates jitter within tolerance and rejects beyond tolerance."""
    cfg = WindowAggregatorConfig(
        window_duration_seconds=30.0,
        allow_out_of_order=True,
        max_out_of_order_seconds=3.0,
    )
    agg = WindowAggregator(cfg)

    agg.add_event(NetworkEvent(timestamp=100.0, destination_port=80))
    # Event jumping backward by 2.0s (within 3.0s tolerance) should be accepted
    agg.add_event(NetworkEvent(timestamp=98.0, destination_port=81))
    assert len(agg.events) == 2

    # Event jumping backward by 5.0s with allow_out_of_order=False should be rejected
    cfg_strict = WindowAggregatorConfig(
        window_duration_seconds=30.0,
        allow_out_of_order=False,
        max_out_of_order_seconds=1.0,
    )
    agg_strict = WindowAggregator(cfg_strict)
    agg_strict.add_event(NetworkEvent(timestamp=100.0, destination_port=80))
    with pytest.raises(ValueError, match="Out-of-order event rejected"):
        agg_strict.add_event(NetworkEvent(timestamp=95.0, destination_port=81))


def test_lru_host_profile_eviction_under_high_cardinality() -> None:
    """Verify that HostProfileManager bounds memory by evicting least-recently-used hosts."""
    manager = HostProfileManager(max_hosts=5)

    for i in range(5):
        manager.record_event(
            f"10.0.0.{i}",
            NetworkEvent(destination_ip="192.168.1.1", destination_port=80),
        )

    assert len(manager) == 5
    assert "10.0.0.0" in manager

    # Insert 6th host
    manager.record_event(
        "10.0.0.100",
        NetworkEvent(destination_ip="192.168.1.1", destination_port=80),
    )

    assert len(manager) == 5
    # Oldest host (10.0.0.0) must be evicted
    assert "10.0.0.0" not in manager
    assert "10.0.0.100" in manager
