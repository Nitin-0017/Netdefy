"""Unit tests for hardware device detection, verification, and diagnostics."""

from __future__ import annotations

import pytest
import torch

from netdefy.models.device import (
    DeviceDiagnostics,
    get_device,
    get_device_diagnostics,
    verify_tensor_computation,
)


def test_verify_tensor_computation_cpu() -> None:
    """Verify live tensor execution on standard CPU device."""
    cpu_device = torch.device("cpu")
    verified, msg = verify_tensor_computation(cpu_device)

    assert verified is True
    assert "successfully" in msg.lower()


def test_get_device_cpu_explicit() -> None:
    """Verify explicit CPU device selection."""
    device = get_device(preference="cpu")

    assert isinstance(device, torch.device)
    assert device.type == "cpu"


def test_get_device_auto() -> None:
    """Verify automatic device detection selects a functional device."""
    device = get_device(preference="auto")

    assert isinstance(device, torch.device)
    assert device.type in {"mps", "cuda", "cpu"}
    verified, _ = verify_tensor_computation(device)
    assert verified is True


def test_get_device_cuda_fallback() -> None:
    """Verify graceful CPU fallback when CUDA is requested on non-CUDA hardware."""
    if not torch.cuda.is_available():
        # With fallback enabled
        device = get_device(preference="cuda", fallback_to_cpu=True)
        assert device.type == "cpu"

        # Without fallback enabled
        with pytest.raises(RuntimeError, match="CUDA was requested"):
            get_device(preference="cuda", fallback_to_cpu=False)


def test_get_device_diagnostics() -> None:
    """Verify diagnostic report generation and schema."""
    diagnostics = get_device_diagnostics(preference="auto")

    assert isinstance(diagnostics, DeviceDiagnostics)
    assert diagnostics.device_type in {"mps", "cuda", "cpu"}
    assert diagnostics.verification_passed is True
    assert isinstance(diagnostics.selected_device, str)
    assert isinstance(diagnostics.os_name, str)
    assert isinstance(diagnostics.torch_version, str)

    # Test dictionary serialization
    diag_dict = diagnostics.to_dict()
    assert isinstance(diag_dict, dict)
    assert "verification_passed" in diag_dict

    # Test summary string
    summary_str = diagnostics.summary()
    assert "Device:" in summary_str
    assert "Platform:" in summary_str
