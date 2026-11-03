"""Feature schema management, exclusion rules, and service port mappings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


def map_destination_port_to_service(port: int | float) -> str:
    """Map a destination port number to its canonical service category.

    Args:
        port: Integer or float port number.

    Returns:
        Categorical service label.
    """
    if pd.isna(port) or port < 0:
        return "UNKNOWN"

    p = int(port)
    if p in (80, 8080):
        return "HTTP"
    if p in (443, 8443):
        return "HTTPS"
    if p in (20, 21):
        return "FTP"
    if p == 22:
        return "SSH"
    if p == 53:
        return "DNS"
    if p in (25, 465, 587):
        return "SMTP"
    if p == 123:
        return "NTP"
    if p == 3389:
        return "RDP"
    if p in (3306, 5432, 1521, 1433):
        return "DATABASE"
    if p < 1024:
        return "WELL_KNOWN_OTHER"
    if p <= 49151:
        return "REGISTERED"
    return "DYNAMIC_EPHEMERAL"


@dataclass
class FeatureSchema:
    """Explicit, reproducible feature schema definition."""

    raw_column_count: int
    cleaned_column_count: int
    unique_column_count: int
    target_column: str
    duplicate_columns: list[str]
    excluded_columns: dict[str, str]
    retained_features_service_independent: list[str]
    retained_features_service_aware: list[str]
    feature_dtypes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert schema to dictionary representation."""
        return asdict(self)

    def save(self, destination: Path) -> None:
        """Serialize schema to formatted JSON file.

        Args:
            destination: Path to destination JSON file.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, source: Path) -> FeatureSchema:
        """Load schema from JSON file.

        Args:
            source: Path to schema JSON file.

        Returns:
            Instantiated FeatureSchema.
        """
        with open(source, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


def build_feature_schema(raw_headers: list[str]) -> FeatureSchema:
    """Programmatically construct the leakage-safe feature schema.

    Args:
        raw_headers: Raw column names directly read from the CSV header line.

    Returns:
        FeatureSchema with deterministic feature lists and exclusion reasons.
    """
    raw_col_count = len(raw_headers)
    cleaned_cols = [c.strip() for c in raw_headers]

    # Detect duplicate headers (e.g., Fwd Header Length at indices 34 and 55)
    seen_headers: set[str] = set()
    duplicate_headers: list[str] = []
    for c in cleaned_cols:
        if c in seen_headers and c not in duplicate_headers:
            duplicate_headers.append(c)
        seen_headers.add(c)

    unique_col_count = len(seen_headers)

    # Track exclusions with explicit scientific/engineering justifications
    excluded: dict[str, str] = {
        "Label": "Ground truth target; isolated for evaluation to prevent fatal data leakage.",
    }
    for dup in duplicate_headers:
        excluded[f"{dup} (duplicate instance)"] = (
            "Exact redundant column produced by CICFlowMeter tapping bugs; causes multicollinearity."
        )

    # Identifiers checked for absence
    for ident in [
        "Flow ID",
        "Source IP",
        "Destination IP",
        "Timestamp",
        "Source Port",
        "Fwd Header Length.1",
    ]:
        if ident in cleaned_cols:
            excluded[ident] = (
                f"Excluded to prevent testbed shortcut memorization and temporal leakage ({ident})."
            )

    # Build unique feature candidates preserving original order of first occurrence
    unique_features: list[str] = []
    seen_unique: set[str] = set()
    for col in cleaned_cols:
        if col not in excluded and col not in seen_unique:
            unique_features.append(col)
            seen_unique.add(col)

    # Destination Port handling
    service_independent = [c for c in unique_features if c != "Destination Port"]
    service_aware = list(unique_features)

    return FeatureSchema(
        raw_column_count=raw_col_count,
        cleaned_column_count=len(cleaned_cols),
        unique_column_count=unique_col_count,
        target_column="Label",
        duplicate_columns=duplicate_headers,
        excluded_columns=excluded,
        retained_features_service_independent=service_independent,
        retained_features_service_aware=service_aware,
    )
