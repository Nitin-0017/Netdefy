"""Leakage-safe feature engineering and temporal preprocessing for NETDEFY."""

from netdefy.preprocessing.cleaner import DataCleaner, ImputationAudit
from netdefy.preprocessing.deduplication import DuplicateAuditReport, HashVerifiedDeduplicator
from netdefy.preprocessing.pipeline import (
    PreprocessingRunMetadata,
    TemporalPreprocessingPipeline,
)
from netdefy.preprocessing.scaler import FeatureScaler, ScalerMetadata
from netdefy.preprocessing.schema import (
    FeatureSchema,
    build_feature_schema,
    map_destination_port_to_service,
)

__all__ = [
    "DataCleaner",
    "DuplicateAuditReport",
    "FeatureScaler",
    "FeatureSchema",
    "HashVerifiedDeduplicator",
    "ImputationAudit",
    "PreprocessingRunMetadata",
    "ScalerMetadata",
    "TemporalPreprocessingPipeline",
    "build_feature_schema",
    "map_destination_port_to_service",
]
