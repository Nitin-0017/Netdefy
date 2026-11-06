# NETDEFY — Scientific Limitations & Operational Boundaries

> **Document Type:** Research Integrity & Limitations Statement  
> **Status:** Research Prototype Boundaries  
> **Audience:** Researchers, AI/ML Engineers, Technical Evaluators  

---

## 1. Single-Flow Detection Boundaries

### 1.1 Inherent Blindness to Stealthy Port Scans & Botnets
In isolated single-flow analysis, each flow record represents aggregate summary statistics for a single bidirectional connection. The following attacks exhibit severe detection boundaries:
- **PortScan (Friday Capture, $6,837$ test flows):** A horizontal port scan sends single `SYN` packets across thousands of destination ports. When evaluated as an isolated connection, a single port probe has a duration of a few microseconds, zero backward payload, and standard TCP flag states—statistically indistinguishable from a benign dropped connection or closed port request. Single-flow detection recall on PortScan is near zero ($0.19\%$ AE, $0.00\%$ XGBoost).
- **Botnet ARES (Friday Capture, $85$ test flows):** Botnet command-and-control (C2) check-in beacons use low-frequency HTTP GET requests designed to blend into normal browsing traffic. Isolated single-flow models achieve only $4.71\%$ recall.
- **Infiltration (Thursday Capture, $2$ test flows, $36$ diagnostic flows):** Internal lateral movement via benign utility execution generates flow statistics that mirror legitimate administrative file transfers.

> [!IMPORTANT]
> **Resolution in Phase 5:** These empirical single-flow failure modes directly motivated NETDEFY's Phase 5 multi-flow behavioral context tracking, which monitors destination port diversity ratios ($> 0.60$) and inter-flow periodicity across sliding time windows.

### 1.2 Absence of Deep Packet Inspection (DPI)
NETDEFY processes aggregated statistical flow features extracted via CICFlowMeter. It does not inspect packet payloads, HTTP request bodies, or TLS handshake extensions. Consequently, payload-specific exploits that do not alter connection geometry (such as cross-site scripting payloads inside normal-length HTTP parameters or SQL injection within standard POST requests) cannot be detected by flow statistics alone.

---

## 2. Dataset Artifacts & Capture Imperfections

### 2.1 Label Collisions and Ambiguity in CICIDS2017
Forensic auditing discovered that **$3,305$ records in the 50,000-flow test holdout share identical 76-feature continuous vectors across conflicting ground-truth labels** ($3,254$ PortScan, $49$ Benign, $2$ Bot). 
- Dual-homed network taps monitoring both ingress and egress interfaces simultaneously generated identical flow records with differing ground-truth attributions.
- Any machine learning model evaluated on View A is mathematically bounded by this collision noise. Excluding these collision rows (View B) increases hybrid attack recall from $27.73\%$ to $37.46\%$ ($+35.1\%$ relative gain).

### 2.2 Severe Class Imbalance
The CICIDS2017 dataset reflects extreme class imbalance:
- `Heartbleed` contains only **$11$ total samples** in the entire 2.8 GB dataset ($7$ in classifier train, $4$ in validation, $0$ in test holdout).
- `Infiltration` contains only **$36$ flows** across the diagnostic partition and $2$ in holdout testing.
- While statistically realistic for rare zero-day threats, these tiny sample sizes limit statistical confidence in per-class generalization.

---

## 3. Open-Set Recognition Limitations

### 3.1 Closed-Set Classifier Blindness
When supervised GBDT models are evaluated on unseen attack classes from subsequent days:
- XGBoost misclassified **$71.72\%$ of unseen holdout attacks as `BENIGN`** because Thursday/Friday attack categories (DDoS, PortScan, Botnet, Web Attacks) were absent from Tuesday/Wednesday training data.
- While unsupervised anomaly detectors flag these flows as anomalous, they cannot determine attack taxonomy. The Hybrid Engine addresses this by routing unclassified anomalies to `SUSPICIOUS_UNKNOWN`.

---

## 4. Cross-Domain Generalization Collapse

When models trained on CICIDS2017 were evaluated against **CSE-CIC-IDS2018**:
- Detection performance degraded significantly on novel network topologies, AWS virtualized infrastructure, and differing background benign traffic distributions.
- Flow-based anomaly detectors learn ambient network characteristics (subnet sizes, average flow lengths, corporate server response times). Moving models to a new environment without local baseline calibration leads to elevated false alarm rates and depressed recall.

---

## 5. System & Infrastructure Scope

- **Prototype Status:** NETDEFY is an applied research prototype. It does not provide automated firewall rule injection, kernel-level packet filtering, or distributed high-availability clustering.
- **Resource Constraints:** Designed for local evaluation on Apple Silicon (M-series) or standard Linux x86_64 machines with 8 GB RAM. High-volume stream ingestion requires Redis Streams with external horizontal scaling.

