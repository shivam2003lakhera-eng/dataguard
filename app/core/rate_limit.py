import threading
import time
from collections import deque
from collections.abc import Callable


class LoginRateLimiter:
    """Blocks a key after too many recent failures.

    In-memory, so it only works for a single server process and resets on restart.
    Good enough for a small deployment; use a shared store for several workers.
    """

    def __init__(
        self,
        max_failures: int = 5,
        window_seconds: float = 900,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self.max_keys = max_keys
        self.clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque[float] | None:
        entries = self._failures.get(key)
        if entries is None:
            return None
        while entries and now - entries[0] >= self.window:
            entries.popleft()
        if not entries:
            del self._failures[key]
            return None
        return entries

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            entries = self._recent(key, self.clock())
            return entries is not None and len(entries) >= self.max_failures

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = self.clock()
            entries = self._recent(key, now)
            if entries is None:
                if len(self._failures) >= self.max_keys:
                    self._failures.pop(next(iter(self._failures)))  # drop the oldest key
                entries = self._failures.setdefault(key, deque(maxlen=self.max_failures))
            entries.append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()