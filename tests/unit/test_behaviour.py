"""NETDEFY — Behavioral Network Intelligence Unit Tests (Phase 5).

Validates intra-flow feature builder, sliding window aggregation, destination & port diversity,
burst detection, host profiling, connection pattern analysis, and temporal validation.
"""

from __future__ import annotations

import pytest

from netdefy.behaviour.behavioural_profiles import HostProfileManager
from netdefy.behaviour.burst_detection import BurstDetector
from netdefy.behaviour.connection_patterns import ConnectionPatternAnalyzer
from netdefy.behaviour.destination_diversity import DestinationDiversityAnalyzer
from netdefy.behaviour.feature_builder import BehavioralFeatureBuilder
from netdefy.behaviour.schema import NetworkEvent
from netdefy.behaviour.validation import TemporalValidationError, TemporalValidator
from netdefy.behaviour.window_aggregator import WindowAggregator, WindowAggregatorConfig


def test_feature_builder_intra_flow_metrics() -> None:
    """Validate calculation of Tier A intra-flow behavioral metrics and scan signature."""
    builder = BehavioralFeatureBuilder()

    # Synthetic normal flow
    normal_flow = {
        "Total Fwd Packets": 10.0,
        "Total Backward Packets": 10.0,
        "Total Length of Fwd Packets": 1000.0,
        "Total Length of Bwd Packets": 2000.0,
        "Flow Duration": 5000.0,
        "Flow IAT Mean": 500.0,
        "Flow IAT Std": 250.0,
        "Fwd IAT Mean": 600.0,
        "Bwd IAT Mean": 550.0,
        "Active Mean": 2000.0,
        "Init_Win_bytes_forward": 8192.0,
        "Init_Win_bytes_backward": 8192.0,
        "Destination Port": 443.0,
    }

    metrics = builder.compute_intra_flow(normal_flow)

    assert pytest.approx(metrics.directional_packet_ratio, rel=1e-2) == 10.0 / 11.0
    assert pytest.approx(metrics.directional_byte_ratio, rel=1e-2) == 1001.0 / 2001.0
    assert pytest.approx(metrics.burstiness_index, rel=1e-2) == 250.0 / 500.0
    assert metrics.active_duration_ratio < 1.0
    assert not metrics.is_scan_signature
    assert metrics.service_category == "HTTPS"

    # Synthetic PortScan closed-port flow (1 forward pkt, 1 backward pkt, 6 backward bytes)
    scan_flow = {
        "Total Fwd Packets": 1.0,
        "Total Backward Packets": 1.0,
        "Total Length of Fwd Packets": 0.0,
        "Total Length of Bwd Packets": 6.0,
        "Flow Duration": 120.0,
        "Flow IAT Mean": 120.0,
        "Flow IAT Std": 0.0,
        "Fwd IAT Mean": 0.0,
        "Bwd IAT Mean": 0.0,
        "Active Mean": 0.0,
        "Init_Win_bytes_forward": 1024.0,
        "Init_Win_bytes_backward": 0.0,
        "Destination Port": 8080.0,
    }

    scan_metrics = builder.compute_intra_flow(scan_flow)
    assert scan_metrics.is_scan_signature is True


def test_window_aggregator_sliding_behavior() -> None:
    """Validate sliding window time-based eviction and rate calculation."""
    config = WindowAggregatorConfig(window_duration_seconds=10.0, max_events_capacity=100)
    aggregator = WindowAggregator(config)

    # Insert events across 15 seconds
    t0 = 1000.0
    for i in range(15):
        event = NetworkEvent(
            timestamp=t0 + i,
            source_ip="192.168.1.10",
            destination_ip=f"10.0.0.{i % 3}",
            destination_port=80 + (i % 2),
        )
        aggregator.add_event(event)

    context = aggregator.get_context()
    # At t = 1014, events strictly older than 1004 are pruned (so 1004 to 1014 remain, exactly 11 events in [1004, 1014])
    assert context.connection_count == 11
    assert context.unique_destinations == 3
    assert context.unique_destination_ports == 2
    assert pytest.approx(context.connection_rate, rel=1e-2) == 1.1  # 11 events / 10s


def test_window_aggregator_out_of_order_rejection() -> None:
    """Validate strict handling of excessively delayed out-of-order events."""
    config = WindowAggregatorConfig(
        window_duration_seconds=30.0,
        allow_out_of_order=False,
        max_out_of_order_seconds=2.0,
    )
    aggregator = WindowAggregator(config)
    aggregator.add_event(NetworkEvent(timestamp=100.0))

    # Backward event within tolerance should pass if allow_out_of_order is True, but here false with 5s delta
    with pytest.raises(ValueError, match="Out-of-order event rejected"):
        aggregator.add_event(NetworkEvent(timestamp=90.0))


def test_destination_diversity_analyzer() -> None:
    """Validate horizontal and vertical scanning pattern detection."""
    analyzer = DestinationDiversityAnalyzer(
        min_connections_for_scan=10,
        horizontal_scan_ip_threshold=8,
        horizontal_scan_fan_out=0.70,
        vertical_scan_port_threshold=8,
        vertical_scan_fan_out=0.70,
    )

    # 1. Horizontal scan: 10 connections to 10 distinct destination IPs on port 80
    horiz_events = [
        NetworkEvent(
            source_ip="192.168.1.50",
            destination_ip=f"10.0.0.{i}",
            destination_port=80,
        )
        for i in range(10)
    ]
    horiz_profile = analyzer.analyze(horiz_events)
    assert horiz_profile.is_horizontal_scan is True
    assert horiz_profile.is_vertical_scan is False
    assert horiz_profile.destination_fan_out_ratio == 1.0

    # 2. Vertical scan: 10 connections to a single destination IP across 10 distinct ports
    vert_events = [
        NetworkEvent(
            source_ip="192.168.1.50",
            destination_ip="10.0.0.1",
            destination_port=1000 + i,
        )
        for i in range(10)
    ]
    vert_profile = analyzer.analyze(vert_events)
    assert vert_profile.is_horizontal_scan is False
    assert vert_profile.is_vertical_scan is True
    assert vert_profile.port_fan_out_ratio == 1.0

    # 3. Normal traffic: 10 connections to 2 IPs on 2 ports
    normal_events = [
        NetworkEvent(
            source_ip="192.168.1.50",
            destination_ip=f"10.0.0.{i % 2}",
            destination_port=443 if i % 2 == 0 else 80,
        )
        for i in range(10)
    ]
    norm_profile = analyzer.analyze(normal_events)
    assert norm_profile.is_horizontal_scan is False
    assert norm_profile.is_vertical_scan is False


def test_burst_detector() -> None:
    """Validate EWMA rate baseline updates and Z-score burst alerting."""
    detector = BurstDetector(
        alpha=0.1,
        z_threshold=3.0,
        min_rate_for_burst=20.0,
        initial_baseline_rate=5.0,
        initial_baseline_std=2.0,
    )

    # Steady normal rate
    for _ in range(20):
        status = detector.update_and_check(5.0)
    assert status.is_burst is False
    assert status.severity == "NORMAL"

    # Sudden burst surge to 50 conns/sec
    burst_status = detector.update_and_check(50.0)
    assert burst_status.is_burst is True
    assert burst_status.rate_z_score > 3.0
    assert burst_status.severity in ("BURST", "CRITICAL")


def test_host_profile_manager_and_lru() -> None:
    """Validate HostProfile aggregation and LRU eviction under bounded capacity."""
    manager = HostProfileManager(max_hosts=3)

    event = NetworkEvent(
        timestamp=100.0,
        destination_ip="10.0.0.1",
        destination_port=443,
        features={"Total Length of Fwd Packets": 500.0, "Total Length of Bwd Packets": 1000.0},
    )

    manager.record_event("192.168.1.1", event)
    manager.record_event("192.168.1.2", event)
    manager.record_event("192.168.1.3", event)
    assert len(manager) == 3
    assert "192.168.1.1" in manager

    # Insert 4th host - oldest ("192.168.1.1") must be evicted
    manager.record_event("192.168.1.4", event)
    assert len(manager) == 3
    assert "192.168.1.1" not in manager
    assert "192.168.1.4" in manager

    profile = manager.get_or_create("192.168.1.4")
    assert profile.total_fwd_bytes == 500
    assert profile.total_bwd_bytes == 1000
    assert 443 in profile.accessed_ports


def test_temporal_validator() -> None:
    """Validate strict monotonicity and temporal leakage detection."""
    # 1. Monotonic timestamps pass
    valid_ts = [10.0, 10.5, 11.0, 11.2, 12.0]
    assert TemporalValidator.validate_monotonicity(valid_ts) is True

    # 2. Non-monotonic timestamps fail
    invalid_ts = [10.0, 11.0, 9.0, 12.0]
    with pytest.raises(TemporalValidationError, match="Temporal monotonicity violation"):
        TemporalValidator.validate_monotonicity(invalid_ts, max_allowed_backward_seconds=0.5)

    # 3. Clean chronological separation between train and test
    train_ts = [1.0, 2.0, 3.0, 4.0]
    test_ts = [4.1, 5.0, 6.0]
    assert TemporalValidator.check_temporal_leakage(train_ts, test_ts) is True

    # 4. Temporal leakage detected
    leaked_test_ts = [3.5, 4.5, 5.5]
    with pytest.raises(TemporalValidationError, match="Temporal leakage detected"):
        TemporalValidator.check_temporal_leakage(train_ts, leaked_test_ts)


def test_connection_pattern_analyzer() -> None:
    """Validate SYN-flood and RST-storm pattern classification."""
    analyzer = ConnectionPatternAnalyzer(
        min_connections=10,
        syn_flood_ratio_threshold=0.80,
        rst_storm_ratio_threshold=0.75,
    )

    # SYN flood pattern: forward packets sent, zero backward packets returned
    syn_flood_events = [
        NetworkEvent(
            destination_ip="10.0.0.1",
            destination_port=80,
            features={"Total Fwd Packets": 1.0, "Total Backward Packets": 0.0},
        )
        for _ in range(12)
    ]
    syn_profile = analyzer.analyze(syn_flood_events)
    assert syn_profile.is_syn_flood is True
    assert syn_profile.syn_only_ratio == 1.0
    assert syn_profile.is_rst_storm is False

    # RST storm: 1 fwd, 1 bwd, 6 bytes (TCP RST)
    rst_storm_events = [
        NetworkEvent(
            destination_ip="10.0.0.1",
            destination_port=80,
            features={
                "Total Fwd Packets": 1.0,
                "Total Backward Packets": 1.0,
                "Total Length of Bwd Packets": 6.0,
            },
        )
        for _ in range(12)
    ]
    rst_profile = analyzer.analyze(rst_storm_events)
    assert rst_profile.is_rst_storm is True
    assert rst_profile.is_syn_flood is False
