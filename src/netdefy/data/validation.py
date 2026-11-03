"""Reusable dataset validation engine for network traffic data."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd


class ValidationSeverity(StrEnum):
    """Severity levels for validation issues."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ValidationIssue:
    """Individual data quality or schema validation issue."""

    check_name: str
    severity: ValidationSeverity
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert issue to serializable dictionary."""
        return {
            "check_name": self.check_name,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class ValidationResult:
    """Consolidated outcome of dataset validation."""

    is_valid: bool
    total_rows: int
    total_columns: int
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        """Whether any warnings were recorded."""
        return any(issue.severity == ValidationSeverity.WARNING for issue in self.issues)

    @property
    def has_errors(self) -> bool:
        """Whether any errors were recorded."""
        return any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    def get_errors(self) -> list[ValidationIssue]:
        """Retrieve all recorded errors."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    def get_warnings(self) -> list[ValidationIssue]:
        """Retrieve all recorded warnings."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    def summary(self) -> str:
        """Formatted human-readable summary of validation findings."""
        status = "PASSED" if self.is_valid else "FAILED"
        err_count = len(self.get_errors())
        warn_count = len(self.get_warnings())
        return (
            f"Validation Status: {status} | Rows: {self.total_rows:,} | "
            f"Columns: {self.total_columns} | Errors: {err_count} | Warnings: {warn_count}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "is_valid": self.is_valid,
            "total_rows": self.total_rows,
            "total_columns": self.total_columns,
            "error_count": len(self.get_errors()),
            "warning_count": len(self.get_warnings()),
            "issues": [issue.to_dict() for issue in self.issues],
        }


class DatasetValidator:
    """Validates network traffic tabular data against schema and numerical health rules."""

    def __init__(
        self,
        required_columns: list[str] | None = None,
        allow_empty: bool = False,
        check_duplicates: bool = True,
        check_missing: bool = True,
        check_infinites: bool = True,
        check_unexpected_types: bool = True,
    ) -> None:
        """Initialize the DatasetValidator.

        Args:
            required_columns: Column names that must be present in the DataFrame.
            allow_empty: Whether an empty DataFrame is treated as an error (False) or allowed.
            check_duplicates: Whether to detect and report duplicate rows.
            check_missing: Whether to detect and report missing / NaN / None values.
            check_infinites: Whether to detect and report +/- infinity numerical values.
            check_unexpected_types: Whether to inspect columns expected to be numeric.
        """
        self.required_columns = required_columns or []
        self.allow_empty = allow_empty
        self.check_duplicates = check_duplicates
        self.check_missing = check_missing
        self.check_infinites = check_infinites
        self.check_unexpected_types = check_unexpected_types

    def validate(self, df: pd.DataFrame) -> ValidationResult:
        """Run all configured validation rules against the provided DataFrame.

        Args:
            df: Input pandas DataFrame to validate.

        Returns:
            ValidationResult with passed/failed status and list of findings.
        """
        issues: list[ValidationIssue] = []
        total_rows = len(df)
        total_columns = len(df.columns)

        # 1. Empty dataset check
        if (total_rows == 0 or total_columns == 0) and not self.allow_empty:
            issues.append(
                ValidationIssue(
                    check_name="empty_dataset",
                    severity=ValidationSeverity.ERROR,
                    message=f"Dataset is empty: {total_rows} rows, {total_columns} columns.",
                    details={"rows": total_rows, "columns": total_columns},
                )
            )
            return ValidationResult(
                is_valid=False,
                total_rows=total_rows,
                total_columns=total_columns,
                issues=issues,
            )

        # 2. Duplicate column header check
        # CICIDS2017 raw CSVs occasionally have duplicate headers (e.g. 'Fwd Header Length')
        col_names = [str(c).strip() for c in df.columns]
        seen_cols: set[str] = set()
        duplicate_cols: list[str] = []
        for c in col_names:
            if c in seen_cols and c not in duplicate_cols:
                duplicate_cols.append(c)
            seen_cols.add(c)

        if duplicate_cols:
            issues.append(
                ValidationIssue(
                    check_name="duplicate_columns",
                    severity=ValidationSeverity.ERROR,
                    message=f"Found duplicate column headers: {duplicate_cols}",
                    details={"duplicate_columns": duplicate_cols},
                )
            )

        # 3. Missing required columns
        current_cols_set = {str(c).strip() for c in df.columns}
        missing_required = [
            col for col in self.required_columns if col.strip() not in current_cols_set
        ]
        if missing_required:
            issues.append(
                ValidationIssue(
                    check_name="missing_required_columns",
                    severity=ValidationSeverity.ERROR,
                    message=f"Dataset is missing {len(missing_required)} required columns.",
                    details={"missing_columns": missing_required},
                )
            )

        # 4. Duplicate rows check
        if self.check_duplicates and total_rows > 0:
            try:
                dup_count = int(df.duplicated().sum())
                if dup_count > 0:
                    dup_pct = (dup_count / total_rows) * 100.0
                    issues.append(
                        ValidationIssue(
                            check_name="duplicate_records",
                            severity=ValidationSeverity.WARNING,
                            message=f"Found {dup_count:,} duplicate rows ({dup_pct:.2f}% of dataset).",
                            details={"duplicate_count": dup_count, "duplicate_percentage": dup_pct},
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                issues.append(
                    ValidationIssue(
                        check_name="duplicate_records",
                        severity=ValidationSeverity.WARNING,
                        message=f"Could not compute duplicate records: {exc}",
                    )
                )

        # 5. Missing values check (NaN, None, empty strings)
        if self.check_missing and total_rows > 0:
            missing_per_col: dict[str, int] = {}
            for col in df.columns:
                series = df[col]
                # Check standard nulls
                null_count = int(series.isna().sum())
                # Check empty whitespace strings if object dtype
                if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
                    empty_str_count = int((series.astype(str).str.strip() == "").sum())
                    null_count += empty_str_count

                if null_count > 0:
                    missing_per_col[str(col)] = null_count

            if missing_per_col:
                total_missing = sum(missing_per_col.values())
                issues.append(
                    ValidationIssue(
                        check_name="missing_values",
                        severity=ValidationSeverity.WARNING,
                        message=f"Found {total_missing:,} missing values across {len(missing_per_col)} columns.",
                        details={"columns_with_missing": missing_per_col},
                    )
                )

        # 6. Infinite values check (+inf, -inf)
        if self.check_infinites and total_rows > 0:
            infinite_per_col: dict[str, int] = {}
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                series = df[col]
                inf_count = int(np.isinf(series).sum())
                if inf_count > 0:
                    infinite_per_col[str(col)] = inf_count

            if infinite_per_col:
                total_inf = sum(infinite_per_col.values())
                issues.append(
                    ValidationIssue(
                        check_name="infinite_values",
                        severity=ValidationSeverity.ERROR,
                        message=f"Found {total_inf:,} infinite values across {len(infinite_per_col)} columns.",
                        details={"columns_with_infinites": infinite_per_col},
                    )
                )

        # 7. Unexpected data types check
        if self.check_unexpected_types and total_rows > 0:
            # Detect string/object columns containing values like 'Infinity' or numbers that failed conversion
            suspicious_object_cols: list[str] = []
            for col in df.select_dtypes(include=["object"]).columns:
                # If column name suggests a numeric metric (e.g. rate, length, count, duration)
                col_lower = str(col).lower()
                is_numeric_name = any(
                    term in col_lower
                    for term in ["duration", "bytes/s", "packets/s", "len", "iat", "count", "size"]
                )
                if is_numeric_name:
                    suspicious_object_cols.append(str(col))

            if suspicious_object_cols:
                issues.append(
                    ValidationIssue(
                        check_name="unexpected_data_types",
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Columns with numeric naming conventions are stored as object/string: "
                            f"{suspicious_object_cols}"
                        ),
                        details={"suspicious_columns": suspicious_object_cols},
                    )
                )

        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        return ValidationResult(
            is_valid=is_valid,
            total_rows=total_rows,
            total_columns=total_columns,
            issues=issues,
        )

    @staticmethod
    def validate_schema_consistency(dataframes: list[pd.DataFrame]) -> list[ValidationIssue]:
        """Verify that multiple partitioned DataFrames share an identical column schema.

        Args:
            dataframes: List of DataFrames representing different partitions (e.g., days).

        Returns:
            List of schema mismatch ValidationIssues, if any.
        """
        if len(dataframes) < 2:
            return []

        issues: list[ValidationIssue] = []
        reference_schema = [str(c).strip() for c in dataframes[0].columns]

        for idx, df in enumerate(dataframes[1:], start=2):
            current_schema = [str(c).strip() for c in df.columns]
            if current_schema != reference_schema:
                missing_in_current = set(reference_schema) - set(current_schema)
                extra_in_current = set(current_schema) - set(reference_schema)
                issues.append(
                    ValidationIssue(
                        check_name="schema_consistency",
                        severity=ValidationSeverity.ERROR,
                        message=f"Schema mismatch between Partition 1 and Partition {idx}.",
                        details={
                            "partition_index": idx,
                            "missing_in_partition": list(missing_in_current),
                            "extra_in_partition": list(extra_in_current),
                        },
                    )
                )

        return issues


def validate_dataset(
    df: pd.DataFrame,
    required_columns: list[str] | None = None,
) -> ValidationResult:
    """Convenience function to validate a network flow DataFrame.

    Args:
        df: Pandas DataFrame of network flow records.
        required_columns: Optional list of mandatory column names.

    Returns:
        ValidationResult instance.
    """
    validator = DatasetValidator(required_columns=required_columns)
    return validator.validate(df)
