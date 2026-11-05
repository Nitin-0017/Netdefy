# NETDEFY — PHASE 5.1: PRE-VALIDATION AUDIT REPORT
**Systematic Forensic Audit of Phase 5 Behavioural Architecture, Mathematical Formulations, Threshold Provenance, and Empirical Reproducibility**

---

## 1. Audit Scope & Executive Summary

- **Audit Date:** 2026-11-05
- **Auditor:** Senior Research Scientist & Independent AI Quality Assurance Lead
- **Target Architecture:** NETDEFY Phase 5 Behavioural & Temporal Intelligence Engine (`src/netdefy/behaviour/`)
- **Git Commit Audited:** `bc2a10e` (`Add behaviour engine`)

### Executive Summary:
Phase 5 introduced a two-tiered behavioural network intelligence architecture designed to transcend isolated flow-level classification:
1. **Tier A (Intra-flow Dynamics):** Mathematical features computed directly from continuous physical counters present in the CICIDS2017 benchmark.
2. **Tier B (Multi-flow Streaming Context):** A streaming architecture featuring memory-bounded sliding temporal windows, EWMA rate burst detection, and horizontal/vertical scan fan-out analytics.

This audit establishes the mathematical formulations, threshold provenance, dataset dependencies, and reproducibility status of all Phase 5 claims prior to independent generalization testing.

---

## 2. Feature Formulations & Implementation Audit

Every behavioural metric in `src/netdefy/behaviour/` was audited line-by-line against its theoretical specification:

### 2.1 Tier A: Intra-Flow Metrics (`feature_builder.py`)

1. **Directional Packet Ratio ($\rho_{\text{pkt}}$):**
   $$\rho_{\text{pkt}} = \frac{\text{Total Fwd Packets}}{\text{Total Backward Packets} + 1.0}$$
   - *Implementation:* `src/netdefy/behaviour/feature_builder.py:96`
   - *Verification:* Exact match. `unscale=True` correctly inverts z-score normalization using `FeatureScaler` parameters.

2. **Directional Byte Ratio ($\rho_{\text{byte}}$):**
   $$\rho_{\text{byte}} = \frac{\text{Total Length of Fwd Packets} + 1.0}{\text{Total Length of Bwd Packets} + 1.0}$$
   - *Implementation:* `src/netdefy/behaviour/feature_builder.py:97`
   - *Verification:* Exact match.

3. **IAT Burstiness Index ($\beta_{\text{burst}}$):**
   $$\beta_{\text{burst}} = \frac{\text{Flow IAT Std}}{\text{Flow IAT Mean} + 10^{-6}}$$
   - *Implementation:* `src/netdefy/behaviour/feature_builder.py:100`
   - *Verification:* Exact match. Correct coefficient of variation formulation.

4. **Forward-to-Backward IAT Directional Asymmetry ($\Delta_{\text{IAT}}$):**
   $$\Delta_{\text{IAT}} = \frac{\text{Fwd IAT Mean} - \text{Bwd IAT Mean}}{\max(\text{Fwd IAT Mean}, \text{Bwd IAT Mean}, 1.0)}$$
   - *Implementation:* `src/netdefy/behaviour/feature_builder.py:103-104`
   - *Verification:* Exact match. Normalization bounds output in $[-1.0, 1.0]$.

5. **Active-to-Duration Ratio ($\alpha_{\text{active}}$):**
   $$\alpha_{\text{active}} = \min\left(1.0, \frac{\text{Active Mean}}{\text{Flow Duration} + 1.0}\right)$$
   - *Implementation:* `src/netdefy/behaviour/feature_builder.py:107`
   - *Verification:* Exact match. Capped at $1.0$.

6. **TCP Window Negotiation Disparity ($\Delta_{\text{win}}$):**
   $$\Delta_{\text{win}} = \frac{\text{Init\_Win\_bytes\_forward} - \text{Init\_Win\_bytes\_backward}}{\max(|\text{Init\_Win\_bytes\_forward}|, |\text{Init\_Win\_bytes\_backward}|, 1.0)}$$
   - *Implementation:* `src/netdefy/behaviour/feature_builder.py:110-111`
   - *Verification:* Exact match.

7. **Closed-Port RST Scan Signature ($S_{\text{scan}}$):**
   $$S_{\text{scan}} = \begin{cases} 1.0 & \text{if } \text{Fwd Pkts} \in [0.8, 1.2] \;\land\; \text{Bwd Pkts} \in [0.8, 1.2] \;\land\; \text{Bwd Bytes} \in [4.0, 40.0] \\ 0.0 & \text{otherwise} \end{cases}$$
   - *Implementation:* `src/netdefy/behaviour/feature_builder.py:114-118`
   - *Verification:* Exact match. Floats are bounded within $[0.8, 1.2]$ to accommodate floating-point unscaling inaccuracies for integer values of $1.0$.

---

### 2.2 Tier B: Multi-Flow Metrics (`window_aggregator.py`, `destination_diversity.py`, `burst_detection.py`)

1. **Sliding Window Aggregation:**
   $$\mathcal{W}(t, \Delta t) = \{e \in \mathcal{E} \mid t - \Delta t \le e.\text{timestamp} \le t\}$$
   - *Implementation:* `src/netdefy/behaviour/window_aggregator.py:58-62`
   - *Verification:* Online left-pruning on `deque(maxlen=10000)` enforces memory bounds and $\mathcal{O}(1)$ amortized pruning.

2. **Horizontal Scan Fan-Out ($D_{\text{dst}}$):**
   $$D_{\text{dst}} = \frac{|\{d \mid (s, d) \in \mathcal{W}\}|}{|\mathcal{W}|}$$
   - *Threshold:* $n_{\text{conn}} \ge 10 \;\land\; u_{\text{ips}} \ge 8 \;\land\; D_{\text{dst}} \ge 0.70$.
   - *Implementation:* `src/netdefy/behaviour/destination_diversity.py:74-78`

3. **Vertical Scan Port Fan-Out ($D_{\text{port}}$):**
   $$D_{\text{port}} = \frac{|\{p \mid (s, d, p) \in \mathcal{W}\}|}{|\mathcal{W}|}$$
   - *Threshold:* $n_{\text{conn}} \ge 10 \;\land\; u_{\text{ports}} \ge 8 \;\land\; D_{\text{port}} \ge 0.70 \;\land\; (u_{\text{ips}} \le 3 \lor u_{\text{ips}} == 0)$.
   - *Implementation:* `src/netdefy/behaviour/destination_diversity.py:81-86`

4. **EWMA Rate Surge Z-Score ($Z_{\text{burst}}$):**
   $$\mu_t = (1 - \alpha)\mu_{t-1} + \alpha R_t, \quad \sigma_t^2 = (1 - \alpha)(\sigma_{t-1}^2 + \alpha(R_t - \mu_{t-1})^2)$$
   $$Z_{\text{burst}} = \frac{R_t - \mu_t}{\sqrt{\sigma_t^2 + 10^{-4}}}$$
   - *Threshold:* $Z_{\text{burst}} \ge 3.0 \;\land\; R_t \ge 20.0\text{ conns/sec}$.
   - *Implementation:* `src/netdefy/behaviour/burst_detection.py:44-59`

---

## 3. Threshold Provenance & Development Datasets

| Threshold / Parameter | Value | Selection Provenance | Vulnerability / Bias |
| :--- | :---: | :--- | :--- |
| **$S_{\text{scan}}$ Packet Bounds** | $\text{Fwd} = 1, \text{Bwd} = 1$ | Fitted to Friday CICIDS2017 PortScan traffic | Overfitted to SYN scan tools that receive RST; blind to UDP or stealth FIN/Xmas scans. |
| **$S_{\text{scan}}$ Byte Bounds** | $4 \le \text{Bwd Bytes} \le 40$ | Fitted to CICFlowMeter TCP RST header representation ($6$ bytes) | May misclassify legitimate closed port connection rejections as malicious. |
| **$n_{\text{conn}}$ (Min Scan Connections)** | $10$ connections | Standard Zeek/Bro heuristic | May fail to detect slow, distributed, or low-rate stealth scans ($< 10$ probes/window). |
| **$D_{\text{port}}$ (Vertical Fan-Out)** | $\ge 0.70$ | Empirical heuristic | May alert on legitimate host vulnerability assessment or network management tools. |
| **$D_{\text{dst}}$ (Horizontal Fan-Out)** | $\ge 0.70$ | Empirical heuristic | May alert on legitimate subnet service discovery (e.g. SSDP, mDNS, ARP sweep). |
| **$Z_{\text{burst}}$ (Rate Z-Score)** | $\ge 3.0$ | Classical statistical outlier boundary | Prone to false alarms during legitimate scheduled automated backup or sync jobs. |

---

## 4. Empirical Claims Audit & Reproducibility Assessment

### 4.1 Claim: Tier A PortScan Recall ($99.33\%$)
- **Status:** **REPRODUCIBLE ON BENCHMARK v1 TEST SET.**
- **Verification:** Evaluated on `data/benchmark/v1/test.parquet` ($N = 50,000$):
  - Total PortScan flows: $6,837$
  - Flows matching $S_{\text{scan}}$: $6,791$
  - Exact measured recall: **$99.3272\%$ ($6,791 / 6,837$)**.
  - Benign flows matching $S_{\text{scan}}$: $1,678$ out of $37,474$ (**$4.4778\%$ false positive rate**).
- **Audit Caveat:** This $99.33\%$ recall was measured on the same CICIDS2017 dataset from which the 6-byte RST characteristic was originally observed. Whether real-world scanning outside CICIDS2017 produces this exact signature remains unproven.

### 4.2 Claim: Tier B "100.0% Detection & 0.0% False Positive Rate"
- **Status:** **CRITICALLY UNVERIFIED ON REAL NETWORK TRAFFIC.**
- **Forensic Discovery:** The reports (`PHASE5_PORTSCAN_INVESTIGATION.md`, `PHASE5_FINAL_REPORT.md`) referenced $100.0\%$ detection and $0.0\%$ FPR for Tier B multi-flow sliding windows.
- **Audit Finding:** In `tests/integration/test_behaviour_integration.py:test_behavioural_pipeline_with_streaming_temporal_events`, this was tested exclusively against a **synthetic 12-event fixture**:
  ```python
  events = [NetworkEvent(timestamp=1000.0 + i, source_ip="192.168.1.100", ...) for i in range(12)]
  ```
- **Rigorous Scientific Judgment:** A synthetic integration test with 12 handcrafted events **does not constitute empirical proof of 0% FPR**. In real networks with diverse background traffic, service discovery protocols (SSDP, mDNS, LDAP, NetBIOS) and web browser connection pools frequently open connections across multiple ports or endpoints. The claim that Tier B exhibits 0% FPR is an artifact of synthetic testing and must be tested against real, independent multi-flow network captures.

### 4.3 Claim: Latency ($71.50$ µs Tier A, $4.56$ ms End-to-End)
- **Status:** **REPRODUCIBLE ON APPLE M3.**
- **Verification:** Evaluated via `scripts/evaluate_behaviour.py`. Tier A extraction completed in $71.50$ µs/flow. End-to-end multi-model inference completed in $4.56$ ms/flow.

---

## 5. Pre-Validation Conclusion & Immediate Mandate

1. **Tier A** works as implemented on CICIDS2017 benchmark data, but has a known **$4.48\%$ baseline false positive rate** on benign traffic that requires external validation.
2. **Tier B** streaming logic is syntactically sound and passes unit tests, but has **never been evaluated on independent real-world network traffic containing genuine timestamps and IP addresses**.
3. **Phase 5.1 Mandate:** An independent dataset containing verified 5-tuple packet/flow headers and genuine timestamps must be acquired to scientifically stress-test both Tier A and Tier B.
