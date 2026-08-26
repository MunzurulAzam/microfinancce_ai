

import threading
import time


class TTLCache:
    """Small thread-safe TTL cache."""

    def __init__(self, ttl, max_entries=256):
        self.ttl = ttl
        self.max_entries = max_entries
        self._data = {}
        self._lock = threading.Lock()

    def get(self, key):
        if self.ttl <= 0:
            return None
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at < time.time():
                del self._data[key]
                return None
            return value

    def set(self, key, value):
        if self.ttl <= 0:
            return
        with self._lock:
            if len(self._data) >= self.max_entries:
                self._evict_expired()
            if len(self._data) >= self.max_entries:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest]
            self._data[key] = (time.time() + self.ttl, value)

    def clear(self):
        with self._lock:
            self._data.clear()

    def _evict_expired(self):
        now = time.time()
        for key in [k for k, (exp, _) in self._data.items() if exp < now]:
            del self._data[key]
