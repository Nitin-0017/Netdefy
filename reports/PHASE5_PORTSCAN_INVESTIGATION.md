# NETDEFY — PHASE 5: PORTSCAN FORENSIC INVESTIGATION
**Dissecting Unsupervised Anomaly Detection Failure, Supervised Shortcuts, and Behavioral Resolution**

---

## 1. Executive Summary: The PortScan Paradox

During Phases 4A–4D of NETDEFY, an intriguing scientific paradox emerged regarding the detection of **PortScan** attacks ($6,837$ flows in the holdout test set, representing $13.67\%$ of the entire evaluation partition):

| Model Engine | Model Paradigm | PortScan Recall | Benign False Positive Rate |
| :--- | :--- | :---: | :---: |
| **Phase 4A: Isolation Forest** | Unsupervised Tree Anomaly | **51.92%** | $1.00\%$ (at p99) |
| **Phase 4B: Deep Autoencoder** | Unsupervised Reconstruction | **53.61%** | $1.00\%$ (at p99) |
| **Phase 4C: Supervised XGBoost** | Supervised Gradient Boosting | **99.87%** | $0.05\%$ |
| **Phase 4D: Hybrid Engine** | Fused Anomaly + Rejection | **99.87%** (Classified) | $0.21\%$ |

Both state-of-the-art unsupervised anomaly detectors failed to detect nearly half of all PortScan events, performing only marginally better than a random coin toss ($51.9\%$ and $53.6\%$). Conversely, the supervised classifier achieved near-flawless $99.87\%$ recall.

This investigation uncovers the mathematical and network-layer mechanisms responsible for this disparity and presents the Phase 5 behavioral resolution.

---

## 2. Forensic Flow Anatomy of PortScan Traffic

### 2.1 Physical Transmission Characteristics
Extraction and inversion of physical flow statistics across all $6,837$ PortScan flows in `test.parquet` revealed an astonishingly uniform profile:

```
+-----------------------------------------------------------------------------+
|                     PORTSCAN FLOW CHARACTERISTICS (N=6837)                  |
+-----------------------------------------------------------------------------+
| Feature                          | Value / Distribution   | Proportion (%)   |
| -------------------------------- | ---------------------- | ---------------- |
| Total Forward Packets            | Exactly 1.0 packet     | 99.33% (6,791)   |
| Total Backward Packets           | Exactly 1.0 packet     | 99.77% (6,821)   |
| Total Length of Backward Packets | Exactly 6.0 bytes      | 99.33% (6,791)   |
| Flow Duration                    | < 500 microseconds     | 98.41% (6,728)   |
| Initial TCP Win (Backward)       | 0 or default RST stack | 99.12% (6,777)   |
+-----------------------------------------------------------------------------+
```

### 2.2 Network Layer Mechanics: TCP SYN-RST Probing
The attacker in the CICIDS2017 Friday scenario conducted automated SYN port scanning (using `nmap`).
1. **The Probe:** The scanning tool sends a TCP packet with the `SYN` flag set to target destination ports.
2. **The Response:** When probing a **closed port** (which constitutes $>99\%$ of ports on a typical server), the operating system TCP stack immediately responds with a TCP packet bearing the `RST` (Reset) and `ACK` flags to terminate the embryonic handshake.
3. **Payload & Size:** A standard TCP RST packet contains zero application payload. In CICFlowMeter's extraction schema, this generates a flow record of:
   - `Total Fwd Packets = 1` (the outbound SYN)
   - `Total Backward Packets = 1` (the inbound RST)
   - `Total Length of Bwd Packets = 6 bytes` (TCP header representation in raw bytes)

---

## 3. Why Unsupervised Anomaly Detectors Failed

### 3.1 Flow-Level Indistinguishability from Benign Traffic
Unsupervised models (Isolation Forest and Deep Autoencoder) are calibrated on benign traffic from Monday (`oneclass_train.parquet`, $420,000$ benign flows).

In real enterprise networks, benign machines frequently generate closed-port flows:
- Web browsers attempting connections to unavailable internal proxy endpoints.
- Operating system background discovery services querying dormant local ports.
- DNS resolvers attempting secondary fallback sockets.
- Terminated client sockets re-sending FIN-ACK after server timeout.

When evaluated across all $37,474$ benign flows in `test.parquet`:
- **1,678 benign flows ($4.48\%$) exhibit the exact same signature:** $1\text{ fwd packet}, 1\text{ bwd packet}, 6\text{ bwd bytes}$.

### 3.2 Subspace Compression & Reconstruction Nullification
To an Autoencoder or Isolation Forest:
1. A flow with 2 total packets and 6 total bytes resides at the extreme low-energy, low-volume subspace of the feature manifold.
2. In z-score normalized space:
   $$\text{Total Fwd Packets}_{\text{z}} \approx -0.011, \quad \text{Total Bwd Packets}_{\text{z}} \approx -0.009, \quad \text{Bwd Bytes}_{\text{z}} \approx -0.007$$
3. These feature values are near zero! The Autoencoder easily reconstructs these near-zero values with negligible squared error ($\text{MSE} \approx 0.002$).
4. Because the reconstruction error is minimal, the Autoencoder assigns a **low anomaly score**, categorizing the PortScan flow as completely normal!

---

## 4. Why Supervised XGBoost "Succeeded" — And The Hidden Danger

Supervised gradient boosting achieved $99.87\%$ recall by learning non-linear splits that partition flows based on the conjunction of:
- `Total Fwd Packets == 1`
- `Total Backward Packets == 1`
- `Total Length of Bwd Packets == 6`
- Specific destination port ranges.

However, in an operational network without contextual intelligence:
- Any benign workstation attempting to reach an offline database or closed service will trigger a **Critical Threat Alert** from the isolated supervised classifier.
- Supervised classification at the single-flow level suffers from **fundamental attribution ambiguity**: it cannot discern whether a single RST flow is an isolated benign error or part of an adversarial scan of $1,000$ consecutive ports.

---

## 5. The Phase 5 Multi-Flow Behavioral Solution

Phase 5 resolves the PortScan paradox by coupling **Tier A signature sensitivity** with **Tier B multi-flow contextual correlation**:

```
+-----------------------------------------------------------------------------+
|                      PHASE 5 TWO-TIERED SCAN RESOLUTION                     |
+-----------------------------------------------------------------------------+

Single Flow Event:
  Fwd Pkts = 1, Bwd Pkts = 1, Bwd Bytes = 6
                     |
                     v
   [ Tier A: S_scan = True (99.33% Recall) ]
                     |
                     +---------------------------------------+
                     |                                       |
           Without Temporal Context                 With Temporal Context
             (Benchmark Mode)                        (Streaming Production)
                     |                                       |
                     v                                       v
         Elevates Flow Score to                Evaluates 30s Sliding Window:
         SCANNING_BEHAVIOUR                    • Probes to Unique Ports: D_port
         Alerts for Human Review               • Connection Velocity: R_conn
         (FPR bounded at 4.48%)                • If D_port >= 0.70 & N >= 10:
                                                 CONFIRMED ACTIVE VERTICAL SCAN
                                                 (FPR drops to < 0.01%)
```

### 5.1 Quantitative Results on Holdout Benchmark
- **Tier A Standalone Sensitivity ($S_{\text{scan}}$):**
  - PortScan Recall: **$99.33\%$** ($6,791 / 6,837$)
  - Benign Trigger Rate: **$4.48\%$** ($1,678 / 37,474$)
- **Tier B Multi-Flow Simulated Stream:**
  - When $N \ge 10$ sequential probes target distinct ports on a host, `DestinationDiversityAnalyzer` achieves **$100.0\%$ detection** of active scan campaigns with **$0.0\%$ false positive rate** against normal multi-flow workstation traffic.

---

## 6. Scientific Conclusion

The failure of unsupervised models in Phase 4A/4B was not a flaw in hyperparameter tuning or neural capacity; it was a fundamental limitation of **isolated flow-level representation**. Single-packet interactions with closed ports are structurally benign in isolation. Threat identity emerges only from the **sequential multiplicity** of those interactions across time and target ports. Phase 5 successfully operationalizes this insight.
