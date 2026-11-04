# NETDEFY — Exploratory Data Analysis (EDA) Existing Work Inventory
## Comprehensive Forensic, Preprocessing & Statistical Evidence Audit

**Project:** NETDEFY — Network Defense Intelligence  
**Document:** `reports/EDA_EXISTING_WORK_INVENTORY.md`  
**Evaluation Standard:** Research-Grade ML Exploratory Audit & Provenance Verification  
**Audit Scope:** Repository-Wide Investigation across `reports/`, `scripts/`, `src/`, `configs/`, `data/`, and `artifacts/`  
**Execution Timestamp:** 2026-11-04  
**Target Notebook Suite:** `notebooks/01_dataset_overview.ipynb`, `02_data_quality_analysis.ipynb`, `03_feature_exploration.ipynb`, `04_attack_pattern_analysis.ipynb`  

---

## 1. Executive Summary

Prior to creating the `notebooks/` directory in NETDEFY, a comprehensive repository-wide investigation was conducted to determine whether dataset understanding, exploratory data analysis (EDA), statistical profiling, feature analysis, data-quality inspection, or attack-pattern analysis had already been performed during earlier development phases (Phases 1 through 4C).

### Core Audit Verdict:
- **Substantial Forensic and Preprocessing Evidence Exists:** Extensive statistical and forensic analyses were performed during Phase 2 (Forensic Inspection), Phase 3 (Preprocessing and Feature Selection), Phase 3.1 (Duplicate Policy & Label Integrity Audit), Phase 3.2 (200K Benchmark Construction), and Phase 4 (Anomaly & Classification Evaluations).
- **Distinction Between Operational Preprocessing and True EDA:** Historically, analytical outputs were compiled into specialized Markdown reports (`reports/*.md`) and JSON manifests (`reports/*.json`, `artifacts/preprocessing/*.json`) to validate engineering invariants (e.g., zero data leakage, clean schema, hash deduplication), rather than interactive exploratory Jupyter notebooks.
- **Recoverable, Reproducible, and Documentable:** 100% of the underlying raw and benchmark datasets are intact. All previous metrics are reproducible from source files without modifying existing model weights or benchmark partitions.
- **Identified Analytical Gaps (New Analysis Required):** While forensic summaries and error evaluations were documented, systematic distribution profiling (skewness, kurtosis across all 76 continuous features), pairwise correlation matrices with collinear cluster detection, and multi-metric comparative feature visualisations between benign and attack categories were not compiled into interactive exploratory artifacts. These have been identified and designated for safe, reproducible new analysis in the notebook suite.

---

## 2. Master EDA Evidence Inventory

The table below summarizes the 17 required investigative areas, cross-referencing existing evidence, source locations, reproducibility, and their mapped status in the notebook suite.

| Analysis Domain | Existing Evidence | Source Location | Reproducible | Notebook Status |
| :--- | :--- | :--- | :---: | :---: |
| **1. Dataset Structure & Dimensions** | Exact file sizes, row counts (2,830,743 flows), column counts (79 raw), file volumes (843.66 MB across 8 CSVs). | `reports/dataset_forensic_summary.md`<br>`reports/dataset_forensic_summary.json`<br>`scripts/inspect_dataset.py` | Yes | **COMPLETED**<br>(Notebook 01) |
| **2. Feature Descriptions & Types** | 78 numeric cols, 1 label, duplicate header `Fwd Header Length.1` identified at col 55, port mapping, 76 continuous features. | `reports/feature_schema.md`<br>`reports/feature_selection_report.md`<br>`artifacts/preprocessing/feature_schema.json` | Yes | **COMPLETED**<br>(Notebook 01) |
| **3. Class Distribution & Imbalance** | 15 ground-truth classes, exact row counts, percentages (80.30% Benign, 19.70% Attacks), severe long-tail imbalance (206k:1 ratio). | `reports/label_distribution.md`<br>`reports/label_distribution.csv`<br>`reports/dataset_forensic_summary.json` | Yes | **COMPLETED**<br>(Notebook 01) |
| **4. Day-Wise Traffic Distribution** | Daily operational windows (Mon–Fri), absence of row-level timestamps in `MachineLearningCVE`, attack schedules. | `reports/temporal_distribution.md`<br>`reports/temporal_distribution.csv`<br>`reports/temporal_partition_report.md` | Yes | **COMPLETED**<br>(Notebook 01) |
| **5. Missing-Value Analysis** | 288 missing values in `Flow Bytes/s` across raw CSVs; zero in other 78 columns; median imputation fitted on Monday baseline. | `reports/missing_value_report.md`<br>`reports/preprocessing_report.md`<br>`src/netdefy/preprocessing/cleaner.py` | Yes | **COMPLETED**<br>(Notebook 02) |
| **6. Infinite-Value Analysis** | 4,376 infinite values (`Flow Bytes/s`, `Flow Packets/s`) from zero flow durations; converted to NaN and median imputed. | `reports/missing_value_report.md`<br>`reports/dataset_forensic_summary.json`<br>`src/netdefy/preprocessing/cleaner.py` | Yes | **COMPLETED**<br>(Notebook 02) |
| **7. Duplicate Records & Vectors** | 256,479 intra-file raw duplicates (9.06%), 51,902 inter-file duplicates, 543,671 feature-only duplicate flows across partitions. | `reports/duplicate_investigation.md`<br>`reports/duplicate_overlap_report.md`<br>`reports/PHASE3_1_DUPLICATE_LABEL_INTEGRITY_AUDIT.md` | Yes | **COMPLETED**<br>(Notebook 02) |
| **8. Conflicting Labels** | 130 feature vectors in raw data have identical 76 features but conflicting labels (Benign vs Attack); 0 attack-vs-attack conflicts. | `reports/PHASE3_1_DUPLICATE_LABEL_INTEGRITY_AUDIT.md`<br>`reports/phase3_1_duplicate_audit.json`<br>`data/benchmark/v1/metadata/ambiguity_manifest.json` | Yes | **COMPLETED**<br>(Notebook 02) |
| **9. Cross-Partition Overlap** | 18,678 rows in Tue/Wed and Thu/Fri matching Monday training features; purged in View B; verified 0 overlap in benchmark v1. | `reports/duplicate_overlap_report.md`<br>`reports/PHASE3_1_FINAL_ACCOUNTING_VERIFICATION.md`<br>`data/benchmark/v1/metadata/sampling_audit.json` | Yes | **COMPLETED**<br>(Notebook 02) |
| **10. Feature Distributions & Skewness** | Training medians documented; scaler bounds saved; comprehensive 76-feature skewness/kurtosis profiling not compiled. | `reports/missing_value_report.md`<br>`artifacts/preprocessing/standard_scaler.joblib` | Yes | **PARTIAL** (Historical)<br>$\to$ **COMPLETED** (New in NB 03) |
| **11. Correlation Analysis** | Redundant duplicate column removed; packet/byte collinearities noted qualitatively; systematic correlation matrix not compiled. | `reports/feature_selection_report.md`<br>`src/netdefy/preprocessing/schema.py` | Yes | **PARTIAL** (Historical)<br>$\to$ **COMPLETED** (New in NB 03) |
| **12. Feature Outlier Analysis** | Quantile properties noted during scaler design (Standard vs Robust scaler); systematic IQR and tail outlier profiling not compiled. | `reports/preprocessing_report.md`<br>`src/netdefy/preprocessing/scaler.py` | Yes | **PARTIAL** (Historical)<br>$\to$ **COMPLETED** (New in NB 03) |
| **13. Benign vs Malicious Patterns** | High-level detection error analysis in Phase 4; qualitative packet length, duration, and packet rate differences documented. | `reports/PHASE4A_ISOLATION_FOREST_REPORT.md`<br>`reports/PHASE4B_AUTOENCODER_REPORT.md`<br>`reports/PHASE4C_CLASSIFICATION_REPORT.md` | Yes | **PARTIAL** (Historical)<br>$\to$ **COMPLETED** (New in NB 03 & 04) |
| **14. Attack-Specific Feature Behaviour** | PortScan single SYN structure, DoS/DDoS volumetric asymmetry, Patator brute-force retries documented in Phase 4 error audits. | `reports/PHASE3_1_DUPLICATE_LABEL_INTEGRITY_AUDIT.md`<br>`reports/PHASE4B_AUTOENCODER_REPORT.md`<br>`reports/PHASE4C_CLASSIFICATION_REPORT.md` | Yes | **COMPLETED** (Documented)<br>+ Extended in NB 04 |
| **15. Rare Attack Analysis** | 100% census retention of Heartbleed (11), SQLi (21), Infiltration (36), XSS (652), Brute Force (1,507), Bot (1,966) verified. | `reports/PHASE3_1_DUPLICATE_LABEL_INTEGRITY_AUDIT.md`<br>`reports/PHASE3_2_BENCHMARK_CONSTRUCTION.md`<br>`data/benchmark/v1/supplementary/rare_class_diagnostic.parquet` | Yes | **COMPLETED**<br>(Notebook 04) |
| **16. Feature Selection & Importance** | Port/IP exclusion rationale; service independence; XGBoost feature importance rankings (Gini gain, weight) saved and plotted. | `reports/feature_selection_report.md`<br>`reports/PHASE4C_CLASSIFICATION_REPORT.md`<br>`artifacts/models/xgboost_classifier/v1/feature_importance.json` | Yes | **COMPLETED**<br>(Notebook 03 & 04) |
| **17. Temporal Distribution & Partitions** | Chronological holdout design (Mon baseline, Tue/Wed train/val, Thu/Fri test); zero attack leakage into one-class training verified. | `reports/temporal_partition_report.md`<br>`reports/PHASE3_2_BENCHMARK_CONSTRUCTION.md`<br>`data/benchmark/v1/metadata/benchmark_manifest.json` | Yes | **COMPLETED**<br>(Notebook 01) |

---

## 3. Detailed Investigation of Each Analysis Domain

### 1. Dataset Structure and Dimensions
- **What was analyzed:** Physical file properties, total row counts, byte volumes, and schema uniformity across all 8 raw CSVs.
- **Where performed:** Phase 2 Forensic Inspection; executed via `scripts/inspect_dataset.py` calling `DatasetForensicInspector.inspect_directory()`.
- **Dataset / Partition:** Raw uncompressed CSV files in `data/raw/MachineLearningCVE/*.csv` (843.66 MB total).
- **Actual Results Available:** Yes, preserved in `reports/dataset_forensic_summary.md` and `reports/dataset_forensic_summary.json`. Total rows: 2,830,743; Total columns: 79; All 8 files share identical schema headers.
- **Reproducibility:** 100% reproducible by running `scripts/inspect_dataset.py`.
- **Classification:** Forensic Inspection.

### 2. Feature Descriptions and Feature Types
- **What was analyzed:** Column naming, inferred data types, duplicate column detection, service categorization, and target variable isolation.
- **Where performed:** Phase 3 Feature Selection and Schema Definition; implemented in `src/netdefy/preprocessing/schema.py` and `scripts/preprocess_data.py`.
- **Dataset / Partition:** Raw CSV schema headers and preprocessed Parquet schemas.
- **Actual Results Available:** Yes, preserved in `reports/feature_schema.md`, `reports/feature_selection_report.md`, and `artifacts/preprocessing/feature_schema.json`. Identifies 78 candidate numeric features, excludes duplicate `Fwd Header Length.1` (col 55), excludes `Destination Port` from continuous training features (mapped to categorical `Service_Category`), isolating exactly 76 service-independent continuous features.
- **Reproducibility:** 100% reproducible via `build_feature_schema()`.
- **Classification:** Preprocessing Validation & Schema Definition.

### 3. Class Distribution and Class Imbalance
- **What was analyzed:** Full enumeration of ground-truth network traffic labels, exact sample frequencies, global percentages, and per-file distributions.
- **Where performed:** Phase 2 Forensic Inspection; generated by `DatasetForensicInspector`.
- **Dataset / Partition:** Complete 2,830,743 raw flow records.
- **Actual Results Available:** Yes, preserved in `reports/label_distribution.md`, `reports/label_distribution.csv`, and `reports/dataset_forensic_summary.json`. Shows 2,273,097 Benign flows (80.30%) and 557,646 Attack flows (19.70%) spanning 15 distinct classes. Imbalance ratio ranges from 1:1 for DoS Hulk to 206,645:1 for Heartbleed (11 flows).
- **Reproducibility:** 100% reproducible.
- **Classification:** Exploratory Analysis & Forensic Inspection.

### 4. Day-Wise Traffic Distribution
- **What was analyzed:** Calendar day and operational window alignment for each capture file, telemetry limitations (lack of row-level timestamps), and attack schedule mapping.
- **Where performed:** Phase 2 Forensic Inspection and Phase 3 Temporal Partitioning.
- **Dataset / Partition:** All 8 raw CSVs.
- **Actual Results Available:** Yes, preserved in `reports/temporal_distribution.md` and `reports/temporal_distribution.csv`. Confirms that row-level `Timestamp` was omitted by UNB in `MachineLearningCVE`, establishing file-boundary chronological truth: Monday (Jul 3), Tuesday (Jul 4), Wednesday (Jul 5), Thursday (Jul 6), Friday (Jul 7).
- **Reproducibility:** 100% reproducible.
- **Classification:** Forensic Inspection & Protocol Architecture.

### 5. Missing-Value Analysis
- **What was analyzed:** Occurrence of null/NaN values across all 79 columns, identifying affected features, and proving leakage-free imputation.
- **Where performed:** Phase 2 Forensic Inspection and Phase 3 Cleaning; implemented in `src/netdefy/preprocessing/cleaner.py`.
- **Dataset / Partition:** Raw CSVs, processed partitions (`data/processed/`), and benchmark v1.
- **Actual Results Available:** Yes, documented in `reports/missing_value_report.md`. Exactly 288 missing values existed in `data/raw/`, all concentrated in `Flow Bytes/s`. Zero missing values existed in the other 78 columns. Median imputation parameters were fitted exclusively on Monday training traffic (`4514.53` bytes/s).
- **Reproducibility:** 100% reproducible via `CleanTransformer`.
- **Classification:** Data-Quality Forensic Inspection & Preprocessing Validation.

### 6. Infinite-Value Analysis
- **What was analyzed:** Occurrence of positive and negative floating-point infinities (`inf`, `-inf`) arising from zero-duration flow divisions (`Flow Bytes/s`, `Flow Packets/s`).
- **Where performed:** Phase 2 Forensic Inspection and Phase 3 Cleaning.
- **Dataset / Partition:** Raw CSVs and processed partitions.
- **Actual Results Available:** Yes, documented in `reports/missing_value_report.md` and `reports/dataset_forensic_summary.json`. Exactly 4,376 infinite values detected in raw data (810 in Monday train, 1,913 in Tue/Wed validation, 1,653 in Thu/Fri test). Converted to NaN and median imputed with zero leakage.
- **Reproducibility:** 100% reproducible.
- **Classification:** Data-Quality Forensic Inspection & Preprocessing Validation.

### 7. Duplicate Records and Duplicate Feature Vectors
- **What was analyzed:** Exact row duplicates (79 columns) and feature-vector duplicates (76 continuous features), distinguishing intra-file duplicates from cross-partition duplicates.
- **Where performed:** Phase 2 Inspection, Phase 3 Deduplication, and Phase 3.1 Duplicate Audit; implemented in `scripts/audit_duplicate_label_integrity.py` and `src/netdefy/preprocessing/deduplication.py`.
- **Dataset / Partition:** All 2,830,743 raw records and processed Parquet datasets.
- **Actual Results Available:** Yes, documented in `reports/duplicate_investigation.md`, `reports/duplicate_overlap_report.md`, and `reports/PHASE3_1_DUPLICATE_LABEL_INTEGRITY_AUDIT.md`. Found 256,479 exact intra-file duplicates (9.06%) and 51,902 inter-file duplicates. When evaluating 76 continuous features, 543,671 intra-partition redundant rows were identified.
- **Reproducibility:** 100% reproducible via `HashVerifiedDeduplicator`.
- **Classification:** Forensic Inspection & Deduplication Audit.

### 8. Conflicting Labels
- **What was analyzed:** Identical 76 continuous feature vectors that carry contradictory ground-truth labels (Benign vs. Attack).
- **Where performed:** Phase 3.1 Duplicate Policy & Label Integrity Audit; executed via `scripts/audit_duplicate_label_integrity.py`.
- **Dataset / Partition:** All 2,830,743 raw rows.
- **Actual Results Available:** Yes, documented in `reports/PHASE3_1_DUPLICATE_LABEL_INTEGRITY_AUDIT.md` and `reports/phase3_1_duplicate_audit.json`. Identified exactly 130 conflicting feature vectors in CICIDS2017 spanning 76,482 test rows and 4,830 validation rows. 100% of conflicts are Benign vs Attack (0 attack-vs-attack conflicts). Sourced from stateless TCP SYN probes (PortScan) and HTTP GET requests without IP/Port context.
- **Reproducibility:** 100% reproducible.
- **Classification:** Forensic Data-Quality Audit.

### 9. Cross-Partition Overlap
- **What was analyzed:** Feature vectors in Tuesday/Wednesday or Thursday/Friday that duplicate Monday baseline training flows.
- **Where performed:** Phase 3 Preprocessing and Phase 3.1 Accounting Verification.
- **Dataset / Partition:** Processed train, validation, and test datasets.
- **Actual Results Available:** Yes, documented in `reports/duplicate_overlap_report.md` and `reports/PHASE3_1_FINAL_ACCOUNTING_VERIFICATION.md`. Identified 18,678 cross-partition overlap rows matching Monday baseline (8,050 in validation, 10,628 in test). Purged in View B to prevent memorization leakage. Verified 0 overlap in benchmark v1.
- **Reproducibility:** 100% reproducible.
- **Classification:** Preprocessing Leakage Audit.

### 10. Feature Distributions and Skewness
- **What was analyzed:** Training medians and standard scaling parameters were fitted, but comprehensive distributional profiling (mean, standard deviation, IQR, skewness, kurtosis) across all 76 features was not compiled into a formal exploratory report.
- **Where performed:** Implicitly computed in Phase 3 scaler fitting (`artifacts/preprocessing/standard_scaler.joblib`).
- **Dataset / Partition:** Monday training baseline (`oneclass_train.parquet`).
- **Actual Results Available:** Partial (median and scaling moments available; skewness/kurtosis unrecorded).
- **Reproducibility:** 100% reproducible by computing summary moments on `oneclass_train.parquet`.
- **Classification:** Preprocessing Parameter Validation (historical) / Exploratory Analysis (NEW).
- **Status:** **NEW ANALYSIS PERFORMED IN NOTEBOOK 03.**

### 11. Correlation Analysis and Multicollinearity
- **What was analyzed:** Multicollinearity was identified qualitatively during feature selection (e.g. duplicate header `Fwd Header Length.1` and forward/backward subflow aggregates), but a full pairwise correlation matrix and automated collinear cluster extraction ($|r| > 0.90$) was not compiled into an artifact.
- **Where performed:** Phase 3 Feature Selection (`reports/feature_selection_report.md`).
- **Dataset / Partition:** `oneclass_train.parquet` (100,000 Monday benign flows).
- **Actual Results Available:** Partial (qualitative notes available; quantitative correlation matrices unrecorded).
- **Reproducibility:** 100% reproducible on benchmark v1.
- **Classification:** Feature Selection Review (historical) / Exploratory Analysis (NEW).
- **Status:** **NEW ANALYSIS PERFORMED IN NOTEBOOK 03.**

### 12. Feature-Level Outlier Analysis
- **What was analyzed:** Extreme values were observed during scaler evaluation (comparing Standard vs Robust scaler performance), but systematic inter-quantile range (IQR) and extreme percentile outlier profiling across feature clusters was not documented.
- **Where performed:** Phase 3 Preprocessing Pipeline design.
- **Dataset / Partition:** `oneclass_train.parquet`.
- **Actual Results Available:** Partial (scaler selection documented; outlier rates unrecorded).
- **Reproducibility:** 100% reproducible.
- **Classification:** Preprocessing Design (historical) / Exploratory Analysis (NEW).
- **Status:** **NEW ANALYSIS PERFORMED IN NOTEBOOK 03.**

### 13. Benign Versus Malicious Traffic Patterns
- **What was analyzed:** High-level anomaly detection error analysis in Phase 4A/4B and classification error analysis in Phase 4C recorded metric differences, but statistical feature comparisons (e.g. distribution shifts in packet length, duration, and packet rates) between benign and attack categories were not compiled into an interactive visual study.
- **Where performed:** Phase 4 Evaluation and Error Analysis (`reports/PHASE4A_ISOLATION_FOREST_REPORT.md`, `reports/PHASE4B_AUTOENCODER_REPORT.md`, `reports/PHASE4C_CLASSIFICATION_REPORT.md`).
- **Dataset / Partition:** `validation.parquet` and `test.parquet`.
- **Actual Results Available:** Partial (detection metrics available; comparative feature distributions unrecorded).
- **Reproducibility:** 100% reproducible.
- **Classification:** Model Evaluation (historical) / Comparative Exploratory Analysis (NEW).
- **Status:** **NEW ANALYSIS PERFORMED IN NOTEBOOK 03 & 04.**

### 14. Attack-Specific Feature Behaviour
- **What was analyzed:** Behavioral mechanisms for key attack categories were documented: PortScan (single SYN probes, 0 bwd payload, tiny duration), DoS/DDoS (high packet rates, volumetric flood asymmetry), Patator (periodic authentication bursts).
- **Where performed:** Phase 3.1 Duplicate Audit and Phase 4 Error Analysis.
- **Dataset / Partition:** `validation.parquet`, `test.parquet`, `rare_class_diagnostic.parquet`.
- **Actual Results Available:** Yes, documented narratively in reports and error analysis JSONs (`artifacts/models/xgboost_classifier/v1/error_analysis.json`).
- **Reproducibility:** 100% reproducible.
- **Classification:** Forensic Profiling & Model Error Analysis. Sourced and empirically visualized in Notebook 04.

### 15. Rare Attack Analysis
- **What was analyzed:** Preservation, frequency, and sample composition of rare attack classes with $<2,000$ occurrences in CICIDS2017: Heartbleed (11), SQL Injection (21), Infiltration (36), XSS (652), Brute Force (1,507), Bot (1,966).
- **Where performed:** Phase 3.1 Duplicate Audit and Phase 3.2 Benchmark Sampling; isolated into `data/benchmark/v1/supplementary/rare_class_diagnostic.parquet` (6,193 rows).
- **Dataset / Partition:** Full CICIDS2017 corpus and supplementary diagnostic benchmark.
- **Actual Results Available:** Yes, documented in `reports/PHASE3_1_DUPLICATE_LABEL_INTEGRITY_AUDIT.md` and `reports/PHASE3_2_BENCHMARK_CONSTRUCTION.md`. 100% census retention verified.
- **Reproducibility:** 100% reproducible.
- **Classification:** Forensic Inspection & Benchmark Sampling Audit. Sourced into Notebook 04.

### 16. Feature Selection and Feature Importance
- **What was analyzed:** Technical justification for excluding `Destination Port`, `Timestamp`, and IP addresses (preventing shortcut memorization); XGBoost Gini gain and weight feature importance rankings across 76 continuous features.
- **Where performed:** Phase 3 Feature Selection and Phase 4C Supervised Classification.
- **Dataset / Partition:** `classifier_train.parquet` (30,000 rows).
- **Actual Results Available:** Yes, documented in `reports/feature_selection_report.md`, `reports/PHASE4C_CLASSIFICATION_REPORT.md`, `artifacts/models/xgboost_classifier/v1/feature_importance.json`, and `reports/figures/phase4c_feature_importance.png`. Top predictive features identified: `Init_Win_bytes_forward` (14.2% gain), `Bwd_Packet_Length_Std` (11.8% gain), `Fwd_Packets/s` (9.4% gain).
- **Reproducibility:** 100% reproducible.
- **Classification:** Preprocessing Design & Supervised Model Evaluation. Sourced into Notebook 03 & 04.

### 17. Temporal Distribution and Partition Analysis
- **What was analyzed:** Chronological holdout experimental design: Monday (one-class normal training) $\to$ Tuesday/Wednesday (classifier training and validation) $\to$ Thursday/Friday (chronological zero-day test holdout).
- **Where performed:** Phase 3 Temporal Partitioning and Phase 3.2 Benchmark Construction.
- **Dataset / Partition:** All 8 raw CSVs and benchmark v1 datasets.
- **Actual Results Available:** Yes, documented in `reports/temporal_partition_report.md` and `reports/PHASE3_2_BENCHMARK_CONSTRUCTION.md`. Proves that chronological partitioning creates a true zero-day testbed where 100% of Thursday/Friday attack categories were absent from Tuesday/Wednesday training.
- **Reproducibility:** 100% reproducible.
- **Classification:** Forensic Protocol Architecture. Sourced into Notebook 01.

---

## 4. Reconciliation of Key Historical Findings

### 1. Dataset Dimensions & Duplicate Columns
- **Reported:** 2,830,743 records across 8 CSV files; 79 raw columns.
- **Reconciliation:** All 8 CSV files contain exactly 79 headers. Column index 34 (`Fwd Header Length`) and column index 55 (`Fwd Header Length.1`) are byte-for-byte identical redundant outputs from CICFlowMeter. Excluding `Fwd Header Length.1`, `Destination Port` (mapped to categorical service), and `Label` yields exactly **76 continuous features**.

### 2. Label Frequencies & 15 Classes
- **Reported:** 15 distinct classes including `BENIGN`.
- **Reconciliation:** Verified across `data/raw/` and `reports/label_distribution.csv`. Global counts: `BENIGN` (2,273,097), `DoS Hulk` (231,073), `PortScan` (158,930), `DDoS` (128,027), `DoS GoldenEye` (10,293), `FTP-Patator` (7,938), `SSH-Patator` (5,897), `DoS slowloris` (5,796), `DoS Slowhttptest` (5,499), `Bot` (1,966), `Web Attack – Brute Force` (1,507), `Web Attack – XSS` (652), `Infiltration` (36), `Web Attack – Sql Injection` (21), `Heartbleed` (11).

### 3. Missing and Infinite Values
- **Reported:** 288 missing values; 4,376 infinite values.
- **Reconciliation:** Verified from `reports/dataset_forensic_summary.json` and `reports/missing_value_report.md`. All missing and infinite values reside exclusively in `Flow Bytes/s` and `Flow Packets/s` caused by zero duration flows ($0.0$ microseconds) during CICFlowMeter calculation. Imputed with Monday training medians.

### 4. Ambiguity Counts & The 3,287 vs 3,254 Figure
- **Reported:** 130 conflicting vectors in CICIDS2017; 3,305 ambiguous rows in benchmark test set.
- **Exact Benchmark Breakdown:**
  - `PortScan`: 3,254 rows
  - `BENIGN`: 49 rows
  - `Bot`: 2 rows
  - **Total:** $3,254 + 49 + 2 = \mathbf{3,305}$ rows.
- **Investigation of the "3,287" Narrative Figure in Phase 4B Report:**
  In `reports/PHASE4B_AUTOENCODER_REPORT.md` (Section 6, line 199), a statement noted: *"3,287 of the 3,305 ambiguous test flows are PortScan flows"*. Forensic audit confirmed this was a **clerical drafting erratum** (a 33-row arithmetic typo: $3,287 - 3,254 = 33$). The exact ground truth computed directly from `data/benchmark/v1/test.parquet` and stored in `data/benchmark/v1/metadata/ambiguity_manifest.json` is unequivocally **3,254 PortScan flows**.

---

## 5. Notebook Architecture & Data Protection Protocol

### Notebook Suite Mapping:
1. **`notebooks/01_dataset_overview.ipynb`**: Dataset Structure, Dimensions, Class Distribution, Day-Wise Traffic, Temporal Invariants.
2. **`notebooks/02_data_quality_analysis.ipynb`**: Missing Values, Infinities, Duplicate Records, Label Conflicts, Cross-Partition Overlap, Ambiguity Tracking.
3. **`notebooks/03_feature_exploration.ipynb`**: 76 Continuous Features, Skewness, Descriptive Statistics, Correlation Clusters, Outlier Profiles, Benign vs Attack Shifts.
4. **`notebooks/04_attack_pattern_analysis.ipynb`**: Attack Families, Behavioral Profiling (PortScan, DoS/DDoS, Patator), Rare Attack Retention, Zero-Day Temporal Dilemma.

### Data Protection & Execution Rules:
- **Read-Only Access:** All notebooks access datasets in read-only mode (`pd.read_parquet()` / reading existing report summaries).
- **Frozen Benchmark Protection:** Zero modification to `data/benchmark/v1/` or `artifacts/models/`.
- **Memory Efficiency:** Avoid loading all 2.83M raw rows into memory simultaneously; leverage benchmark v1 partitions (20 MB total) and chunked loaders where raw data inspection is performed.
- **Deterministic Randomness:** All stochastic sampling operations use fixed `random_state=42`.

