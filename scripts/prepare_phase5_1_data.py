"""NETDEFY — Phase 5.1 Independent Benchmark Preparation Pipeline.

Ingests raw CSE-CIC-IDS2018 external dataset, audits data integrity, maps canonical
feature schemas, enforces strict chronological splitting (Zero-Leakage), and outputs
clean benchmark partitions in data/benchmark/phase5_1/.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from netdefy.utils.logging import setup_logging

logger = logging.getLogger(__name__)

# Canonical mapping from CSE-CIC-IDS2018 column names to NETDEFY feature schema
COLUMN_MAPPING: dict[str, str] = {
    "Dst Port": "Destination Port",
    "Tot Fwd Pkts": "Total Fwd Packets",
    "Tot Bwd Pkts": "Total Backward Packets",
    "TotLen Fwd Pkts": "Total Length of Fwd Packets",
    "TotLen Bwd Pkts": "Total Length of Bwd Packets",
    "Fwd Pkt Len Max": "Fwd Packet Length Max",
    "Fwd Pkt Len Min": "Fwd Packet Length Min",
    "Fwd Pkt Len Mean": "Fwd Packet Length Mean",
    "Fwd Pkt Len Std": "Fwd Packet Length Std",
    "Bwd Pkt Len Max": "Bwd Packet Length Max",
    "Bwd Pkt Len Min": "Bwd Packet Length Min",
    "Bwd Pkt Len Mean": "Bwd Packet Length Mean",
    "Bwd Pkt Len Std": "Bwd Packet Length Std",
    "Flow Byts/s": "Flow Bytes/s",
    "Flow Pkts/s": "Flow Packets/s",
    "Fwd IAT Tot": "Fwd IAT Total",
    "Bwd IAT Tot": "Bwd IAT Total",
    "Fwd Header Len": "Fwd Header Length",
    "Bwd Header Len": "Bwd Header Length",
    "Pkt Len Min": "Min Packet Length",
    "Pkt Len Max": "Max Packet Length",
    "Pkt Len Mean": "Packet Length Mean",
    "Pkt Len Std": "Packet Length Std",
    "Pkt Len Var": "Packet Length Variance",
    "FIN Flag Cnt": "FIN Flag Count",
    "SYN Flag Cnt": "SYN Flag Count",
    "RST Flag Cnt": "RST Flag Count",
    "PSH Flag Cnt": "PSH Flag Count",
    "ACK Flag Cnt": "ACK Flag Count",
    "URG Flag Cnt": "URG Flag Count",
    "ECE Flag Cnt": "ECE Flag Count",
    "Pkt Size Avg": "Average Packet Size",
    "Fwd Seg Size Avg": "Avg Fwd Segment Size",
    "Bwd Seg Size Avg": "Avg Bwd Segment Size",
    "Fwd Byts/b Avg": "Fwd Avg Bytes/Bulk",
    "Fwd Pkts/b Avg": "Fwd Avg Packets/Bulk",
    "Fwd Blk Rate Avg": "Fwd Avg Bulk Rate",
    "Bwd Byts/b Avg": "Bwd Avg Bytes/Bulk",
    "Bwd Pkts/b Avg": "Bwd Avg Packets/Bulk",
    "Bwd Blk Rate Avg": "Bwd Avg Bulk Rate",
    "Init Fwd Win Byts": "Init_Win_bytes_forward",
    "Init Bwd Win Byts": "Init_Win_bytes_backward",
    "Fwd Act Data Pkts": "act_data_pkt_fwd",
    "Fwd Seg Size Min": "min_seg_size_forward",
    "Fwd Pkts/s": "Fwd Packets/s",
    "Bwd Pkts/s": "Bwd Packets/s",
    "Subflow Fwd Pkts": "Subflow Fwd Packets",
    "Subflow Fwd Byts": "Subflow Fwd Bytes",
    "Subflow Bwd Pkts": "Subflow Bwd Packets",
    "Subflow Bwd Byts": "Subflow Bwd Bytes",
}


def prepare_benchmark_phase5_1() -> dict[str, Any]:
    """Execute end-to-end data preparation and chronological splitting for Phase 5.1."""
    setup_logging(level=logging.INFO)
    logger.info("Initializing Phase 5.1 Data Preparation & Integrity Pipeline...")

    root_dir = Path(__file__).resolve().parent.parent
    raw_file = root_dir / "data" / "external" / "csecicids2018_thursday_01_03_2018.csv"
    benchmark_dir = root_dir / "data" / "benchmark" / "phase5_1"
    interim_dir = root_dir / "data" / "interim" / "phase5_1"

    benchmark_dir.mkdir(parents=True, exist_ok=True)
    interim_dir.mkdir(parents=True, exist_ok=True)

    if not raw_file.exists():
        raise FileNotFoundError(f"Raw external dataset missing at {raw_file}")

    # 1. Chunked reading and cleaning
    logger.info("Reading and sanitizing raw CSV from %s in chunks...", raw_file)
    chunks: list[pd.DataFrame] = []
    total_raw_rows = 0
    header_artifacts = 0

    chunk_size = 50000
    for chunk in pd.read_csv(raw_file, chunksize=chunk_size, low_memory=False):
        total_raw_rows += len(chunk)
        # Filter header repeats
        is_header = chunk["Label"] == "Label"
        header_artifacts += int(is_header.sum())
        clean_chunk = chunk[~is_header].copy()

        # Rename columns to canonical names
        clean_chunk.rename(columns=COLUMN_MAPPING, inplace=True)
        chunks.append(clean_chunk)

    df_all = pd.concat(chunks, ignore_index=True)
    logger.info(
        "Loaded %d raw rows (discarded %d embedded header artifacts; %d valid flows)",
        total_raw_rows,
        header_artifacts,
        len(df_all),
    )

    # 2. Timestamp parsing and chronological sorting
    logger.info("Parsing timestamps and enforcing chronological ordering...")
    df_all["datetime"] = pd.to_datetime(
        df_all["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors="coerce"
    )
    null_ts_count = int(df_all["datetime"].isna().sum())
    if null_ts_count > 0:
        logger.warning("Found %d rows with unparseable timestamps; dropping", null_ts_count)
        df_all = df_all[df_all["datetime"].notna()].copy()

    # Convert to Unix epoch seconds (unit-agnostic timedelata division)
    df_all["epoch_timestamp"] = (
        (df_all["datetime"] - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)
    ).astype("int64")

    # Sort strictly chronologically
    df_all.sort_values(by="epoch_timestamp", ascending=True, inplace=True, kind="stable")
    df_all.reset_index(drop=True, inplace=True)

    t_min = df_all["datetime"].min()
    t_max = df_all["datetime"].max()
    logger.info(
        "Chronological traffic span: %s -> %s (%.2f hours)",
        t_min,
        t_max,
        (t_max - t_min).total_seconds() / 3600,
    )

    # 3. Numeric sanitation & precision cast
    logger.info("Casting numeric features and handling non-finite values...")
    # Standardize label: Infilteration -> Infiltration
    df_all["Label"] = df_all["Label"].replace({"Infilteration": "Infiltration"}).astype(str)
    df_all["Timestamp"] = df_all["Timestamp"].astype(str)
    df_all["Protocol"] = (
        pd.to_numeric(df_all["Protocol"], errors="coerce").fillna(0).astype(np.int32)
    )
    df_all["Destination Port"] = (
        pd.to_numeric(df_all["Destination Port"], errors="coerce").fillna(0).astype(np.int32)
    )

    # Identify numeric columns
    metadata_cols = [
        "Timestamp",
        "datetime",
        "epoch_timestamp",
        "Protocol",
        "Label",
        "Destination Port",
    ]
    feature_cols = [c for c in df_all.columns if c not in metadata_cols]

    for col in feature_cols:
        df_all[col] = pd.to_numeric(df_all[col], errors="coerce")
        # Replace inf with nan, then fill with 0.0 or median
        df_all[col] = df_all[col].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        df_all[col] = df_all[col].astype(np.float32)

    # 4. Chronological Splitting Strategy (Zero Temporal Leakage)
    # Split 1: Calibration (First 2 hours: 01:00:00 to 03:00:00)
    # Split 2: Validation (Next 4 hours: 03:00:00 to 07:00:00)
    # Split 3: Test Holdout (Final 6 hours: 07:00:00 to 13:00:00)
    logger.info("Applying strict chronological splits...")
    t_split1 = pd.Timestamp("2018-03-01 03:00:00")
    t_split2 = pd.Timestamp("2018-03-01 07:00:00")

    mask_cal = df_all["datetime"] < t_split1
    mask_val = (df_all["datetime"] >= t_split1) & (df_all["datetime"] < t_split2)
    mask_test = df_all["datetime"] >= t_split2

    df_cal = df_all[mask_cal].copy()
    df_val = df_all[mask_val].copy()
    df_test = df_all[mask_test].copy()

    # Verify temporal non-overlap
    max_cal_ts = df_cal["epoch_timestamp"].max()
    min_val_ts = df_val["epoch_timestamp"].min()
    max_val_ts = df_val["epoch_timestamp"].max()
    min_test_ts = df_test["epoch_timestamp"].min()

    assert max_cal_ts <= min_val_ts, "Temporal leakage between calibration and validation!"
    assert max_val_ts <= min_test_ts, "Temporal leakage between validation and test!"
    logger.info("Temporal leakage verification passed! (max_cal <= min_val <= max_val <= min_test)")

    # 5. Export clean parquet benchmarks
    cal_path = benchmark_dir / "calibration.parquet"
    val_path = benchmark_dir / "validation.parquet"
    test_path = benchmark_dir / "test.parquet"

    # Drop intermediate datetime column for parquet serialization
    save_cols = [c for c in df_all.columns if c != "datetime"]

    logger.info("Writing benchmark partitions to %s...", benchmark_dir)
    df_cal[save_cols].to_parquet(cal_path, index=False)
    df_val[save_cols].to_parquet(val_path, index=False)
    df_test[save_cols].to_parquet(test_path, index=False)

    # 6. Generate Manifest
    manifest = {
        "dataset_name": "CSE-CIC-IDS2018-Phase5.1",
        "source": "AWS Open Data (s3://cse-cic-ids2018/)",
        "original_file": "Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv",
        "scenario": "Infiltration with internal Nmap PortScan",
        "acquisition_date": "2026-11-05",
        "total_clean_flows": len(df_all),
        "feature_count": len(feature_cols),
        "split_strategy": "Chronological (Zero-Leakage)",
        "partitions": {
            "calibration": {
                "file": "calibration.parquet",
                "rows": len(df_cal),
                "time_range": f"{df_cal['datetime'].min()} -> {df_cal['datetime'].max()}",
                "class_distribution": df_cal["Label"].value_counts().to_dict(),
            },
            "validation": {
                "file": "validation.parquet",
                "rows": len(df_val),
                "time_range": f"{df_val['datetime'].min()} -> {df_val['datetime'].max()}",
                "class_distribution": df_val["Label"].value_counts().to_dict(),
            },
            "test": {
                "file": "test.parquet",
                "rows": len(df_test),
                "time_range": f"{df_test['datetime'].min()} -> {df_test['datetime'].max()}",
                "class_distribution": df_test["Label"].value_counts().to_dict(),
            },
        },
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    manifest_path = benchmark_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Manifest saved to %s", manifest_path)
    return manifest


if __name__ == "__main__":
    res = prepare_benchmark_phase5_1()
    print(json.dumps(res, indent=2))
