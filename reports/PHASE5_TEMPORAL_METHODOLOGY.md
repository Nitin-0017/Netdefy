# NETDEFY — PHASE 5: TEMPORAL & BEHAVIOURAL METHODOLOGY
**Advanced Network Behaviour Analysis, Multi-Flow Context, and Sequential Threat Detection**

---

## 1. Executive Summary & Scientific Rationale

Traditional network intrusion detection architectures evaluate network flows as isolated, independent, identically distributed (i.i.d.) feature vectors. While single-flow evaluation is computationally convenient, it ignores the foundational reality of modern computer networking: **network threats are inherently sequential, stateful, and contextual processes**. An advanced persistent threat (APT), volumetric denial-of-service, or automated reconnaissance campaign unfolds over time across multiple interrelated flows, hosts, and protocols.

Phase 5 introduces **Temporal & Behavioural Network Intelligence** into NETDEFY, establishing a scientifically grounded bridge between isolated flow-level anomaly detection (Phases 4A–4D) and host-level sequential context awareness.

This document formalizes the mathematical specifications, temporal feasibility boundaries, memory-bounded sliding window algorithms, and chronological validation frameworks governing Phase 5.

---

## 2. Empirical Feasibility Audit & The 5-Tuple Reality

### 2.1 The Data Reality of MachineLearningCSV
A rigorous engineering audit conducted across all eight raw CSV files comprising the CICIDS2017 `MachineLearningCSV` dataset ($2,830,743$ records) revealed a fundamental data reality:
- **Missing Columns:** `Timestamp`, `Source IP`, `Destination IP`, `Source Port`, and `Flow ID` **do not exist** in the dataset provided.
- **Available Columns:** Exactly 78 continuous numerical flow statistics plus `Destination Port` and `Label`.
- **Benchmark Splitting Integrity:** Benchmark v1 partitions (`oneclass_train.parquet`, `classifier_train.parquet`, `validation.parquet`, `test.parquet`) were constructed using stratified sampling to preserve rare attack representation (e.g. Heartbleed, Infiltration, Web Attacks). Stratified sampling breaks physical CSV row adjacency.
- **CICFlowMeter Asynchrony:** Even in raw captures with timestamps, CICFlowMeter generates flow records asynchronously upon TCP FIN/RST or bidirectional activity timeout ($120\text{s}$). Physical arrival of flows at an exporter does not follow packet arrival chronology.

### 2.2 Rejection of Synthetic Hallucination
Many machine learning publications synthesize artificial timestamps by linearly spacing rows (e.g. assigning $t = i \times 1\text{ms}$ to row $i$) or inventing synthetic IP addresses. In NETDEFY, **we strictly reject synthetic temporal hallucination**:
1. Arbitrary row ordering in stratified datasets does not represent chronological traffic.
2. Fabricating host identities creates artificial clustering artifacts that inflate model performance metrics without generalizability to real networks.
3. Scientifically valid systems must explicitly separate features verifiable on isolated flow records from features requiring real packet headers.

---

## 3. Two-Tiered Behavioral Intelligence Architecture

To resolve this reality with scientific rigor, Phase 5 establishes a **two-tiered behavioral intelligence architecture**:

```
+-----------------------------------------------------------------------------+
|                               NETDEFY ENGINE                                |
+-----------------------------------------------------------------------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
         [ Tier A: Intra-Flow ]                 [ Tier B: Multi-Flow ]
     Directly Supported in Benchmark       Conditionally Supported via 5-Tuple
  -------------------------------------  -------------------------------------
  • Directional Packet Ratio (ρ_pkt)     • Sliding Time Windows (W(t, Δt))
  • Directional Byte Ratio (ρ_byte)      • Connection Arrival Rate (R_conn)
  • IAT Burstiness Index (β_burst)       • Destination Fan-Out (D_dst)
  • IAT Directional Asymmetry (Δ_IAT)    • Vertical Port Fan-Out (D_port)
  • Active Duration Ratio (α_active)     • EWMA Rate Surge Z-Score (Z_burst)
  • TCP Window Disparity (Δ_win)         • LRU Host Behavioral Profiles
  • Closed-Port RST Signature (S_scan)   • Handshake Completion Tracking
```

### 3.1 Tier A: Advanced Intra-Flow Behavioral Dynamics (Directly Supported)
Tier A extracts non-linear physical transmission dynamics directly from the 76 continuous flow counters in the existing verified benchmark, requiring no external timestamps or IP addresses:

1. **Directional Packet Ratio ($\rho_{\text{pkt}}$):**
   $$\rho_{\text{pkt}} = \frac{\text{Total Fwd Packets}}{\text{Total Backward Packets} + 1}$$
   Measures conversational balance. $\rho_{\text{pkt}} \gg 1$ characterizes unidirectional probing or exfiltration.

2. **Directional Byte Ratio ($\rho_{\text{byte}}$):**
   $$\rho_{\text{byte}} = \frac{\text{Total Length of Fwd Packets} + 1}{\text{Total Length of Bwd Packets} + 1}$$
   Identifies volume asymmetries (e.g., massive outbound payload versus minimal inbound ACK).

3. **IAT Burstiness Index ($\beta_{\text{burst}}$):**
   $$\beta_{\text{burst}} = \frac{\text{Flow IAT Std}}{\text{Flow IAT Mean} + 10^{-6}}$$
   Measures packet pacing variance. $\beta_{\text{burst}} \approx 0$ indicates deterministic automated polling (beaconing); $\beta_{\text{burst}} \gg 1$ reflects pulsed or congestion-induced bursts.

4. **Forward-to-Backward IAT Asymmetry ($\Delta_{\text{IAT}}$):**
   $$\Delta_{\text{IAT}} = \frac{\text{Fwd IAT Mean} - \text{Bwd IAT Mean}}{\max(\text{Fwd IAT Mean}, \text{Bwd IAT Mean}, 1.0)}$$
   Exposes server processing latency or responsiveness degradation under load.

5. **Active-to-Duration Ratio ($\alpha_{\text{active}}$):**
   $$\alpha_{\text{active}} = \frac{\text{Active Mean}}{\text{Flow Duration} + 1.0}$$
   Differentiates continuous bulk transfers from idle-heavy persistent connections.

6. **TCP Window Negotiation Disparity ($\Delta_{\text{win}}$):**
   $$\Delta_{\text{win}} = \frac{\text{Init\_Win\_bytes\_forward} - \text{Init\_Win\_bytes\_backward}}{\max(|\text{Init\_Win\_bytes\_forward}|, |\text{Init\_Win\_bytes\_backward}|, 1.0)}$$
   Captures OS TCP stack negotiation mismatches and fingerprint anomalies.

7. **Closed-Port RST Scan Signature ($S_{\text{scan}}$):**
   $$S_{\text{scan}} = \begin{cases} 1.0 & \text{if } \text{Fwd Pkts} = 1 \;\land\; \text{Bwd Pkts} = 1 \;\land\; \text{Bwd Bytes} \in [6, 40] \\ 0.0 & \text{otherwise} \end{cases}$$
   Captures the empirical physical reality that $99.77\%$ of PortScan flows in CICIDS2017 consist of a single TCP SYN eliciting a 6-byte TCP RST packet from closed target ports.

---

## 4. Tier B: Multi-Flow Streaming Context Architecture

When operating in live production or on PCAP datasets containing 5-tuple headers, NETDEFY activates Tier B multi-flow sliding window analytics.

### 4.1 Memory-Bounded Sliding Window Aggregator
The `WindowAggregator` maintains an in-memory double-ended queue ($\mathcal{Q}$) bounded by maximum event capacity ($N_{\max} = 10,000$) and temporal duration ($\Delta t \in \{1\text{s}, 5\text{s}, 30\text{s}, 60\text{s}\}$).
- **Online Eviction:** Upon arrival of event $e_t$ at timestamp $t$, expired events where $t_i < t - \Delta t$ are pruned from the left of the deque in $\mathcal{O}(1)$ amortized time.
- **Bounded Memory:** Bounded deque prevents uncontrolled heap growth during volumetric DoS floods.

### 4.2 Destination and Port Diversity Engine
The `DestinationDiversityAnalyzer` evaluates structural fan-out:
- **Horizontal Network Scan:** One source IP probes $k \ge 8$ distinct destination IPs with fan-out ratio $D_{\text{dst}} = \frac{|\{d \mid (s, d) \in \mathcal{W}\}|}{|\mathcal{W}|} \ge 0.70$.
- **Vertical Port Scan:** One source IP probes $p \ge 8$ distinct destination ports on a single target with port fan-out ratio $D_{\text{port}} = \frac{|\{p \mid (s, d, p) \in \mathcal{W}\}|}{|\mathcal{W}|} \ge 0.70$.

### 4.3 EWMA Connection Rate & Burst Detection
Connection rate $R_{\text{conn}} = \frac{|\mathcal{W}|}{\Delta t}$ is monitored via online Exponentially Weighted Moving Average (EWMA):
$$\mu_t = (1 - \alpha)\mu_{t-1} + \alpha R_t, \quad \sigma^2_t = (1 - \alpha)(\sigma^2_{t-1} + \alpha(R_t - \mu_{t-1})^2)$$
Burst anomaly score is quantified via instantaneous standard score:
$$Z_{\text{burst}} = \frac{R_t - \mu_t}{\sigma_t + \epsilon}$$
A burst alert is triggered when $Z_{\text{burst}} \ge 3.0$ and $R_t \ge 20.0 \text{ conns/sec}$.

### 4.4 LRU Host Behavioral Profiles
Host historical state is tracked using `HostProfileManager` backed by an `OrderedDict` LRU cache (default $10,000$ active host profiles). Each profile accumulates rolling byte volumes, top contacted ports, unique peer sets, and anomaly occurrences, automatically evicting stale host profiles when cache bounds are reached.

---

## 5. Temporal Causality, Validation & Leakage Prevention

Chronological validity in sequential ML systems requires strict adherence to physical time:

1. **Monotonicity & Jitter Bounds:**
   The `TemporalValidator` inspects event streams to enforce non-decreasing timestamps. In distributed capture taps, out-of-order delivery is tolerated only within bounded network jitter $\tau_{\max} \le 5.0\text{s}$; backward jumps exceeding tolerance raise `TemporalValidationError`.
2. **Zero Temporal Leakage Guarantee:**
   In offline benchmarking with sequential splits, `check_temporal_leakage` enforces:
   $$\max(T_{\text{train}}) \le \min(T_{\text{test}})$$
   Any overlap or future-information leakage raises immediate validation failure.
3. **Graceful Pipeline Degradation:**
   When input data lacks timestamps or host IPs, `BehavioralHybridPipeline` transparently executes Tier A intra-flow evaluations, records `INSUFFICIENT_CONTEXT` for Tier B, and yields clean, deterministic predictions without crashing or synthesizing fake context.

---

## 6. Summary of Architectural Impact

By formalizing the separation between flow-level physics (Tier A) and multi-flow sequential context (Tier B), NETDEFY achieves:
- **Research Integrity:** Uncompromised honesty regarding raw dataset boundaries without fabrication.
- **Operational Readiness:** Production capability to ingest live packet streams and leverage sliding-window context when available.
- **Targeted Threat Disambiguation:** Precision identification of scanning and burst behaviors that elude isolated flow classifiers.
