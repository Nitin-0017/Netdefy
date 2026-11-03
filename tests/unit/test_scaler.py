"""Unit tests for training-only feature scalers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from netdefy.preprocessing.scaler import FeatureScaler


def test_standard_scaler_and_float32_output() -> None:
    """Verify StandardScaler computes mean/std and outputs float32."""
    train_df = pd.DataFrame(
        {
            "FeatA": [10.0, 20.0, 30.0],  # mean=20.0, std=10.0
            "ZeroVar": [5.0, 5.0, 5.0],  # zero variance -> scale=1.0
        }
    )

    scaler = FeatureScaler(scaler_type="standard")
    scaled = scaler.fit_transform(train_df, ["FeatA", "ZeroVar"])

    assert scaler.is_fitted is True
    assert scaler.center_["FeatA"] == 20.0
    assert scaler.scale_["FeatA"] == 10.0
    assert scaler.scale_["ZeroVar"] == 1.0  # Safe unit scale

    # Check scaled values: (10 - 20) / 10 = -1.0
    assert scaled["FeatA"].iloc[0] == -1.0
    assert scaled["FeatA"].iloc[1] == 0.0
    assert scaled["FeatA"].iloc[2] == 1.0
    assert scaled["FeatA"].dtype == np.float32


def test_robust_scaler_median_and_iqr() -> None:
    """Verify RobustScaler computes median and IQR."""
    train_df = pd.DataFrame(
        {
            "Feat": [10.0, 20.0, 30.0, 40.0, 50.0],  # median=30, q25=20, q75=40, iqr=20
        }
    )

    scaler = FeatureScaler(scaler_type="robust")
    scaled = scaler.fit_transform(train_df, ["Feat"])

    assert scaler.center_["Feat"] == 30.0
    assert scaler.scale_["Feat"] == 20.0
    assert scaled["Feat"].iloc[2] == 0.0  # (30 - 30) / 20 = 0.0


def test_validation_values_cannot_change_fitted_training_scaler() -> None:
    """Verify that transforming arbitrary validation or test values cannot alter training parameters."""
    train_df = pd.DataFrame({"Feat": [10.0, 20.0, 30.0]})
    scaler = FeatureScaler(scaler_type="standard")
    scaler.fit(train_df, ["Feat"])

    orig_center = scaler.center_["Feat"]
    orig_scale = scaler.scale_["Feat"]

    # Transform massive outliers in evaluation data
    eval_df_outliers = pd.DataFrame({"Feat": [1e9, -1e9, 500000.0]})
    scaler.transform(eval_df_outliers)

    # Stored training parameters must remain strictly identical
    assert scaler.center_["Feat"] == orig_center
    assert scaler.scale_["Feat"] == orig_scale


def test_scaler_save_and_load(tmp_path: Path) -> None:
    """Verify scaler artifact serialization with joblib."""
    train_df = pd.DataFrame({"Metric": [2.0, 4.0, 6.0]})
    scaler = FeatureScaler(scaler_type="standard")
    scaler.fit(train_df, ["Metric"])

    dest_file = tmp_path / "scaler.joblib"
    scaler.save(dest_file)
    assert dest_file.is_file()

    loaded = FeatureScaler.load(dest_file)
    assert loaded.is_fitted is True
    assert loaded.center_["Metric"] == 4.0


def test_unfitted_transform_raises_runtime_error() -> None:
    """Verify error when transforming before fit."""
    scaler = FeatureScaler()
    with pytest.raises(RuntimeError, match="must be fitted"):
        scaler.transform(pd.DataFrame({"a": [1]}))

