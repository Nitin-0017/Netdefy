#!/usr/bin/env python3
"""NETDEFY — Phase 6 Real-Time Stream Processor Performance Benchmark.

Benchmarks event validation, broker throughput, inference latency, alert persistence,
and end-to-end system throughput on Apple Silicon / CPU hardware.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psutil

# Ensure src is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from netdefy.alerts.alert_engine import AlertEngine
from netdefy.behaviour.feature_builder import BehavioralFeatureBuilder
from netdefy.behaviour.pipeline_adapter import BehavioralHybridPipeline
from netdefy.hybrid.inference_pipeline import HybridInferencePipeline
from netdefy.storage.alert_repository import AlertRepository
from netdefy.storage.database import DatabaseManager
from netdefy.streaming.backpressure import BackpressureController
from netdefy.streaming.consumer import StreamConsumer
from netdefy.streaming.event_schema import FlowSummary, NetworkFlowEvent, SourceMetadata
from netdefy.streaming.event_validator import EventValidator
from netdefy.streaming.in_memory_broker import InMemoryStreamBroker
from netdefy.streaming.producer import EventProducer
from netdefy.utils.logging import setup_logging

logger = logging.getLogger("netdefy.benchmark")


def create_synthetic_event(idx: int, is_scan: bool = False) -> NetworkFlowEvent:
    """Generate a realistic test event with feature dictionary."""
    ts = pd.Timestamp.now(tz="UTC")
    dst_port = 80 if not is_scan else (1000 + (idx % 500))
    event = NetworkFlowEvent(
        event_id=f"bench-event-{idx:06d}",
        schema_version="1.0",
        event_timestamp=ts.to_pydatetime(),
        source=SourceMetadata(
            sensor_id="sensor-bench-01",
            source_ip="192.168.1.100",
            destination_ip="10.0.0.1",
            source_port=50000 + (idx % 10000),
            destination_port=dst_port,
            protocol="TCP",
        ),
        flow=FlowSummary(
            duration=0.5,
            forward_packets=2,
            backward_packets=1 if is_scan else 3,
            forward_bytes=120,
            backward_bytes=6 if is_scan else 500,
        ),
        features={
            "Destination Port": float(dst_port),
            "Flow Duration": 500000.0,
            "Total Fwd Packets": 2.0,
            "Total Backward Packets": 1.0 if is_scan else 3.0,
            "Fwd Packet Length Max": 60.0,
            "Bwd Packet Length Min": 6.0 if is_scan else 0.0,
            "FIN Flag Count": 0.0,
            "SYN Flag Count": 1.0,
            "RST Flag Count": 1.0 if is_scan else 0.0,
            "PSH Flag Count": 0.0,
            "ACK Flag Count": 0.0,
        },
    )
    return event


def run_benchmarks() -> dict[str, Any]:
    """Execute isolated and end-to-end component benchmarks."""
    setup_logging(level="INFO")
    logger.info("Starting Phase 6 Streaming Performance Benchmarks...")
    process = psutil.Process(os.getpid())

    results: dict[str, Any] = {}

    # 1. Event Validation Benchmark (N = 10,000)
    N_VAL = 10000
    validator = EventValidator()
    events = [create_synthetic_event(i) for i in range(N_VAL)]

    logger.info("1. Benchmarking Event Validation (N=%d)...", N_VAL)
    t0 = time.time()
    for ev in events:
        validator.validate_event(ev)
    t_val = time.time() - t0
    val_tps = N_VAL / t_val
    results["validation"] = {
        "count": N_VAL,
        "elapsed_sec": round(t_val, 4),
        "throughput_fps": round(val_tps, 2),
        "mean_latency_us": round((t_val / N_VAL) * 1e6, 2),
    }
    logger.info(
        "-> Validation Throughput: %.1f flows/s (%.2f µs/flow)", val_tps, (t_val / N_VAL) * 1e6
    )

    # 2. Broker Producer Benchmark (InMemory Broker, N = 10,000)
    broker = InMemoryStreamBroker()
    producer = EventProducer(
        broker=broker,
        backpressure=BackpressureController(broker, low_watermark=50000, max_depth=100000),
    )

    logger.info("2. Benchmarking Broker Producer Throughput (N=%d)...", N_VAL)
    t0 = time.time()
    for ev in events:
        producer.publish_event(ev)
    t_prod = time.time() - t0
    prod_tps = N_VAL / t_prod
    results["broker_producer"] = {
        "count": N_VAL,
        "elapsed_sec": round(t_prod, 4),
        "throughput_fps": round(prod_tps, 2),
        "mean_latency_us": round((t_prod / N_VAL) * 1e6, 2),
    }
    logger.info("-> Broker Producer Throughput: %.1f flows/s", prod_tps)

    # 3. Broker Consumer Read Throughput (N = 10,000)
    broker.create_consumer_group("netdefy:events:stream", "bench-cg", start_id="0")
    logger.info("3. Benchmarking Broker ReadGroup Throughput (N=%d)...", N_VAL)
    t0 = time.time()
    read_count = 0
    while read_count < N_VAL:
        msgs = broker.read_group("netdefy:events:stream", "bench-cg", "bench-worker", count=100)
        if not msgs:
            break
        read_count += len(msgs)
        broker.ack("netdefy:events:stream", "bench-cg", [m.message_id for m in msgs])
    t_read = time.time() - t0
    read_tps = read_count / max(1e-5, t_read)
    results["broker_consumer"] = {
        "count": read_count,
        "elapsed_sec": round(t_read, 4),
        "throughput_fps": round(read_tps, 2),
        "mean_latency_us": round((t_read / max(1, read_count)) * 1e6, 2),
    }
    logger.info("-> Broker ReadGroup Throughput: %.1f flows/s", read_tps)

    # 4. Database Alert Persistence Throughput (SQLite WAL mode, N = 2,000)
    N_ALERTS = 2000
    db_path = PROJECT_ROOT / "reports" / "bench_alerts.db"
    if db_path.exists():
        db_path.unlink()
    db_mgr = DatabaseManager(db_url=f"sqlite:///{db_path}")
    session = db_mgr.session_factory()
    repo = AlertRepository(session=session)

    alert_samples = [
        {
            "alert_id": f"alert-bench-{i:06d}",
            "event_id": f"event-bench-{i:06d}",
            "severity": "HIGH",
            "decision": "SUSPICIOUS_KNOWN",
            "threat_category": "PortScan",
            "anomaly_score": 0.985,
            "destination_port": 80 + i,
            "protocol": "TCP",
            "decision_reason": "Benchmarked portscan alert",
        }
        for i in range(N_ALERTS)
    ]

    logger.info("4. Benchmarking Alert Persistence Throughput (N=%d)...", N_ALERTS)
    t0 = time.time()
    for a in alert_samples:
        repo.create_alert(a)
    session.commit()
    t_persist = time.time() - t0
    persist_tps = N_ALERTS / t_persist
    session.close()
    if db_path.exists():
        db_path.unlink()
    results["alert_persistence"] = {
        "count": N_ALERTS,
        "elapsed_sec": round(t_persist, 4),
        "throughput_alerts_sec": round(persist_tps, 2),
        "mean_latency_ms": round((t_persist / N_ALERTS) * 1000.0, 3),
    }
    logger.info("-> Alert Persistence Throughput: %.1f alerts/s", persist_tps)

    # 5. Full End-to-End Pipeline Ingestion & Inference Benchmark (N = 1,000)
    config_path = PROJECT_ROOT / "configs" / "hybrid.yaml"
    pipe: BehavioralHybridPipeline | None = None
    if config_path.exists():
        try:
            hp = HybridInferencePipeline.from_config(config_path)
            sc_path = PROJECT_ROOT / "artifacts" / "preprocessing" / "standard_scaler.joblib"
            bld = BehavioralFeatureBuilder(
                scaler_path=sc_path if sc_path.exists() else None,
                feature_names=hp.feature_names,
            )
            pipe = BehavioralHybridPipeline(hybrid_pipeline=hp, feature_builder=bld)
            logger.info("Loaded full BehavioralHybridPipeline for E2E benchmark.")
        except Exception as e:
            logger.warning("Could not load hybrid models for benchmark: %s", e)

    N_E2E = 1000
    e2e_broker = InMemoryStreamBroker()
    e2e_prod = EventProducer(broker=e2e_broker)
    e2e_events = [create_synthetic_event(i, is_scan=(i % 10 == 0)) for i in range(N_E2E)]

    for ev in e2e_events:
        e2e_prod.publish_event(ev)

    consumer = StreamConsumer(
        broker=e2e_broker,
        pipeline=pipe,
        alert_engine=AlertEngine(),
        alert_repository=None,  # isolate inference/pipeline from disk I/O in this measurement
    )

    logger.info(
        "5. Benchmarking Full End-to-End Ingestion + Neural-Hybrid Inference (N=%d)...", N_E2E
    )
    latencies_ms: list[float] = []
    t0 = time.time()

    processed_count = 0
    while processed_count < N_E2E:
        step_t0 = time.time()
        cnt = consumer.consume_batch(count=32, block_ms=100)
        if cnt == 0:
            break
        step_elapsed_ms = (time.time() - step_t0) * 1000.0
        latencies_ms.extend([step_elapsed_ms / cnt] * cnt)
        processed_count += cnt

    t_e2e = time.time() - t0
    e2e_tps = processed_count / max(1e-5, t_e2e)
    lat_arr = np.array(latencies_ms) if latencies_ms else np.array([0.0])

    mem_rss = process.memory_info().rss / (1024 * 1024)

    results["end_to_end"] = {
        "count": processed_count,
        "elapsed_sec": round(t_e2e, 4),
        "sustained_throughput_fps": round(e2e_tps, 2),
        "p50_latency_ms": round(float(np.percentile(lat_arr, 50)), 3),
        "p95_latency_ms": round(float(np.percentile(lat_arr, 95)), 3),
        "p99_latency_ms": round(float(np.percentile(lat_arr, 99)), 3),
        "peak_rss_mb": round(mem_rss, 2),
    }

    logger.info(
        "-> End-to-End Throughput: %.1f flows/s | p50: %.2f ms | p95: %.2f ms | p99: %.2f ms | RSS: %.1f MB",
        e2e_tps,
        results["end_to_end"]["p50_latency_ms"],
        results["end_to_end"]["p95_latency_ms"],
        results["end_to_end"]["p99_latency_ms"],
        mem_rss,
    )

    # Save benchmark results
    out_dir = PROJECT_ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "phase6_benchmark_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info("Saved benchmark metrics to %s", out_file)
    return results


if __name__ == "__main__":
    run_benchmarks()
