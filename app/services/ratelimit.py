import threading
import time
from typing import Optional


class FixedWindow:
    """Counts requests per key inside a fixed window.

    Fixed window, not a sliding one: it is a few lines, it is easy to reason
    about under pressure, and its one weakness — a burst straddling the window
    edge can briefly double the rate — does not matter for a form endpoint.
    """

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self.counters: dict[str, tuple[float, int]] = {}
        self.lock = threading.Lock()

    def hit(self, key: str) -> Optional[int]:
        """Count one request. Returns seconds to wait if the key is over."""
        now = time.monotonic()
        with self.lock:
            started, count = self.counters.get(key, (now, 0))
            if now - started >= self.window:
                started, count = now, 0
            count += 1
            self.counters[key] = (started, count)
            if count > self.limit:
                return max(1, int(self.window - (now - started)))
        return None

    def sweep(self, now: Optional[float] = None):
        """Drop expired keys so the dict cannot grow forever under attack."""
        now = now or time.monotonic()
        with self.lock:
            expired = [key for key, (started, _) in self.counters.items() if now - started >= self.window]
            for key in expired:
                del self.counters[key]


class RateLimiter:
    """Two limits at once: one per IP, one per widget.

    The per-IP limit stops one machine from flooding. The per-widget limit stops
    a distributed flood from burying a single customer's form — and is the one
    that a botnet with a thousand addresses actually runs into.
    """

    def __init__(self, ip_limit: int, ip_window: int, widget_limit: int, widget_window: int):
        self.by_ip = FixedWindow(ip_limit, ip_window)
        self.by_widget = FixedWindow(widget_limit, widget_window)
        self.requests_since_sweep = 0

    def check(self, ip: str, widget_id: str) -> Optional[tuple[str, int]]:
        """Returns (which limit, retry-after seconds) or None."""
        self.maybe_sweep()
        retry = self.by_ip.hit(ip or "unknown")
        if retry:
            return "ip", retry
        retry = self.by_widget.hit(widget_id)
        if retry:
            return "widget", retry
        return None

    def maybe_sweep(self):
        self.requests_since_sweep += 1
        if self.requests_since_sweep >= 500:
            self.requests_since_sweep = 0
            self.by_ip.sweep()
            self.by_widget.sweep()
