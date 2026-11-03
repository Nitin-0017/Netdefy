"""Unit tests for random seeding and determinism configuration."""

from __future__ import annotations

import random

import numpy as np
import pytest
import torch

from netdefy.utils.reproducibility import ReproducibilityReport, set_seed


def test_set_seed_returns_valid_report() -> None:
    """Verify that set_seed returns a properly populated report."""
    report = set_seed(seed=42, deterministic=True)

    assert isinstance(report, ReproducibilityReport)
    assert report.seed == 42
    assert report.deterministic is True
    assert report.python_hash_seeded is True
    assert report.numpy_seeded is True
    assert report.torch_cpu_seeded is True


def test_random_reproducibility() -> None:
    """Verify that identical seeds produce bitwise-identical pseudorandom sequences."""
    # Run 1
    set_seed(12345, deterministic=True)
    py_val_1 = random.random()
    np_val_1 = float(np.random.rand())
    torch_val_1 = float(torch.rand(1).item())

    # Run 2 with same seed
    set_seed(12345, deterministic=True)
    py_val_2 = random.random()
    np_val_2 = float(np.random.rand())
    torch_val_2 = float(torch.rand(1).item())

    assert py_val_1 == py_val_2
    assert np_val_1 == np_val_2
    assert torch_val_1 == torch_val_2


def test_negative_seed_raises_value_error() -> None:
    """Verify ValueError when attempting to seed with negative integer."""
    with pytest.raises(ValueError, match="must be non-negative"):
        set_seed(seed=-1)
