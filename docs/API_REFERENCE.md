# NETDEFY — API Reference & Schema Specification

> **Base URL:** `http://localhost:8000`  
> **API Version:** `v1` (`/api/v1/*`)  
> **Interactive OpenAPI Docs:** `http://localhost:8000/docs`  
> **Research Workbench UI:** `http://localhost:8000/workbench`  

---

## 1. Authentication & Headers

- **Optional API Key Authentication:** If `NETDEFY_API_KEY` is configured in `.env`, analyst-level routes require:
  ```http
  X-API-Key: your-secure-api-key-here
  ```
- **Standard Observability Headers:** Every response returns:
  - `X-Request-ID`: Unique UUID tracking the request lifecycle.
  - `X-Process-Time-Ms`: End-to-end execution latency in milliseconds.

---

## 2. Research & Evaluation Endpoints (`/api/v1/research/*`)

### 2.1 Research Overview
```http
GET /api/v1/research/overview
```
* **Description:** Returns high-level research objectives, baseline datasets, model architectures, and key scientific findings.
* **Response `200 OK`:**
```json
{
  "project": "NETDEFY",
  "tagline": "Detect Anomalies. Understand Network Behaviour.",
  "research_objective": "Evaluate whether a hybrid anomaly detection system can identify suspicious network traffic...",
  "datasets": {
    "primary": "CICIDS2017 MachineLearningCSV (July 3-7, 2017)",
    "independent_validation": "CSE-CIC-IDS2018 (March 1, 2018)"
  },
  "verified_metrics": {
    "hybrid_holdout_auroc": 0.7377,
    "hybrid_holdout_pr_auc": 0.4318,
    "operational_alert_precision": 0.8473,
    "attack_escalation_recall": 0.2773,
    "operational_f1": 0.4178
  }
}
```

### 2.2 Head-to-Head Model Comparison
```http
GET /api/v1/research/comparison
```
* **Description:** Returns verified View A (Full 50k benchmark) and View B (Disambiguated 46.7k benchmark) metrics across Isolation Forest, Deep Autoencoder, XGBoost, and the Hybrid Engine.
* **Response `200 OK`:**
```json
{
  "benchmark_partition": "data/benchmark/v1/test.parquet (50,000 flows)",
  "models": [
    {
      "id": "isolation_forest",
      "name": "Isolation Forest",
      "holdout_test_view_a": {
        "roc_auc": 0.6558,
        "pr_auc": 0.3423,
        "precision": 0.5106,
        "recall": 0.0654,
        "f1": 0.1159
      }
    },
    {
      "id": "hybrid_engine",
      "name": "NETDEFY Hybrid Intelligence Engine",
      "holdout_test_view_a": {
        "fused_score_roc_auc": 0.7377,
        "fused_score_pr_auc": 0.4318,
        "operational_alert_precision": 0.8473,
        "operational_attack_recall": 0.2773,
        "operational_f1": 0.4178,
        "false_alarm_reduction_vs_ae": "-46.5%"
      },
      "holdout_test_view_b": {
        "attack_detection_recall": 0.3746,
        "operational_f1": 0.5196,
        "disambiguation_gain": "+35.1% relative recall gain when excluding label collisions"
      }
    }
  ]
}
```

### 2.3 Empirical Threshold Calibration
```http
GET /api/v1/research/thresholds
```
* **Description:** Returns calibrated percentile cutoffs for Autoencoder, Isolation Forest, and Hybrid score fusion fitted strictly on $15,315$ benign validation flows.
* **Response `200 OK`:**
```json
{
  "calibration_dataset": "data/benchmark/v1/validation.parquet (20,000 flows)",
  "methodology": "Empirical quantile estimation on benign validation distribution with zero test leakage",
  "threshold_tiers": [
    {
      "tier": "p95.0",
      "name": "High Sensitivity (Forensic Capture)",
      "autoencoder_mse_threshold": 0.096558,
      "isolation_forest_threshold": 0.563559,
      "hybrid_fused_threshold": 0.937041,
      "benign_fpr": "4.8% - 5.2%"
    },
    {
      "tier": "p99.0",
      "name": "Balanced Operational (Default Production Policy)",
      "autoencoder_mse_threshold": 0.708433,
      "isolation_forest_threshold": 0.650183,
      "hybrid_fused_threshold": 0.982084,
      "benign_fpr": "1.67% (16.7 alarms / 1,000 flows)"
    },
    {
      "tier": "p99.5",
      "name": "High Specificity (Critical Threat Priority)",
      "autoencoder_mse_threshold": 1.951052,
      "isolation_forest_threshold": 0.694358,
      "hybrid_fused_threshold": 0.992959,
      "benign_fpr": "0.5% (5 alarms / 1,000 flows)"
    }
  ]
}
```

### 2.4 Confusion Matrices & Diagnostics
```http
GET /api/v1/research/confusion-matrix
```
* **Description:** Returns the $8 \times 8$ closed-set validation matrix and the $14$-class holdout open-set confusion matrix.

### 2.5 Feature Importance Rankings
```http
GET /api/v1/research/feature-importance
```
* **Description:** Returns global tree split gain rankings across all 76 continuous features.

---

## 3. Interactive Inference Playground Endpoints (`/api/v1/playground/*`)

### 3.1 Curated Benchmark Samples
```http
GET /api/v1/playground/samples
```
* **Description:** Returns 11 verified physical network flows extracted from the holdout benchmark representing validated attack categories and benign traffic.
* **Response `200 OK`:**
```json
{
  "count": 11,
  "samples": [
    {
      "id": "benign_web",
      "name": "Normal Enterprise Web Browsing (Monday Capture)",
      "ground_truth_label": "BENIGN",
      "source_day": "Monday",
      "expected_decision": "NORMAL",
      "features": { "Flow Duration": 1205.0, ... }
    },
    {
      "id": "dos_slowloris",
      "name": "DoS Slowloris Connection Exhaustion (Wednesday)",
      "ground_truth_label": "DoS slowloris",
      "source_day": "Wednesday",
      "expected_decision": "REVIEW_REQUIRED",
      "features": { ... }
    }
  ]
}
```

### 3.2 Live Multi-Paradigm Prediction
```http
POST /api/v1/playground/predict
Content-Type: application/json
```
* **Request Payload:**
```json
{
  "flow_id": "flow_demo_01",
  "is_synthetic": false,
  "features": {
    "Flow Duration": 14205.0,
    "Total Fwd Packets": 12.0,
    "Total Backward Packets": 8.0,
    ...
  }
}
```
* **Response `200 OK`:**
```json
{
  "flow_id": "flow_demo_01",
  "decision": "SUSPICIOUS_KNOWN",
  "anomaly": {
    "fused_score": 0.9904,
    "autoencoder_mse": 0.8412,
    "autoencoder_percentile": 0.9921,
    "isolation_forest_raw": 0.6721,
    "isolation_forest_percentile": 0.9887,
    "threshold_p99": 0.982084,
    "is_anomaly": true
  },
  "classifier": {
    "attributed_class": "DoS Slowhttptest",
    "top_probability": 0.9985,
    "decision_margin": 0.9972,
    "normalized_entropy": 0.0084,
    "class_probabilities": {
      "BENIGN": 0.0012,
      "DoS Slowhttptest": 0.9985,
      ...
    }
  },
  "explanation": {
    "autoencoder_top_deviating_features": [
      { "feature": "Fwd Packet Length Min", "error": 0.4128 },
      { "feature": "Min Packet Length", "error": 0.3891 },
      { "feature": "Flow Duration", "error": 0.2740 }
    ],
    "xgboost_feature_gain": [
      { "feature": "Bwd Packet Length Max", "gain": 549.47 },
      { "feature": "Init_Win_bytes_forward", "gain": 328.12 }
    ]
  },
  "is_synthetic": false
}
```

---

## 4. Real-Time Streaming Endpoints (`/api/v1/events/*` & `/api/v1/stream/*`)

### 4.1 Ingest Flow Event Batch
```http
POST /api/v1/events/ingest
Content-Type: application/json
```
* **Request Payload:** Array of event objects adhering to the 76-continuous-feature schema.
* **Response Codes:**
  * `202 Accepted`: Event batch successfully validated and placed onto the event stream.
  * `422 Unprocessable Content`: Missing required flow features or non-finite rate values.
  * `429 Too Many Requests`: Adaptive backpressure admission controller throttled the request due to queue lag ($> 5,000$ messages) or critical memory utilization.

### 4.2 Stream Health & Lag Observability
```http
GET /api/v1/stream/metrics
```
* **Response `200 OK`:** Returns stream depth, pending entry list (PEL) count, consumer lag, and DLQ message counts.

## 5. Network Threat Detection Platform Endpoints

### 5.1 Detection Schema & Metadata
```http
GET /api/v1/detection/schema
```
* **Response `200 OK`:** Returns metadata for all 76 continuous features (grouped into 9 operational categories with physical units and default values), 8 trained attack classes, and 7 absent open-set categories.

### 5.2 Single-Flow Inference
```http
POST /api/v1/detection/analyze-flow
Content-Type: application/json
```
* **Request Payload:** `{ "features": { ... }, "flow_id": "...", "source": "..." }`
* **Response `200 OK`:** Returns 4-state operational triage decision (`NORMAL`, `SUSPICIOUS_KNOWN`, `SUSPICIOUS_UNKNOWN`, `REVIEW_REQUIRED`), model score breakdown (Isolation Forest, Autoencoder MSE, Fused Score), supervised class attribution, confidence margin, top contributing feature residuals, and audit session ID.

### 5.3 Batch Inference
```http
POST /api/v1/detection/analyze-batch
Content-Type: application/json
```
* **Request Payload:** `{ "flows": [ { "features": { ... }, "flow_id": "..." } ], "source_name": "..." }`
* **Response `200 OK`:** Returns vectorized multi-model predictions, decision distribution summary, and persistent audit record.

### 5.4 CSV Telemetry Upload
```http
POST /api/v1/detection/upload-csv
Content-Type: multipart/form-data
```
* **Form Data:** `file: <traffic.csv>`, `max_rows: 250`
* **Response `200 OK`:** Validates 76 continuous features, isolates ground-truth `Label` column if present (never fed to models), evaluates batch, persists analysis session, and returns comprehensive prediction breakdown.

### 5.5 Download Sample Benchmark CSV
```http
GET /api/v1/detection/sample-csv
```
* **Response `200 OK`:** Serves `netdefy_sample_network_traffic.csv` containing 28 verified CICIDS2017 benchmark flows.

### 5.6 Forensic Detection History
```http
GET /api/v1/detection/history
GET /api/v1/detection/history/{session_id}
DELETE /api/v1/detection/history
GET /api/v1/detection/stats
```
* Provides persistent audit logging, flow-level inspection of historical analyses, and aggregated operational triage statistics.

