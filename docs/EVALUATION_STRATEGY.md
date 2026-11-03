# NETDEFY Critical Evaluation Strategy & Temporal Protocol

## 1. Principles of Rigorous Network Anomaly Evaluation

Traditional evaluations of machine learning in network intrusion detection often exhibit severe methodological flaws:
- **Random Shuffling Leakage:** Splitting network flow datasets randomly across the whole week allows test samples to be nearly identical to training samples recorded seconds earlier within the same connection session.
- **Accuracy Fallacy:** In a dataset with 99% benign traffic, a naive classifier predicting all flows as benign achieves 99% accuracy while detecting zero attacks.
- **Threshold Cherry-Picking:** Post-hoc tuning of the decision threshold on the final test set inflates reported F1-scores and produces un-deployable security baselines.

NETDEFY enforces a strict, reproducible, and leakage-free evaluation protocol designed to evaluate real-world temporal generalization.

---

## 2. Chronological Partitioning Methodology

```
+-----------------------------------------------------------------------------------------+
|                                    CICIDS2017 TIMELINE                                  |
+-----------------------------------------------------------------------------------------+
| Monday (Jul 3)   | Tuesday (Jul 4)  | Wednesday (Jul 5) | Thursday (Jul 6) | Friday (Jul 7) |
| Benign Baseline  | Brute Force      | DoS / DDoS        | Web Attacks      | Botnet, Port   |
+------------------+------------------+-------------------+------------------+----------------+
        \                 /                    |                    \                /
         \               /                     |                     \              /
   [ Phase 3 Training Partition ]     [ Validation Partition ]      [ Final Test Partition ]
   - Mon Benign + Tue Benign          - Tue Attacks + Wed           - Thu & Fri (All traffic)
   - Learn normal baseline manifold   - Calibrate threshold (tau)   - Untouched until final eval
```

### Partitioning Rules:
1. **Chronological Splitting:**
   - **Training Partition:** Early benign traffic (Monday July 3 and Tuesday morning July 4 benign records).
   - **Validation Partition:** Tuesday afternoon and Wednesday July 5 traffic.
   - **Final Test Partition:** Thursday July 6 and Friday July 7 traffic.
2. **Day-Wise Attack Inspection:** Each day features distinct attack vectors. Models trained on early days must be evaluated on how effectively they detect unseen, novel attacks occurring days later.
3. **Cross-Partition Duplicate Audit:** Inter-split duplication checks eliminate flow repetition across days, ensuring test sets evaluate actual generalization rather than memorized session flows.

---

## 3. Modeling Strategies

### 3.1 PyTorch Deep Autoencoder Strategy
The Autoencoder operates as a semi-supervised one-class novelty detector:
1. **Training Phase:** Trained exclusively on benign network traffic from the training partition to learn normal communication patterns.
2. **Representation Learning:** Compresses flow metrics into a low-dimensional bottleneck manifold representing typical benign packet lengths, inter-arrival times, and flag dynamics.
3. **Reconstruction Metric:** Anomaly score is defined as the mean squared error (MSE) between input $x$ and reconstruction $\hat{x}$:
   $$\mathcal{S}(x) = \frac{1}{D} \sum_{i=1}^D (x_i - \hat{x}_i)^2$$
4. **Threshold Selection on Validation Set:** An anomaly threshold $\tau$ is chosen on the validation set (e.g., the 99th or 99.5th percentile of benign validation reconstruction error).
5. **Threshold Freeze:** The threshold $\tau$ is permanently frozen.
6. **Final Evaluation:** Evaluated exactly once on the untouched temporal test set.

### 3.2 Scikit-Learn Isolation Forest Strategy
The Isolation Forest serves as our classical ML benchmark:
1. **Training Data Assumptions:** We evaluate two regimes:
   - *Benign-Only Training:* Mirroring the autoencoder setup.
   - *Contaminated Training:* Training on realistic, mixed traffic containing unlabelled anomalies.
2. **Contamination Parameter:** Set based on estimated baseline attack proportions on the training set (e.g., 0.01).
3. **Scoring Mechanism:** Anomaly score derived from average isolation path length in an ensemble of random trees.
4. **Vulnerability to Drift:** Isolation trees partition feature space with orthogonal hyperplanes, making them particularly sensitive to temporal shift when traffic volume or packet size shifts naturally across days.

---

## 4. Preprocessing and Leakage-Prevention Guardrails

1. **Strict Train-Only Fitting:** Scalers (`StandardScaler`, `RobustScaler`) and imputers are fitted solely on the training partition. The validation and test sets are transformed using these stored parameters.
2. **Exclusion of Spurious Identifiers:** The following features are excluded prior to training:
   - `Flow ID`, `Source IP`, `Destination IP`, `Timestamp`, `Source Port`.
3. **Port Feature Evaluation:** Destination ports indicate victim services (port 80/443 for web, 21 for FTP, 22 for SSH). We evaluate clustering into broad service categories (e.g., Well-Known <1024 vs Ephemeral >1024) rather than treating them as arbitrary continuous integers.
4. **Zero Variance Filter:** Features with zero variance across the training set are eliminated.
5. **Label Isolation:** Ground-truth labels are isolated from the feature matrix at ingestion and only used during threshold calibration and final evaluation.

---

## 5. Mandatory Evaluation Metrics

NETDEFY prohibits the reporting of accuracy alone. All evaluation reports must provide:

| Metric | Definition & Purpose |
| :--- | :--- |
| **Precision** | $\frac{TP}{TP + FP}$ — Proportion of flagged alerts that were actual intrusions. |
| **Recall** | $\frac{TP}{TP + FN}$ — Proportion of actual intrusions successfully detected. |
| **F1-Score** | $2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$ — Harmonic mean balancing both concerns. |
| **PR-AUC** | Area under the Precision-Recall curve; primary metric for imbalanced anomaly detection. |
| **ROC-AUC** | Receiver Operating Characteristic Area under Curve (reported alongside PR-AUC). |
| **Confusion Matrix** | Breakdown of True Positives, False Positives, True Negatives, False Negatives. |
| **False Alarm Rate (FAR)** | Number of false alerts per 1,000 benign flows: $\frac{FP}{FP + TN} \times 1000$. Critical for SOC operational viability. |
| **Attack-Wise Recall** | Detection recall broken down per attack category (DoS, Brute Force, Web Attack, PortScan, Infiltration, Botnet). |
| **Inference Latency** | Median and 99th percentile inference time in milliseconds per flow on target hardware. |
| **Peak Memory Consumption** | Memory footprint (MB) during feature transformation and model inference. |
