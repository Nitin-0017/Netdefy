# NETDEFY — Reproducibility & Verification Guide

> **Document Type:** Scientific Replication Manual  
> **Environment:** Python 3.12.x (`uv` package manager) & Node.js 20+  
> **Hardware Support:** Apple Silicon (macOS ARM64) & Linux (Ubuntu x86_64)  
> **Target Seed:** `42` (Deterministic random states)  

---

## 1. System Requirements & Setup

### 1.1 Prerequisites
- **Python:** Python 3.12 (managed via `uv` or system Python)
- **Node.js:** Node.js v20.x or v22.x with `npm`
- **Git & Git LFS:** Git 2.30+ with Git LFS installed (`git lfs install`)
- **Memory & Storage:** 8 GB RAM minimum; 5 GB free disk space

### 1.2 Quickstart Installation
```bash
# 1. Clone repository with LFS tracking
git clone https://github.com/Nitin-0017/Netdefy.git
cd Netdefy
git lfs pull

# 2. Install Python dependencies with uv
uv venv
uv pip install -e ".[dev]"

# 3. Install frontend dependencies and compile UI
cd frontend
npm ci
npm run build
cd ..
```

---

## 2. Determinism & Random Seed Controls

NETDEFY centralizes all random number generation in [`src/netdefy/utils/reproducibility.py`](../src/netdefy/utils/reproducibility.py):
```python
from netdefy.utils.reproducibility import set_seed

# Seeds random, numpy, torch, torch.cuda, and torch.mps
set_seed(42)
```
- **Torch Determinism:** Sets `torch.manual_seed(42)` and configures `torch.backends.cudnn.deterministic = True` when CUDA is available.
- **Scikit-Learn & XGBoost:** All estimators pin `random_state = 42`.
- **OpenMP Handling:** macOS Apple Silicon automatically sets OpenMP threading variables to prevent runtime library collisions between PyTorch and XGBoost.

---

## 3. Benchmark Verification & Invariant Auditing

Before running evaluations or training routines, verify the integrity of the benchmark partitions:

```bash
uv run python scripts/validate_benchmark.py --benchmark-dir data/benchmark/v1
```

This automated auditor validates **20 strict requirements**:
1. Exact row counts: `oneclass_train` ($100,000$), `classifier_train` ($30,000$), `validation` ($20,000$), `test` ($50,000$).
2. Pure Monday benign baseline in `oneclass_train` (zero attack contamination).
3. Zero temporal overlap between Tuesday/Wednesday training and Thursday/Friday testing.
4. Identical 76-feature continuous schema across all partitions.
5. Absolute absence of `NaN`, `+inf`, `-inf`, or `null` values.
6. Exclusion of `Destination Port` and `Label` from feature matrices.
7. Verification of SHA-256 cryptographic file checksums against `checksums.json`.

---

## 4. Model Training & Evaluation Reproduction

All model weights and threshold calibrators are pre-trained and preserved in `artifacts/models/`. To reproduce training and evaluations from scratch:

### 4.1 Retrain Models (Optional)
```bash
# 1. Train Unsupervised Isolation Forest (Monday Benign)
uv run python scripts/train_isolation_forest.py

# 2. Train Deep Autoencoder (Monday Benign, PyTorch)
uv run python scripts/train_autoencoder.py

# 3. Train Supervised XGBoost Classifier (Tuesday/Wednesday, 8 Classes)
uv run python scripts/train_classifier.py
```

### 4.2 Execute Holdout Benchmark Evaluations
```bash
# 1. Evaluate Isolation Forest
uv run python scripts/evaluate_isolation_forest.py

# 2. Evaluate Deep Autoencoder
uv run python scripts/evaluate_autoencoder.py

# 3. Evaluate XGBoost Classifier (Closed-Set & Open-Set)
uv run python scripts/evaluate_classifier.py

# 4. Evaluate Full Hybrid Decision Engine (View A & View B)
uv run python scripts/evaluate_hybrid.py
```

---

## 5. Automated Quality Assurance & CI Commands

Execute the exact test suite and quality gates enforced in GitHub Actions CI:

```bash
# 1. Pytest Test Suite (174 Tests)
uv run pytest

# 2. Ruff Linter
uv run ruff check .

# 3. Ruff Formatter Check
uv run ruff format --check .

# 4. Strict MyPy Type Checking (160+ files)
uv run mypy src tests scripts

# 5. Frontend TypeScript Verification & Production Build
cd frontend
npm test
npm run build
cd ..
```

---

## 6. Running the Interactive Platform Locally

```bash
# Start backend API (mounts Research Workbench at /workbench)
uv run uvicorn netdefy.api.app:app --host 127.0.0.1 --port 8000 --reload
```
Navigate to:
- **Interactive Research Workbench:** [http://127.0.0.1:8000/workbench](http://127.0.0.1:8000/workbench)
- **FastAPI OpenAPI Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
