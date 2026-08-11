"""Fetch per-artist listener counts and tags from Last.fm. Resumable: only
names absent from the store are requested, and the store is written
periodically so an interrupted run keeps its progress."""

import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from artist_meta import load_meta, save_meta  # noqa: E402

API_URL = "https://ws.audioscrobbler.com/2.0/"
REQUESTS_PER_SECOND = 5.0

_SLASHES = re.compile(r"[/\\]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_for_lookup(name: str) -> str:
    """Last.fm rejects some literal separator characters in artist names."""
    return _WHITESPACE.sub(" ", _SLASHES.sub(" ", name)).strip()


def parse_artist_info(payload: dict) -> dict:
    artist = payload.get("artist")
    if not artist:
        return {"missing": True}
    stats = artist.get("stats", {}) or {}
    tags = (artist.get("tags", {}) or {}).get("tag", []) or []
    return {
        "lastfm_name": artist.get("name"),
        "listeners": int(stats.get("listeners", 0) or 0),
        "playcount": int(stats.get("playcount", 0) or 0),
        "tags": [t["name"].lower() for t in tags],
    }


class _Throttle:
    def __init__(self, per_second: float):
        self._interval = 1.0 / per_second
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self):
        with self._lock:
            delay = self._last + self._interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._last = time.monotonic()


def fetch_missing(names, api_key: str, save_every: int = 100) -> dict:
    meta = load_meta()
    todo = sorted({n for n in names if n not in meta})
    if not todo:
        return meta

    throttle = _Throttle(REQUESTS_PER_SECOND)

    def one(name):
        throttle.wait()
        try:
            response = requests.get(
                API_URL,
                params={
                    "method": "artist.getinfo",
                    "artist": normalize_for_lookup(name),
                    "api_key": api_key,
                    "format": "json",
                    "autocorrect": 1,
                },
                timeout=15,
            )
            return name, parse_artist_info(response.json())
        except Exception as exc:
            return name, {"error": str(exc)[:120]}

    done = 0
    with ThreadPoolExecutor(max_workers=5) as pool:
        for name, entry in pool.map(one, todo):
            meta[name] = entry
            done += 1
            if done % save_every == 0:
                save_meta(meta)
                print(f"  {done}/{len(todo)}", flush=True)

    save_meta(meta)
    return meta
