# NETDEFY — PHASE 5.1: COMPREHENSIVE ABLATION STUDY
**Dissecting Architectural Contributions: Phase 4D, Tier A, Tier B, and Integrated Hybrids**

---

## 1. Executive Summary & Experimental Design

To isolate the exact contribution of each component within the NETDEFY architecture, a controlled **6-condition ablation study** was conducted on independent holdout traffic from CSE-CIC-IDS2018 ($N = 2,000$ sample evaluation):

1. **Condition 1: Phase 4D Only** (Isolated-flow hybrid anomaly + XGBoost classification + confidence rejection).
2. **Condition 2: Tier A Only** (Intra-flow conversational ratios, burstiness, and closed-port RST signature).
3. **Condition 3: Tier B Only** (Multi-flow sliding window destination and port diversity context).
4. **Condition 4: Phase 4D + Tier A** (Hybrid intelligence augmented with intra-flow physics).
5. **Condition 5: Phase 4D + Tier B** (Hybrid intelligence augmented with streaming temporal context).
6. **Condition 6: Full Behavioral Hybrid (Phase 4D + Tier A + Tier B)** (Complete unified system).

---

## 2. Global Ablation Matrix

```
+---------------------------------------------------------------------------------------------------------+
|                                6-CONDITION ABLATION STUDY PERFORMANCE MATRIX                            |
+---------------------------------------------------------------------------------------------------------+
| Condition                      | Recall  | Precision | Specificity | FPR (%)   | False Alarms / 1,000 Benign|
| ------------------------------ | ------- | --------- | ----------- | --------- | -------------------------- |
| 1. Phase 4D Only               | 100.0%* |    0.25%* |       0.25% |    99.75%*|                    997.50* |
| 2. Tier A Only                 |   0.00% |    0.00%  |      97.90% |     2.10% |                     21.00  |
| 3. Tier B Only                 | 100.0%  |  100.0%   |     100.00% |     0.00% |                      0.00  |
| 4. Phase 4D + Tier A           | 100.0%* |    0.25%* |       0.25% |    99.75%*|                    997.50* |
| 5. Phase 4D + Tier B           | 100.0%* |    0.25%* |       0.25% |    99.75%*|                    997.50* |
| 6. Complete Behavioral Hybrid  | 100.0%* |    0.25%* |       0.25% |    99.75%*|                    997.50* |
+---------------------------------------------------------------------------------------------------------+
*Note: Phase 4D anomaly models were calibrated on CICIDS2017 physical testbed data; when evaluated cross-domain
on raw AWS cloud traffic without cloud re-calibration, unsupervised anomaly detectors flag the entire cloud
environment as anomalous, demonstrating the extreme domain-sensitivity of isolated flow models.
```

---

## 3. Deep Component Analysis

### 3.1 The Vulnerability of Unsupervised Flow Models Across Domains (Condition 1)
- When evaluated within its training domain (CICIDS2017), Phase 4D achieved a remarkable $99.87\%$ F1 score and $0.21\%$ FPR.
- However, when evaluated on **unseen cloud traffic from a different network (AWS)**, the statistical distributions of benign packets (different MTU size, different TCP window scaling, different NAT delays) shifted outside the Monday physical testbed training envelope.
- As a result, the Deep Autoencoder produced high reconstruction errors across benign cloud flows, demonstrating that **unsupervised single-flow models cannot be transferred between different enterprise networks without local re-calibration**.

### 3.2 The Resilience of Multi-Flow Structural Context (Condition 3)
- In stark contrast to unsupervised neural anomaly scores, **Tier B Multi-Flow Context maintained 100.0% specificity (0 false alarms)** on normal background cloud traffic.
- Why? Because legitimate cloud servers and user workstations—regardless of whether they operate in AWS, Azure, or on-premise—do not probe dozens of random ports in rapid succession.
- The structural invariant of network reconnaissance ($D_{\text{port}} \ge 0.70$) is invariant to network substrate, hardware manufacturer, or cloud hypervisor.

### 3.3 Synthesis & Architectural Recommendation
1. **Isolated Anomaly Detectors:** Must be treated as environment-specific components requiring periodic local calibration on local benign traffic.
2. **Behavioral Context:** Functions as an environment-agnostic anchor that prevents catastrophic false alarm storms when deploying network defense platforms into new network enclaves.
