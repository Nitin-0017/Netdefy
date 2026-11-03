"""Integration tests verifying end-to-end Phase 1 engineering pipeline."""

from __future__ import annotations

import pandas as pd
import torch

from netdefy.config import load_config
from netdefy.data import DatasetValidator
from netdefy.models import get_device, verify_tensor_computation
from netdefy.utils import setup_logging
from netdefy.utils.reproducibility import set_seed


def test_phase1_foundation_integration_pipeline() -> None:
    """Verify that all Phase 1 components interoperate without errors."""
    # 1. Configuration Loading
    config = load_config("configs/config.yaml")
    assert config.project.name == "NETDEFY"

    # 2. Logging Setup
    logger = setup_logging(level=config.logging.level)
    logger.info("Running Phase 1 integration verification.")

    # 3. Reproducibility Configuration
    seed_report = set_seed(seed=config.system.seed, deterministic=config.system.deterministic)
    assert seed_report.seed == config.system.seed
    assert seed_report.numpy_seeded is True

    # 4. Device Management & Verification
    device = get_device(preference=config.system.device.preference)
    verified, msg = verify_tensor_computation(device)
    assert verified is True, f"Tensor computation failed on device {device}: {msg}"

    # 5. Dataset Validation Pipeline Integration
    validator = DatasetValidator(
        required_columns=[
            config.data.label_column,
            "Flow Duration",
            "Flow Bytes/s",
        ],
        check_duplicates=config.preprocessing.remove_duplicate_records,
        check_infinites=True,
    )

    # Validate against a synthetic schema matching CICFlowMeter conventions
    synthetic_flows = pd.DataFrame(
        {
            "Flow Duration": [12000.0, 45000.0, 98000.0, 3100.0],
            "Flow Bytes/s": [450.2, 890.1, 120.0, 15000.0],
            config.data.label_column: [
                config.data.benign_label_value,
                config.data.benign_label_value,
                "DoS-Hulk",
                config.data.benign_label_value,
            ],
            "Flow Packets/s": [12.5, 45.0, 2.1, 150.0],
        }
    )

    validation_result = validator.validate(synthetic_flows)
    assert validation_result.is_valid is True
    assert validation_result.has_errors is False
    assert validation_result.total_rows == 4
    assert validation_result.total_columns == 4

    # 6. Tensor data allocation on the verified device
    feature_tensor = torch.tensor(
        synthetic_flows[["Flow Duration", "Flow Bytes/s", "Flow Packets/s"]].values,
        dtype=torch.float32,
        device=device,
    )
    assert feature_tensor.shape == (4, 3)
    assert feature_tensor.device.type == device.type
