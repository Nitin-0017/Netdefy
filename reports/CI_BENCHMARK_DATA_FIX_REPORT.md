# NETDEFY — CI BENCHMARK DATA MANAGEMENT & FIX REPORT
## Resolution of GitHub Actions CI Failures via Git LFS & Verification Invariants

**Project:** NETDEFY — Network Defense Intelligence  
**Document:** CI & Benchmark Data Architecture Resolution Report  
**Author:** Senior ML Infrastructure & DevOps Engineer  
**Execution Timestamp:** 2026-11-04T05:48:00Z  
**Target Environments:** GitHub Actions CI (`ubuntu-latest`, `macos-latest`, Python 3.12)  
**Status:** **CONDITIONAL GO — Local checks pass with 100% success; remote GitHub Actions verification is pending git push.**  

---

## 1. Executive Summary & Exact Root Cause

### The Problem:
GitHub Actions CI was failing on both `ubuntu-latest` and `macos-latest` runners during the pytest step. Four integration tests failed:
1. `test_partition_row_counts` (`FileNotFoundError: data/benchmark/v1/oneclass_train.parquet`)
2. `test_attack_representation_and_rare_split` (`FileNotFoundError: data/benchmark/v1/classifier_train.parquet`)
3. `test_rare_class_diagnostic_exact_composition` (`FileNotFoundError: data/benchmark/v1/supplementary/rare_class_diagnostic.parquet`)
4. `test_ambiguity_tracking` (`AssertionError: data/benchmark/v1/metadata/ambiguity_manifest.json does not exist`)

All other checks (Ruff Lint, Ruff Format Check, Strict MyPy) passed.

### The Exact Root Cause:
The `.gitignore` file contained the following blanket ignore rule:
```gitignore
data/benchmark/*
!data/benchmark/.gitkeep
!data/benchmark/README.md
```
This rule prevented Git from tracking `data/benchmark/v1/` and all of its contents (both the binary Parquet files and the JSON/YAML metadata). When GitHub Actions ran `actions/checkout@v4`, only git-tracked files were cloned. Consequently, `data/benchmark/v1/` did not exist on the runner virtual machines, causing immediate `FileNotFoundError` exceptions when the integration tests ran.

---

## 2. Selected Storage Strategy & Justification

### Comparative Evaluation:

| Strategy | Storage / Bandwidth Tradeoff | CI Complexity | Reproducibility | Selected? |
| :--- | :--- | :--- | :--- | :--- |
| **Option 1: Hybrid Git LFS + Native Git Tracking** | Parquets (20.5 MB) & raw manifest (65.6 MB) via Git LFS; small JSON/YAML manifests via normal Git | Minimal (`lfs: true` in `actions/checkout@v4`) | **Optimal.** Guarantees bit-identical benchmark availability without downloading full 1GB raw data in CI. | **YES (SELECTED)** |
| **Option 2: Raw Preprocessing in CI** | Requires downloading full 1GB raw CICIDS2017 dataset in CI and running 2-minute pipeline | Extremely high (CI network downloads, UNB authentication barrier) | Poor (UNB requires manual web registration; direct CI curl is HTTP 403 Forbidden). | **NO** |

### Selected Architecture:
1. **Git LFS for Binary Parquets and Large Manifests (`.gitattributes`):**
   - `data/benchmark/v1/*.parquet` (20.54 MB total)
   - `data/benchmark/v1/supplementary/*.parquet` (0.58 MB)
   - `data/benchmark/v1/metadata/source_row_manifest.json` (65.6 MB)
2. **Standard Git for Metadata & Manifests:**
   - `data/benchmark/v1/metadata/ambiguity_manifest.json` (333 B)
   - `data/benchmark/v1/metadata/benchmark_manifest.json` (1.3 KB)
   - `data/benchmark/v1/metadata/feature_schema.json` (4.2 KB)
   - `data/benchmark/v1/metadata/sampling_audit.json` (1.9 KB)
   - `data/benchmark/v1/metadata/sampling_config.yaml` (484 B)
   - Tracked directly in Git to allow human-readable code reviews, PR diffs, and rapid inspection without LFS overhead.

---

## 3. Files Modified & Configuration Changes

### A. `.gitignore`
Replaced the blanket `data/benchmark/*` rule with an explicit exception for `data/benchmark/v1/`:
```gitignore
# Benchmark Datasets (v1 is tracked: Parquets & large manifests via Git LFS, metadata via normal Git)
# Unversioned or temporary benchmark scratch files remain excluded
data/benchmark/*
!data/benchmark/.gitkeep
!data/benchmark/README.md
!data/benchmark/v1/
```

### B. `.gitattributes` (Created)
Configured LFS filters for all Parquet tables and the 66MB source row manifest:
```gitattributes
*.parquet filter=lfs diff=lfs merge=lfs -text
data/benchmark/v1/metadata/source_row_manifest.json filter=lfs diff=lfs merge=lfs -text
```

### C. `.github/workflows/tests.yml`
1. Enabled LFS checkout in `actions/checkout@v4`:
   ```yaml
   - name: Check out repository
     uses: actions/checkout@v4
     with:
       lfs: true
   ```
2. Added pre-test benchmark invariant verification:
   ```yaml
   - name: Verify Benchmark Dataset Integrity & 20 Invariants
     run: |
       uv run python scripts/validate_benchmark.py --benchmark-dir data/benchmark/v1
   ```
   This step guarantees that before integration tests execute:
   - All 5 Parquet files exist on disk with actual contents (not 130-byte LFS pointer files).
   - Checksums match `benchmark_manifest.json` bit-for-bit.
   - All 76 features, float32 precision, and zero-leakage invariants are verified.
   - If any file or pointer is corrupt, CI fails immediately with an actionable diagnostic report.

---

## 4. Benchmark File Availability & Checksum Verification

All benchmark files are tracked and verified locally via `scripts/validate_benchmark.py`:

| Benchmark Artifact Path | Tracking Engine | File Size | SHA-256 Checksum | Verified? |
| :--- | :--- | :--- | :--- | :--- |
| `data/benchmark/v1/oneclass_train.parquet` | Git LFS | 10.36 MB | `06157578c42449a053190325ecea4c41e999797dbfec033b572f62df789f633c` | **PASS** |
| `data/benchmark/v1/classifier_train.parquet` | Git LFS | 3.07 MB | `d5d69f75f44612fb455a77c9d03bf88b5d444ed22e123926e4867e88bc3e44c7` | **PASS** |
| `data/benchmark/v1/validation.parquet` | Git LFS | 2.11 MB | `3116213f1a94f24a2a1b39123fc3a0ac300a231581fc3788045525698f9c72bf` | **PASS** |
| `data/benchmark/v1/test.parquet` | Git LFS | 4.44 MB | `263437c2e7da289ad29246dc923e5b6f41443c4d71f4f00497e0e69928d6e6e1` | **PASS** |
| `data/benchmark/v1/supplementary/rare_class_diagnostic.parquet` | Git LFS | 0.56 MB | `4eb33a3d3b28ff7f3ddb37fd94da2de2fb1d37a07889d28d9c5e16bdb20b29ff` | **PASS** |
| `data/benchmark/v1/metadata/ambiguity_manifest.json` | Git (Native) | 333 B | `0d0617ef1ba7fe79f5ddfd56fc79a9aa83e6065582dc33eb8ca08b1a8f9ca621` | **PASS** |
| `data/benchmark/v1/metadata/benchmark_manifest.json` | Git (Native) | 1.3 KB | `40bbfb772bb45e3f367fae45138344e6c1e9e8f4c281df6f8ce30a38d7807ee1` | **PASS** |
| `data/benchmark/v1/metadata/feature_schema.json` | Git (Native) | 4.2 KB | `0417387431e6bc7ba5a5d85d7747e0975618b0e8c71bbcd50e82f5b82c3f8f1c` | **PASS** |
| `data/benchmark/v1/metadata/sampling_audit.json` | Git (Native) | 1.9 KB | `b347b70bc9bb699a7e04efebcefa9c09c531d0ce4723ca9bf0bc52dfb4dd881b` | **PASS** |
| `data/benchmark/v1/metadata/sampling_config.yaml` | Git (Native) | 484 B | `3cb976d8b3daecceceb7b51b3260c79ca912aa1f52d2f707f4339176378c2eec` | **PASS** |
| `data/benchmark/v1/metadata/source_row_manifest.json` | Git LFS | 65.6 MB | `5021e06d9b9d79904944fa6600cce9d8ec387bf4c06f3e1a6be167d48342410a` | **PASS** |

---

## 5. Local Verification Results

### A. Full PyTest Suite & Code Coverage
- **Passed:** **92 tests** (100% pass rate)
- **Failed:** **0 tests**
- **Skipped:** **0 tests**
- **Runtime:** 11.91 seconds
- **Line Coverage:** **93% across 1,788 statements** (120 misses in optional device fallback paths)

### B. Code Quality & Linting
- **Ruff Format Check:** **89 files already formatted**, 0 modifications required.
- **Ruff Lint Check:** **All checks passed**, 0 errors, 0 warnings.
- **Strict MyPy:** **Success: no issues found in 63 source files**.

### C. Benchmark Invariant Audit (20/20 Passed)
- All 20 structural, numeric, and leakage invariants verified via `scripts/validate_benchmark.py`:
  - 100,000 pure BENIGN Monday flows
  - 30,000 classifier train & 20,000 validation flows (0 overlapping records)
  - 50,000 chronological test holdout flows
  - 6,193 rare class diagnostic flows (100% rare attack instances preserved)
  - 76 float32 continuous features, 0 NaNs, 0 Infs, Port and Label excluded.

---

## 6. Remaining Limitations & Operating Guidance

1. **Git LFS Bandwidth & Quota:**
   - Free GitHub accounts include 1 GB of LFS storage and 1 GB/month of bandwidth.
   - The tracked LFS objects total ~86.7 MB per clean clone.
   - When running frequent CI builds, GitHub Actions caches layers; however, repository owners should monitor LFS bandwidth usage in GitHub Account Billing.
2. **Local Contributor Setup:**
   - Any contributor cloning the repository should ensure `git-lfs` is installed (`brew install git-lfs` on macOS, `sudo apt-get install git-lfs` on Ubuntu) and run `git lfs install` once.

---

## 7. Status & Phase Gate Recommendation

```
==========================================================================================
                         CI BENCHMARK DATA MANAGEMENT STATUS
==========================================================================================
  Local Status: ALL 92 TESTS PASS (0 failed, 0 skipped).
  Code Quality: Ruff Lint PASS, Ruff Format PASS, Strict MyPy PASS.
  Benchmark Invariants: 20/20 INVARIANTS PASS with cryptographic checksum verification.
  LFS Status: Objects staged and verified (6 LFS objects, 5 Git text objects).
  
  OVERALL STATUS:
  >>> CONDITIONAL GO
  Local verification is 100% complete and validated.
  Remote GitHub Actions CI run will confirm green status once pushed to origin/main.
==========================================================================================
```

