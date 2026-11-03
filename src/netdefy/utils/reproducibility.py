"""Reproducibility utilities for controlling random seeds and determinism."""

from __future__ import annotations

import logging
import os
import random
from dataclasses import dataclass

import numpy as np
import torch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReproducibilityReport:
    """Summary of applied random seeds and determinism configurations."""

    seed: int
    deterministic: bool
    python_hash_seeded: bool
    numpy_seeded: bool
    torch_cpu_seeded: bool
    torch_cuda_seeded: bool
    cudnn_deterministic: bool
    warn_only_deterministic_enabled: bool
    notes: str


def set_seed(seed: int = 42, deterministic: bool = True) -> ReproducibilityReport:
    """Seed Python random, NumPy, and PyTorch across CPU and GPU/MPS.

    Args:
        seed: Positive integer seed value.
        deterministic: Whether to request deterministic algorithms in PyTorch.
                       Uses `warn_only=True` to preserve compatibility with Apple MPS
                       and certain CUDA operations that do not implement deterministic kernels.

    Returns:
        ReproducibilityReport detailing seeded components.
    """
    if seed < 0:
        raise ValueError(f"Random seed must be non-negative, got {seed}")

    # 1. Python built-in random & hash seed
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)

    # 2. NumPy RNG
    np.random.seed(seed)

    # 3. PyTorch RNG
    torch.manual_seed(seed)
    cuda_seeded = False
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        cuda_seeded = True

    # 4. Deterministic settings & hardware caveats
    cudnn_deterministic = False
    warn_only_enabled = False
    notes_list: list[str] = []

    if deterministic:
        if torch.cuda.is_available():
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
            cudnn_deterministic = True

        try:
            # warn_only=True prevents fatal crashes on Apple Silicon MPS where certain
            # reduction and scatter operations do not yet possess deterministic kernels.
            torch.use_deterministic_algorithms(True, warn_only=True)
            warn_only_enabled = True
        except Exception as exc:  # noqa: BLE001
            notes_list.append(f"torch.use_deterministic_algorithms failed: {exc}")

        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            notes_list.append(
                "Hardware Caveat (Apple MPS): Certain MPS kernels lack strict bitwise "
                "determinism across runs in PyTorch; warn_only=True is applied to maintain execution."
            )

    logger.info(
        "Seeded all random generators with seed=%d (deterministic=%s)",
        seed,
        deterministic,
    )

    return ReproducibilityReport(
        seed=seed,
        deterministic=deterministic,
        python_hash_seeded=True,
        numpy_seeded=True,
        torch_cpu_seeded=True,
        torch_cuda_seeded=cuda_seeded,
        cudnn_deterministic=cudnn_deterministic,
        warn_only_deterministic_enabled=warn_only_enabled,
        notes="; ".join(notes_list) if notes_list else "All standard generators seeded.",
    )
