"""Dataset manifest generation, serialization, and integrity verification."""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from netdefy.data.acquisition import compute_sha256

logger = logging.getLogger(__name__)


@dataclass
class DatasetFileEntry:
    """Metadata entry for an individual raw dataset file."""

    filename: str
    relative_path: str
    size_bytes: int
    sha256: str
    row_count: int | None = None
    column_count: int | None = None
    last_modified: str = ""
    download_source: str = "UNB Official CICIDS2017"
    status: str = "verified"

    def to_dict(self) -> dict[str, Any]:
        """Serialize file entry to dictionary."""
        return asdict(self)


@dataclass
class DatasetManifest:
    """Master manifest detailing all files in the raw dataset."""

    dataset_name: str = "CICIDS2017"
    version: str = "1.0.0"
    generated_at: str = field(default_factory=lambda: dt.datetime.now(dt.UTC).isoformat())
    total_files: int = 0
    total_size_bytes: int = 0
    total_rows: int | None = None
    files: list[DatasetFileEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize manifest to dictionary."""
        return {
            "dataset_name": self.dataset_name,
            "version": self.version,
            "generated_at": self.generated_at,
            "total_files": self.total_files,
            "total_size_bytes": self.total_size_bytes,
            "total_rows": self.total_rows,
            "files": [f.to_dict() for f in self.files],
        }

    def save(self, destination: Path) -> None:
        """Save manifest to formatted JSON file.

        Args:
            destination: Path to manifest JSON output.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Saved dataset manifest to %s", destination)

    @classmethod
    def load(cls, manifest_path: Path) -> DatasetManifest:
        """Load manifest from JSON file.

        Args:
            manifest_path: Path to manifest JSON.

        Returns:
            Populated DatasetManifest instance.
        """
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)

        files = [DatasetFileEntry(**item) for item in data.get("files", [])]
        return cls(
            dataset_name=data.get("dataset_name", "CICIDS2017"),
            version=data.get("version", "1.0.0"),
            generated_at=data.get("generated_at", ""),
            total_files=data.get("total_files", len(files)),
            total_size_bytes=data.get("total_size_bytes", 0),
            total_rows=data.get("total_rows"),
            files=files,
        )

    def to_markdown(self) -> str:
        """Format manifest into a structured Markdown report."""
        lines = [
            f"# Dataset Manifest: {self.dataset_name} (v{self.version})",
            "",
            f"- **Generated At:** {self.generated_at}",
            f"- **Total Files:** {self.total_files}",
            f"- **Total Size:** {self.total_size_bytes / (1024**2):.2f} MB ({self.total_size_bytes:,} bytes)",
        ]
        if self.total_rows is not None:
            lines.append(f"- **Total Rows:** {self.total_rows:,}")
        lines.extend(
            [
                "",
                "## Manifest File Entries",
                "",
                "| Filename | Size (MB) | Rows | Columns | SHA-256 Checksum | Status |",
                "| :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
        )

        for f in self.files:
            size_mb = f.size_bytes / (1024**2)
            rows_str = f"{f.row_count:,}" if f.row_count is not None else "N/A"
            cols_str = str(f.column_count) if f.column_count is not None else "N/A"
            short_sha = f"{f.sha256[:12]}..." if len(f.sha256) > 16 else f.sha256
            lines.append(
                f"| `{f.filename}` | {size_mb:.2f} | {rows_str} | {cols_str} | `{short_sha}` | {f.status} |"
            )

        return "\n".join(lines)

    def verify_integrity(self, base_dir: Path) -> dict[str, bool]:
        """Verify the integrity of existing files against their manifest SHA-256 hashes.

        Args:
            base_dir: Directory containing the files referenced by relative_path.

        Returns:
            Dictionary mapping filename to integrity pass (True) or fail (False).
        """
        results: dict[str, bool] = {}
        for entry in self.files:
            target_path = base_dir / entry.relative_path
            if not target_path.is_file():
                results[entry.filename] = False
                continue
            current_sha = compute_sha256(target_path)
            results[entry.filename] = current_sha.lower() == entry.sha256.lower()
        return results


def create_manifest_from_directory(
    raw_dir: Path,
    dataset_name: str = "CICIDS2017",
    source_label: str = "UNB Official CICIDS2017",
) -> DatasetManifest:
    """Scan raw_dir and generate an initial manifest with SHA-256 checksums.

    Args:
        raw_dir: Directory containing raw dataset files.
        dataset_name: Canonical dataset name.
        source_label: Attribution source label.

    Returns:
        Populated DatasetManifest instance.
    """
    csv_files = sorted(
        [p for p in raw_dir.rglob("*.csv") if not p.name.startswith(".")],
        key=lambda p: p.name,
    )
    entries: list[DatasetFileEntry] = []
    total_size = 0

    for path in csv_files:
        size = path.stat().st_size
        total_size += size
        mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.UTC).isoformat()
        sha = compute_sha256(path)
        rel_path = str(path.relative_to(raw_dir))

        entries.append(
            DatasetFileEntry(
                filename=path.name,
                relative_path=rel_path,
                size_bytes=size,
                sha256=sha,
                last_modified=mtime,
                download_source=source_label,
                status="registered",
            )
        )

    return DatasetManifest(
        dataset_name=dataset_name,
        generated_at=dt.datetime.now(dt.UTC).isoformat(),
        total_files=len(entries),
        total_size_bytes=total_size,
        files=entries,
    )
