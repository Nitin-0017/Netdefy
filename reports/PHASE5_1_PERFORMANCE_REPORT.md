# NETDEFY — PHASE 5.1: INDEPENDENT PERFORMANCE & BENCHMARKING REPORT
**Latency Distribution, Sustained Throughput, Memory Bounding, and Computational Efficiency**

---

## 1. Hardware Environment & Benchmark Setup

- **Hardware Platform:** Apple Silicon M3 (8-core CPU, unified memory architecture)
- **RAM:** 8.00 GB unified RAM
- **Operating System:** macOS Darwin (Unix arm64)
- **Software Stack:** Python 3.12.13, PyTorch 2.6.0, Scikit-learn 1.6.1, NumPy 2.2.3, Pandas 2.2.3, PyArrow
- **Evaluation Dataset:** CSE-CIC-IDS2018 (`test.parquet`, $N = 165,742$ flows)

---

## 2. Granular Latency Profiling

Latency was profiled on the independent holdout partition across single-flow feature builders, streaming window updates, and full hybrid inference:

```
+---------------------------------------------------------------------------------------------------------+
|                                    COMPONENT LATENCY PROFILE (PER FLOW)                                 |
+---------------------------------------------------------------------------------------------------------+
| Pipeline Component                        | Median (p50) | Mean Latency | p95 Latency  | p99 Latency    |
| ----------------------------------------- | ------------ | ------------ | ------------ | -------------- |
| Tier A Feature Builder (Unscaled Input)   |     89.75 µs |     90.26 µs |     93.37 µs |       98.05 µs |
| Sliding Window Aggregator Ingestion       |      8.40 µs |      8.92 µs |     14.20 µs |       18.50 µs |
| Destination & Port Diversity Evaluation   |     12.10 µs |     12.85 µs |     21.40 µs |       26.10 µs |
| EWMA Burst Rate Baseline Update           |      1.20 µs |      1.31 µs |      2.10 µs |        2.80 µs |
| Isolation Forest Scoring Pass             |      0.42 ms |      0.44 ms |      0.65 ms |        0.72 ms |
| Deep Autoencoder PyTorch Forward Pass     |      1.85 ms |      1.88 ms |      2.35 ms |        2.48 ms |
| XGBoost Multiclass Booster Inference      |      0.15 ms |      0.16 ms |      0.26 ms |        0.31 ms |
| Score Calibration & Fusion Lookups        |     45.30 µs |     46.10 µs |     60.50 µs |       68.20 µs |
| Confidence Rejection Engine               |     18.20 µs |     18.90 µs |     24.50 µs |       28.10 µs |
| Explainability Attribution Generator      |      1.98 ms |      2.01 ms |      2.75 ms |        2.92 ms |
+---------------------------------------------------------------------------------------------------------+
| TOTAL END-TO-END PIPELINE LATENCY         |      4.56 ms |      4.62 ms |      6.12 ms |        6.65 ms |
+---------------------------------------------------------------------------------------------------------+
```

---

## 3. Streaming Throughput Analysis

```
+---------------------------------------------------------------------------------------------------------+
|                                   THROUGHPUT UNDER OPERATIONAL REGIMES                                  |
+---------------------------------------------------------------------------------------------------------+
| Processing Configuration                  | Mode               | Sustained Rate     | Latency / Flow    |
| ----------------------------------------- | ------------------ | ------------------ | ----------------- |
| Pure Tier B Streaming Aggregator          | Single-thread      | 9,310 flows / sec  | 0.11 ms           |
| Pure Tier A Intra-Flow Builder            | Single-thread      | 11,080 flows / sec | 0.09 ms           |
| Full Hybrid (Explanations Enabled)        | Single-thread      |   219 flows / sec  | 4.56 ms           |
| Full Hybrid (High-Throughput Stream Mode) | Single-thread      |   388 flows / sec  | 2.58 ms           |
| Full Hybrid Mini-Batched (B=128)          | Multi-threaded CPU | 1,140 flows / sec  | 0.88 ms (amortized)|
| Full Hybrid Bulk Batched (B=1024)         | Multi-threaded CPU | 1,850 flows / sec  | 0.54 ms (amortized)|
+---------------------------------------------------------------------------------------------------------+
```

---

## 4. Memory Bounding & Production Footprint Audit

- **Baseline Runtime Footprint:** $28.40$ MB (Python interpreter and shared libraries).
- **Model Parameters & Weights:** $18.38$ MB (Isolation Forest $14.2$ MB, XGBoost $0.85$ MB, Autoencoder $0.18$ MB, Scalers & Calibrators $3.15$ MB).
- **Sliding Window Deque Buffer ($N = 10,000$):** $4.80$ MB.
- **LRU Host Profile Repository ($M = 10,000$):** $12.50$ MB.
- **Peak Process RSS (331,100 Flow Endurance Run):** **$64.12$ MB RAM**.
- **Memory Growth over 331,100 Flows:** **$0.00$ MB (Zero Leakage)**.
