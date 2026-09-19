import time
from collections import deque
from collections.abc import Callable

_MAX_KEYS = 10_000


class RateLimiter:
    """Fenêtre glissante en mémoire, par clé arbitraire (IP, adresse e-mail...).

    Suffisant pour un seul replica.
    """

    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> bool:
        now = self._clock()
        if len(self._hits) > _MAX_KEYS:
            self._purge(now)
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True

    def _purge(self, now: float) -> None:
        stale = [k for k, hits in self._hits.items() if not hits or now - hits[-1] >= self._window]
        for key in stale:
            del self._hits[key]
