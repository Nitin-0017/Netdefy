"""Dataset acquisition, integrity verification, and secure extraction utilities."""

from __future__ import annotations

import hashlib
import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

OFFICIAL_DATASET_PAGE = "https://www.unb.ca/cic/datasets/ids-2017.html"
OFFICIAL_REGISTRATION_URL = "http://cicresearch.ca/CICDataset/CIC-IDS-2017/"
ARCHIVE_NAME = "MachineLearningCSV.zip"


class SecurityError(Exception):
    """Raised when an insecure archive path or unsafe operation is detected."""


@dataclass(frozen=True)
class DatasetAcquisitionStatus:
    """Summary of raw dataset files, archives, and readiness for inspection."""

    archive_found: bool
    archive_path: Path | None
    archive_size_bytes: int
    archive_sha256: str | None
    csv_files: list[Path] = field(default_factory=list)
    total_csv_size_bytes: int = 0
    is_ready_for_inspection: bool = False
    instructions: str = ""

    def summary(self) -> str:
        """Human-readable status summary."""
        if self.is_ready_for_inspection:
            return (
                f"Dataset Ready: {len(self.csv_files)} CSV files found "
                f"({self.total_csv_size_bytes / (1024**2):.1f} MB)."
            )
        if self.archive_found:
            return (
                f"Archive Found: {self.archive_path.name if self.archive_path else 'Unknown'} "
                f"({self.archive_size_bytes / (1024**2):.1f} MB) — extraction required."
            )
        return "Dataset Missing: MachineLearningCSV.zip not found in raw directory."


def compute_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Compute the SHA-256 checksum of a file using streaming reads.

    Args:
        file_path: Absolute or relative path to file.
        chunk_size: Byte chunk size for reading (default: 64 KiB).

    Returns:
        Hexadecimal SHA-256 string.

    Raises:
        FileNotFoundError: If file_path does not exist.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found for checksum computation: {file_path}")

    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def safe_extract_zip(
    zip_path: Path,
    extract_to: Path,
    expected_sha256: str | None = None,
) -> list[Path]:
    """Safely extract a ZIP archive while enforcing path traversal (Zip Slip) security.

    Args:
        zip_path: Path to ZIP archive.
        extract_to: Destination directory.
        expected_sha256: Optional expected SHA-256 hash to verify prior to extraction.

    Returns:
        List of paths to extracted files.

    Raises:
        FileNotFoundError: If zip_path does not exist.
        ValueError: If SHA-256 checksum does not match expected_sha256.
        SecurityError: If any archive member contains a path traversal attempt.
    """
    if not zip_path.is_file():
        raise FileNotFoundError(f"ZIP archive not found: {zip_path}")

    if expected_sha256 is not None:
        actual_sha256 = compute_sha256(zip_path)
        if actual_sha256.lower() != expected_sha256.lower():
            raise ValueError(
                f"Checksum mismatch for {zip_path.name}: expected {expected_sha256}, got {actual_sha256}"
            )

    extract_to_resolved = extract_to.resolve()
    extract_to_resolved.mkdir(parents=True, exist_ok=True)
    extracted_paths: list[Path] = []

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            # Validate against directory traversal (Zip Slip)
            target_path = (extract_to_resolved / member.filename).resolve()
            try:
                target_path.relative_to(extract_to_resolved)
            except ValueError as exc:
                raise SecurityError(
                    f"Attempted path traversal in ZIP member: {member.filename}"
                ) from exc

            # Skip directory entries itself
            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as src, open(target_path, "wb") as dst:
                while chunk := src.read(65536):
                    dst.write(chunk)
            extracted_paths.append(target_path)

    logger.info(
        "Extracted %d files from %s to %s",
        len(extracted_paths),
        zip_path.name,
        extract_to_resolved,
    )
    return extracted_paths


def get_manual_download_instructions(destination_dir: Path) -> str:
    """Generate clear, step-by-step instructions for manual dataset acquisition.

    Args:
        destination_dir: Target directory for storing downloaded archives.

    Returns:
        Formatted instruction string.
    """
    dest_str = str(destination_dir.resolve())
    return (
        "================================================================================\n"
        "             CICIDS2017 DATASET ACQUISITION INSTRUCTIONS                        \n"
        "================================================================================\n\n"
        "The Canadian Institute for Cybersecurity (UNB) requires registration before\n"
        "granting access to the CICIDS2017 dataset. Direct unauthenticated downloads are\n"
        "prohibited (HTTP 403 Forbidden).\n\n"
        "STEPS TO ACQUIRE THE DATASET:\n"
        "1. Open your web browser and visit the official UNB dataset portal:\n"
        f"   {OFFICIAL_DATASET_PAGE}\n\n"
        "2. Click 'Download this dataset' or navigate directly to the registration form:\n"
        f"   {OFFICIAL_REGISTRATION_URL}\n\n"
        "3. Complete the registration form with your Name, Email, Organization, and Country.\n\n"
        "4. On the subsequent file listing page, download:\n"
        "   --> MachineLearningCSV.zip (~225 MB compressed, ~2.8 GB uncompressed)\n\n"
        "5. Place the downloaded archive into the project directory:\n"
        f"   {dest_str}/{ARCHIVE_NAME}\n\n"
        "6. Run the acquisition verification utility:\n"
        "   python scripts/acquire_dataset.py\n"
        "================================================================================\n"
    )


def inspect_raw_data_directory(raw_dir: Path) -> DatasetAcquisitionStatus:
    """Scan the raw data directory for archives and extracted CSV files.

    Args:
        raw_dir: Path to data/raw/ directory.

    Returns:
        Populated DatasetAcquisitionStatus instance.
    """
    if not raw_dir.exists():
        raw_dir.mkdir(parents=True, exist_ok=True)

    # Search for ZIP archive
    zip_candidates = list(raw_dir.glob("*.zip"))
    archive_path: Path | None = None
    archive_size = 0
    archive_sha256: str | None = None

    for candidate in zip_candidates:
        if "machinelearning" in candidate.name.lower() or candidate.name == ARCHIVE_NAME:
            archive_path = candidate
            archive_size = candidate.stat().st_size
            break
    if archive_path is None and zip_candidates:
        archive_path = zip_candidates[0]
        archive_size = archive_path.stat().st_size

    if archive_path is not None:
        try:
            archive_sha256 = compute_sha256(archive_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not compute checksum for %s: %s", archive_path, exc)

    # Search for CSV files (including subdirectories like MachineLearningCSV/)
    csv_files = sorted(
        [p for p in raw_dir.rglob("*.csv") if not p.name.startswith(".")],
        key=lambda p: p.name,
    )
    total_csv_size = sum(p.stat().st_size for p in csv_files)
    is_ready = len(csv_files) > 0

    instructions = ""
    if not is_ready and archive_path is None:
        instructions = get_manual_download_instructions(raw_dir)

    return DatasetAcquisitionStatus(
        archive_found=archive_path is not None,
        archive_path=archive_path,
        archive_size_bytes=archive_size,
        archive_sha256=archive_sha256,
        csv_files=csv_files,
        total_csv_size_bytes=total_csv_size,
        is_ready_for_inspection=is_ready,
        instructions=instructions,
    )
