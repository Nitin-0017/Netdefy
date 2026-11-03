# NETDEFY Local Development Guide

This guide describes how to configure, develop, test, and verify the **NETDEFY** codebase locally.

---

## 1. Prerequisites

- **Operating System:** macOS (Apple Silicon arm64 recommended) or Linux x86_64.
- **Python Version:** Python 3.12 (`>=3.12`).
- **Package Manager:** [`uv`](https://github.com/astral-sh/uv) (strongly recommended) or standard `pip`/`venv`.
- **Hardware Target:** Optimized for Apple Silicon (M-series with unified memory) using Metal Performance Shaders (MPS), with CUDA and CPU fallback support.

---

## 2. Environment Setup

### Option A: Using `uv` (Recommended)

1. Clone the repository (or navigate to the workspace):
   ```bash
   cd /path/to/Netdefy
   ```

2. Create virtual environment with Python 3.12:
   ```bash
   uv venv --python 3.12 .venv
   source .venv/bin/activate
   ```

3. Install project dependencies in editable mode with development tools:
   ```bash
   uv pip install -e ".[dev]"
   ```

### Option B: Using standard Python `venv`

1. Create and activate a Python 3.12 virtual environment:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```

2. Upgrade packaging tools and install:
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

---

## 3. Environment Verification Script

Run the automated diagnostic utility to verify hardware detection, accelerator availability, and dependency installations:

```bash
python scripts/check_environment.py
```

This checks:
- Python version and interpreter path.
- Operating system and CPU architecture.
- Total and available system memory.
- PyTorch installation and device detection (MPS / CUDA / CPU) with live tensor execution.
- Key dependency import statuses.
- Configuration file schema validation.

---

## 4. Code Quality & Verification Commands

All pull requests and code modifications must satisfy the following checks:

### 4.1 Ruff Linting
Check for code style violations, bug hazards, and import hygiene:
```bash
ruff check .
```
To automatically apply safe fixes:
```bash
ruff check --fix .
```

### 4.2 Ruff Formatting
Verify code formatting against the 100-character line limit and double-quote standard:
```bash
ruff format --check .
```
To apply formatting:
```bash
ruff format .
```

### 4.3 MyPy Strict Type Checking
Ensure 100% type annotations with zero implicit optionals or untyped definitions:
```bash
mypy src tests scripts
```

### 4.4 Automated Testing with PyTest
Run the full test suite with verbose output:
```bash
pytest
```
To run with coverage reporting:
```bash
pytest --cov=netdefy --cov-report=term-missing
```

---

## 5. Phase Implementation Status

| Component | Status | Phase |
| :--- | :--- | :--- |
| Modular Directory Structure | **Implemented** | Phase 1 |
| Pydantic Configuration System (`settings.py`) | **Implemented** | Phase 1 |
| Hardware & Device Manager with MPS/CUDA (`device.py`) | **Implemented** | Phase 1 |
| Reproducibility & Seeding Utilities (`reproducibility.py`) | **Implemented** | Phase 1 |
| Structured Logging Utility (`logging.py`) | **Implemented** | Phase 1 |
| Dataset Validation Engine (`validation.py`) | **Implemented** | Phase 1 |
| Environment Diagnostic Script (`check_environment.py`) | **Implemented** | Phase 1 |
| CI GitHub Actions Workflow (`tests.yml`) | **Implemented** | Phase 1 |
| CICIDS2017 Dataset Ingestion & Partitioning | *Pending* | Phase 2 |
| Leakage-Free Preprocessing Pipeline | *Pending* | Phase 2 |
| PyTorch Autoencoder Architecture & Training | *Pending* | Phase 2 |
| Isolation Forest Baseline Training | *Pending* | Phase 2 |
| Temporal Generalization Evaluation Suite | *Pending* | Phase 2 |
| MLflow Experiment Tracking & Logging | *Pending* | Phase 2 |
| FastAPI Model Serving & Inference | *Pending* | Phase 3 |
| Statistical Data Drift & Model Monitoring | *Pending* | Phase 4 |
| React Analytics Dashboard | *Pending* | Phase 4 |

---

## 6. Development Conventions

1. **Defensive Cyber Scope:** NETDEFY is strictly defensive. Do not commit exploit scripts, automated attacking harnesses, or unauthorized packet injectors.
2. **Deterministic Execution:** Always seed RNGs using `set_seed(seed, deterministic=True)` from `netdefy.utils.reproducibility`.
3. **Memory Guardrails:** Keep batch sizes $\le 512$ and cast feature matrices to `np.float32` / `torch.float32` to avoid OOM faults on 8 GB systems.
4. **No Test Leakage:** Transformations (scalers, encoders) must be fitted on training sets only. Never fit on full datasets or evaluation partitions.

