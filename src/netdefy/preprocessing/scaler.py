"""Feature scaling utilities with training-only parameter fitting."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ScalerMetadata:
    """Provenance and parameters of a fitted scaler."""

    scaler_type: str
    feature_count: int
    fitted_partition: str
    numeric_precision: str
    epsilon: float
    clipping_applied: bool
    clip_range: tuple[float, float] | None


class FeatureScaler:
    """Configurable scaler (StandardScaler or RobustScaler) enforcing strict train-only fitting."""

    def __init__(
        self,
        scaler_type: Literal["standard", "robust"] = "standard",
        clip_range: tuple[float, float] | None = None,
        epsilon: float = 1e-8,
    ) -> None:
        """Initialize the feature scaler.

        Args:
            scaler_type: 'standard' (z-score) or 'robust' (median/IQR).
            clip_range: Optional tuple (min_val, max_val) for explicit clipping. Default None.
            epsilon: Small constant added to scale to prevent division by zero on zero-variance features.
        """
        self.scaler_type = scaler_type
        self.clip_range = clip_range
        self.epsilon = epsilon

        self.feature_names_in_: list[str] = []
        self.center_: dict[str, float] = {}
        self.scale_: dict[str, float] = {}
        self.is_fitted: bool = False

    def fit(self, train_df: pd.DataFrame, feature_columns: list[str]) -> FeatureScaler:
        """Fit scaling statistics strictly on the training partition.

        Args:
            train_df: DataFrame of training partition flows.
            feature_columns: Columns to fit scaling parameters on.

        Returns:
            Fitted FeatureScaler instance.
        """
        logger.info(
            "Fitting %s on %d features exclusively using the training partition.",
            self.scaler_type,
            len(feature_columns),
        )

        center: dict[str, float] = {}
        scale: dict[str, float] = {}

        for col in feature_columns:
            series = (
                pd.to_numeric(train_df[col], errors="coerce")
                .replace([np.inf, -np.inf], np.nan)
                .dropna()
            )
            if series.empty:
                center[col] = 0.0
                scale[col] = 1.0
                continue

            if self.scaler_type == "standard":
                mean_val = float(series.mean())
                std_val = float(series.std(ddof=1))
                if np.isnan(std_val) or std_val < self.epsilon:
                    std_val = 1.0  # Safe unit scale for zero-variance features
                center[col] = mean_val
                scale[col] = std_val

            elif self.scaler_type == "robust":
                median_val = float(series.median())
                q25 = float(series.quantile(0.25))
                q75 = float(series.quantile(0.75))
                iqr = q75 - q25
                if iqr < self.epsilon:
                    iqr = 1.0
                center[col] = median_val
                scale[col] = iqr
            else:
                raise ValueError(f"Unknown scaler type: {self.scaler_type}")

        self.feature_names_in_ = list(feature_columns)
        self.center_ = center
        self.scale_ = scale
        self.is_fitted = True

        logger.info(
            "Successfully fitted %s on %d features.", self.scaler_type, len(feature_columns)
        )
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform a DataFrame using the stored frozen parameters.

        Args:
            df: DataFrame to transform.

        Returns:
            Transformed DataFrame cast to np.float32.

        Raises:
            RuntimeError: If transform is called prior to fit.
        """
        if not self.is_fitted:
            raise RuntimeError(
                "FeatureScaler must be fitted on training data before calling transform."
            )

        out_df = pd.DataFrame(index=df.index)

        for col in self.feature_names_in_:
            if col not in df.columns:
                out_df[col] = np.zeros(len(df), dtype=np.float32)
                continue

            series = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            c = self.center_.get(col, 0.0)
            s = self.scale_.get(col, 1.0)

            z = (series - c) / s

            if self.clip_range is not None:
                min_c, max_c = self.clip_range
                z = z.clip(lower=min_c, upper=max_c)

            out_df[col] = z.astype(np.float32)

        return out_df

    def fit_transform(self, train_df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
        """Fit on training data and return transformed training DataFrame."""
        return self.fit(train_df, feature_columns).transform(train_df)

    def get_metadata(self) -> ScalerMetadata:
        """Retrieve scaler parameters and metadata."""
        return ScalerMetadata(
            scaler_type=self.scaler_type,
            feature_count=len(self.feature_names_in_),
            fitted_partition="train (Monday)",
            numeric_precision="float32",
            epsilon=self.epsilon,
            clipping_applied=self.clip_range is not None,
            clip_range=self.clip_range,
        )

    def save(self, destination: Path) -> None:
        """Save fitted scaler artifact to joblib file.

        Args:
            destination: Path to output joblib file.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, destination)
        logger.info("Saved %s artifact to %s", self.scaler_type, destination)

    @classmethod
    def load(cls, source: Path) -> FeatureScaler:
        """Load fitted scaler artifact from joblib file.

        Args:
            source: Path to joblib file.

        Returns:
            Loaded FeatureScaler instance.
        """
        instance = joblib.load(source)
        if not isinstance(instance, cls):
            raise TypeError(f"Loaded object is not a FeatureScaler, got {type(instance)}")
        return instance
