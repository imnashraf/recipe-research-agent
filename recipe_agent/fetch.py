"""Page fetching: live HTTP first, then a pinned public snapshot of the same URL.

Snapshots are the recipe pages captured by the open-source recipe-scrapers project
(https://github.com/hhursev/recipe-scrapers, tests/test_data), pinned to one commit so a
re-run sees identical bytes. They are downloaded on first use into .cache/pages/ and never
committed, because the raw pages contain commenter names.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import CACHE_DIR, DATA_DIR

SNAPSHOT_INDEX = DATA_DIR / "snapshot_index.json"
USER_AGENT = "recipe-research-agent/1.0 (+course project; polite single-page fetch)"


class FetchError(Exception):
    pass


@dataclass
class FetchedPage:
    html: str
    source: str  # "live" | "snapshot"
    fetched_url: str
    sha256: str


def _load_index() -> dict:
    data = json.loads(SNAPSHOT_INDEX.read_text())
    base = data["mirror_base"].rstrip("/")
    return {url: f"{base}/{path}" for url, path in data["pages"].items()}


class PageFetcher:
    """mode: "auto" (live, then snapshot), "live" or "snapshot"."""

    def __init__(self, mode: str = "auto", cache_dir: Path = CACHE_DIR / "pages", timeout: float = 15.0):
        self.mode = mode
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.index = _load_index()
        self.live_attempts: list[tuple[str, str]] = []  # (url, outcome) for the run log

    def _get(self, url: str) -> str:
        with httpx.Client(follow_redirects=True, timeout=self.timeout, headers={"User-Agent": USER_AGENT}) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.text

    def _snapshot(self, url: str) -> FetchedPage:
        mirror = self.index.get(url) or self.index.get(url.rstrip("/") + "/")
        if not mirror:
            raise FetchError(f"no snapshot pinned for {url}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached = self.cache_dir / (hashlib.sha256(mirror.encode()).hexdigest()[:24] + ".html")
        if cached.exists():
            html = cached.read_text(encoding="utf-8")
        else:
            try:
                html = self._get(mirror)
            except httpx.HTTPError as e:
                raise FetchError(f"snapshot download failed: {type(e).__name__}") from e
            cached.write_text(html, encoding="utf-8")
        return FetchedPage(html, "snapshot", mirror, hashlib.sha256(html.encode()).hexdigest())

    def fetch(self, url: str) -> FetchedPage:
        if self.mode in ("auto", "live"):
            try:
                html = self._get(url)
                self.live_attempts.append((url, "ok"))
                return FetchedPage(html, "live", url, hashlib.sha256(html.encode()).hexdigest())
            except httpx.HTTPError as e:
                self.live_attempts.append((url, type(e).__name__))
                if self.mode == "live":
                    raise FetchError(f"live fetch failed: {type(e).__name__}") from e
        return self._snapshot(url)
