"""Unit tests for structured logging initialization and routing."""

from __future__ import annotations

import io
from pathlib import Path

from netdefy.utils.logging import setup_logging


def test_setup_logging_console_stream() -> None:
    """Verify console stream capture and log format."""
    stream = io.StringIO()
    logger = setup_logging(level="DEBUG", stream=stream)

    test_message = "Test diagnostic log message"
    logger.info(test_message)

    output = stream.getvalue()
    assert test_message in output
    assert "INFO" in output
    assert "netdefy" in output


def test_setup_logging_to_file(tmp_path: Path) -> None:
    """Verify file-based logging."""
    log_file = tmp_path / "test_run.log"
    logger = setup_logging(level="INFO", log_to_file=True, log_file_path=log_file)

    msg = "Persistent file test message"
    logger.warning(msg)

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert msg in content
    assert "WARNING" in content


def test_setup_logging_idempotent_handlers() -> None:
    """Verify that multiple setup_logging calls do not duplicate log handlers."""
    setup_logging(level="INFO")
    setup_logging(level="DEBUG")
    logger = setup_logging(level="INFO")

    # Should only have 1 handler (console)
    assert len(logger.handlers) == 1
