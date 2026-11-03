"""Data ingestion, validation, acquisition, manifest, and inspection for NETDEFY."""

from netdefy.data.acquisition import (
    ARCHIVE_NAME,
    OFFICIAL_DATASET_PAGE,
    OFFICIAL_REGISTRATION_URL,
    DatasetAcquisitionStatus,
    compute_sha256,
    get_manual_download_instructions,
    inspect_raw_data_directory,
    safe_extract_zip,
)
from netdefy.data.inspection import (
    DatasetForensicInspector,
    DatasetForensicReport,
    FileForensicReport,
)
from netdefy.data.manifest import (
    DatasetFileEntry,
    DatasetManifest,
    create_manifest_from_directory,
)
from netdefy.data.validation import (
    DatasetValidator,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    validate_dataset,
)

__all__ = [
    "ARCHIVE_NAME",
    "OFFICIAL_DATASET_PAGE",
    "OFFICIAL_REGISTRATION_URL",
    "DatasetAcquisitionStatus",
    "DatasetFileEntry",
    "DatasetForensicInspector",
    "DatasetForensicReport",
    "DatasetManifest",
    "DatasetValidator",
    "FileForensicReport",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    "compute_sha256",
    "create_manifest_from_directory",
    "get_manual_download_instructions",
    "inspect_raw_data_directory",
    "safe_extract_zip",
    "validate_dataset",
]
