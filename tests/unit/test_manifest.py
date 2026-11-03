"""Unit tests for dataset manifest creation, serialization, and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from netdefy.data.manifest import (
    DatasetFileEntry,
    DatasetManifest,
    create_manifest_from_directory,
)


def test_dataset_file_entry_serialization() -> None:
    """Verify DatasetFileEntry serialization to dict."""
    entry = DatasetFileEntry(
        filename="Monday.csv",
        relative_path="Monday.csv",
        size_bytes=1024,
        sha256="abc123sha",
        row_count=50,
        column_count=10,
    )
    d = entry.to_dict()
    assert d["filename"] == "Monday.csv"
    assert d["size_bytes"] == 1024
    assert d["row_count"] == 50


def test_manifest_save_and_load_roundtrip(tmp_path: Path) -> None:
    """Verify JSON saving and reloading of manifest preserves all fields."""
    manifest_path = tmp_path / "manifest.json"
    manifest = DatasetManifest(
        dataset_name="CICIDS2017",
        version="1.0.0",
        total_files=1,
        total_size_bytes=2048,
        total_rows=100,
        files=[
            DatasetFileEntry(
                filename="Tuesday.csv",
                relative_path="Tuesday.csv",
                size_bytes=2048,
                sha256="deadbeef" * 8,
                row_count=100,
                column_count=15,
            )
        ],
    )
    manifest.save(manifest_path)
    assert manifest_path.is_file()

    loaded = DatasetManifest.load(manifest_path)
    assert loaded.dataset_name == "CICIDS2017"
    assert loaded.total_files == 1
    assert loaded.total_rows == 100
    assert len(loaded.files) == 1
    assert loaded.files[0].filename == "Tuesday.csv"


def test_manifest_load_non_existent_file() -> None:
    """Verify FileNotFoundError when loading missing manifest."""
    with pytest.raises(FileNotFoundError, match="Manifest not found"):
        DatasetManifest.load(Path("missing_manifest.json"))


def test_manifest_markdown_generation() -> None:
    """Verify markdown report generation for manifest."""
    manifest = DatasetManifest(
        dataset_name="CICIDS2017",
        total_files=1,
        total_size_bytes=1048576,
        total_rows=5000,
        files=[
            DatasetFileEntry(
                filename="Friday.csv",
                relative_path="Friday.csv",
                size_bytes=1048576,
                sha256="1234567890abcdef",
                row_count=5000,
                column_count=20,
            )
        ],
    )
    md = manifest.to_markdown()
    assert "# Dataset Manifest: CICIDS2017" in md
    assert "Friday.csv" in md
    assert "5,000" in md


def test_create_manifest_from_directory(tmp_path: Path) -> None:
    """Verify scanning directory with real CSV files creates valid manifest."""
    csv1 = tmp_path / "File1.csv"
    csv1.write_text("a,b\n1,2\n", encoding="utf-8")
    csv2 = tmp_path / "File2.csv"
    csv2.write_text("c,d\n3,4\n5,6\n", encoding="utf-8")

    manifest = create_manifest_from_directory(tmp_path)
    assert manifest.total_files == 2
    assert len(manifest.files) == 2
    filenames = {f.filename for f in manifest.files}
    assert filenames == {"File1.csv", "File2.csv"}

    # Test integrity verification
    integrity = manifest.verify_integrity(tmp_path)
    assert integrity["File1.csv"] is True
    assert integrity["File2.csv"] is True
