"""Configuration management and schema validation for NETDEFY."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""


class ProjectConfig(BaseModel):
    """Project-level metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str = "NETDEFY"
    full_name: str = "Network Defense Intelligence"
    version: str = "0.1.0"
    tagline: str = "Detect Anomalies. Understand Network Behaviour."
    environment: Literal["development", "staging", "production", "test"] = "development"


class DeviceConfig(BaseModel):
    """Hardware device preferences and compute settings."""

    model_config = ConfigDict(extra="forbid")

    preference: Literal["auto", "mps", "cuda", "cpu"] = "auto"
    fallback_to_cpu: bool = True
    benchmark: bool = False


class SystemConfig(BaseModel):
    """System-level execution settings."""

    model_config = ConfigDict(extra="forbid")

    seed: int = Field(default=42, ge=0, description="Global random seed")
    deterministic: bool = True
    device: DeviceConfig = Field(default_factory=DeviceConfig)


class DataConfig(BaseModel):
    """Data paths and ingestion parameters."""

    model_config = ConfigDict(extra="forbid")

    raw_dir: Path = Path("data/raw")
    interim_dir: Path = Path("data/interim")
    processed_dir: Path = Path("data/processed")
    dataset_name: str = "CICIDS2017"
    label_column: str = "Label"
    benign_label_value: str = "BENIGN"
    chunk_size: int = Field(default=50000, gt=0)
    float_precision: Literal["float32", "float64"] = "float32"


class PreprocessingConfig(BaseModel):
    """Preprocessing and data hygiene configuration."""

    model_config = ConfigDict(extra="forbid")

    scaler_type: Literal["standard", "robust", "minmax"] = "standard"
    handle_infinite: Literal["nan_then_impute", "clip", "drop"] = "nan_then_impute"
    imputation_strategy: Literal["mean", "median", "zero"] = "median"
    remove_duplicate_records: bool = True
    drop_identifier_columns: list[str] = Field(
        default_factory=lambda: [
            "Flow ID",
            "Source IP",
            "Destination IP",
            "Timestamp",
            "Source Port",
        ]
    )
    low_variance_threshold: float = Field(default=0.0, ge=0.0)


class AutoencoderConfig(BaseModel):
    """Deep Autoencoder architectural and optimization hyperparameters."""

    model_config = ConfigDict(extra="forbid")

    latent_dim: int = Field(default=16, gt=0)
    hidden_dims: list[int] = Field(default_factory=lambda: [64, 32])
    activation: Literal["relu", "leaky_relu", "gelu", "elu"] = "relu"
    dropout_rate: float = Field(default=0.1, ge=0.0, le=0.9)
    learning_rate: float = Field(default=0.001, gt=0.0)
    weight_decay: float = Field(default=1e-5, ge=0.0)
    batch_size: int = Field(default=256, gt=0)
    epochs: int = Field(default=25, gt=0)
    early_stopping_patience: int = Field(default=5, gt=0)

    @field_validator("hidden_dims")
    @classmethod
    def validate_hidden_dims(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("hidden_dims list must contain at least one hidden layer dimension")
        if any(dim <= 0 for dim in v):
            raise ValueError("All hidden dimensions must be positive integers")
        return v


class IsolationForestConfig(BaseModel):
    """Scikit-Learn Isolation Forest parameters."""

    model_config = ConfigDict(extra="forbid")

    n_estimators: int = Field(default=100, gt=0)
    max_samples: int | float | Literal["auto"] = "auto"
    contamination: float = Field(default=0.01, gt=0.0, le=0.5)
    n_jobs: int = -1


class ModelsConfig(BaseModel):
    """Model-level settings container."""

    model_config = ConfigDict(extra="forbid")

    autoencoder: AutoencoderConfig = Field(default_factory=AutoencoderConfig)
    isolation_forest: IsolationForestConfig = Field(default_factory=IsolationForestConfig)


class EvaluationConfig(BaseModel):
    """Evaluation protocol and metrics configuration."""

    model_config = ConfigDict(extra="forbid")

    threshold_method: Literal["percentile", "f1_optimal", "extreme_value"] = "percentile"
    threshold_percentile: float = Field(default=99.0, ge=0.0, le=100.0)
    target_metrics: list[str] = Field(
        default_factory=lambda: [
            "precision",
            "recall",
            "f1",
            "pr_auc",
            "roc_auc",
            "false_alarms_per_1000_flows",
            "attack_wise_recall",
            "inference_latency_ms",
            "peak_memory_mb",
        ]
    )


class MLflowConfig(BaseModel):
    """Experiment tracking configuration."""

    model_config = ConfigDict(extra="forbid")

    tracking_uri: str = "file:./mlruns"
    experiment_name: str = "netdefy-anomaly-detection"
    log_models: bool = True
    log_system_metrics: bool = True


class LoggingConfig(BaseModel):
    """Logging configuration."""

    model_config = ConfigDict(extra="forbid")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: str = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    log_to_file: bool = False
    log_file_path: Path = Path("reports/netdefy.log")


class AppConfig(BaseModel):
    """Root configuration object representing the full system settings."""

    model_config = ConfigDict(extra="forbid")

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    mlflow: MLflowConfig = Field(default_factory=MLflowConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_config(config_path: Path | str | None = None) -> AppConfig:
    """Load and validate configuration from YAML file and environment overrides.

    Args:
        config_path: Path to YAML configuration file. If None, resolves from
                     NETDEFY_CONFIG_PATH env var or defaults to 'configs/config.yaml'.

    Returns:
        Validated AppConfig instance.

    Raises:
        FileNotFoundError: If the specified configuration file does not exist.
        ConfigValidationError: If configuration syntax or schema validation fails.
    """
    if config_path is None:
        env_path = os.getenv("NETDEFY_CONFIG_PATH")
        resolved_path = Path(env_path) if env_path else Path("configs/config.yaml")
    else:
        resolved_path = Path(config_path)

    if not resolved_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {resolved_path.resolve()}")

    try:
        with open(resolved_path, encoding="utf-8") as f:
            raw_data: Any = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigValidationError(
            f"YAML syntax error in configuration file {resolved_path}: {exc}"
        ) from exc

    if raw_data is None:
        raw_data = {}

    if not isinstance(raw_data, dict):
        raise ConfigValidationError(
            f"Configuration root must be a mapping (dictionary), got {type(raw_data).__name__}"
        )

    try:
        return AppConfig.model_validate(raw_data)
    except Exception as exc:
        raise ConfigValidationError(
            f"Configuration validation failed for {resolved_path}:\n{exc}"
        ) from exc
