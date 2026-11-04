# NETDEFY — PHASE 4D: DECISION ENGINE POLICY DOCUMENT

**Document ID:** NETDEFY-POL-4D-DEC  
**Date:** 2026-11-04  
**Author:** Antigravity AI Engineering & Research Team  
**Status:** Approved & Enforced  
**Scope:** Formal definition of operational decision categories, deterministic decision logic, conflict resolution rules, and triage workflows for the NETDEFY Hybrid Intelligence & Decision Engine.

---

## 1. Operational Decision Categories

The NETDEFY Hybrid Intelligence Engine maps multi-model evidence into four mutually exclusive operational categories:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DECISION CATEGORIES                             │
├─────────────────────┬──────────────────────────────────────────────────┤
│ NORMAL              │ Conforms to learned benign baseline; no alert.   │
├─────────────────────┼──────────────────────────────────────────────────┤
│ SUSPICIOUS_KNOWN    │ Verified anomaly attributed to a known category. │
├─────────────────────┼──────────────────────────────────────────────────┤
│ SUSPICIOUS_UNKNOWN  │ Verified anomaly with unclassified attribution.  │
├─────────────────────┼──────────────────────────────────────────────────┤
│ REVIEW_REQUIRED     │ Material model conflict or borderline evidence.  │
└─────────────────────┴──────────────────────────────────────────────────┘
```

### Category Definitions:

#### A. `NORMAL`
- **Definition:** The network flow exhibits behavioral metrics consistent with learned benign traffic patterns.
- **Trigger Conditions:**
  1. Calibrated fused anomaly score is strictly below the operational threshold:
     $$s_{\text{fused}} < \tau_{\text{operational}} \quad (\text{Default } p_{99.0} = 0.9900)$$
  2. Supervised classifier does not assert a known attack with high confidence ($p < 0.85$ or predicted class is `BENIGN`).
- **Operational Action:** Traffic permitted without SOC operator interruption; summary metrics logged to telemetry stream.

#### B. `SUSPICIOUS_KNOWN`
- **Definition:** The flow is verified as statistically anomalous, and the supervised attack classifier attributes it to a known attack category with high confidence and decision margin.
- **Trigger Conditions:**
  1. Calibrated fused anomaly score meets or exceeds the operational threshold:
     $$s_{\text{fused}} \ge \tau_{\text{operational}}$$
  2. Classifier predicted category is a known attack:
     $$\hat{y}_{\text{clf}} \ne \text{"BENIGN"}$$
  3. Classifier attribution passes all rejection criteria:
     $$\text{Confidence } \ge 0.50 \quad \land \quad \text{Margin } \ge 0.10 \quad \land \quad \text{Entropy } \le 2.00 \text{ bits}$$
- **Operational Action:** High-priority alert routed to Tier-1 SOC analysts with candidate attack signature and feature attributions.

#### C. `SUSPICIOUS_UNKNOWN`
- **Definition:** The flow is verified as anomalous by unsupervised detectors, but cannot be reliably attributed to any known attack category.
- **Trigger Conditions:**
  1. Calibrated fused anomaly score meets or exceeds the operational threshold:
     $$s_{\text{fused}} \ge \tau_{\text{operational}}$$
  2. **EITHER** supervised classifier attribution was rejected (low confidence, narrow margin, or high entropy), **OR** classifier predicted `BENIGN` despite the strong anomaly evidence (open-set signature).
- **Operational Action:** Medium-priority alert routed to Threat Hunting / Tier-2 Forensic specialists for behavioral inspection and potential zero-day or unmodeled attack triage.

#### D. `REVIEW_REQUIRED`
- **Definition:** Independent model components produce contradictory or borderline evidence requiring human analyst arbitration.
- **Trigger Conditions:**
  - **Conflict Type 1 (Detector vs. Classifier):** Anomaly score is below threshold ($s_{\text{fused}} < \tau_{\text{operational}}$), but the supervised classifier insists a known attack with extreme confidence ($p \ge 0.85$).
  - **Conflict Type 2 (Detector Divergence):** Isolation Forest and Deep Autoencoder calibrated scores disagree substantially ($|c_{\text{IF}} - c_{\text{AE}}| \ge 0.50$) on a borderline anomalous flow ($s_{\text{fused}} \in [\tau, \tau + 0.05]$).
- **Operational Action:** Routed to SOC escalation queue for automated contextual packet capture or senior analyst review.

---

## 2. Deterministic Decision Flowchart

```mermaid
flowchart TD
    Start([Network Flow Vector]) --> Score[Score with IF, AE, and XGBoost]
    Score --> Calibrate[Percentile Calibration]
    Calibrate --> Fuse[Fused Anomaly Score s_fused]
    
    Fuse --> CheckAnom{s_fused >= Threshold?}
    
    CheckAnom -- No (Below Anomaly Threshold) --> CheckConf{XGBoost predicts<br/>Known Attack with p >= 0.85?}
    CheckConf -- Yes --> Review1[REVIEW_REQUIRED<br/>'Model Conflict: Normal Anomaly vs Attack Clf']
    CheckConf -- No --> Normal[NORMAL<br/>'Flow conforms to benign baseline']
    
    CheckAnom -- Yes (Above Anomaly Threshold) --> CheckDiv{Severe Detector Divergence<br/>|c_IF - c_AE| >= 0.50<br/>on borderline flow?}
    CheckDiv -- Yes --> Review2[REVIEW_REQUIRED<br/>'Detector Divergence']
    CheckDiv -- No --> CheckRej{Classifier Rejected?<br/>p < 0.50 or Margin < 0.10 or H > 2.0}
    
    CheckRej -- Yes --> Unk1[SUSPICIOUS_UNKNOWN<br/>'Anomalous flow with rejected attribution']
    CheckRej -- No --> CheckBenign{Classifier predicts BENIGN?}
    
    CheckBenign -- Yes --> Unk2[SUSPICIOUS_UNKNOWN<br/>'Anomalous flow; classifier predicted benign']
    CheckBenign -- No --> Known[SUSPICIOUS_KNOWN<br/>'Anomalous flow attributed to known attack']
```

---

## 3. Operational Threshold Configuration

```yaml
decision_policy:
  anomaly_threshold: 0.9900
  threshold_tier: "p99.0"
  detector_disagreement_threshold: 0.50
  high_classifier_conflict_confidence: 0.85
  benign_label: "BENIGN"

rejection:
  min_confidence: 0.50
  min_margin: 0.10
  max_entropy: 2.00
  unknown_label: "UNKNOWN"
```

---

## 4. Structured Output Contract

Every inference result adheres to the following validated schema:

```json
{
  "flow_id": "flow_104829",
  "decision": "SUSPICIOUS_UNKNOWN",
  "decision_reason": "Anomalous flow verified; classifier assigned benign label with insufficient evidence against unsupervised anomaly detection.",
  "anomaly": {
    "isolation_forest_raw_score": 0.6582,
    "isolation_forest_calibrated_score": 0.9912,
    "autoencoder_raw_error": 1.2845,
    "autoencoder_calibrated_score": 0.9934,
    "fused_score": 0.9923,
    "threshold": 0.9900,
    "is_anomaly": true,
    "threshold_tier": "p99.0"
  },
  "classifier": {
    "predicted_class": "BENIGN",
    "top_probability": 0.9842,
    "second_probability": 0.0105,
    "probability_margin": 0.9737,
    "entropy": 0.1245,
    "rejected": false,
    "rejection_reason": null
  },
  "explanation": {
    "decision": "SUSPICIOUS_UNKNOWN",
    "decision_reason": "Anomalous flow verified; classifier assigned benign label...",
    "evidence_summary": [
      "Fused anomaly score (0.9923) exceeded p99.0 operational threshold (0.9900).",
      "Component scores: Isolation Forest (cal=0.9912, raw=0.6582), Autoencoder (cal=0.9934, MSE=1.284500)."
    ],
    "top_contributing_features": [
      {
        "feature_name": "Bwd Packet Length Max",
        "reconstruction_error": 8.421,
        "input_value": 3.12,
        "reconstructed_value": -0.45
      }
    ]
  },
  "model_versions": {
    "isolation_forest": "v1",
    "autoencoder": "v1",
    "xgboost_classifier": "v1",
    "hybrid_engine": "v1"
  }
}
```

---

## 5. Security Analyst Triage Guidelines

1. **Reviewing `SUSPICIOUS_UNKNOWN` Alerts:**
   - Look first at `explanation.top_contributing_features` to identify which protocol counters deviated (e.g. flow duration, packet rates, window sizes).
   - Check destination port and protocol to determine if the activity represents port scanning, web fuzzing, or unexpected background services.
2. **Reviewing `REVIEW_REQUIRED` Alerts:**
   - Prioritize flows where `anomaly_evidence.is_anomaly == false` but `classifier.predicted_class` asserts a high-consequence attack (e.g., `Heartbleed` or `SSH-Patator`).
   - If packet capture confirms attack payload, verify whether the flow was an aborted or truncated connection that evaded volumetric anomaly detection.
