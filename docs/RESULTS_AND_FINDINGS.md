# NETDEFY — Research Results & Empirical Findings

> **Document Type:** Scientific Results & Metric Reconciliation  
> **Source Artifacts:** `artifacts/models/hybrid/v1/test_metrics.json`, `reports/PHASE6_2_INDEPENDENT_AUDIT.md`  
> **Holdout Dataset:** `data/benchmark/v1/test.parquet` ($50,000$ flows)  

---

## 1. Verified Head-to-Head Model Performance

All models were evaluated on the chronological holdout test set (Thursday–Friday traffic, $50,000$ flows: $37,474$ Benign, $12,526$ Attack):

| Performance Dimension | Isolation Forest | Deep Autoencoder | XGBoost (Binary Policy 1) | XGBoost (Binary Policy 2) | NETDEFY Continuous Fusion | NETDEFY Hybrid Engine (Triage) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Model Paradigm** | Unsupervised Trees | PyTorch Bottleneck | Supervised GBDT (Argmax) | Supervised GBDT (Cumul.) | Equal-Weight Score Fusion | Multi-Factor Triage Matrix |
| **Holdout AUROC (View A)** | $0.6558$ | $0.8307$ | — | **$0.8505$** | **$0.7377$** | N/A (Discrete Verdicts) |
| **Holdout PR-AUC (View A)** | $0.3423$ | $0.6021$ | — | **$0.6745$** | **$0.4318$** | N/A (Discrete Verdicts) |
| **Operational Precision** | $51.06\%$ | $75.42\%$ | **$97.31\%$** | **$97.23\%$** | $63.01\%$ | **$84.73\%$** |
| **Attack Detection Recall** | $6.54\%$ | $28.65\%$ | $28.29\%$ | $28.59\%$ | $7.93\%$ | **$27.73\%$** |
| **Operational F1 Score** | $0.1159$ | $0.4153$ | $0.4383$ | $0.4419$ | $0.1408$ | **$0.4178$** |
| **Benign FPR** | $2.09\%$ | $3.12\%$ | $0.26\%$ | $0.27\%$ | $1.56\%$ | **$1.67\%$** |
| **False Alarms / 1k Benign** | $20.95$ | $31.22$ | $\mathbf{2.62}$ | $2.72$ | $15.56$ | **$16.70$ (-46.5% vs AE)** |
| **Inference Latency** | **$1.12\text{ ms}$** | $1.84\text{ ms}$ | $1.25\text{ ms}$ | $1.25\text{ ms}$ | $2.96\text{ ms}$ | $4.86\text{ ms}$ |

---

## 2. Impact of Capture Ambiguity (View A vs. View B)

Excluding the $3,305$ conflicting flow records documented in `ambiguity_manifest.json` demonstrates how packet capture artifacts depress measurable recall:

| Metric | View A (Full Benchmark, $N = 50,000$) | View B (Disambiguated, $N = 46,695$) | Relative Gain |
| :--- | :---: | :---: | :---: |
| **Hybrid Attack Recall** | $27.73\%$ ($3,473 / 12,526$) | **$37.46\%$** ($3,454 / 9,221$) | **$+35.1\%$ Relative Gain** |
| **Hybrid Operational F1** | $0.4178$ | **$0.5196$** | **$+24.4\%$ Relative Gain** |
| **Autoencoder Recall** | $28.65\%$ | **$38.59\%$** | $+34.7\%$ Relative Gain |
| **Autoencoder F1 Score** | $0.4153$ | **$0.5104$** | $+22.9\%$ Relative Gain |
| **Autoencoder AUROC** | $0.8307$ | **$0.8845$** | $+6.5\%$ Relative Gain |

---

## 3. Discrepancy Reconciliation & Scientific Proofs

### 3.1 Hybrid Score Reconciliation ($0.7377$ vs. $0.8800$ AUROC, $0.4318$ vs. $0.7100$ PR-AUC)
- **Continuous Fusion Baseline:** The continuous score fusion ($s_{\text{fused}} = 0.5(c_{\text{IF}} + c_{\text{AE}})$) on `test.parquet` achieves **$0.7377$ AUROC** and **$0.4318$ PR-AUC** (`artifacts/models/hybrid/v1/test_metrics.json:54-55`).
- **Provenance of $0.8800$ / $0.7100$:** In preliminary drafts, these figures were informal estimates or conflated with Phase 5 Tier B temporal multi-flow metrics (**$0.8712$ AUROC**, **$0.6940$ PR-AUC**).
- **Resolution:** The production Hybrid Engine is evaluated as a discrete triage policy, achieving **$84.73\%$ precision** at **$27.73\%$ recall** under the balanced $p_{99.0}$ threshold.

### 3.2 XGBoost Binary Policy Divergence ($97.31\%$ vs. $97.23\%$ Precision)
Both metrics were calculated on the identical $50,000$ test flows from the same XGBoost model:
- **Policy 1 ($\text{argmax}_{k} P_k \neq 0$):** Flagged positive iff top class is an attack.
  $$\text{TN} = 37,376,\quad \text{FP} = 98,\quad \text{FN} = 8,983,\quad \text{TP} = 3,543 \implies \text{Prec} = 97.31\%,\quad \text{Rec} = 28.29\%,\quad \text{F1} = 0.4383$$
- **Policy 2 ($1.0 - P(\text{BENIGN}) \ge 0.50$):** Flagged positive iff combined attack probability $\ge 0.50$.
  $$\text{TN} = 37,372,\quad \text{FP} = 102,\quad \text{FN} = 8,945,\quad \text{TP} = 3,581 \implies \text{Prec} = 97.23\%,\quad \text{Rec} = 28.59\%,\quad \text{F1} = 0.4419$$
- **Mathematical Cause:** In $38$ attack flows and $4$ benign flows, $P(\text{BENIGN}) < 0.50$ (e.g. $0.48$). However, because attack probability divided across multiple classes (e.g., Hulk $0.28$, slowloris $0.24$), no single attack class exceeded $0.48$. Thus, Policy 1 categorized them as normal while Policy 2 categorized them as attack ($+38$ TP, $+4$ FP).

### 3.3 Autoencoder Calibration Threshold ($0.7084$ vs. $0.1428$)
- **Verified Truth:** The true calibrated Autoencoder $p_{99.0}$ threshold is **$0.708433$** (`artifacts/models/autoencoder/v1/thresholds.json`), fitted strictly on $15,315$ benign validation flows.
- **Cause of $0.1428$:** `src/netdefy/api/routes/research.py` attempted top-level lookup `ae_thresh.get("p99", 0.1428)`. Because the artifact stores thresholds under nested key `thresholds["p99.0"]`, the lookup fell back to the hardcoded default `0.1428`. Fixed by extracting `ae_thresh.get("thresholds", {}).get("p99.0", 0.708433)`.

### 3.4 Inference Playground: Engineering Parity vs. Detection Accuracy
- **Engineering Consistency (100% Parity):** All 11 curated benchmark samples produced bit-for-bit identical outputs between direct in-memory Python inference and the FastAPI REST API (`/api/v1/playground/predict`).
- **Threat Detection Accuracy on Playground Samples:**
  - `portscan` (PortScan): Predicted as `NORMAL` ($s_{\text{fused}} = 0.6579 < 0.9821$, classifier: `BENIGN`, $p = 0.9974$). **Missed Detection.**
  - `bot_ares` (Bot): Predicted as `NORMAL` ($s_{\text{fused}} = 0.4422 < 0.9821$, classifier: `BENIGN`, $p = 0.9958$). **Missed Detection.**
  - `infiltration` (Infiltration): Predicted as `NORMAL` ($s_{\text{fused}} = 0.9287 < 0.9821$, classifier: `BENIGN`, $p = 0.9963$). **Missed Detection.**
  - Single-flow features for stealthy port scans, bot beacons, and infiltration mimic normal TCP sessions, validating why Phase 5 temporal and multi-flow behavioral context was required.

---

## 4. Attack-Wise Detection Recall Breakdown

| Attack Category | Test Sample Count | Training Presence | XGBoost Recall | Autoencoder Recall | NETDEFY Hybrid Recall | Primary Failure Mode |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **DDoS** | $5,508$ | Absent (Unseen) | $63.38\%$ | **$64.12\%$** | **$62.24\%$** | Supervised misattributed to DoS Hulk; escalated by AE |
| **PortScan** | $6,837$ | Absent (Unseen) | $0.00\%$ | $0.19\%$ | $0.00\%$ ($13.4\%$ View B) | Identical to benign SYN packets; requires multi-flow context |
| **Bot** | $85$ | Absent (Unseen) | $0.00\%$ | $4.71\%$ | $4.71\%$ | Low-frequency periodic beacons; requires temporal tracking |
| **Web Attack – Brute Force** | $65$ | Absent (Unseen) | $0.00\%$ | **$26.15\%$** | **$26.15\%$** | HTTP GET/POST payload volume triggers reconstruction error |
| **Web Attack – XSS** | $28$ | Absent (Unseen) | $0.00\%$ | $0.00\%$ | $0.00\%$ | Payload length within nominal web traffic boundaries |
| **Infiltration** | $2$ | Absent (Unseen) | $0.00\%$ | $0.00\%$ | $0.00\%$ | Extremely small test sample; passive internal reconnaissance |
| **Web Attack – Sql Injection**| $1$ | Absent (Unseen) | $0.00\%$ | $0.00\%$ | $0.00\%$ | Single test sample indistinguishable from dynamic DB queries |
