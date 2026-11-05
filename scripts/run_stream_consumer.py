#!/usr/bin/env python3
"""NETDEFY — Stream Consumer Worker Daemon (Phase 6).

Continuously consumes events from the broker stream, executes hybrid inference,
and commits offsets with graceful shutdown handling.
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from types import FrameType

from netdefy.api.dependencies import get_consumer
from netdefy.utils.logging import setup_logging

logger = logging.getLogger("netdefy.consumer")


def main() -> None:
    """Run stream consumer worker loop."""
    setup_logging(level="INFO")
    logger.info("Starting NETDEFY Stream Consumer Worker...")

    consumer = get_consumer()
    running = True

    def _handle_shutdown(sig: int, _frame: FrameType | None) -> None:
        nonlocal running
        logger.info("Received signal %d; initiating graceful shutdown...", sig)
        running = False

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    logger.info("Stream Consumer Worker listening on group '%s'...", consumer.group)
    idle_count = 0

    while running:
        try:
            processed = consumer.consume_batch(count=32, block_ms=500)
            if processed > 0:
                idle_count = 0
            else:
                idle_count += 1
                if idle_count % 60 == 0:
                    summary = consumer.metrics.get_summary()
                    logger.info(
                        "Worker heartbeat: processed=%d, alerts=%d, rss=%.1fMB",
                        summary["counters"]["events_processed"],
                        summary["counters"]["alerts_generated"],
                        summary["rss_memory_mb"],
                    )
        except Exception as e:
            logger.error("Unexpected error in consumer loop: %s", e)
            time.sleep(1.0)

    logger.info("Stream Consumer Worker stopped cleanly.")
    sys.exit(0)


if __name__ == "__main__":
    main()
