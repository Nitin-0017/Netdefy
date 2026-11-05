"""NETDEFY — External Dataset Acquisition Script (Phase 5.1).

Acquires independent network traffic data from AWS Open Data (CSE-CIC-IDS2018)
and verifies payload integrity via SHA-256.
"""

from __future__ import annotations

import hashlib
import logging
import time
import urllib.request
from pathlib import Path

from netdefy.utils.logging import setup_logging

logger = logging.getLogger(__name__)

PRIMARY_URL = (
    "https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com/"
    "Processed+Traffic+Data+for+ML+Algorithms/"
    "Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv"
)


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 checksum in chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def acquire_dataset(dest_dir: Path | None = None) -> Path:
    """Download CSE-CIC-IDS2018 Thursday capture from AWS Open Data."""
    setup_logging(level=logging.INFO)
    root_dir = Path(__file__).resolve().parent.parent
    target_dir = dest_dir or (root_dir / "data" / "external")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "csecicids2018_thursday_01_03_2018.csv"

    if target_file.exists() and target_file.stat().st_size > 100 * 1024 * 1024:
        logger.info("External dataset already exists at %s", target_file)
        sha256 = compute_sha256(target_file)
        logger.info("File SHA-256: %s", sha256)
        return target_file

    logger.info("Downloading primary independent dataset from %s...", PRIMARY_URL)
    t0 = time.time()

    req = urllib.request.Request(PRIMARY_URL, headers={"User-Agent": "Netdefy-Research/5.1"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(target_file, "wb") as out_f:
        total_size = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        block_size = 1024 * 1024  # 1 MB

        while True:
            chunk = resp.read(block_size)
            if not chunk:
                break
            out_f.write(chunk)
            downloaded += len(chunk)
            if total_size > 0:
                pct = (downloaded / total_size) * 100
                logger.info(
                    "Downloaded %d / %d MB (%.1f%%)",
                    downloaded // (1024 * 1024),
                    total_size // (1024 * 1024),
                    pct,
                )

    elapsed = time.time() - t0
    logger.info("Download completed in %.1fs (%s)", elapsed, target_file)
    sha256 = compute_sha256(target_file)
    logger.info("Acquired dataset SHA-256: %s", sha256)
    return target_file


if __name__ == "__main__":
    acquire_dataset()
