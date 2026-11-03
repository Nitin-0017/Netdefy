"""Unit tests for network traffic dataset validation engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from netdefy.data.validation import (
    DatasetValidator,
    ValidationSeverity,
    validate_dataset,
)


def _create_sample_valid_df() -> pd.DataFrame:
    """Helper creating a healthy, small synthetic flow dataframe."""
    return pd.DataFrame(
        {
            "Flow Duration": [100.0, 250.0, 50.0],
            "Total Fwd Packets": [2, 5, 1],
            "Total Backward Packets": [1, 4, 1],
            "Flow Bytes/s": [1000.5, 2500.0, 500.2],
            "Label": ["BENIGN", "BENIGN", "BENIGN"],
        }
    )


def test_validation_passes_on_healthy_data() -> None:
    """Verify healthy dataframe with required columns passes with zero issues."""
    df = _create_sample_valid_df()
    validator = DatasetValidator(required_columns=["Flow Duration", "Label"])
    result = validator.validate(df)

    assert result.is_valid is True
    assert result.has_errors is False
    assert result.has_warnings is False
    assert len(result.issues) == 0
    assert result.total_rows == 3
    assert result.total_columns == 5


def test_validation_fails_on_empty_dataframe() -> None:
    """Verify empty dataframe triggers an ERROR issue."""
    df = pd.DataFrame()
    result = validate_dataset(df)

    assert result.is_valid is False
    assert result.has_errors is True
    errors = result.get_errors()
    assert len(errors) == 1
    assert errors[0].check_name == "empty_dataset"


def test_validation_fails_on_missing_required_columns() -> None:
    """Verify missing required columns trigger an ERROR issue."""
    df = _create_sample_valid_df()
    validator = DatasetValidator(required_columns=["NonExistentColumn", "Label"])
    result = validator.validate(df)

    assert result.is_valid is False
    errors = result.get_errors()
    assert any(e.check_name == "missing_required_columns" for e in errors)


def test_validation_detects_duplicate_records() -> None:
    """Verify duplicate records are detected as a WARNING."""
    df = pd.DataFrame(
        {
            "FeatureA": [1.0, 2.0, 1.0],
            "FeatureB": [10.0, 20.0, 10.0],
        }
    )
    validator = DatasetValidator(check_duplicates=True)
    result = validator.validate(df)

    assert result.is_valid is True  # Duplicates are warnings, not hard blocking errors
    assert result.has_warnings is True
    warnings = result.get_warnings()
    assert any(w.check_name == "duplicate_records" for w in warnings)


def test_validation_detects_missing_values() -> None:
    """Verify NaN, None, and empty string missing values generate warnings."""
    df = pd.DataFrame(
        {
            "FeatureA": [1.0, np.nan, 3.0],
            "StringCol": ["alpha", "   ", "gamma"],
        }
    )
    result = validate_dataset(df)

    assert result.has_warnings is True
    warnings = result.get_warnings()
    missing_issue = next(w for w in warnings if w.check_name == "missing_values")
    assert missing_issue.severity == ValidationSeverity.WARNING
    assert "FeatureA" in missing_issue.details["columns_with_missing"]
    assert "StringCol" in missing_issue.details["columns_with_missing"]


def test_validation_detects_infinite_values() -> None:
    """Verify positive and negative infinities trigger an ERROR issue."""
    df = pd.DataFrame(
        {
            "Flow Duration": [100.0, 200.0, 300.0],
            "Flow Bytes/s": [1500.0, np.inf, -np.inf],
        }
    )
    result = validate_dataset(df)

    assert result.is_valid is False
    assert result.has_errors is True
    errors = result.get_errors()
    inf_issue = next(e for e in errors if e.check_name == "infinite_values")
    assert inf_issue.details["columns_with_infinites"]["Flow Bytes/s"] == 2


def test_validation_detects_unexpected_types() -> None:
    """Verify string/object types on columns with numeric names trigger warnings."""
    df = pd.DataFrame(
        {
            "Flow Duration": ["100", "200", "corrupted_entry"],
            "Label": ["BENIGN", "BENIGN", "BENIGN"],
        }
    )
    result = validate_dataset(df)

    assert result.has_warnings is True
    warnings = result.get_warnings()
    assert any(w.check_name == "unexpected_data_types" for w in warnings)


def test_schema_consistency_between_partitions() -> None:
    """Verify schema consistency check between multiple partitions/days."""
    day1_df = pd.DataFrame({"colA": [1], "colB": [2]})
    day2_df = pd.DataFrame({"colA": [3], "colB": [4]})
    day3_mismatch = pd.DataFrame({"colA": [5], "colC_different": [6]})

    # Consistent schemas -> no issues
    issues_consistent = DatasetValidator.validate_schema_consistency([day1_df, day2_df])
    assert len(issues_consistent) == 0

    # Inconsistent schemas -> reports error
    issues_mismatched = DatasetValidator.validate_schema_consistency([day1_df, day3_mismatch])
    assert len(issues_mismatched) == 1
    assert issues_mismatched[0].check_name == "schema_consistency"
