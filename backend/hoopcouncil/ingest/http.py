"""Polite HTTP fetching with an on-disk raw cache.

* Every response is cached under data/raw/<host>/<sha1>.{body,meta.json} so the
  pipeline can be re-run (and re-parsed) without touching the network again.
* Requests to each host are spaced by a minimum interval (rate limit).
* robots.txt is honoured.
* A 429 from a site stops ingestion for that host instead of hammering it.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.robotparser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .. import config

log = logging.getLogger(__name__)


class RateLimitedError(RuntimeError):
    """Raised when a host answers 429; the caller should stop and retry much later."""


class FetchError(RuntimeError):
    pass


@dataclass
class FetchResult:
    url: str
    status: int
    text: str
    retrieved_at: str  # ISO-8601 UTC
    from_cache: bool


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class PoliteFetcher:
    def __init__(
        self,
        cache_dir: Path | None = None,
        min_interval_s: float = 3.5,
        user_agent: str | None = None,
        extra_headers: dict | None = None,
        respect_robots: bool = True,
        offline: bool = False,
        refresh: bool = False,
        timeout_s: float = 30.0,
    ):
        self.cache_dir = Path(cache_dir or config.RAW_CACHE_DIR)
        self.min_interval_s = min_interval_s
        self.user_agent = user_agent or config.USER_AGENT
        self.extra_headers = extra_headers or {}
        self.respect_robots = respect_robots
        self.offline = offline        # only serve from cache
        self.refresh = refresh        # ignore cache and re-download
        self.timeout_s = timeout_s
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._blocked_hosts: set[str] = set()
        self._session = None

    # -- cache ---------------------------------------------------------------
    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        host = urlparse(url).netloc or "local"
        h = hashlib.sha1(url.encode()).hexdigest()
        d = self.cache_dir / host
        return d / f"{h}.body", d / f"{h}.meta.json"

    def cached(self, url: str) -> FetchResult | None:
        body, meta = self._cache_paths(url)
        if body.exists() and meta.exists():
            m = json.loads(meta.read_text())
            return FetchResult(url=url, status=m["status"], text=body.read_text(encoding="utf-8"),
                               retrieved_at=m["retrieved_at"], from_cache=True)
        return None

    def _store(self, res: FetchResult) -> None:
        body, meta = self._cache_paths(res.url)
        body.parent.mkdir(parents=True, exist_ok=True)
        body.write_text(res.text, encoding="utf-8")
        meta.write_text(json.dumps({"url": res.url, "status": res.status, "retrieved_at": res.retrieved_at}))

    # -- network -------------------------------------------------------------
    def _get_session(self):
        if self._session is None:
            import requests  # local import keeps parsing code importable without requests

            s = requests.Session()
            s.headers.update({"User-Agent": self.user_agent, "Accept-Language": "en-US,en;q=0.9"})
            s.headers.update(self.extra_headers)
            self._session = s
        return self._session

    def _allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        p = urlparse(url)
        root = f"{p.scheme}://{p.netloc}"
        if root not in self._robots:
            robots_url = root + "/robots.txt"
            res = self.cached(robots_url)  # robots.txt is cached too, so offline re-runs make the same decisions
            if res is None and not self.offline:
                try:
                    r = self._get_session().get(robots_url, timeout=self.timeout_s)
                    res = FetchResult(url=robots_url, status=r.status_code, text=r.text, retrieved_at=utcnow_iso(), from_cache=False)
                    if r.status_code in (200, 404):
                        self._store(res)
                except Exception as e:  # network trouble: proceed, rate limits still apply
                    log.warning("robots.txt unavailable for %s (%s); proceeding cautiously", root, e)
            if res is not None and res.status == 200:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(res.text.splitlines())
                self._robots[root] = rp
            else:
                self._robots[root] = None
        rp = self._robots[root]
        return True if rp is None else rp.can_fetch(self.user_agent, url)

    def allowed(self, url: str) -> bool:
        """Public robots.txt check (cached per host). Offline mode never blocks cached pages."""
        return self._allowed(url)

    def _wait(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            delta = time.monotonic() - last
            if delta < self.min_interval_s:
                time.sleep(self.min_interval_s - delta)
        self._last_request[host] = time.monotonic()

    def get(self, url: str, params: dict | None = None, allow_404: bool = True) -> FetchResult | None:
        """Fetch a URL (cache first). Returns None for 404 when allow_404."""
        key_url = url
        if params:
            from urllib.parse import urlencode

            key_url = f"{url}?{urlencode(params)}"
        if not self.refresh:
            c = self.cached(key_url)
            if c is not None:
                return None if (c.status == 404 and allow_404) else c
        if self.offline:
            log.info("offline mode: no cache for %s", key_url)
            return None
        host = urlparse(url).netloc
        if host in self._blocked_hosts:
            raise RateLimitedError(f"{host} previously rate-limited this run; stopping")
        if not self._allowed(key_url):
            log.warning("robots.txt disallows %s; skipping", key_url)
            return None
        self._wait(host)
        log.info("GET %s", key_url)
        try:
            r = self._get_session().get(url, params=params, timeout=self.timeout_s)
        except Exception as e:
            raise FetchError(f"{key_url}: {e}") from e
        if r.status_code == 429:
            self._blocked_hosts.add(host)
            raise RateLimitedError(
                f"{host} returned 429 Too Many Requests. Stop and retry later (Sports Reference "
                f"blocks for about an hour). Cached pages are kept, so a re-run resumes."
            )
        r.encoding = r.encoding or "utf-8"
        res = FetchResult(url=key_url, status=r.status_code, text=r.text, retrieved_at=utcnow_iso(), from_cache=False)
        if r.status_code in (200, 404):
            self._store(res)
        if r.status_code == 404 and allow_404:
            return None
        if r.status_code != 200:
            raise FetchError(f"{key_url}: HTTP {r.status_code}")
        return res
