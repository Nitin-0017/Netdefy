# NETDEFY — Developer & Engineering Standards

> **Document Type:** Developer Guide & Quality Standards  
> **Source Directory:** `src/netdefy/`  
> **Test Directory:** `tests/`  
> **Frontend Directory:** `frontend/`  

---

## 1. Development Philosophy

NETDEFY is an applied machine learning and cybersecurity engineering platform built under strict production-grade standards:

1. **Type Safety Throughout:** All Python code enforces strict type checking (`mypy --strict`, zero untyped definitions). All frontend code enforces TypeScript compilation with zero errors.
2. **Deterministic & Reproducible:** All random seeds, dataset splits, and evaluation metrics must be completely deterministic and reproducible.
3. **Defense-in-Depth Testing:** Testing spans unit tests, component integration tests, schema contract verification, and automated 20-invariant benchmark auditing.
4. **Zero-Leakage Science:** No test set information (labels, feature distributions, or thresholds) may ever leak into training or calibration routines.

---

## 2. Local Environment Setup

### 2.1 Backend Setup (`uv`)
```bash
# Clone the repository
git clone https://github.com/Nitin-0017/Netdefy.git
cd Netdefy

# Pull Git LFS assets
git lfs pull

# Create virtual environment and install dev dependencies
uv venv
uv pip install -e ".[dev]"

# Configure environment variables
cp .env.example .env
```

### 2.2 Frontend Setup (`npm`)
```bash
cd frontend
npm ci
npm run build
cd ..
```

---

## 3. Code Quality & Automated Tooling

Every contribution must satisfy the five automated quality gates:

### 3.1 Ruff Linter
Enforces pycodestyle, pyflakes, isort, flake8-bugbear, pyupgrade, and modern idioms:
```bash
uv run ruff check .
```

### 3.2 Ruff Formatter
Enforces deterministic black-compatible code formatting (100 character line length):
```bash
uv run ruff format --check .
# To auto-format files:
uv run ruff format .
```

### 3.3 Strict MyPy Type Checking
Enforces zero missing types, no implicit optionals, and checked function definitions:
```bash
uv run mypy src tests scripts
```

### 3.4 Pytest Suite
Executes all unit and integration tests with coverage tracking:
```bash
uv run pytest
```

### 3.5 Frontend Verification
Ensures TypeScript compiles without warnings or errors:
```bash
cd frontend
npm test       # runs tsc --noEmit
npm run build  # compiles production bundle to dist/
cd ..
```

---

## 4. Test Organization & Philosophy

Tests are partitioned into two directories in `tests/`:

- **`tests/unit/` (Fast Unit Tests):**
  - Feature scaling & imputation (`test_scaler.py`, `test_cleaner.py`)
  - Anomaly scoring mathematics (`test_isolation_forest.py`, `test_autoencoder_model.py`)
  - Supervised GBDT mechanics (`test_xgboost_classifier.py`)
  - Quantile threshold calibration (`test_thresholds.py`)
  - Streaming components & backpressure (`test_streaming_components.py`)
  - API routers and playground schema contracts (`test_research_api.py`)
  - Hardware device detection (`test_device.py`)
- **`tests/integration/` (End-to-End System Tests):**
  - Benchmark v1 dataset integrity & invariants (`test_benchmark_v1.py`)
  - Preprocessing pipeline reproducibility (`test_pipeline_sanity.py`, `test_phase3_sanity.py`)
  - Model pipeline training and loading (`test_autoencoder_pipeline.py`, `test_classifier_pipeline.py`)
  - Hybrid engine decision determinism (`test_hybrid_pipeline.py`)
  - Real-time streaming and dead-letter queue recovery (`test_stream_reliability.py`, `test_streaming_pipeline.py`)

---

## 5. Clean Git & Commit Workflow

- **Branching Policy:** Work on feature branches and submit PRs targeting `main`.
- **Commit Messages:** Use clear, concise commit messages (2–4 words preferred).
- **History Preservation:** Never force-push or rewrite public history.
- **CI Verification:** Ensure both Ubuntu and macOS GitHub Actions workflows pass before merging.
