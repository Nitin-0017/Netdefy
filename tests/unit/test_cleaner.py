"""Unit tests for missing and infinite value imputation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from netdefy.preprocessing.cleaner import DataCleaner


def test_cleaner_converts_infinities_and_imputes_median() -> None:
    """Verify that +/- infinities are converted to NaN and imputed with training median."""
    train_df = pd.DataFrame(
        {
            "FeatureA": [10.0, 20.0, 30.0, np.nan, 20.0],  # Median: 20.0
            "FeatureB": [
                100.0,
                np.inf,
                -np.inf,
                200.0,
                300.0,
            ],  # Infs -> NaN, valid: 100, 200, 300 -> Median: 200.0
        }
    )

    cleaner = DataCleaner(strategy="median")
    cleaner.fit(train_df, ["FeatureA", "FeatureB"])

    assert cleaner.is_fitted is True
    assert cleaner.statistics_["FeatureA"] == 20.0
    assert cleaner.statistics_["FeatureB"] == 200.0

    # Transform evaluation set containing infinities and missing
    eval_df = pd.DataFrame(
        {
            "FeatureA": [np.nan, 50.0],
            "FeatureB": [np.inf, np.nan],
        }
    )

    transformed = cleaner.transform(eval_df, ["FeatureA", "FeatureB"], partition_name="test")
    assert transformed["FeatureA"].iloc[0] == 20.0
    assert transformed["FeatureA"].iloc[1] == 50.0
    assert transformed["FeatureB"].iloc[0] == 200.0
    assert transformed["FeatureB"].iloc[1] == 200.0
    assert transformed["FeatureA"].dtype == np.float32


def test_transform_unfitted_raises_runtime_error() -> None:
    """Verify RuntimeError when calling transform before fit."""
    cleaner = DataCleaner()
    with pytest.raises(RuntimeError, match="must be fitted"):
        cleaner.transform(pd.DataFrame({"a": [1]}), ["a"])


def test_validation_values_cannot_change_fitted_training_imputer() -> None:
    """Verify that transforming arbitrary validation or test values cannot alter training statistics."""
    train_df = pd.DataFrame({"Metric": [10.0, 20.0, 30.0]})
    cleaner = DataCleaner(strategy="median")
    cleaner.fit(train_df, ["Metric"])

    original_stat = cleaner.statistics_["Metric"]
    assert original_stat == 20.0

    # Transform massive outliers in evaluation data
    eval_df_outliers = pd.DataFrame({"Metric": [9999999.0, -9999999.0, np.nan, np.inf]})
    cleaner.transform(eval_df_outliers, ["Metric"], partition_name="validation")

    # Stored training statistic must be completely unchanged
    assert cleaner.statistics_["Metric"] == original_stat


def test_cleaner_save_and_load(tmp_path: Path) -> None:
    """Verify cleaner artifact serialization with joblib."""
    train_df = pd.DataFrame({"Col": [5.0, 15.0, 25.0]})
    cleaner = DataCleaner()
    cleaner.fit(train_df, ["Col"])

    artifact_file = tmp_path / "imputer.joblib"
    cleaner.save(artifact_file)
    assert artifact_file.is_file()

    loaded = DataCleaner.load(artifact_file)
    assert loaded.is_fitted is True
    assert loaded.statistics_["Col"] == 15.0
