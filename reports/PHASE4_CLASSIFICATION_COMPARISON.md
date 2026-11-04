# NETDEFY — PHASE 4: MULTI-MODEL ARCHITECTURE COMPARISON
## Anomaly Detection Engines (4A & 4B) vs. Supervised Classifier (4C)

**Project:** NETDEFY — Network Defense Intelligence  
**Document:** Cross-Paradigm Model Architecture & Evaluation Report  
**Author:** Senior Machine Learning Research Engineer & Network Security Data Scientist  
**Status:** **COMPLETE & FULLY VERIFIED**

---

## 1. Executive Comparison & Paradigm Alignment

The three models implemented in Phase 4 solve distinct, complementary operational roles in the NETDEFY defense architecture:

| System Component | Model Type | Core Objective | Training Supervision | Output Format |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 4A Engine** | Isolation Forest | Zero-day / Novel Anomaly Detection | 100% Unsupervised (100k Monday Benign) | Continuous anomaly score |
| **Phase 4B Engine** | Deep Autoencoder | Manifold Reconstruction Error | 100% Unsupervised (100k Monday Benign) | Continuous MSE reconstruction error |
| **Phase 4C Engine** | XGBoost Classifier | Known Attack Category Attribution | Supervised Multiclass (30k Tue/Wed flows) | Class probabilities + Rejection |

> [!IMPORTANT]
> **Task-Aware Evaluation Principle:**
> Isolation Forest and Autoencoder flag whether a flow deviates from normal network behavior without specifying attack taxonomy. In contrast, XGBoost identifies known attack categories (e.g., DoS Hulk, SSH-Patator) learned during midweek training. When evaluated on Thursday/Friday holdout traffic, all 7 attack families (PortScan, DDoS, Bot, Web attacks) are entirely unseen by XGBoost. Thus, the supervised classifier must reject them as `UNKNOWN` rather than forcing incorrect attribution.

---

## 2. Performance Breakdown: Known Midweek Validation

On the 20,000-flow validation partition (where all attack categories were observed during training):

| Metric | Isolation Forest (4A) | Deep Autoencoder (4B) | XGBoost Classifier (4C) |
| :--- | :--- | :--- | :--- |
| **Primary Metric** | ROC-AUC: `0.8297` | ROC-AUC: `0.8736` | **Accuracy: `99.67%`** |
| **Precision-Recall**| PR-AUC: `0.6778` | PR-AUC: `0.7789` | **Macro F1: `0.9759`** |
| **Balanced Accuracy**| — | — | **Balanced Acc: `98.68%`** |
| **Log Loss** | — | — | **Log Loss: `0.0156`** |

On known classes, XGBoost provides near-perfect attribution and high macro F1 across rare attacks like Heartbleed and SSH-Patator.

---

## 3. Performance Breakdown: Chronological Holdout Test Traffic (50,000 flows)

On Thursday/Friday holdout traffic (containing 12,526 attacks across 7 unseen attack categories):

| Evaluation Dimension | Isolation Forest (4A) | Deep Autoencoder (4B) | XGBoost Classifier (4C) |
| :--- | :--- | :--- | :--- |
| **Detection of Unseen Attacks** | `1.32%` (165 TP at p99.0) | **`26.70%` (3,344 TP at p99.0)** | Closed: Forced misclassification<br>Open: **Rejected as UNKNOWN** |
| **DDoS Recall** | `2.99%` | **`60.58%`** | Classified as UNKNOWN or Hulk |
| **BENIGN Classification** | FPR: `1.38%` | FPR: `2.40%` | **`99.74%` Benign Recall** |
| **Inference Throughput** | `209,926 flows/s` | **`391,261 flows/s`** | **`359338.4 flows/s`** |
| **Model Size on Disk** | `181.0 KB` | **`66.5 KB`** | **`1688.0 KB`** |

---

## 4. Architectural Synthesis for Phase 5 Hybrid Defense

The empirical findings from Phase 4 establish the clear blueprint for Phase 5:
1. **Tier 1 (Anomaly Screening):** Deep Autoencoder filters all incoming network flows with sub-millisecond latency (0.0026 ms), detecting large volumetric anomalies and novel attacks (60.58% DDoS detection).
2. **Tier 2 (Threat Attribution):** Supervised XGBoost classifies flows flagged as anomalous into known threat categories (DoS Hulk, GoldenEye, Patator).
3. **Tier 3 (Zero-Day Triaging):** Flows with high reconstruction error but rejected as `UNKNOWN` by XGBoost are quarantined as potential novel zero-day threats for analyst inspection.
