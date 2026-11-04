# NETDEFY — PHASE 4D: PRE-IMPLEMENTATION AUDIT
## Comprehensive Model, Artifact, Schema, and Inference Interface Verification

**Document ID:** NETDEFY-AUD-4D-001  
**Date:** 2026-11-04  
**Author:** Antigravity AI Engineering & Research Team  
**Status:** Approved & Certified  
**Scope:** Technical audit of all Phase 1–4C artifacts, schemas, calibration parameters, and compatibility interfaces prior to implementing Phase 4D (Hybrid Intelligence & Decision Engine).

---

## 1. Existing Artifact Inventory & Cryptographic Checksums

Every model artifact, benchmark partition, and preprocessing object on disk was inspected and verified via SHA-256 cryptographic hashing.

| Artifact Role | File System Path | File Size | SHA-256 Checksum |
| :--- | :--- | :---: | :--- |
| **Isolation Forest (v1)** | `artifacts/models/isolation_forest/v1/model.joblib` | 185,258 B | `807d5b9c3693b3631f447826c442b3000dd8e6a4cb49590f3e6cb6bb9a543846` |
| **Deep Autoencoder (v1)** | `artifacts/models/autoencoder/v1/best_model.pt` | 69,749 B | `5ea72c57213f6ae6c41b0d1f8f8126fd6dadf1a45bc78d7de0f594b0089b5be7` |
| **XGBoost Metadata (v1)** | `artifacts/models/xgboost_classifier/v1/model.json` | 2,621 B | `18a40ca26425321ca601d7769c053acc077011f39b205dc3176a4a4940b64a72` |
| **XGBoost Native Booster** | `artifacts/models/xgboost_classifier/v1/model.ubj` | 1,728,512 B | `e708242901a9f2088804e72960d1bbce272d1921db559aa1fb93e826f86cf30c` |
| **StandardScaler Object** | `artifacts/preprocessing/standard_scaler.joblib` | 3,282 B | `6255c7f64886060cb0cd60c5151f87241c51a96a6290b0a519ee655d6b1793cc` |
| **Feature Schema Definition** | `artifacts/preprocessing/feature_schema.json` | 4,164 B | `a7f83d5a35bdb418dede8a9359a3d054b65c8129db79a3987753287e0159c9a0` |
| **One-Class Train Benchmark** | `data/benchmark/v1/oneclass_train.parquet` | 10,865,492 B | `06157578c42449a053190325ecea4c41e999797dbfec033b572f62df789f633c` |
| **Classifier Train Benchmark** | `data/benchmark/v1/classifier_train.parquet` | 3,217,700 B | `d5d69f75f44612fb455a77c9d03bf88b5d444ed22e123926e4867e88bc3e44c7` |
| **Validation Benchmark** | `data/benchmark/v1/validation.parquet` | 2,207,653 B | `3116213f1a94f24a2a1b39123fc3a0ac300a231581fc3788045525698f9c72bf` |
| **Holdout Test Benchmark** | `data/benchmark/v1/test.parquet` | 4,654,887 B | `263437c2e7da289ad29246dc923e5b6f41443c4d71f4f00497e0e69928d6e6e1` |
| **Rare Attack Diagnostic** | `data/benchmark/v1/supplementary/rare_class_diagnostic.parquet` | 592,175 B | `4eb33a3d3b28ff7f3ddb37fd94da2de2fb1d37a07889d28d9c5e16bdb20b29ff` |
| **Ambiguity Manifest** | `data/benchmark/v1/metadata/ambiguity_manifest.json` | 333 B | `a1d8377f13a407f6a240c9662f90d557e620d7f39e3c0386797742e5236bd973` |

**Integrity Certification:** Zero artifacts are missing, corrupt, or truncated. All existing hashes match their parent phase manifests.

---

## 2. Model Input & Feature Schema Compatibility

### 2.1 Feature Compatibility
- **Feature Vector Length:** Exactly 76 continuous features (`float32`).
- **Feature Identity:** A programmatic equality test confirmed:
  $$\text{IF.feature\_names} \equiv \text{AE.feature\_names} \equiv \text{XGB.feature\_names} \equiv \text{schema.model\_features}$$
  All 76 column names, ordering, and data types are 100% identical across all three models.
- **Excluded Features:**
  - `Destination Port`: Excluded from model features to avoid synthetic memorization of testbed infrastructure ports.
  - `Fwd Header Length.1`: Removed during Phase 3 due to duplicate collinearity with `Fwd Header Length`.
  - `Label`: Excluded from model features, retained strictly as ground truth.
- **Normalization:** All models operate on standardized features ($z = \frac{x - \mu_{\text{Monday}}}{\sigma_{\text{Monday}}}$) produced by the frozen `StandardScaler` fitted exclusively on Monday benign traffic.

---

## 3. Score Orientation & Scale Discrepancies

### 3.1 Orientation Alignment
All anomaly detection models in NETDEFY adhere strictly to the uniform convention:
$$\text{Higher Anomaly Score} \implies \text{More Anomalous / Suspicious}$$

- **Isolation Forest:** Raw scikit-learn `score_samples(X)` returns negative Liu et al. path length metrics. NETDEFY's wrapper computes $s_{\text{IF}}(x) = -\text{sklearn.score\_samples}(x)$, ensuring positive and direct alignment.
- **Deep Autoencoder:** Measures Mean Squared Error (MSE) reconstruction loss: $s_{\text{AE}}(x) = \frac{1}{D}\sum_{d=1}^D (x_d - \hat{x}_d)^2$. Naturally aligned: higher error = less reconstructed = more anomalous.
- **XGBoost Classifier:** Softmax probability vector $\mathbf{p} = [p_0, p_1, \dots, p_7]$ where $p_k = P(y = k \mid x)$ and $\sum_{k=0}^7 p_k = 1.0$.

### 3.2 Scale Discrepancy Analysis (Why Direct Addition is Forbidden)
Empirical validation distribution statistics from `artifacts/models/*/v1/thresholds.json`:

| Model Metric | Min | Median | Mean | p95.0 | p99.0 | p99.5 | Max |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Isolation Forest Score** | 0.3185 | 0.3422 | 0.3778 | 0.5636 | 0.6502 | 0.6944 | 0.7482 |
| **Autoencoder MSE Error** | 0.0002 | 0.0020 | 0.1027 | 0.0966 | 0.7084 | 1.9511 | 816.4168 |

**Crucial Finding:**
Autoencoder reconstruction errors span across 6 orders of magnitude ($10^{-4}$ to $10^2$), whereas Isolation Forest scores are tightly bounded between $\approx 0.30$ and $0.75$. Unnormalized summation or averaging ($s_{\text{IF}} + s_{\text{AE}}$) would result in Autoencoder reconstruction errors completely dominating the fused decision by a factor exceeding $1,000 \times$, rendering Isolation Forest functionally inert. Score calibration (empirical percentiles or robust scaling) is mandatory.

---

## 4. Class Mapping & Open-Set Ground Truth

### 4.1 Supervised Classifier Class Mapping
The trained XGBoost classifier possesses 8 output classes (`artifacts/models/xgboost_classifier/v1/class_mapping.json`):
```json
{
  "0": "BENIGN",
  "1": "DoS GoldenEye",
  "2": "DoS Hulk",
  "3": "DoS Slowhttptest",
  "4": "DoS slowloris",
  "5": "FTP-Patator",
  "6": "Heartbleed",
  "7": "SSH-Patator"
}
```

### 4.2 Partition Class Composition vs Classifier Exposure
Inspection of the benchmark partitions reveals the core open-set reality:

| Attack Category | Raw Source Day | Classifier Train (30K) | Validation (20K) | Holdout Test (50K) | Status to Classifier |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **BENIGN** | Mon, Tue, Wed, Thu, Fri | 22,973 | 15,315 | 37,474 | **Known Normal** |
| **DoS Hulk** | Wednesday | 6,086 | 4,058 | 0 | **Known Attack** |
| **DoS GoldenEye** | Wednesday | 272 | 181 | 0 | **Known Attack** |
| **FTP-Patator** | Tuesday | 208 | 139 | 0 | **Known Attack** |
| **SSH-Patator** | Tuesday | 156 | 104 | 0 | **Known Attack** |
| **DoS slowloris** | Wednesday | 154 | 102 | 0 | **Known Attack** |
| **DoS Slowhttptest** | Wednesday | 145 | 97 | 0 | **Known Attack** |
| **Heartbleed** | Wednesday | 6 | 4 | 0 | **Known Attack (Rare)** |
| **PortScan** | Friday | 0 | 0 | **6,837** | **UNSEEN (Open-Set)** |
| **DDoS** | Friday | 0 | 0 | **5,508** | **UNSEEN (Open-Set)** |
| **Bot** | Friday | 0 | 0 | **85** | **UNSEEN (Open-Set)** |
| **Web Attack — Brute Force** | Thursday | 0 | 0 | **65** | **UNSEEN (Open-Set)** |
| **Web Attack — XSS** | Thursday | 0 | 0 | **28** | **UNSEEN (Open-Set)** |
| **Infiltration** | Thursday | 0 | 0 | **2** | **UNSEEN (Open-Set)** |
| **Web Attack — Sql Injection**| Thursday | 0 | 0 | **1** | **UNSEEN (Open-Set)** |

### 4.3 Fundamental Open-Set Implication
**100% of the 12,526 attack flows in the final holdout test set belong to categories that were absent during classifier training.**  
When evaluated as a closed-set system, XGBoost forced:
- 6,823 of 6,837 PortScan flows into **BENIGN** ($99.79\%$).
- 1,981 of 5,508 DDoS flows into **BENIGN** ($35.97\%$) and 3,527 into **DoS Hulk** ($64.03\%$).
- 85 of 85 Bot flows into **BENIGN** ($100.0\%$).

This establishes beyond doubt why a single closed-set supervised model cannot secure network infrastructure against novel threats, and why the Hybrid Engine must use unsupervised anomaly detection to catch unclassified threats and reject low-confidence / out-of-distribution attributions.

---

## 5. Existing Operational Thresholds

Both anomaly detectors were previously calibrated on benign validation records ($N = 15,315$):

| Nominal Operating Level | Nominal Benign FPR | Isolation Forest Threshold | Autoencoder MSE Threshold |
| :--- | :---: | :---: | :---: |
| **Conservative (p95.0)** | $5.0\%$ | $0.56355858$ | $0.09655800$ |
| **Balanced (p99.0)** | $1.0\%$ | $0.65018266$ | $0.70843279$ |
| **Strict Low-FPR (p99.5)** | $0.5\%$ | $0.69435763$ | $1.95105243$ |

---

## 6. Existing Model Inference Interfaces

| Component | Class Name | Module Path | Loading Method | Scoring Method | Output Shape / Dtype |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Isolation Forest** | `IsolationForestDetector` | `netdefy.models.isolation_forest` | `.load(path)` | `.score_samples(X)` | `(N,)` `float32` |
| **Deep Autoencoder** | `AutoencoderDetector` | `netdefy.models.autoencoder` | `.load(path, device)` | `.score_samples(X, batch_size)` | `(N,)` `float32` |
| **XGBoost Classifier**| `XGBoostAttackClassifier` | `netdefy.models.xgboost_classifier`| `.load(path)` | `.predict_proba(X)` | `(N, 8)` `float32` |

All three wrappers accept `pd.DataFrame` or `np.ndarray`, validate against NaN/Inf, and maintain `feature_names`.

---

## 7. Identified Technical & Research Risks

1. **Test Set Contamination Risk:** Operational threshold calibration and score normalization parameters must be computed strictly on training/validation reference distributions. No parameter may be fitted or adjusted using `test.parquet`.
2. **Probability Calibration Flaw:** Raw softmax outputs from deep trees often exhibit overconfidence even on out-of-distribution inputs. We must evaluate probability margins ($\Delta p = p_{\text{top1}} - p_{\text{top2}}$) and entropy alongside the raw top probability.
3. **Hardware / Latency Bottlenecks:** Autoencoder inference involves PyTorch tensor allocation. For batch inference on Apple Silicon M3 (8 GB RAM), single-threaded CPU inference with vectorized batching ($B = 1024$) minimizes IPC overhead and avoids Metal/MPS initialization latency.
4. **Ambiguity Impact:** The 3,305 ambiguous test records (130 colliding vectors) contain PortScan flows with identical feature signatures to benign flows. Disambiguated sensitivity analysis (View B: 46,695 flows) must be reported alongside Full Test (View A: 50,000 flows).

---

## 8. Recommended Phase 4D Integration Architecture

```
                                  Input Flow Vector (76 float32)
                                                │
                     ┌──────────────────────────┼──────────────────────────┐
                     │                          │                          │
                     ▼                          ▼                          ▼
           Isolation Forest             Deep Autoencoder           XGBoost Classifier
             Detector                     Detector                   (8 classes)
                     │                          │                          │
           Raw Score s_IF              Reconstruction s_AE          Class Probabilities p
                     │                          │                          │
                     ▼                          ▼                          ▼
            Score Calibration           Score Calibration          Confidence & Margin
          (Empirical Percentile)      (Empirical Percentile)       Rejection Analysis
                     │                          │                          │
            Calibrated c_IF             Calibrated c_AE                    │
                     │                          │                          │
                     └──────────┬───────────────┘                          │
                                │                                          │
                                ▼                                          │
                         Fused Anomaly                                     │
                             Score                                         │
                                │                                          │
                                └───────────────────┬──────────────────────┘
                                                    │
                                                    ▼
                                        Decision Policy Engine
                                 (Rules A, B, C, D + Explainability)
                                                    │
                        ┌───────────────────────────┼───────────────────────────┐
                        ▼                           ▼                           ▼
                     NORMAL                SUSPICIOUS_KNOWN            SUSPICIOUS_UNKNOWN
             (Below Anomaly Thresh)     (Above Anomaly Thresh       (Above Anomaly Thresh
                                         + High Conf Known Attack)   + Unseen/Low Conf Attack)
                                                    │
                                                    ▼
                                             REVIEW_REQUIRED
                                        (Conflicting Evidence /
                                         High Anomaly + Benign Clf)
```

### Module Blueprint
- `src/netdefy/hybrid/score_calibration.py`: Empirical percentile and robust scaling calibrators.
- `src/netdefy/hybrid/score_fusion.py`: Modular fusion strategies (Max, Equal-Weight Mean, Calibrated Weighted).
- `src/netdefy/hybrid/classifier_rejection.py`: Confidence thresholding, probability margin, entropy filtering.
- `src/netdefy/hybrid/decision_engine.py`: 4-category deterministic decision rules with structural reason codes.
- `src/netdefy/hybrid/explanation.py`: Feature-level reconstruction attribution and decision evidence generation.
- `src/netdefy/hybrid/schemas.py`: Validated Pydantic/dataclass schemas for single-flow and batch results.
- `src/netdefy/hybrid/inference_pipeline.py`: Production-grade `HybridInferencePipeline` with input sanitation and batch support.

**Audit Status:** COMPLETE & VERIFIED. Safe to proceed with Phase 4D implementation.
