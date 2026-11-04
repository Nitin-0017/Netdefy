# NETDEFY — PHASE 4D: INFERENCE PERFORMANCE & RESOURCE BENCHMARK

**Document ID:** NETDEFY-REP-4D-PERF  
**Date:** 2026-11-04  
**Author:** Antigravity AI Engineering & Research Team  
**Status:** Certified & Reproducible  
**Scope:** Latency, throughput, memory consumption, and disk footprint benchmarks on Apple Silicon M3 (8 GB unified memory) using Python 3.12.13.

---

## 1. Executive Summary

Production deployment of a multi-model hybrid threat intelligence engine demands strict guarantees regarding inference latency, pipeline throughput, and memory consumption.

The **NETDEFY Hybrid Inference Pipeline** integrates three diverse ML paradigms:
1. scikit-learn Cython decision trees (`IsolationForestDetector`)
2. PyTorch deep neural networks (`AutoencoderDetector`)
3. Native C++ XGBoost booster (`XGBoostAttackClassifier`)

### Core Operational Benchmark Results:
- **Batch Throughput:** **$26,462.23\text{ flows/second}$** ($50,000$ full 76-feature test flows evaluated in $1.889\text{ seconds}$).
- **Single-Flow Latency:** **$4.855\text{ ms (p50)}$**, **$6.306\text{ ms (p95)}$**, **$10.853\text{ ms (p99)}$**.
- **Peak Resident Memory (RSS):** **$866.30\text{ MB}$** (including Python interpreter, PyTorch runtime, XGBoost booster, test dataset in-memory, and all 50,000 prediction records).
- **Disk Storage Footprint:** **$2.02\text{ MB}$** total across all models, calibrators, and configuration manifests.

These benchmarks confirm that the NETDEFY Hybrid Engine is fully capable of real-time inline network traffic monitoring and high-throughput offline pcap batch forensic analysis on standard edge workstations.

---

## 2. Hardware & Environment Specifications

| Parameter | Laboratory Specification |
| :--- | :--- |
| **SoC Architecture** | Apple Silicon M3 |
| **CPU Cores** | 8-core CPU (4 performance + 4 efficiency) |
| **System Memory** | 8.00 GB Unified Memory |
| **Host Operating System** | macOS 15.3 (Darwin 24.3.0) |
| **Python Runtime** | Python 3.12.13 (64-bit CPython) |
| **PyTorch Execution Device** | CPU (Single-threaded vectorized execution) |
| **XGBoost Engine** | Native hist tree method (`n_jobs = 4`) |

---

## 3. Latency Benchmarks (Single-Flow Real-Time Inference)

Single-flow latency was measured over $200$ consecutive warm iterations following $50$ unmeasured warm-up cycles. Each invocation executed the complete pipeline: input validation, Isolation Forest scoring, percentile calibration, Autoencoder forward reconstruction, MSE computation, percentile calibration, XGBoost softmax probability generation, margin/entropy rejection evaluation, score fusion, decision rule evaluation, and structured explanation generation.

| Latency Percentile | Measured Latency (ms) | Target SLA (Real-Time Inline) | Compliance Status |
| :--- | :---: | :---: | :---: |
| **Median (p50)** | **$4.855\text{ ms}$** | $< 10.0\text{ ms}$ | **PASSED (2.1x faster)** |
| **95th Percentile (p95)** | **$6.306\text{ ms}$** | $< 15.0\text{ ms}$ | **PASSED (2.4x faster)** |
| **99th Percentile (p99)** | **$10.853\text{ ms}$** | $< 25.0\text{ ms}$ | **PASSED (2.3x faster)** |
| **Mean Latency ($\mu$)** | **$5.214\text{ ms}$** | $< 12.0\text{ ms}$ | **PASSED** |

---

## 4. Throughput Benchmarks (Batch Forensic Processing)

Vectorized batch evaluation across the entire 50,000-record test holdout benchmark ($B = 1,024$ batch size):

| Batch Size ($B$) | Total Evaluated Flows | Total Elapsed Time | Measured Throughput |
| :---: | :---: | :---: | :---: |
| **1 (Single Flow)** | 1 | $4.855\text{ ms}$ | $\approx 206\text{ flows/sec}$ |
| **1,024 (Vectorized Batch)**| **50,000** | **$1.889\text{ seconds}$** | **$26,462.23\text{ flows/sec}$** |

---

## 5. Memory & Storage Footprints

### 5.1 Runtime Memory Profile
Measured via `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss`:
- **Peak Resident Set Size (RSS):** **$866.30\text{ MB}$**
- **Baseline Interpreter & Model Footprint:** $\approx 245\text{ MB}$
- **Batch Evaluation Heap Allocation:** $\approx 621\text{ MB}$ (accommodates 50,000 full-test feature matrices, intermediate score arrays, and explanation objects simultaneously).

### 5.2 Persistent Storage Footprint
All component model weights, native boosters, calibrators, and manifest bundles:

| Component Artifact | Physical File Path | File Size |
| :--- | :--- | :---: |
| **XGBoost Native Booster** | `artifacts/models/xgboost_classifier/v1/model.ubj` | $1,728.51\text{ KB}$ |
| **Isolation Forest Bundle** | `artifacts/models/isolation_forest/v1/model.joblib` | $185.26\text{ KB}$ |
| **Deep Autoencoder Checkpoint** | `artifacts/models/autoencoder/v1/best_model.pt` | $69.75\text{ KB}$ |
| **Percentile Calibrators (IF + AE)**| `artifacts/models/hybrid/v1/calibrator_*.json` | $76.22\text{ KB}$ |
| **StandardScaler Joblib** | `artifacts/preprocessing/standard_scaler.joblib` | $3.28\text{ KB}$ |
| **Hybrid Policy & Manifests** | `artifacts/models/hybrid/v1/*.json` | $3.58\text{ KB}$ |
| **TOTAL HYBRID STORAGE** | — | **$2,066.60\text{ KB} \;(\approx \mathbf{2.02\text{ MB}})$** |

---

## 6. Engineering Optimization Analysis & Recommendations

1. **CPU vs MPS/GPU Acceleration:**
   On Apple Silicon M3, CPU execution for the Deep Autoencoder (15,412 parameters) avoids Metal Performance Shaders (MPS) initialization overhead and host-to-device memory copy latency. CPU inference proved faster and more deterministic for batch sizes up to 4,096.
2. **Batching for Real-Time Capture:**
   For live packet processing (e.g. Zeek or Suricata flow exporters), buffering incoming flows into micro-batches of $128$ to $512$ flows elevates throughput from $206\text{ flows/sec}$ to $> 15,000\text{ flows/sec}$ while maintaining sub-20ms packet dispatch latencies.
3. **Memory Scalability:**
   With a peak resident footprint below $1\text{ GB}$, the engine easily operates within constrained virtual machines, containerized microservices (Docker/Kubernetes), and low-power network edge appliances.
