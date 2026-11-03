#!/usr/bin/env python3
"""Environment diagnostic and hardware verification script for NETDEFY."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

# Add src to python path if executed directly
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

import psutil
import torch

from netdefy.config import load_config  # noqa: E402
from netdefy.models.device import get_device_diagnostics, verify_tensor_computation  # noqa: E402


def format_bytes(byte_count: int) -> str:
    """Format bytes into human-readable GiB string."""
    gib = byte_count / (1024**3)
    return f"{gib:.2f} GiB"


def main() -> int:
    """Run comprehensive environment and accelerator verification."""
    print("=" * 80)
    print("       NETDEFY — ENVIRONMENT DIAGNOSTICS & HARDWARE VERIFICATION       ")
    print("=" * 80)

    # 1. System and Platform Architecture
    print("\n[1] HOST ENVIRONMENT & ARCHITECTURE")
    print(f"  • Operating System:       {platform.system()} ({platform.release()})")
    print(f"  • OS Platform:            {platform.platform()}")
    print(f"  • CPU Architecture:       {platform.machine()}")
    print(f"  • Processor:              {platform.processor() or 'N/A'}")
    print(f"  • Python Version:         {platform.python_version()}")
    print(f"  • Python Executable:      {sys.executable}")

    # 2. System Memory
    print("\n[2] SYSTEM MEMORY")
    mem = psutil.virtual_memory()
    print(f"  • Total Physical Memory:  {format_bytes(mem.total)}")
    print(f"  • Available Memory:       {format_bytes(mem.available)}")
    print(f"  • Memory Usage:           {mem.percent}%")

    # 3. PyTorch & Compute Accelerators
    print("\n[3] PYTORCH & COMPUTE ACCELERATOR DIAGNOSTICS")
    print(f"  • PyTorch Version:        {torch.__version__}")
    print(f"  • CUDA Available:         {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"    - Device Count:         {torch.cuda.device_count()}")
        print(f"    - Device Name (0):      {torch.cuda.get_device_name(0)}")

    mps_available = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
    mps_built = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_built())
    print(f"  • Apple MPS Available:    {mps_available}")
    print(f"  • Apple MPS Built:        {mps_built}")

    # 4. Device Selection & Live Tensor Execution
    print("\n[4] DEVICE SELECTION & LIVE TENSOR VERIFICATION")
    diagnostics = get_device_diagnostics(preference="auto")
    print(f"  • Selected Device:        {diagnostics.selected_device}")
    print(f"  • Device Type:            {diagnostics.device_type}")
    print(f"  • Device Name:            {diagnostics.device_name}")
    print(f"  • Verification Passed:    {diagnostics.verification_passed}")
    print(f"  • Verification Details:   {diagnostics.verification_message}")

    # Explicit tensor verification
    selected_device = torch.device(diagnostics.selected_device)
    verified, msg = verify_tensor_computation(selected_device)
    if not verified:
        print(f"  [CRITICAL ERROR] Live tensor verification failed: {msg}")
        return 1
    print("  • Active Tensor Computation: SUCCESSFUL")

    # 5. Configuration Validation
    print("\n[5] MASTER CONFIGURATION SCHEMA")
    try:
        config = load_config(project_root / "configs" / "config.yaml")
        print("  • Config File:            configs/config.yaml")
        print(f"  • Project Name:           {config.project.name} ({config.project.full_name})")
        print(f"  • Environment:            {config.project.environment}")
        print(f"  • Random Seed:            {config.system.seed}")
        print(f"  • Device Preference:      {config.system.device.preference}")
        print(f"  • Target Dataset:         {config.data.dataset_name}")
        print("  • Schema Validation:      PASSED")
    except Exception as exc:  # noqa: BLE001
        print(f"  [ERROR] Configuration schema validation failed: {exc}")
        return 1

    print("\n" + "=" * 80)
    print("       DIAGNOSTICS COMPLETE — ENVIRONMENT IS READY FOR NETDEFY          ")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
