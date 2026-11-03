"""Unit tests for feature schema definition, exclusion rules, and port mapping."""

from __future__ import annotations

from pathlib import Path

from netdefy.preprocessing.schema import (
    FeatureSchema,
    build_feature_schema,
    map_destination_port_to_service,
)


def test_destination_port_service_mapping() -> None:
    """Verify mapping of port numbers to canonical service tiers."""
    assert map_destination_port_to_service(80) == "HTTP"
    assert map_destination_port_to_service(8080) == "HTTP"
    assert map_destination_port_to_service(443) == "HTTPS"
    assert map_destination_port_to_service(21) == "FTP"
    assert map_destination_port_to_service(22) == "SSH"
    assert map_destination_port_to_service(53) == "DNS"
    assert map_destination_port_to_service(25) == "SMTP"
    assert map_destination_port_to_service(123) == "NTP"
    assert map_destination_port_to_service(3306) == "DATABASE"
    assert map_destination_port_to_service(3389) == "RDP"
    assert map_destination_port_to_service(88) == "WELL_KNOWN_OTHER"
    assert map_destination_port_to_service(8000) == "REGISTERED"
    assert map_destination_port_to_service(55000) == "DYNAMIC_EPHEMERAL"
    assert map_destination_port_to_service(-1) == "UNKNOWN"


def test_build_feature_schema_detection() -> None:
    """Verify feature schema construction on headers with whitespace and duplicate columns."""
    sample_headers = [
        " Destination Port",
        " Flow Duration",
        " Total Fwd Packets",
        " Fwd Header Length",
        " Bwd Header Length",
        " Fwd Header Length",  # Duplicate instance
        " Flow Bytes/s",
        " Flow ID",  # Leakage identifier
        " Label",  # Target
    ]

    schema = build_feature_schema(sample_headers)

    assert schema.raw_column_count == 9
    assert schema.unique_column_count == 8
    assert schema.target_column == "Label"
    assert "Fwd Header Length" in schema.duplicate_columns

    # Leakage exclusions
    assert "Label" in schema.excluded_columns
    assert "Flow ID" in schema.excluded_columns
    assert any("duplicate" in k.lower() for k in schema.excluded_columns)

    # Retained features
    assert "Flow Duration" in schema.retained_features_service_independent
    assert "Destination Port" not in schema.retained_features_service_independent
    assert "Destination Port" in schema.retained_features_service_aware
    assert "Flow ID" not in schema.retained_features_service_independent
    assert "Label" not in schema.retained_features_service_independent


def test_feature_schema_save_and_load(tmp_path: Path) -> None:
    """Verify schema JSON serialization and deserialization."""
    schema = FeatureSchema(
        raw_column_count=5,
        cleaned_column_count=5,
        unique_column_count=4,
        target_column="Label",
        duplicate_columns=["DupCol"],
        excluded_columns={"DupCol": "duplicate"},
        retained_features_service_independent=["FeatA", "FeatB"],
        retained_features_service_aware=["FeatA", "FeatB", "Destination Port"],
    )

    out_file = tmp_path / "schema.json"
    schema.save(out_file)
    assert out_file.is_file()

    loaded = FeatureSchema.load(out_file)
    assert loaded.raw_column_count == 5
    assert loaded.retained_features_service_independent == ["FeatA", "FeatB"]

