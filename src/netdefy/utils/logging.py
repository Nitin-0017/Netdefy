"""Structured logging configuration for NETDEFY."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TextIO

DEFAULT_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
)
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: str | int = "INFO",
    log_format: str = DEFAULT_LOG_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
    log_to_file: bool = False,
    log_file_path: Path | str | None = None,
    stream: TextIO | None = None,
    capture_warnings: bool = True,
) -> logging.Logger:
    """Initialize structured logging across the application.

    Args:
        level: Log level name (e.g. 'DEBUG', 'INFO', 'WARNING') or numeric level.
        log_format: Format string for log messages.
        date_format: Format string for timestamps.
        log_to_file: If True, writes logs to a file in addition to the console stream.
        log_file_path: Destination path for file logging.
        stream: Output stream for console logging (defaults to sys.stderr).
        capture_warnings: Whether to route Python warnings through the logging system.

    Returns:
        The configured 'netdefy' root logger.
    """
    if isinstance(level, str):
        numeric_level = getattr(logging, level.upper(), logging.INFO)
    else:
        numeric_level = level

    logger = logging.getLogger("netdefy")
    logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplication on re-initialization
    logger.handlers.clear()

    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    # Console stream handler
    console_handler = logging.StreamHandler(stream or sys.stderr)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optional file handler
    if log_to_file and log_file_path:
        file_path = Path(log_file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent logs from propagating to root logger and causing double printing
    logger.propagate = False

    logging.captureWarnings(capture_warnings)

    return logger
