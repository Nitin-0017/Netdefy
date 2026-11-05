"""NETDEFY — Event Deduplication Engine (Phase 6).

Implements bounded LRU cache with TTL expiration to prevent re-ingestion of
duplicate network events across sliding time windows.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict

logger = logging.getLogger(__name__)


class EventDeduplicator:
    """Thread-safe bounded LRU deduplicator for network event IDs."""

    def __init__(self, capacity: int = 50000, ttl_seconds: float = 3600.0) -> None:
        self.capacity = capacity
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    def is_duplicate(self, event_id: str) -> bool:
        """Check if event_id has been seen recently within TTL."""
        if not event_id:
            return False

        with self._lock:
            now = time.time()
            if event_id in self._cache:
                seen_time = self._cache[event_id]
                if now - seen_time <= self.ttl_seconds:
                    # Refresh LRU position
                    self._cache.move_to_end(event_id)
                    return True
                else:
                    # Expired
                    del self._cache[event_id]
            return False

    def record(self, event_id: str) -> None:
        """Record an event_id into the cache, evicting oldest if capacity reached."""
        if not event_id:
            return

        with self._lock:
            now = time.time()
            if event_id in self._cache:
                self._cache[event_id] = now
                self._cache.move_to_end(event_id)
            else:
                if len(self._cache) >= self.capacity:
                    self._cache.popitem(last=False)
                self._cache[event_id] = now

    def check_and_record(self, event_id: str) -> bool:
        """Atomic check-and-record operation. Returns True if duplicate, False if new."""
        if not event_id:
            return False

        with self._lock:
            now = time.time()
            if event_id in self._cache:
                seen_time = self._cache[event_id]
                if now - seen_time <= self.ttl_seconds:
                    self._cache.move_to_end(event_id)
                    return True
                else:
                    # Expired, overwrite with current time
                    self._cache[event_id] = now
                    self._cache.move_to_end(event_id)
                    return False

            if len(self._cache) >= self.capacity:
                self._cache.popitem(last=False)
            self._cache[event_id] = now
            return False

    def clear(self) -> None:
        """Clear cache state."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Return current cache count."""
        with self._lock:
            return len(self._cache)
