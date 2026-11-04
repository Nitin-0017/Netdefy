# NETDEFY — Phase 3 Completion Audit & Forensic Verification Report

**Author:** NETDEFY MLOps & Machine Learning Engineering Team  
**Evaluation Standard:** Leakage-Safe Temporal Preprocessing Audit  
**Dataset:** CICIDS2017 (`MachineLearningCVE`)  
**Status:** COMPLETE & INDEPENDENTLY AUDITED  
**Execution Timestamp:** 2026-11-04T03:24:52.443320+00:00 (08:54:52 IST)  
**Task ID:** `task-669` (Exit Code: 0)  

---

## 1. Executive Summary & Verification Verdict

Phase 3 of **NETDEFY (Network Defense Intelligence)** is fully executed, tested, and empirically verified. All 2,830,743 raw network flow records across the eight canonical CSV files of CICIDS2017 have been preprocessed through a deterministic, strictly chunk-streamed, leakage-controlled pipeline.

All preprocessed partitions and artifacts have been verified via independent byte-level and schema audits (`scripts/audit_phase3_outputs.py` and `tests/integration/test_processed_datasets.py`).

| Verification Dimension | Standard Requirement | Observed Empirical Result | Status |
| :--- | :--- | :--- | :--- |
| **Row Count Reconciliation** | Exactly 2,830,743 raw rows | **2,830,743** raw rows across train, val, test | **PASS (100%)** |
| **Feature Schema** | 76 service-independent flow features | **76 features** (plus 1 evaluation target: `Label`) | **PASS** |
| **Model Target Isolation** | `Label` excluded from feature matrices | `Label` isolated to column index 76 in Parquet | **PASS** |
| **Identifier Leakage** | Zero IP/Port/ID/Timestamp columns | **0** identifiers present (`Flow ID`, IPs dropped) | **PASS** |
| **Duplicate Header Resolution** | Column 55 `Fwd Header Length.1` dropped | Exactly 1 redundant column dropped | **PASS** |
| **Imputer Fitting Boundary** | Fit strictly on Monday training flows | `imputer.joblib` fitted on Monday benign flows | **PASS** |
| **Scaler Fitting Boundary** | Fit strictly on Monday training flows | `standard_scaler.joblib` fitted on Monday benign flows | **PASS** |
| **Numerical Integrity** | Zero NaNs, Zero Infinities | **0 NaNs, 0 Infinities** in all partitions | **PASS** |
| **Memory Efficiency** | Stay strictly within 8 GB RAM budget | **752.62 MB** peak RAM utilized | **PASS** |
| **Test Suite Compliance** | 100% pass rate, Ruff lint, Strict MyPy | **61 / 61 tests passed**, 0 lint/format/type issues | **PASS** |

---

## 2. Actual Partition Counts & Reconciliation

The 2,830,743 raw flow records were partitioned strictly by day-wise boundaries. No random row-level splitting was permitted.

### Empirical Partition Breakdown

| Partition | Calendar Days & Files | Raw Rows (View A) | Deduplicated Rows (View B) | Records Purged | Retention Rate (%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Train** | Monday (1 file: `Monday-WorkingHours.pcap_ISCX.csv`) | 529,918 | 459,112 | 70,806 | 86.64% |
| **Validation** | Tue & Wed (2 files: `Tuesday-WorkingHours`, `Wednesday-workingHours`) | 1,138,612 | 963,879 | 174,733 | 84.65% |
| **Test (Untouched)** | Thu & Fri (5 files: WebAttacks, Infiltration, Bot, PortScan, DDoS) | 1,162,213 | 845,403 | 316,810 | 72.74% |
| **TOTAL** | **All 8 Canonical Files** | **2,830,743** | **2,268,394** | **562,349** | **80.13%** |

### Mathematical Reconciliation of Original Raw Rows
$$\text{Raw Total} = 529{,}918 \;(\text{Train}) + 1{,}138{,}612 \;(\text{Validation}) + 1{,}162{,}213 \;(\text{Test}) = 2{,}830{,}743$$

Every difference between View A (Raw) and View B (Deduplicated) is accounted for by exact intra-partition duplicate collisions and cross-partition training overlap:
- **Intra-Partition Duplicates Purged:** 70,806 (Train) + 166,683 (Validation) + 306,182 (Test) = **543,671 records**.
- **Cross-Partition Overlap with Monday Purged:** 8,050 (Validation) + 10,628 (Test) = **18,678 records**.
- **Total Reductions:** $543{,}671 + 18{,}678 = 562{,}349$ records.
- **Verification:** $2{,}830{,}743 - 562{,}349 = 2{,}268{,}394$ retained records in View B.

---

## 3. Final Feature Schema Reconciliation

A programmatically verified schema (`artifacts/preprocessing/feature_schema.json`) reconciles historical literature discrepancies:

1. **Raw CSV Columns:** 79 columns.
2. **Ground Truth Target:** 1 column (`Label`), isolated for ground truth scoring and never passed as an input feature.
3. **Duplicate Hardware Header:** Column 55 (`Fwd Header Length.1`) is identical to Column 34 (`Fwd Header Length`) due to a CICFlowMeter tapping duplication bug. It is completely dropped.
4. **Candidate Flow Features:** $79 - 1 - 1 = 77$ unique candidate features.
5. **Destination Port:** Discretized into categorical `Service_Category` (e.g., HTTP, HTTPS, DNS, SSH, FTP, Ephemeral) and preserved alongside raw `Destination Port` in the audit datasets (`*_audit.parquet`).
6. **Final Continuous Feature Set:** **76 service-independent flow dynamics features** (Durations, Packet Counts, Byte Rates, Inter-Arrival Times, Flag Counts, Subflow Statistics, and Window Sizes).

### Excluded Columns Matrix

| Column Name | Action | Concrete Technical & Scientific Rationale |
| :--- | :--- | :--- |
| `Label` | **Target Only** | Ground truth string (`BENIGN` or attack name). Must never enter model input matrix. |
| `Fwd Header Length.1` | **Dropped** | Exact duplicate of column 34 created by packet parser bugs; introduces collinear singularity. |
| `Flow ID` | **Excluded** | High-cardinality testbed identifier; causes fatal shortcut memorization. |
| `Source IP` | **Excluded** | Identifies specific attacker/victim subnets (e.g. `192.168.10.x`); destroys temporal generalization. |
| `Destination IP` | **Excluded** | Identifies local testbed server IPs; causes server-fingerprinting shortcuts. |
| `Timestamp` | **Excluded** | Not present at row-level in `MachineLearningCVE`; temporal progression is preserved via file boundaries. |
| `Source Port` | **Excluded** | Ephemeral, non-stationary client port allocation; induces severe overfitting. |

---

## 4. Missing & Infinite Value Treatment

In network flow captures, zero flow duration produces division-by-zero artifacts resulting in $+\infty$ and $-\infty$ values in `Flow Bytes/s` and `Flow Packets/s`.

### Empirical Cleaning Summary

| Partition | Infinities Converted ($\pm\infty \to \text{NaN}$) | Missing Values Imputed ($\text{NaN} \to \text{Median}$) | Imputation Source |
| :--- | :--- | :--- | :--- |
| `train` (Monday Raw) | **810** | **874** | Monday Training Median (Fitted) |
| `validation` (Tue/Wed Raw) | **1,913** | **3,122** | Monday Training Median (Frozen) |
| `test` (Thu/Fri Raw) | **1,653** | **1,738** | Monday Training Median (Frozen) |
| **Total Interventions** | **4,376** | **5,734** | Strict Train-Only Parameters |

### Zero-Variance Features in Monday Baseline
During fitting on Monday training data, 10 features exhibited zero variance (constant at 0.0):
`Bwd PSH Flags`, `Fwd URG Flags`, `Bwd URG Flags`, `CWE Flag Count`, `Fwd Avg Bytes/Bulk`, `Fwd Avg Packets/Bulk`, `Fwd Avg Bulk Rate`, `Bwd Avg Bytes/Bulk`, `Bwd Avg Packets/Bulk`, and `Bwd Avg Bulk Rate`.

To prevent division-by-zero during standardization, `FeatureScaler` applies an epsilon guard ($\epsilon = 10^{-8}$): features with $\sigma < \epsilon$ are assigned a unit scale factor ($s = 1.0$) with center $c = 0.0$, guaranteeing numerical stability without distortion.

---

## 5. Duplicate Investigation & Handling (View A vs View B)

### Impact on Attack & Benign Class Distributions

| Partition | Benign Retained | Benign Removed | Attacks Retained | Attacks Removed | Attack % (View A) | Attack % (View B) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Train** | 459,112 | 70,806 | 0 | 0 | 0.00% | 0.00% |
| **Validation** | 760,061 | 112,044 | 203,818 | 62,689 | 23.41% | 21.15% |
| **Test** | 711,935 | 159,139 | 133,468 | 157,671 | 25.05% | 15.79% |

### Scientific Discussion on Repeated Network Behavior
1. **Periodic Infrastructure Flows:** Repeated network transactions (e.g., DNS queries to `8.8.8.8` on port 53, NTP time synchronizations, ARP requests) occur continuously across all days.
2. **Evaluation Leakage Hazard:** If an exact training record appears in the test partition, an anomaly detection model or classifier could achieve artificially high detection scores purely through nearest-neighbor lookup or kernel memorization.
3. **Dual Preservation Policy:** NETDEFY preserves **View A** (all 2,830,743 original flows) to benchmark against published literature, and **View B** (2,268,394 leakage-controlled flows) to evaluate true generalization to novel behavioral flows.

---

## 6. Training-Only Imputation & Scaling Provenance

To guarantee zero information leakage, transformers were fitted strictly on Monday benign flows before evaluation data was touched:

```
[Monday Raw (529,918)] ──> [Deduplicator] ──> [Monday Dedup (459,112)]
                                                       │
                               ┌───────────────────────┴───────────────────────┐
                               ▼                                               ▼
                      [Fit DataCleaner]                              [Transform Monday]
                      Median parameters:                                       │
                      artifacts/imputer.joblib                                 ▼
                               │                                     [Fit FeatureScaler]
                               │                                     Mean & Std parameters:
                               │                                     artifacts/standard_scaler.joblib
                               ▼                                               ▼
                    ┌─────────────────────────────────────────────────────────────────────┐
                    │               FROZEN TRANSFORMERS APPLIED DOWNSTREAM                │
                    │               (Validation and Test Never Refit Scalers)             │
                    └─────────────────────────────────────────────────────────────────────┘
```

1. **Imputer Provenance:** `artifacts/preprocessing/imputer.joblib` contains medians derived strictly from Monday. Validation outliers (e.g. DoS packet bursts) cannot alter the imputation baseline.
2. **Scaler Provenance:** `artifacts/preprocessing/standard_scaler.joblib` and `robust_scaler.joblib` contain centers ($\mu$) and scales ($\sigma$) derived strictly from cleaned Monday training data.
3. **Verified Mathematical Guarantee:** Test suite `test_validation_values_cannot_change_fitted_training_imputer` and `test_validation_values_cannot_change_fitted_training_scaler` explicitly verify that injecting extreme outliers into evaluation datasets does not modify the trained transformer parameters.

---

## 7. Resource Consumption & System Efficiency

The pipeline was executed on an Apple Silicon M3 (arm64) system with 8 GB unified memory.

| Metric | Target Specification | Observed Measurement |
| :--- | :--- | :--- |
| **Total Duration** | $< 10.0$ minutes | **75.95 seconds (1.27 min)** |
| **Peak RAM Utilization** | $< 4.0$ GB (Strict Budget) | **752.62 MB** |
| **Row Streaming Chunk Size**| 50,000 rows | **50,000 rows** |
| **Total Disk Space (Processed)**| $< 2.0$ GB | **492 MB** |
| **Float Precision** | `float32` (PyTorch MPS ready) | **`np.float32` verified across all matrices** |

### Produced Datasets on Disk

```
data/processed/
├── train/
│   ├── train_raw.parquet        (52.02 MB, 529,918 rows, 77 cols)
│   ├── train_dedup.parquet      (48.10 MB, 459,112 rows, 77 cols)
│   └── train_audit.parquet      ( 0.71 MB, 459,112 rows,  3 cols)
├── validation/
│   ├── validation_raw.parquet   (103.45 MB, 1,138,612 rows, 77 cols)
│   ├── validation_dedup.parquet ( 96.15 MB,   963,879 rows, 77 cols)
│   └── validation_audit.parquet (  1.27 MB,   963,879 rows,  3 cols)
└── test/
    ├── test_raw.parquet         ( 91.78 MB, 1,162,213 rows, 77 cols)
    ├── test_dedup.parquet       ( 84.23 MB,   845,403 rows, 77 cols)
    └── test_audit.parquet       (  0.95 MB,   845,403 rows,  3 cols)
```

---

## 8. Testing & Code Quality Verification

The codebase adheres strictly to professional MLOps and software engineering quality standards:

1. **Ruff Linter:** Passed with 0 errors across all 65 Python files.
2. **Ruff Formatter:** All 65 files strictly adhere to Black/PEP 8 formatting rules.
3. **Strict MyPy:** Passed with 0 type errors across 47 source files in `src`, `tests`, and `scripts`.
4. **Pytest Test Suite:** **61 passed tests out of 61** (100% pass rate).
   - Foundation & Config tests: 14 passed
   - Data Acquisition & Forensic tests: 19 passed
   - Leakage-safe Preprocessing unit tests: 24 passed
   - End-to-end integration tests (including parquet disk audit): 4 passed

---

## 9. Remaining Limitations & Architectural Considerations

1. **Absence of Sub-Hour Timestamps:** As proven in Phase 2, the `MachineLearningCVE` CSV files do not contain packet-level timestamps. Chronological progression is enforced at the file level (Monday $\to$ Tuesday/Wednesday $\to$ Thursday/Friday).
2. **Constant Features in Baseline:** Ten features are constant during Monday benign traffic. If future models require feature reduction, these zero-variance features can be cleanly pruned based on `imputer.constant_columns_in_training`.
3. **Non-I.I.D. Concept Drift:** Attack types present on Thursday and Friday (Web Attacks, Infiltration, Bot, PortScan, DDoS) do not appear in the Monday training data. This intentional distribution shift is the core research subject of NETDEFY.

---

## 10. Phase 4 Readiness Verdict

### Final Verdict: **READY FOR PHASE 4 (BASELINE ANOMALY DETECTION ENGINE)**

All criteria for Phase 3 completion have been satisfied with zero shortcuts:
- Dual evaluation matrices (`raw` and `dedup`) are generated, validated, and serialized to Parquet format.
- Preprocessing artifacts (`imputer.joblib`, `standard_scaler.joblib`, `robust_scaler.joblib`, `feature_schema.json`) are preserved with complete provenance metadata.
- Preprocessing integration test suite confirms 100% compliance.
- No model has been trained, no threshold has been calibrated, and the final test set remains completely isolated.

**Awaiting user approval to proceed to Phase 4.**

