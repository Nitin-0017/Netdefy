"""Missing and infinite value treatment with training-only median imputation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ImputationAudit:
    """Summary of missing and infinite values cleaned across partitions."""

    partition_name: str
    total_infinities_converted: int = 0
    total_missing_imputed: int = 0
    infinities_per_feature: dict[str, int] = field(default_factory=dict)
    missing_per_feature: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert audit to dictionary."""
        return {
            "partition_name": self.partition_name,
            "total_infinities_converted": self.total_infinities_converted,
            "total_missing_imputed": self.total_missing_imputed,
            "infinities_per_feature": self.infinities_per_feature,
            "missing_per_feature": self.missing_per_feature,
        }


class DataCleaner:
    """Handles infinite-to-NaN conversion and training-only imputation."""

    def __init__(
        self,
        strategy: Literal["median", "mean", "zero"] = "median",
    ) -> None:
        """Initialize the data cleaner.

        Args:
            strategy: Imputation method ('median', 'mean', or 'zero').
        """
        self.strategy = strategy
        self.statistics_: dict[str, float] = {}
        self.constant_columns_in_training: list[str] = []
        self.all_missing_columns_in_training: list[str] = []
        self.is_fitted: bool = False
        self.audits: dict[str, ImputationAudit] = {}

    def fit(self, train_df: pd.DataFrame, feature_columns: list[str]) -> DataCleaner:
        """Fit imputation statistics strictly on the training partition.

        Args:
            train_df: DataFrame containing the training partition records.
            feature_columns: Columns to compute statistics for.

        Returns:
            Fitted DataCleaner instance.
        """
        logger.info(
            "Fitting DataCleaner (strategy=%s) strictly on training partition.", self.strategy
        )

        # Replace +/- inf with NaN on training data copy
        df_sub = train_df[feature_columns].replace([np.inf, -np.inf], np.nan)

        stats: dict[str, float] = {}
        constant_cols: list[str] = []
        all_missing_cols: list[str] = []

        for col in feature_columns:
            series = pd.to_numeric(df_sub[col], errors="coerce")
            valid_series = series.dropna()

            if valid_series.empty:
                logger.warning(
                    "Feature %s is entirely NaN/empty in training data. Defaulting imputation value to 0.0.",
                    col,
                )
                stats[col] = 0.0
                all_missing_cols.append(col)
                continue

            # Check if column is constant in training data
            if valid_series.nunique() <= 1:
                constant_cols.append(col)

            if self.strategy == "median":
                val = float(valid_series.median())
            elif self.strategy == "mean":
                val = float(valid_series.mean())
            elif self.strategy == "zero":
                val = 0.0
            else:
                raise ValueError(f"Unsupported imputation strategy: {self.strategy}")

            stats[col] = val

        self.statistics_ = stats
        self.constant_columns_in_training = constant_cols
        self.all_missing_columns_in_training = all_missing_cols
        self.is_fitted = True

        logger.info(
            "Fitted imputer on %d features. Found %d constant and %d all-missing features in training.",
            len(stats),
            len(constant_cols),
            len(all_missing_cols),
        )
        return self

    def transform(
        self,
        df: pd.DataFrame,
        feature_columns: list[str],
        partition_name: str = "unknown",
    ) -> pd.DataFrame:
        """Apply the frozen imputation statistics to a DataFrame chunk.

        Args:
            df: DataFrame to clean and impute.
            feature_columns: Feature columns to process.
            partition_name: Partition label for audit tracking.

        Returns:
            Cleaned DataFrame with NaN values filled and numeric columns cast to float32.

        Raises:
            RuntimeError: If transform is called prior to fit.
        """
        if not self.is_fitted:
            raise RuntimeError(
                "DataCleaner must be fitted on training data before calling transform."
            )

        if partition_name not in self.audits:
            self.audits[partition_name] = ImputationAudit(partition_name=partition_name)
        audit = self.audits[partition_name]

        out_df = df.copy()

        for col in feature_columns:
            if col not in out_df.columns:
                continue

            series = pd.to_numeric(out_df[col], errors="coerce")

            # Count infinities
            inf_count = int(np.isinf(series).sum())
            if inf_count > 0:
                audit.total_infinities_converted += inf_count
                audit.infinities_per_feature[col] = (
                    audit.infinities_per_feature.get(col, 0) + inf_count
                )
                series = series.replace([np.inf, -np.inf], np.nan)

            # Count missing values
            null_count = int(series.isna().sum())
            if null_count > 0:
                audit.total_missing_imputed += null_count
                audit.missing_per_feature[col] = audit.missing_per_feature.get(col, 0) + null_count
                impute_val = self.statistics_.get(col, 0.0)
                series = series.fillna(impute_val)

            out_df[col] = series.astype(np.float32)

        return out_df

    def fit_transform(self, train_df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
        """Fit on training data and return the transformed training DataFrame."""
        return self.fit(train_df, feature_columns).transform(
            train_df, feature_columns, partition_name="train"
        )

    def save(self, destination: Path) -> None:
        """Save fitted cleaner to joblib file.

        Args:
            destination: Path to joblib file.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, destination)
        logger.info("Saved DataCleaner artifact to %s", destination)

    @classmethod
    def load(cls, source: Path) -> DataCleaner:
        """Load fitted cleaner from joblib file.

        Args:
            source: Path to joblib file.

        Returns:
            Loaded DataCleaner instance.
        """
        instance = joblib.load(source)
        if not isinstance(instance, cls):
            raise TypeError(f"Loaded object is not a DataCleaner, got {type(instance)}")
        return instance

    def generate_missing_value_report_markdown(self) -> str:
        """Generate markdown report documenting missing and infinite value treatments."""
        lines = [
            "# NETDEFY Missing & Infinite Value Imputation Report",
            "",
            "## 1. Methodology & Leakage Prevention",
            "",
            "- **Infinities Conversion:** Positive and negative infinities (arising from zero duration division in",
            "  `Flow Bytes/s` and `Flow Packets/s`) are converted to `NaN` prior to imputation.",
            f"- **Imputation Strategy:** `{self.strategy.capitalize()}` imputation.",
            "- **Training-Only Fit Provenance:** Imputation parameters were fitted exclusively on the Monday training",
            "  partition. Validation and test sets are imputed using these stored parameters with zero leakage.",
            "",
            "## 2. Partition Cleaning Summary",
            "",
            "| Partition | Infinities Converted to NaN | Missing Values Imputed |",
            "| :--- | :--- | :--- |",
        ]

        for p_name in ["train", "validation", "test"]:
            aud = self.audits.get(p_name, ImputationAudit(partition_name=p_name))
            lines.append(
                f"| `{p_name}` | {aud.total_infinities_converted:,} | {aud.total_missing_imputed:,} |"
            )

        lines.extend(
            [
                "",
                "## 3. Fitted Training Imputation Parameters (Sample Features)",
                "",
                "| Feature | Training Median Value | Constant in Training? |",
                "| :--- | :--- | :--- |",
            ]
        )

        for col, val in list(self.statistics_.items())[:25]:
            is_const = "YES (Zero Variance)" if col in self.constant_columns_in_training else "No"
            lines.append(f"| `{col}` | `{val:.6f}` | {is_const} |")

        if self.constant_columns_in_training:
            lines.extend(
                [
                    "",
                    f"### Constant Features in Monday Training ({len(self.constant_columns_in_training)} Features)",
                    "These features have zero variance in Monday benign traffic:",
                ]
            )
            for const_col in self.constant_columns_in_training:
                lines.append(f"- `{const_col}`")

        return "\n".join(lines)
