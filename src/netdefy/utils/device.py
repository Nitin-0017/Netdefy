"""Hardware device utilities and re-exports for NETDEFY."""

from __future__ import annotations

from netdefy.models.device import (
    DeviceDiagnostics,
    get_device,
    get_device_diagnostics,
    verify_tensor_computation,
)

__all__ = [
    "DeviceDiagnostics",
    "get_device",
    "get_device_diagnostics",
    "verify_tensor_computation",
]
