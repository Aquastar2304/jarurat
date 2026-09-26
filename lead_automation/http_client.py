"""A single, polite HTTP session: identifies itself, retries transient
failures with back-off and sleeps between requests to the same host."""

from __future__ import annotations

import logging
import threading
import time
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)


class PoliteSession(requests.Session):
    def __init__(self, user_agent: str, delay: float = 0.5, timeout: int = 15):
        super().__init__()
        self.headers.update({"User-Agent": user_agent, "Accept-Language": "en"})
        self._delay = delay
        self._timeout = timeout
        self._last_hit: dict[str, float] = {}
        self._lock = threading.Lock()

        retry = Retry(
            total=3,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
        self.mount("https://", adapter)
        self.mount("http://", adapter)

    def _throttle(self, url: str) -> None:
        host = urlsplit(url).netloc
        with self._lock:
            last = self._last_hit.get(host, 0.0)
            wait = self._delay - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
            self._last_hit[host] = time.monotonic()

    def get(self, url: str, **kwargs) -> requests.Response:  # type: ignore[override]
        kwargs.setdefault("timeout", self._timeout)
        self._throttle(url)
        log.debug("GET %s", url)
        return super().get(url, **kwargs)
