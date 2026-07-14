"""Failed-login rate limiting. In-memory sliding window — sufficient for a
single process; swap for a Redis-backed limiter when deployed multi-instance."""
import time
from collections import defaultdict


class FailureLimiter:
    def __init__(self, max_failures: int = 5, window_seconds: int = 300):
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, list[float]] = defaultdict(list)

    def blocked(self, key: str) -> bool:
        now = time.time()
        recent = [t for t in self._failures[key] if now - t < self.window]
        self._failures[key] = recent
        return len(recent) >= self.max_failures

    def record_failure(self, key: str) -> None:
        self._failures[key].append(time.time())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


login_limiter = FailureLimiter()
