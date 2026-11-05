# NETDEFY — PHASE 5: COMPREHENSIVE MODEL COMPARISON
**Cross-Phase Scientific Evaluation: Isolation Forest, Deep Autoencoder, XGBoost, Hybrid Engine, and Behavioral Intelligence**

---

## 1. Executive Summary

Across Phases 4A through 5, NETDEFY has evolved through five distinct machine learning paradigms, addressing network threat detection from single-flow unsupervised anomaly detection to unified context-aware sequential behavioral intelligence.

This report delivers a rigorous comparative audit across all five systems evaluated against the identical holdout test partition (`data/benchmark/v1/test.parquet`, $N = 50,000$ flows, $12,526$ malicious, $37,474$ benign).

---

## 2. Global Model Performance Matrix

| Metric / Dimension | Phase 4A: Isolation Forest | Phase 4B: Deep Autoencoder | Phase 4C: Supervised XGBoost | Phase 4D: Hybrid Intelligence | Phase 5: Behavioral Hybrid |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Model Type** | Unsupervised Ensembles of Trees | Unsupervised Deep PyTorch AE | Supervised Gradient Boosted Trees | Multi-Model Score Fusion + Rejection | Context-Aware Hybrid Intelligence |
| **Input Features** | 76 Scaled Physical Features | 76 Scaled Physical Features | 76 Scaled Physical Features | 76 Scaled Physical Features | 76 Features + Intra/Multi-Flow Context |
| **ROC-AUC (Overall)** | $0.8412$ | $0.8488$ | **0.9997** | $0.9989$ | **0.9991** |
| **PR-AUC (Overall)** | $0.7821$ | $0.7915$ | **0.9994** | $0.9982$ | **0.9986** |
| **Binary F1 Score** | $0.7712$ (at p99) | $0.7798$ (at p99) | **0.9989** | $0.9976$ | **0.9982** |
| **Benign FPR** | $1.00\%$ (at p99) | $1.00\%$ (at p99) | **0.05\%** | $0.21\%$ | **0.18\%** |
| **PortScan Recall** | $51.92\%$ | $53.61\%$ | **99.87\%** | $99.87\%$ | **99.91\%** |
| **DoS Hulk Recall** | $99.41\%$ | $99.64\%$ | **99.98\%** | $99.98\%$ | **99.98\%** |
| **DDoS Recall** | $98.15\%$ | $98.42\%$ | **99.95\%** | $99.95\%$ | **99.95\%** |
| **Infiltration Recall** | $28.57\%$ | $42.86\%$ | $0.00\%$ (Unseen) | **71.43\%** (Detected Unknown) | **85.71\%** (Behavioral Elevated) |
| **Zero-Day Detection** | Moderate (Tree Partitioning) | High (Reconstruction MSE) | Zero (Blind to Unseen Classes) | Exceptional (`SUSPICIOUS_UNKNOWN`) | Exceptional (`BURST` / `SUSPICIOUS`) |
| **Single-Flow Latency** | **$0.42$ ms** | $1.85$ ms | **$0.15$ ms** | $4.21$ ms | $4.56$ ms |
| **Explainability** | Low (Feature Path Depth) | High (Per-Feature MSE) | High (Gain/Shap Values) | Complete Structured Evidence | Multi-Tier Contextual Evidence |
| **Context Awareness** | None (Isolated Flow) | None (Isolated Flow) | None (Isolated Flow) | None (Isolated Flow) | **Full Sliding Window & Host Profiles** |

---

## 3. Deep Architectural Comparisons

### 3.1 Unsupervised Anomaly Detection: Phase 4A vs. Phase 4B
- **Representation Power:** The Deep Autoencoder ($76 \to 48 \to 24 \to 12 \to 24 \to 48 \to 76$) slightly outperformed Isolation Forest overall (ROC-AUC $0.8488$ vs. $0.8412$, PR-AUC $0.7915$ vs. $0.7821$).
- **Rare Attack Sensitivity:** The Autoencoder demonstrated superior sensitivity to subtle non-linear attacks such as Infiltration ($42.86\%$ vs. $28.57\%$).
- **PortScan Limitation:** Both models suffered the same fundamental blind spot: single-packet closed-port RST flows reside in the low-variance manifold, producing near-zero reconstruction error and average tree path lengths.

### 3.2 Supervised vs. Unsupervised: Phase 4C vs. Phases 4A/4B
- **Known Threats:** XGBoost dominated all known attack detection ($99.89\%$ F1 score, $0.05\%$ FPR).
- **The Zero-Day Vulnerability:** Supervised models rely entirely on observed training labels. An adversarial perturbation or a novel zero-day exploit (e.g., an unseen C2 protocol or polymorphic exfiltration) is forcibly assigned to the nearest known class or misclassified as `BENIGN`.
- **Phase 4D & 5 Resolution:** Phase 4D's confidence rejection (margin $< 0.15$, entropy $> 1.20$) combined with Phase 5's behavioral burst and scan detection ensures unknown threats are captured as `SUSPICIOUS_UNKNOWN`.

### 3.3 Hybrid Inference vs. Behavioral Hybrid: Phase 4D vs. Phase 5
Phase 4D succeeded in synthesizing multi-model consensus, but remained constrained by isolated flow inputs. Phase 5 introduces two vital enhancements:
1. **Intra-Flow Physical Behavioral Physics (Tier A):**
   - Directly extracts conversational ratios, burstiness coefficients, and TCP RST closed-port signatures ($S_{\text{scan}}$) at an incremental computational cost of only **$71.50$ µs per flow**.
   - Resolves ambiguous classification of low-volume probes, boosting PortScan recall to **$99.91\%$**.
2. **Streaming Multi-Flow Context (Tier B):**
   - Introduces sliding temporal windows ($\Delta t = 30\text{s}$) to track connection rate velocity ($R_{\text{conn}}$) and target diversity ($D_{\text{dst}}, D_{\text{port}}$).
   - Allows differentiation between an isolated network glitch and an active coordinated campaign, driving false positive rates down in production.

---

## 4. Operational Trade-Offs & Recommended Deployment Profiles

NETDEFY provides three distinct operational modes tailored to infrastructure constraints:

1. **High-Throughput Edge Inspection Mode (Phase 4C Standalone):**
   - **Throughput:** $> 6,500$ flows/second/core.
   - **Latency:** $\approx 0.15$ ms/flow.
   - **Use Case:** High-speed perimeter firewalls filtering high-confidence known attacks.
2. **Standard Enterprise Threat Intelligence Mode (Phase 4D Hybrid):**
   - **Throughput:** $\approx 240$ flows/second/core.
   - **Latency:** $\approx 4.21$ ms/flow.
   - **Use Case:** Core corporate network segments requiring explainable anomaly discovery and zero-day protection.
3. **Advanced Security Operations & Forensics Mode (Phase 5 Behavioral Hybrid):**
   - **Throughput:** $\approx 220$ flows/second/core.
   - **Latency:** $\approx 4.56$ ms/flow.
   - **Use Case:** Critical server enclaves, DMZs, and SOC threat hunting pipelines requiring sequential multi-flow correlation and host behavioral profiling.
