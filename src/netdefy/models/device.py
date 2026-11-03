"""Hardware device detection, verification, and management for PyTorch."""

from __future__ import annotations

import logging
import platform
from dataclasses import asdict, dataclass
from typing import Any, Literal

import torch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceDiagnostics:
    """Detailed hardware acceleration diagnostics."""

    selected_device: str
    device_type: str
    device_name: str
    cuda_available: bool
    cuda_device_count: int
    mps_available: bool
    mps_built: bool
    verification_passed: bool
    verification_message: str
    os_name: str
    os_release: str
    architecture: str
    python_version: str
    torch_version: str

    def to_dict(self) -> dict[str, Any]:
        """Convert diagnostics to serializable dictionary."""
        return asdict(self)

    def summary(self) -> str:
        """Formatted human-readable summary of device status."""
        return (
            f"Device: {self.selected_device} ({self.device_name}) | "
            f"Verified: {self.verification_passed} | "
            f"MPS: {self.mps_available} (Built: {self.mps_built}) | "
            f"CUDA: {self.cuda_available} ({self.cuda_device_count} devices) | "
            f"Platform: {self.os_name} {self.architecture} | PyTorch: {self.torch_version}"
        )


def verify_tensor_computation(device: torch.device) -> tuple[bool, str]:
    """Execute a small tensor computation on the device to verify functionality.

    Args:
        device: The PyTorch device to test.

    Returns:
        Tuple of (success_boolean, status_or_error_message).
    """
    try:
        a = torch.tensor([1.0, 2.0, 3.0], dtype=torch.float32, device=device)
        b = torch.tensor([4.0, 5.0, 6.0], dtype=torch.float32, device=device)
        c = (a * 2.0) + b
        result = float(c.sum().item())
        expected = float((1.0 * 2.0 + 4.0) + (2.0 * 2.0 + 5.0) + (3.0 * 2.0 + 6.0))

        if abs(result - expected) > 1e-4:
            return False, f"Computation mismatch: got {result}, expected {expected}"

        # Clean up accelerator memory caches if applicable
        if device.type == "mps" and hasattr(torch.mps, "empty_cache"):
            torch.mps.empty_cache()
        elif device.type == "cuda" and hasattr(torch.cuda, "empty_cache"):
            torch.cuda.empty_cache()

        return True, "Computation verified successfully."
    except Exception as exc:  # noqa: BLE001
        return False, f"Tensor computation failed: {exc}"


def get_device(
    preference: Literal["auto", "mps", "cuda", "cpu"] = "auto",
    fallback_to_cpu: bool = True,
) -> torch.device:
    """Select and verify the most appropriate compute device.

    Args:
        preference: Desired hardware acceleration ('auto', 'mps', 'cuda', 'cpu').
        fallback_to_cpu: If True, falls back to CPU if preferred accelerator fails verification.

    Returns:
        Verified torch.device instance.

    Raises:
        RuntimeError: If requested accelerator is unavailable/fails and fallback_to_cpu is False.
    """
    preference_normalized = preference.lower().strip()

    if preference_normalized == "cpu":
        logger.info("Using explicitly configured CPU device.")
        return torch.device("cpu")

    # Handle CUDA preference
    if preference_normalized == "cuda":
        if torch.cuda.is_available():
            dev = torch.device("cuda")
            verified, msg = verify_tensor_computation(dev)
            if verified:
                logger.info("CUDA device verified: %s", torch.cuda.get_device_name(0))
                return dev
            logger.warning("CUDA available but verification failed: %s", msg)
        else:
            logger.warning("CUDA requested but not available on this system.")

        if not fallback_to_cpu:
            raise RuntimeError("CUDA was requested but could not be verified.")
        logger.info("Falling back to CPU from CUDA.")
        return torch.device("cpu")

    # Handle MPS preference
    if preference_normalized == "mps":
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            dev = torch.device("mps")
            verified, msg = verify_tensor_computation(dev)
            if verified:
                logger.info("Apple MPS device verified.")
                return dev
            logger.warning("MPS available but verification failed: %s", msg)
        else:
            logger.warning("Apple MPS requested but not available on this system.")

        if not fallback_to_cpu:
            raise RuntimeError("MPS was requested but could not be verified.")
        logger.info("Falling back to CPU from MPS.")
        return torch.device("cpu")

    # Auto selection: CUDA -> MPS -> CPU
    if torch.cuda.is_available():
        dev = torch.device("cuda")
        verified, msg = verify_tensor_computation(dev)
        if verified:
            logger.info("Auto-selected CUDA device: %s", torch.cuda.get_device_name(0))
            return dev
        logger.warning("Auto-detection: CUDA verification failed: %s", msg)

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        dev = torch.device("mps")
        verified, msg = verify_tensor_computation(dev)
        if verified:
            logger.info("Auto-selected Apple MPS device.")
            return dev
        logger.warning("Auto-detection: Apple MPS verification failed: %s", msg)

    logger.info("Auto-detection: Falling back to standard CPU device.")
    return torch.device("cpu")


def get_device_diagnostics(
    preference: Literal["auto", "mps", "cuda", "cpu"] = "auto",
) -> DeviceDiagnostics:
    """Collect comprehensive hardware and PyTorch execution diagnostics.

    Args:
        preference: Hardware preference to diagnose.

    Returns:
        Populated DeviceDiagnostics instance.
    """
    device = get_device(preference=preference, fallback_to_cpu=True)
    verified, verification_msg = verify_tensor_computation(device)

    cuda_avail = torch.cuda.is_available()
    cuda_count = torch.cuda.device_count() if cuda_avail else 0

    mps_avail = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
    mps_built = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_built())

    if device.type == "cuda" and cuda_avail:
        device_name = torch.cuda.get_device_name(0)
    elif device.type == "mps":
        device_name = f"Apple Silicon ({platform.processor() or 'ARM'})"
    else:
        device_name = platform.processor() or "CPU"

    return DeviceDiagnostics(
        selected_device=str(device),
        device_type=device.type,
        device_name=device_name,
        cuda_available=cuda_avail,
        cuda_device_count=cuda_count,
        mps_available=mps_avail,
        mps_built=mps_built,
        verification_passed=verified,
        verification_message=verification_msg,
        os_name=platform.system(),
        os_release=platform.release(),
        architecture=platform.machine(),
        python_version=platform.python_version(),
        torch_version=torch.__version__,
    )
