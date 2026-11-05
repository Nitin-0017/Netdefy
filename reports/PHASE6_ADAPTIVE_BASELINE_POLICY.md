# NETDEFY — PHASE 6 ADAPTIVE BASELINE & DRIFT MONITORING POLICY
## Security Invariants, Anti-Poisoning Safeguards & Distribution Tracking

---

### 1. Executive Summary & Problem Definition

In production network anomaly detection, network traffic patterns naturally evolve due to diurnal cycles, software deployments, and network topology shifts. However, naive automated baseline updating introduces a catastrophic security vulnerability: **Adversarial Baseline Poisoning**. 

An adversary aware of an adaptive learning system can deliberately inject low-rate, stealthy anomalies over days or weeks ("boiling frog" attack). If the system unconditionally assimilates new traffic into its normal distribution, the baseline shifts until the malicious attack pattern is re-classified as "benign normal".

This policy document formalizes the architectural safeguards implemented in [`src/netdefy/streaming/adaptive_baseline.py`](file:///Users/nitinkumar/Documents/Netdefy/src/netdefy/streaming/adaptive_baseline.py) to guarantee that NETDEFY remains robust against poisoning while providing observability into genuine distribution drift.

---

### 2. Core Architectural Safeguards

#### 2.1 Separation of Concerns
NETDEFY strictly distinguishes between three independent operational tiers:
1. **Drift Monitoring:** Statistical tracking of observed score distributions without changing decision boundaries.
2. **Baseline Adaptation:** Bounded update of online operational metrics for SOC situational awareness.
3. **Model Retraining:** Offline, human-supervised re-estimation of neural network weights and tree ensembles using verified historical datasets.

**Rule:** Model weights and saved Phase 4D model thresholds (`calibrator_if.json`, `calibrator_ae.json`, `thresholds.json`) are **strictly read-only and immutable** in the real-time stream processing pipeline.

---

### 3. Baseline Update Eligibility Policy

To be eligible to update the active adaptive baseline, an incoming network flow event must satisfy all four gates of the **Anti-Poisoning Gatekeeper**:

$$\text{Eligible}(e) \iff \begin{cases}
\text{Decision}(e) == \text{NORMAL} \\
\land\ \text{XGBoost\_Label}(e) == \text{BENIGN} \\
\land\ \text{Has\_Behavioral\_Flag}(e) == \text{False} \\
\land\ \text{Anomaly\_Score}(e) < \text{Threshold}_{\text{ref}}^{p95}
\end{cases}$$

If any condition fails:
- The event is immediately rejected from updating baseline statistics.
- No partial or weighted updates occur for suspicious or uncertain traffic.
- If the flow triggered an alert, it is routed to SOC analysts for investigation without contaminating baseline distributions.

---

### 4. Mathematical Formulation & Bounded Updates

When an observation $x_t$ is certified as eligible, the running mean is updated via an Exponentially Weighted Moving Average (EMA) with a conservative smoothing factor $\alpha = 0.005$:

$$\mu_{t} = (1 - \alpha) \mu_{t-1} + \alpha x_t$$

#### Hard Boundary Clamping
To prevent slow drift from pulling the active baseline away from the validated reference, the active mean is clamped within a maximum deviation ratio $\delta = 0.25$ ($25\%$) relative to the frozen reference baseline $\mu_{\text{frozen}}$:

$$\mu_{\text{clamped}} = \max\left(\mu_{\text{frozen}} \cdot (1 - \delta),\ \min\left(\mu_{\text{frozen}} \cdot (1 + \delta),\ \mu_t\right)\right)$$

Even if an attacker crafts thousands of flows that pass the eligibility gate, they cannot force the baseline beyond the $\pm 25\%$ security corridor.

---

### 5. Drift Detection & Rollback Protocol

1. **Drift Alert Generation:**
   When the deviation ratio between the active baseline and the frozen reference exceeds the boundary threshold:
   $$\frac{|\mu_{\text{active}} - \mu_{\text{frozen}}|}{\mu_{\text{frozen}}} \ge \delta$$
   The engine flags a `Significant baseline drift detected` warning in Prometheus metrics and SOC logs, advising engineers that the environment has shifted materially.
2. **Emergency Rollback (`rollback_to_frozen()`):**
   An authenticated administrator or SOC engineer can invoke an immediate rollback. The active baseline state is atomically restored to the verified Phase 4D/5.1 frozen reference baseline, generating an auditable snapshot record with a distinct version ID (`adaptive-rollback-<id>`).

