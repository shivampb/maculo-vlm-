"""In-memory stores: uploaded images with their SAM embeddings, and a rate limiter.

Nothing here touches disk. Images live only until they expire, are evicted,
or the client deletes them.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any

from PIL import Image


@dataclass
class ImageSession:
    image: Image.Image
    embedding: Any  # engine-specific; opaque to the API layer
    created: float = field(default_factory=time.monotonic)
    touched: float = field(default_factory=time.monotonic)


class ImageStore:
    """A thread-safe LRU of image sessions with an idle timeout."""

    def __init__(self, capacity: int, ttl_s: float, clock=time.monotonic):
        self.capacity = capacity
        self.ttl_s = ttl_s
        self._clock = clock
        self._items: OrderedDict[str, ImageSession] = OrderedDict()
        self._lock = threading.Lock()

    def put(self, session: ImageSession) -> str:
        key = secrets.token_urlsafe(16)
        with self._lock:
            self._sweep()
            session.touched = self._clock()
            self._items[key] = session
            while len(self._items) > self.capacity:
                self._items.popitem(last=False)
        return key

    def get(self, key: str) -> ImageSession | None:
        with self._lock:
            self._sweep()
            s = self._items.get(key)
            if s is not None:
                s.touched = self._clock()
                self._items.move_to_end(key)
            return s

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._items.pop(key, None) is not None

    def __len__(self) -> int:
        with self._lock:
            self._sweep()
            return len(self._items)

    def _sweep(self) -> None:
        cutoff = self._clock() - self.ttl_s
        for key in [k for k, s in self._items.items() if s.touched < cutoff]:
            del self._items[key]


class RateLimiter:
    """Sliding-window limit of N events per minute per key (usually client IP)."""

    def __init__(self, per_minute: int, clock=time.monotonic):
        self.per_minute = per_minute
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.per_minute <= 0:
            return True
        now = self._clock()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= now - 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            if len(self._hits) > 10_000:  # forget idle clients
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return True
