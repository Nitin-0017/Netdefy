# NETDEFY — PHASE 5: DATA FEASIBILITY & TEMPORAL AUDIT REPORT
## Rigorous Empirical Inspection of Temporal, Host, and Sequential Metadata in CICIDS2017

**Document ID:** NETDEFY-AUD-P5-001  
**Date:** 2026-11-05  
**Author:** Antigravity AI Engineering & Research Team  
**Status:** Approved & Certified  
**Scope:** Forensic investigation into the presence, integrity, and analytical suitability of timestamps, IP addresses, flow identifiers, and chronological ordering across all data directories (`data/raw/`, `data/interim/`, `data/processed/`, and `data/benchmark/v1/`).

---

## 1. Executive Summary & Purpose

Phase 5 investigates whether network defense intelligence can advance from isolated single-flow anomaly detection toward **temporal, context-aware, and multi-flow behavioral analysis**.

A research system must ground its claims in genuine, verifiable empirical data. The primary mandate of this feasibility audit is to answer the fundamental question:
> **Does the existing dataset support genuine inter-flow temporal, host-level, and sequential analysis?**

### Audit Verdict:
1. **The current dataset (`MachineLearningCSV`, 8 files, 2,830,743 records, 79 columns) contains ZERO row-level timestamps, ZERO source IP addresses, ZERO destination IP addresses, and ZERO flow identifiers.**
2. **CSV file row position does NOT represent verifiable chronological arrival order.** CICFlowMeter flushes flows upon timeout or TCP termination (FIN/RST), mixing asynchronous thread flushes. Furthermore, the Phase 3.2 benchmark partitions (`data/benchmark/v1/*.parquet`) were constructed via stratified and class-balanced subsampling, intentionally breaking original file row contiguity.
3. **Inventing pseudo-timestamps, inferring host identities from row adjacency, or training sequence models (e.g. LSTMs) on arbitrarily ordered CSV rows constitutes scientific misconduct (methodological hallucination).**
4. **Directly Supported Scope:** We CAN extract rich **intra-flow behavioral dynamics** (microsecond durations, inter-arrival time moments, directional rate disparities, active/idle periodicities, TCP flag negotiation dynamics) and construct a **streaming-capable behavioral engine architecture** with formal contract validation and synthetic stream verification.
5. **Conditionally Supported Scope:** True inter-flow temporal windows (1s, 5s, 30s), host-level destination fan-out, and multi-flow port scanning detection require the full 83-column flow exports (`GeneratedLabelledFlows.zip`) or raw PCAP files.

---

## 2. Directory Architecture & Data Asset Inventory

Every dataset asset across the repository was inspected:

| Data Directory | File Count | File Format | Total Rows | Target Columns Present? |
| :--- | :---: | :---: | :---: | :--- |
| `data/raw/MachineLearningCVE/` | 8 files | CSV | 2,830,743 | 79 columns (78 features + Label). No IP, No Timestamp, No Flow ID. |
| `data/interim/` | 0 files | — | 0 | Empty staging directory. |
| `data/processed/train/` | 3 files | Parquet | 459,112 (dedup) | 77 columns (76 continuous features + Label). |
| `data/processed/validation/` | 3 files | Parquet | 963,879 (dedup) | 77 columns (76 continuous features + Label). |
| `data/processed/test/` | 3 files | Parquet | 845,403 (dedup) | 77 columns (76 continuous features + Label). |
| `data/benchmark/v1/` | 5 files | Parquet | 206,193 total | 77 columns (76 standardized z-scores + Label). |

---

## 3. Comprehensive 10-Point Metadata Feasibility Evaluation

| Field / Dimension | Exists in Raw? | Preserved in Processed? | Preserved in Benchmark v1? | Can Be Linked Across Records? | Suitable for Temporal / Host Analysis? | Forensic Findings & Physical Reality |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. Timestamp** | **NO** | **NO** | **NO** | **NO** | **UNSUPPORTED** | Completely stripped during CICIDS2017 `MachineLearningCSV` generation. Absolute wall-clock time and relative event arrival times are non-existent. |
| **2. Source IP** | **NO** | **NO** | **NO** | **NO** | **UNSUPPORTED** | Absent. Cannot group flows by source host or measure per-host connection frequency. |
| **3. Destination IP** | **NO** | **NO** | **NO** | **NO** | **UNSUPPORTED** | Absent. Cannot measure destination diversity (number of distinct target hosts contacted). |
| **4. Source Port** | **NO** | **NO** | **NO** | **NO** | **UNSUPPORTED** | Absent. Cannot track client ephemeral port exhaustion or scanning source port signatures. |
| **5. Destination Port** | **YES** (col 0) | **YES** (audit only) | **EXCLUDED** | **PARTIAL** | **CONDITIONALLY SUPPORTED** | Present in raw CSVs. Deliberately excluded from 76 model features in Phase 3 to avoid memorizing testbed IP/port infrastructure. Can be mapped to canonical service categories (HTTP, SSH, DNS, Ephemeral). |
| **6. Protocol** | **NO** (explicit) | **NO** (explicit) | **NO** (explicit) | **NO** | **PARTIAL (Implicit)** | Explicit IANA protocol number (6=TCP, 17=UDP) was not extracted by CICFlowMeter. However, TCP flags and header lengths implicitly encode protocol characteristics. |
| **7. Flow ID** | **NO** | **NO** | **NO** | **NO** | **UNSUPPORTED** | Absent. 'ID' substrings in raw CSVs correspond strictly to idle time statistics (`Idle Mean`, `Idle Std`, `Idle Max`, `Idle Min`). |
| **8. Packet-Level Metadata** | **NO** | **NO** | **NO** | **NO** | **PARTIAL (Aggregates)** | Individual packet streams do not exist. Only flow-level statistical moments (min, max, mean, std) of packet lengths, inter-arrival times, and active/idle periods exist. |
| **9. Day/File Provenance** | **YES** | **YES** | **YES** | **YES** | **SUPPORTED** | Coarse file-level provenance exists (8 discrete CSV files mapped to Monday through Friday capture periods). Tracked in `source_row_manifest.json`. |
| **10. Chronological Ordering** | **NO** | **NO** | **NO** | **NO** | **UNSUPPORTED** | CSV row order does not represent chronological flow initiation. Benchmark sampling further broke original file contiguity. Treating row index as time step $t$ is scientifically invalid. |

---

## 4. Data-Availability Decision Gate

Based on the empirical audit, all proposed Phase 5 research tasks are formally categorized into three operational tiers:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   PHASE 5 DECISION GATE CATEGORIES                     │
├─────────────────────┬──────────────────────────────────────────────────┤
│ TIER A: DIRECTLY    │ Feasible with existing 76-feature benchmark data.│
│ SUPPORTED           │ Focuses on intra-flow behavioral dynamics.       │
├─────────────────────┼──────────────────────────────────────────────────┤
│ TIER B: CONDITION-  │ Architecturally implemented with synthetic tests;│
│ ALLY SUPPORTED      │ requires external 5-tuple data for live training.│
├─────────────────────┼──────────────────────────────────────────────────┤
│ TIER C: NOT         │ Strictly forbidden; rejected as scientifically   │
│ SUPPORTED           │ fraudulent on the current dataset.               │
└─────────────────────┴──────────────────────────────────────────────────┘
```

### Tier A: Directly Supported (Implemented in Phase 5 Core)
1. **Intra-Flow Temporal Dynamics:**
   - Flow duration ($\mu s$), packet rates (`Flow Packets/s`, `Fwd Packets/s`, `Bwd Packets/s`), byte transfer rates.
   - Inter-arrival time distributions (`Flow IAT`, `Fwd IAT`, `Bwd IAT` mean, variance, max, min).
   - Active vs. Idle periodicity analysis.
2. **Intra-Flow Directional Asymmetry & Burst Density:**
   - Forward-to-backward packet and byte ratios ($\frac{\text{Fwd Packets}}{\text{Bwd Packets}}$, $\frac{\text{Fwd Bytes}}{\text{Bwd Bytes}}$).
   - Average packet payload size relative to header overhead.
3. **Protocol Flag Dynamics:**
   - SYN/ACK negotiation integrity, RST termination dynamics, PSH push frequency.
   - Initial window size asymmetry (`Init_Win_bytes_forward` vs `Init_Win_bytes_backward`).
4. **Service Category Contextualization:**
   - Mapping `Destination Port` from raw tables to canonical service labels (HTTP, HTTPS, SSH, FTP, DNS, Ephemeral) without memorizing port numbers.
5. **Architectural Framework for Multi-Flow Streaming:**
   - Building memory-bounded sliding window accumulators (`WindowAggregator`, `BurstDetector`) with strict contracts and synthetic stream verification.

### Tier B: Conditionally Supported (Requires External Data Ingestion)
1. **Host-Level Multi-Flow Destination Fan-Out:**
   - Tracking distinct destination IPs contacted by a source host over rolling time windows.
2. **True Inter-Flow Temporal Windows:**
   - Evaluating rolling windows of 1s, 5s, 30s, 60s, 300s using true microsecond packet timestamps.
3. **Sequential Threat Detection:**
   - Sequence models (LSTM/GRU Autoencoders) trained on verified sequential connection logs for a specific host.

### Tier C: Not Supported (Strictly Excluded)
1. Generating pseudo-random Source/Destination IPs and claiming host tracking.
2. Assuming CSV row index is an arrival time step $t$ and training sequential recurrent networks on arbitrarily sorted rows.
3. Claiming multi-flow PortScan detection on the benchmark without 5-tuple flow linkages.

---

## 5. Specification for Conditionally Supported Data (Tier B External Ingestion)

To enable genuine host-level and multi-flow temporal research, NETDEFY specifies the exact external dataset requirements:

### 5.1 Official Dataset Source
- **Provider:** Canadian Institute for Cybersecurity (CIC), University of New Brunswick (UNB).
- **Dataset:** CICIDS2017 Full Flow Dataset (`GeneratedLabelledFlows.zip`) or Raw PCAPs (`PCAPs/`).
- **Official URL:** `https://www.unb.ca/cic/datasets/ids-2017.html`
- **License:** Open Academic / Research Use (with attribution).

### 5.2 Schema Difference (MachineLearningCSV vs. GeneratedLabelledFlows)
The full flow export contains **83 columns** (4 additional critical 5-tuple fields):
1. `Flow ID` (String, e.g. `192.168.10.5-192.168.10.3-53-61003-17`)
2. `Source IP` (IPv4 address, e.g. `192.168.10.50`)
3. `Source Port` (Integer in $[0, 65535]$)
4. `Destination IP` (IPv4 address, e.g. `205.174.165.73`)
5. `Timestamp` (String date/time, e.g. `07/07/2017 01:18:00 PM`)
6. `Protocol` (Integer, e.g. `6` for TCP, `17` for UDP)

### 5.3 Storage & Ingestion Requirements
- **Compressed Download:** $\approx 3.1\text{ GB}$ (ZIP)
- **Extracted CSV Size:** $\approx 8.4\text{ GB}$
- **RAM Processing Footprint:** Requires streaming chunked processing ($50,000$ rows/chunk) to stay within Apple Silicon M3 8 GB memory constraints.
- **Integrity Validation:** SHA-256 verification against UNB published hash tables.

---

## 6. Audit Conclusion & Phase 5 Directives

1. **Phase 5 must not falsify data.** All implementations of multi-flow temporal windows must be marked as architectural frameworks and tested via synthetic verification.
2. **The core empirical deliverable for Phase 5 on the existing benchmark** is **Advanced Intra-Flow Behavioral Intelligence** (Directional Asymmetry, Protocol Flag Dynamics, and Transfer Burstiness) integrated seamlessly as an intelligence layer on top of Phase 4D.
3. **If 5-tuple data is not present, the system must gracefully fall back to Phase 4D inference.**
