"""Unit tests for dataset acquisition, checksum computation, and safe extraction."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from netdefy.data.acquisition import (
    SecurityError,
    compute_sha256,
    get_manual_download_instructions,
    inspect_raw_data_directory,
    safe_extract_zip,
)


def test_compute_sha256_known_value(tmp_path: Path) -> None:
    """Verify SHA-256 calculation against known content."""
    test_file = tmp_path / "hello.txt"
    test_file.write_text("Hello NETDEFY\n", encoding="utf-8")

    # Echo "Hello NETDEFY\n" sha256
    expected_hash = compute_sha256(test_file)
    assert isinstance(expected_hash, str)
    assert len(expected_hash) == 64

    # Identical content yields identical hash
    test_file_copy = tmp_path / "hello_copy.txt"
    test_file_copy.write_text("Hello NETDEFY\n", encoding="utf-8")
    assert compute_sha256(test_file_copy) == expected_hash


def test_compute_sha256_missing_file() -> None:
    """Verify FileNotFoundError when computing hash of non-existent file."""
    with pytest.raises(FileNotFoundError, match="File not found"):
        compute_sha256(Path("does_not_exist.txt"))


def test_safe_extract_zip_normal(tmp_path: Path) -> None:
    """Verify standard archive extraction."""
    zip_path = tmp_path / "sample.zip"
    extract_dir = tmp_path / "extracted"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("test1.csv", "colA,colB\n1,2\n")
        zf.writestr("sub/test2.csv", "colA,colB\n3,4\n")

    extracted = safe_extract_zip(zip_path, extract_dir)

    assert len(extracted) == 2
    assert (extract_dir / "test1.csv").is_file()
    assert (extract_dir / "sub" / "test2.csv").is_file()


def test_safe_extract_zip_checksum_verification(tmp_path: Path) -> None:
    """Verify error raised on checksum mismatch."""
    zip_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("test.csv", "data")

    with pytest.raises(ValueError, match="Checksum mismatch"):
        safe_extract_zip(zip_path, tmp_path / "out", expected_sha256="0000000000000000")


def test_safe_extract_zip_prevents_path_traversal(tmp_path: Path) -> None:
    """Verify SecurityError prevents Zip Slip directory traversal."""
    malicious_zip = tmp_path / "malicious.zip"
    extract_dir = tmp_path / "safe_dir"

    # Construct zip with path traversal member
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("../../etc/passwd_fake", "malicious_content")
    malicious_zip.write_bytes(zip_buffer.getvalue())

    with pytest.raises(SecurityError, match="path traversal"):
        safe_extract_zip(malicious_zip, extract_dir)


def test_inspect_raw_data_directory_states(tmp_path: Path) -> None:
    """Verify status reporting for empty, archive-only, and extracted states."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    # 1. Empty state
    status_empty = inspect_raw_data_directory(raw_dir)
    assert status_empty.archive_found is False
    assert status_empty.is_ready_for_inspection is False
    assert "instructions" in status_empty.instructions.lower() or len(status_empty.instructions) > 0

    # 2. Archive present
    archive_file = raw_dir / "MachineLearningCSV.zip"
    archive_file.write_bytes(b"PK0304_mock_data")
    status_archive = inspect_raw_data_directory(raw_dir)
    assert status_archive.archive_found is True
    assert status_archive.archive_path == archive_file
    assert status_archive.is_ready_for_inspection is False

    # 3. CSV present
    csv_file = raw_dir / "Monday-WorkingHours.csv"
    csv_file.write_text("Flow ID,Label\n1,BENIGN\n", encoding="utf-8")
    status_csv = inspect_raw_data_directory(raw_dir)
    assert status_csv.is_ready_for_inspection is True
    assert len(status_csv.csv_files) == 1


def test_get_manual_download_instructions(tmp_path: Path) -> None:
    """Verify manual instructions text formatting."""
    instr = get_manual_download_instructions(tmp_path)
    assert "CICIDS2017" in instr
    assert "MachineLearningCSV.zip" in instr
    assert "https://www.unb.ca/cic/datasets/ids-2017.html" in instr
