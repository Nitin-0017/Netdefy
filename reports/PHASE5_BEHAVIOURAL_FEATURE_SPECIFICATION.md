# NETDEFY — PHASE 5: BEHAVIOURAL FEATURE SPECIFICATION

**Document ID:** NETDEFY-SPEC-P5-001  
**Date:** 2026-11-05  
**Author:** Antigravity AI Engineering & Research Team  
**Status:** Approved & Enforced  
**Scope:** Mathematical formulas, required inputs, data availability tiers, security interpretations, and leakage safeguards for all Phase 5 behavioral and temporal features.

---

## 1. Feature Architecture Overview

Phase 5 introduces two complementary layers of behavioral feature engineering:
1. **Tier A — Advanced Intra-Flow Behavioral Dynamics:** Engineered directly from the validated 76 continuous features in the existing benchmark, extracting directional asymmetries, transfer burstiness, and protocol negotiation signatures.
2. **Tier B — Multi-Flow Contextual Aggregations:** Engineered for streaming-capable sliding windows ($\Delta t = 1\text{s}, 5\text{s}, 30\text{s}, 60\text{s}$), operating whenever external 5-tuple packet timestamps and host IP addresses are supplied.

---

## 2. Tier A: Intra-Flow Behavioral Feature Specifications (Directly Supported)

### 2.1 Directional Packet Ratio ($\rho_{\text{pkt}}$)
- **Definition:** The ratio of forward packets transmitted by the source to backward packets returned by the responder.
- **Formula:**
  $$\rho_{\text{pkt}} = \frac{\text{Total Fwd Packets}}{\text{Total Backward Packets} + 1}$$
- **Required Inputs:** `Total Fwd Packets`, `Total Backward Packets`.
- **Availability:** **Tier A (Directly Supported in Benchmark v1)**.
- **Security Interpretation:** Highly asymmetric ratios ($\rho_{\text{pkt}} \gg 1$) indicate unidirectional flooding, port scanning probes, or exfiltration; symmetric ratios ($\rho_{\text{pkt}} \approx 1$) indicate interactive protocols.
- **Leakage Risk:** Zero. Uses only flow-level summary counters.

### 2.2 Directional Byte Ratio ($\rho_{\text{byte}}$)
- **Definition:** The ratio of payload/header volume sent forward versus received backward.
- **Formula:**
  $$\rho_{\text{byte}} = \frac{\text{Total Length of Fwd Packets} + 1}{\text{Total Length of Bwd Packets} + 1}$$
- **Required Inputs:** `Total Length of Fwd Packets`, `Total Length of Bwd Packets`.
- **Availability:** **Tier A (Directly Supported in Benchmark v1)**.
- **Security Interpretation:** Extreme byte asymmetry characterizes data exfiltration (high forward, low backward) or large downloads/C2 payloads (low forward, high backward).
- **Leakage Risk:** Zero.

### 2.3 Inter-Arrival Time Burstiness Index ($\beta_{\text{burst}}$)
- **Definition:** The coefficient of variation ($c_v$) of packet inter-arrival times across the entire connection.
- **Formula:**
  $$\beta_{\text{burst}} = \frac{\text{Flow IAT Std}}{\text{Flow IAT Mean} + \epsilon} \quad (\epsilon = 10^{-6})$$
- **Required Inputs:** `Flow IAT Std`, `Flow IAT Mean`.
- **Availability:** **Tier A (Directly Supported in Benchmark v1)**.
- **Security Interpretation:**
  - $\beta_{\text{burst}} \approx 0$: Deterministic, machine-paced polling or automated beaconing.
  - $\beta_{\text{burst}} \approx 1$: Poisson arrival process (typical human web browsing).
  - $\beta_{\text{burst}} \gg 1$: Highly bursty traffic (DoS Hulk floods, automated scraping, or sudden network congestion).
- **Leakage Risk:** Zero.

### 2.4 Forward-to-Backward Inter-Arrival Asymmetry ($\Delta_{\text{IAT}}$)
- **Definition:** Relative disparity between forward transmission pace and responder acknowledgment pace.
- **Formula:**
  $$\Delta_{\text{IAT}} = \frac{\text{Fwd IAT Mean} - \text{Bwd IAT Mean}}{\max(\text{Fwd IAT Mean}, \text{Bwd IAT Mean}, 1.0)}$$
- **Required Inputs:** `Fwd IAT Mean`, `Bwd IAT Mean`.
- **Availability:** **Tier A (Directly Supported in Benchmark v1)**.
- **Security Interpretation:** Unresponsive servers or overloaded targets exhibit delayed backward IATs ($\Delta_{\text{IAT}} \ll 0$), indicative of DoS exhaustion.
- **Leakage Risk:** Zero.

### 2.5 Active-to-Duration Ratio ($\alpha_{\text{active}}$)
- **Definition:** The proportion of total flow duration during which packets were actively transmitted before going idle.
- **Formula:**
  $$\alpha_{\text{active}} = \frac{\text{Active Mean}}{\text{Flow Duration} + 1.0}$$
- **Required Inputs:** `Active Mean`, `Flow Duration`.
- **Availability:** **Tier A (Directly Supported in Benchmark v1)**.
- **Security Interpretation:** Distinguishes persistent connections (HTTP/2, SSH) from ephemeral transactions.
- **Leakage Risk:** Zero.

### 2.6 TCP Window Negotiation Disparity ($\Delta_{\text{win}}$)
- **Definition:** Normalized discrepancy between initial TCP receive window advertisements.
- **Formula:**
  $$\Delta_{\text{win}} = \frac{\text{Init\_Win\_bytes\_forward} - \text{Init\_Win\_bytes\_backward}}{\max(\text{Init\_Win\_bytes\_forward}, \text{Init\_Win\_bytes\_backward}, 1.0)}$$
- **Required Inputs:** `Init_Win_bytes_forward`, `Init_Win_bytes_backward`.
- **Availability:** **Tier A (Directly Supported in Benchmark v1)**.
- **Security Interpretation:** Asymmetric window sizes reflect differing operating system TCP stack implementations or deliberate stack fingerprint masking.
- **Leakage Risk:** Zero.

### 2.7 Flow-Level PortScan Signature Metric ($S_{\text{scan}}$)
- **Definition:** Quantitative flow counter indicator representing closed-port SYN-RST interactions.
- **Formula:**
  $$S_{\text{scan}} = \begin{cases} 1.0 & \text{if } \text{Fwd Pkts} = 1 \;\land\; \text{Bwd Pkts} = 1 \;\land\; \text{Bwd Bytes} \in [6, 40] \\ 0.0 & \text{otherwise} \end{cases}$$
- **Required Inputs:** `Total Fwd Packets`, `Total Backward Packets`, `Total Length of Bwd Packets`.
- **Availability:** **Tier A (Directly Supported in Benchmark v1)**.
- **Security Interpretation:** Empirically verified in Phase 4D: $99.77\%$ of CICIDS2017 PortScan flows exhibit exactly 1 backward packet and $99.33\%$ exhibit 6 backward bytes (TCP RST).
- **Leakage Risk:** Zero.

---

## 3. Tier B: Multi-Flow Contextual Feature Specifications (Conditionally Supported)

These features are computed over sliding temporal windows $\mathcal{W}(t, \Delta t) = [t - \Delta t, t]$:

| Feature Name | Mathematical Formula | Required Inputs | Availability Tier | Security Interpretation |
| :--- | :--- | :--- | :---: | :--- |
| **Connection Rate ($R_{\text{conn}}$)** | $R_{\text{conn}} = \frac{|\mathcal{W}(t, \Delta t)|}{\Delta t}$ | `Timestamp` | **Tier B** | Sudden surges indicate brute-force or volumetric scanning. |
| **Destination Fan-Out ($D_{\text{dst}}$)** | $D_{\text{dst}} = \frac{|\{d \mid (s, d) \in \mathcal{W}\}|}{|\mathcal{W}|}$ | `Timestamp`, `Source IP`, `Destination IP` | **Tier B** | High ratio ($D_{\text{dst}} \to 1$) confirms horizontal network scanning. |
| **Port Diversity ($D_{\text{port}}$)** | $D_{\text{port}} = \frac{|\{p \mid (s, d, p) \in \mathcal{W}\}|}{|\mathcal{W}|}$ | `Timestamp`, `Source IP`, `Destination Port` | **Tier B** | High ratio confirms vertical port scanning against a single target. |
| **Connection Burstiness ($\beta_{\text{stream}}$)** | $\beta_{\text{stream}} = \frac{\sigma(\Delta t_{\text{inter-flow}})}{\mu(\Delta t_{\text{inter-flow}}) + \epsilon}$ | `Timestamp`, `Source IP` | **Tier B** | Differentiates periodic automated C2 heartbeats from random user activity. |

---

## 4. Pipeline Integration & Anti-Leakage Rules

1. **Chronological Precedence:** In any sliding window $\mathcal{W}(t, \Delta t)$, only flows with timestamps $\tau \le t$ may enter the computation. No future flow may influence a historical window.
2. **Fallback Guarantee:** When `Timestamp` or `Source IP` is missing, Tier B features default safely to neutral null representations (`0.0` or `None`), and the system continues evaluation using Tier A intra-flow behavioral features.
3. **No Target Leakage:** Neither ground-truth `Label` nor downstream model predictions may be used in behavioral feature generation.
