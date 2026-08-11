"""Fetch first-release years from MusicBrainz. Strictly serial: MusicBrainz
allows one request per second and requires an identifying User-Agent."""

import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from artist_meta import DATA_DIR  # noqa: E402

YEARS_PATH = DATA_DIR / "track_years.json"
API_URL = "https://musicbrainz.org/ws/2/recording"
USER_AGENT = "youtube-music-mapper/1.0 (https://github.com/willwangfr/youtube-music-mapper)"
SECONDS_PER_REQUEST = 1.0

_YEAR = re.compile(r"^(\d{4})")


def track_key(artist: str, title: str) -> str:
    return f"{artist.strip().lower()}|{title.strip().lower()}"


def parse_year(payload: dict):
    years = []
    for recording in payload.get("recordings", []) or []:
        match = _YEAR.match(str(recording.get("first-release-date", "")))
        if match:
            years.append(int(match.group(1)))
    return min(years) if years else None


def _save(years: dict) -> None:
    """Atomic, so an interrupt cannot leave a half-written store behind."""
    DATA_DIR.mkdir(exist_ok=True)
    tmp = YEARS_PATH.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(years, f)
    tmp.replace(YEARS_PATH)


def fetch_missing(pairs, save_every: int = 50) -> dict:
    years = {}
    if YEARS_PATH.exists():
        try:
            with open(YEARS_PATH) as f:
                years = json.load(f)
        except ValueError:
            print("  track_years.json unreadable; rebuilding", flush=True)

    todo = [(a, t) for a, t in pairs if track_key(a, t) not in years]
    done = 0
    for i, (artist, title) in enumerate(todo):
        if i > 0:
            # No prior request in this run to space against yet.
            time.sleep(SECONDS_PER_REQUEST)
        key = track_key(artist, title)
        try:
            response = requests.get(
                API_URL,
                params={"query": f'artist:"{artist}" AND recording:"{title}"',
                        "fmt": "json", "limit": 5},
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            response.raise_for_status()
            years[key] = parse_year(response.json())
        except Exception as exc:
            # Not recorded, so the next run retries this track.
            print(f"  {artist} - {title}: {str(exc)[:80]}", flush=True)
            continue
        done += 1
        if done % save_every == 0:
            _save(years)
            print(f"  {done}/{len(todo)}", flush=True)

    _save(years)
    return years
