# NETDEFY — PHASE 5.1: DATA INTEGRITY & FORENSIC AUDIT REPORT
**Forensic Analysis, Artifact Cleaning, Schema Mapping, and Quality Verification of CSE-CIC-IDS2018**

---

## 1. Provenance & Artifact Integrity

- **Dataset Identifier:** CSE-CIC-IDS2018-Phase5.1
- **Acquisition Source:** AWS Open Data Registry (`https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com/`)
- **Raw File:** `Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv`
- **Acquisition Timestamp:** 2026-11-05
- **Local Location:** `data/external/csecicids2018_thursday_01_03_2018.csv`
- **File Size:** $107,851,006$ bytes ($102.85$ MB)
- **Verified SHA-256 Checksum:**
  `b0534c5d7d8b41e03df71c6966c995d116a8ed28e61f377c8b14cdf5d28f4edf`

---

## 2. Forensic Quality & Data Cleaning Audit

### 2.1 Embedded Header Artifacts
- **Detection:** In line with known distributed extraction bugs in CICFlowMeter-V3 Spark clusters, the raw CSV file contained repeated header rows interspersed throughout the file.
- **Audit Count:** Exactly **$25$ embedded header rows** (`Label == 'Label'`) were discovered and quarantined.
- **Sanitized Row Total:** $331,125 - 25 = 331,100$ valid network traffic flow records.

### 2.2 Temporal Integrity & Distribution
- **Field Name:** `Timestamp`
- **Raw Format:** String format `DD/MM/YYYY HH:MM:SS` (e.g., `01/03/2018 08:17:11`).
- **Parsed Range:** `2018-03-01 01:00:00` through `2018-03-01 12:59:59` ($12.00$ continuous hours of network telemetry).
- **Null / Unparseable Timestamps:** **$0$ ($0.00\%$)**. Every single record contains a valid, monotonic wall-clock timestamp.
- **Chronological Sorting:** The dataset was ordered strictly by epoch timestamp ($T_i \le T_{i+1}$) using stable sort.

### 2.3 Non-Finite Values (NaN, Inf, -Inf)
- **Infinite Values:** The rate calculation features (`Flow Byts/s` and `Flow Pkts/s`) in CICFlowMeter yield mathematical infinity ($\infty$) when `Flow Duration == 0`.
- **Handling:** All infinite values were replaced with `np.nan` and filled with $0.0$, followed by casting all continuous metrics to `np.float32`.
- **Final Non-Finite Count:** **$0$ across all columns**.

### 2.4 Label Harmonization & Class Distribution
- **Raw Labels Observed:**
  - `Benign`: $238,037$ flows ($71.89\%$)
  - `Infilteration`: $93,063$ flows ($28.11\%$)
- **Correction:** The raw label string was harmonized from the dataset's typographical error `Infilteration` to canonical `Infiltration`.
- **Attack Composition:** The Infiltration scenario in CSE-CIC-IDS2018 captures multi-stage adversarial activity: initial payload download, C2 connection establishment, and **broad internal Nmap port scanning** across $6,071$ unique destination ports.

---

## 3. Feature Schema Alignment with NETDEFY Benchmark

The 80 raw columns in CSE-CIC-IDS2018 were mapped to NETDEFY's canonical 76 continuous features:
- `Tot Fwd Pkts` $\to$ `Total Fwd Packets`
- `Tot Bwd Pkts` $\to$ `Total Backward Packets`
- `TotLen Fwd Pkts` $\to$ `Total Length of Fwd Packets`
- `TotLen Bwd Pkts` $\to$ `Total Length of Bwd Packets`
- `Init Fwd Win Byts` $\to$ `Init_Win_bytes_forward`
- `Init Bwd Win Byts` $\to$ `Init_Win_bytes_backward`
- `Fwd Act Data Pkts` $\to$ `act_data_pkt_fwd`
- `Fwd Seg Size Min` $\to$ `min_seg_size_forward`
- `Dst Port` $\to$ `Destination Port` (stored as `int32` for service mapping).

All 76 continuous features required by Phase 4D's Isolation Forest, Autoencoder, and XGBoost are **$100\%$ present and aligned**.

---

## 4. Benchmark Partitions Summary

```
+-----------------------------------------------------------------------------+
|               PHASE 5.1 INDEPENDENT BENCHMARK PARTITIONS                    |
+-----------------------------------------------------------------------------+
| Partition      | File Name           | Record Count | Benign Flows | Infil Flows |
| -------------- | ------------------- | ------------ | ------------ | ----------- |
| Calibration    | calibration.parquet |  80,423 flows| 46,549 (58%) | 33,874 (42%)|
| Validation     | validation.parquet  |  84,935 flows| 64,498 (76%) | 20,437 (24%)|
| Test (Holdout) | test.parquet        | 165,742 flows|126,990 (77%) | 38,752 (23%)|
+-----------------------------------------------------------------------------+
| TOTAL          |                     | 331,100 flows|238,037 (72%) | 93,063 (28%)|
+-----------------------------------------------------------------------------+
```

Data integrity audit is complete, verified, and certified for research evaluation.
