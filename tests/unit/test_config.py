"""Unit tests for configuration loading and Pydantic validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from netdefy.config.settings import (
    AppConfig,
    AutoencoderConfig,
    ConfigValidationError,
    DeviceConfig,
    load_config,
)


def test_load_default_config() -> None:
    """Verify that configs/config.yaml loads cleanly and passes validation."""
    config = load_config("configs/config.yaml")

    assert isinstance(config, AppConfig)
    assert config.project.name == "NETDEFY"
    assert config.project.version == "0.1.0"
    assert config.system.seed == 42
    assert config.system.device.preference in {"auto", "mps", "cuda", "cpu"}
    assert config.data.dataset_name == "CICIDS2017"
    assert config.models.autoencoder.latent_dim == 16
    assert config.models.isolation_forest.contamination == 0.01


def test_load_config_file_not_found() -> None:
    """Verify FileNotFoundError when config file does not exist."""
    with pytest.raises(FileNotFoundError, match="Configuration file not found"):
        load_config("non_existent_config.yaml")


def test_load_invalid_yaml(tmp_path: Path) -> None:
    """Verify ConfigValidationError when YAML syntax is malformed."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("project: [unclosed list", encoding="utf-8")

    with pytest.raises(ConfigValidationError, match="YAML syntax error"):
        load_config(bad_yaml)


def test_load_invalid_root_type(tmp_path: Path) -> None:
    """Verify ConfigValidationError when YAML root is not a dictionary."""
    list_yaml = tmp_path / "list.yaml"
    list_yaml.write_text("- item1\n- item2", encoding="utf-8")

    with pytest.raises(ConfigValidationError, match="must be a mapping"):
        load_config(list_yaml)


def test_invalid_seed_validation() -> None:
    """Verify validation error when seed is negative."""
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        AppConfig.model_validate({"system": {"seed": -5}})


def test_invalid_device_preference() -> None:
    """Verify validation error for unsupported device preference."""
    with pytest.raises(ValidationError):
        DeviceConfig.model_validate({"preference": "tpu_v4"})


def test_invalid_autoencoder_hidden_dims() -> None:
    """Verify validation error for empty or non-positive hidden dimensions."""
    with pytest.raises(ValueError, match="at least one hidden layer dimension"):
        AutoencoderConfig.model_validate({"hidden_dims": []})

    with pytest.raises(ValueError, match="positive integers"):
        AutoencoderConfig.model_validate({"hidden_dims": [64, -32]})


def test_forbid_extra_attributes() -> None:
    """Verify that unknown configuration keys are strictly rejected."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AppConfig.model_validate({"unauthorized_key": "malicious_payload"})
