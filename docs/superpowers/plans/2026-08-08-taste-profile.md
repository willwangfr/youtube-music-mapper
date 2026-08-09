# Taste Profile (Spec A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a profile page at `/p/<profile_id>` that leads with a named archetype over real statistics — obscurity, diversity, genres, decades, taste clusters, and badges — computed from a person's music library.

**Architecture:** Artist metadata (listener counts, tags, genre) lives in one shared JSON store rather than being duplicated into each profile, because it is the same for everyone. Pure-function modules compute metrics from (library, artist_meta, track_years, genre_reference); Flask routes are thin wrappers over them. Enrichment fetchers are resumable and write incrementally.

**Tech Stack:** Python 3.11, Flask, networkx, requests, pytest. Vanilla JS + D3 on the frontend. Last.fm and MusicBrainz APIs.

**Spec:** `docs/superpowers/specs/2026-08-08-taste-profile-design.md`

## Global Constraints

- All backend scripts run with `backend/` as the working directory; module imports are flat (`from artist_meta import ...`), matching the existing codebase.
- **Run tests with `/opt/homebrew/bin/pytest`, not `python3 -m pytest`.** The default `python3` is 3.9 from CommandLineTools and has no pytest; `backend/venv` has no pytest either. The only working interpreter with pytest is the mambaforge Python 3.13 at `/opt/homebrew/bin/pytest`. Every test command in the tasks below should be read as `cd backend && /opt/homebrew/bin/pytest ...`.
- Obscurity scale bounds are exactly `OBSCURITY_MIN_LISTENERS = 10` and `OBSCURITY_MAX_LISTENERS = 10_000_000`. Do not change these; they were calibrated against the real library.
- Non-artist threshold and tag-trust threshold are both exactly `5000` listeners.
- Peer-percentile and peer-relative badge ranking require at least `5` stored profiles; below that they are hidden.
- Last.fm requests are capped at 5/second. MusicBrainz at 1/second with a descriptive `User-Agent`.
- Era section hides below 40% year coverage.
- `GENRE_VOCABULARY` has exactly 51 entries, listed in Task 7.
- Profiles default to `public=False`.
- Never re-fetch Last.fm data that already exists in `backend/data/artist_meta.json`.
- A pre-fetched cache of 1,148 artists exists at `~/Documents/youtube-music-mapper-backups/artist_meta-lastfm-2026-08-08.json`. Task 2 copies it in.

---

### Task 1: Test scaffolding and collaboration splitting

**Files:**
- Create: `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_collab_split.py`
- Create: `backend/collab_split.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: nothing
- Produces: `split_artist_name(name: str) -> list[str]` — returns `[name]` unchanged when the name holds no separator, otherwise the component artist names in order.

- [ ] **Step 1: Add pytest to requirements**

Append to `backend/requirements.txt`:

```
pytest>=8.0.0
```

Run: `cd backend && python -m pip install -r requirements.txt`

- [ ] **Step 2: Create the test package**

`backend/tests/__init__.py` — empty file.

`backend/tests/conftest.py`:

```python
import sys
from pathlib import Path

# Backend modules are flat imports; make them importable when pytest is run
# from the repo root as well as from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 3: Write the failing test**

`backend/tests/test_collab_split.py`:

```python
from collab_split import split_artist_name


def test_plain_name_is_returned_unchanged():
    assert split_artist_name("Seven Lions") == ["Seven Lions"]


def test_ampersand_splits():
    assert split_artist_name("Seven Lions & Brieanna Grace") == [
        "Seven Lions", "Brieanna Grace"
    ]


def test_comma_and_ampersand_splits():
    assert split_artist_name("ILLENIUM, Wooli, & Grabbitz") == [
        "ILLENIUM", "Wooli", "Grabbitz"
    ]


def test_feat_splits():
    assert split_artist_name("SLANDER feat. Julia Church") == [
        "SLANDER", "Julia Church"
    ]


def test_x_separator_splits():
    assert split_artist_name("ISOxo x Knock2") == ["ISOxo", "Knock2"]


def test_name_containing_x_is_not_split():
    # "ISOxo" has no surrounding spaces, so it must survive intact.
    assert split_artist_name("ISOxo") == ["ISOxo"]


def test_empty_components_are_dropped():
    assert split_artist_name("Dabin,  , Said The Sky") == ["Dabin", "Said The Sky"]
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_collab_split.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'collab_split'`

- [ ] **Step 5: Write the implementation**

`backend/collab_split.py`:

```python
"""Split multi-artist credit strings into component artist names."""

import re

SEPARATOR = re.compile(
    r"\s*(?:,|&| x | X | vs\.? | with | feat\.? | ft\.? )\s*",
    re.IGNORECASE,
)


def split_artist_name(name: str) -> list[str]:
    """Return the component artists in a credit string.

    A name with no separator comes back as a single-element list, so callers
    can treat every artist uniformly.
    """
    parts = [p.strip() for p in SEPARATOR.split(name) if p.strip()]
    return parts if len(parts) > 1 else [name]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_collab_split.py -v`
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add backend/tests backend/collab_split.py backend/requirements.txt
git commit -m "Add collaboration-string splitting with test scaffolding"
```

---

### Task 2: Shared artist metadata store and the non-artist heuristic

**Files:**
- Create: `backend/artist_meta.py`, `backend/tests/test_artist_meta.py`
- Create: `backend/data/artist_meta.json` (copied, not authored)
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `META_PATH: Path`
  - `load_meta() -> dict[str, dict]`
  - `save_meta(meta: dict) -> None`
  - `is_non_artist(entry: dict) -> bool`
  - `trusted_tags(entry: dict) -> list[str]`
  - `NON_ARTIST_LISTENER_THRESHOLD = 5000`, `TAG_TRUST_LISTENER_THRESHOLD = 5000`

An entry has shape `{"lastfm_name": str, "listeners": int, "playcount": int, "tags": list[str], "genre": str | None, "thumbnail": str | None, "is_artist": bool | None}`. `is_artist` is a manual override; when present it wins over the heuristic and is never recomputed.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_artist_meta.py`:

```python
from artist_meta import is_non_artist, trusted_tags


def test_low_listeners_and_no_tags_is_flagged():
    # "Lost Lands Music Festival": 169 listeners, no tags.
    assert is_non_artist({"listeners": 169, "tags": []}) is True


def test_low_listeners_with_tags_is_kept():
    # "RayRay": 2366 listeners but genuinely tagged.
    assert is_non_artist({"listeners": 2366, "tags": ["trap", "electronic"]}) is False


def test_high_listeners_with_no_tags_is_kept():
    assert is_non_artist({"listeners": 500000, "tags": []}) is False


def test_manual_override_wins():
    # "Brieanna Grace" is a real vocalist the heuristic would flag.
    entry = {"listeners": 295, "tags": [], "is_artist": True}
    assert is_non_artist(entry) is False


def test_manual_override_can_force_flag():
    entry = {"listeners": 900000, "tags": ["dubstep"], "is_artist": False}
    assert is_non_artist(entry) is True


def test_missing_listeners_is_flagged():
    assert is_non_artist({"tags": []}) is True


def test_tags_below_trust_threshold_are_discarded():
    # DubstepGutter is tagged "fried vegan eggs saladcore" at 4981 listeners.
    entry = {"listeners": 4981, "tags": ["fried vegan eggs saladcore", "dubstep"]}
    assert trusted_tags(entry) == []


def test_tags_above_trust_threshold_are_kept():
    entry = {"listeners": 530426, "tags": ["melodic dubstep", "electronic"]}
    assert trusted_tags(entry) == ["melodic dubstep", "electronic"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_artist_meta.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'artist_meta'`

- [ ] **Step 3: Write the implementation**

`backend/artist_meta.py`:

```python
"""Shared per-artist metadata. Global rather than per-profile: an artist's
listener count is the same for every user, so it is stored once."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
META_PATH = DATA_DIR / "artist_meta.json"

NON_ARTIST_LISTENER_THRESHOLD = 5000
TAG_TRUST_LISTENER_THRESHOLD = 5000


def load_meta() -> dict:
    if not META_PATH.exists():
        return {}
    with open(META_PATH) as f:
        return json.load(f)


def save_meta(meta: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    tmp = META_PATH.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(meta, f)
    tmp.replace(META_PATH)


def is_non_artist(entry: dict) -> bool:
    """True for upload channels and other non-artist entries.

    YouTube Music libraries carry repost channels alongside real artists;
    left in, they dominate any 'most obscure' statistic.
    """
    override = entry.get("is_artist")
    if override is not None:
        return not override
    listeners = entry.get("listeners", 0) or 0
    return listeners < NON_ARTIST_LISTENER_THRESHOLD and not entry.get("tags")


def trusted_tags(entry: dict) -> list[str]:
    """Tags are user-generated and unreliable on small artists."""
    listeners = entry.get("listeners", 0) or 0
    if listeners < TAG_TRUST_LISTENER_THRESHOLD:
        return []
    return list(entry.get("tags", []))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_artist_meta.py -v`
Expected: 8 passed

- [ ] **Step 5: Seed the store from the pre-fetched cache**

```bash
mkdir -p backend/data
cp ~/Documents/youtube-music-mapper-backups/artist_meta-lastfm-2026-08-08.json backend/data/artist_meta.json
python3 -c "import json;d=json.load(open('backend/data/artist_meta.json'));print(len(d),'artists,',sum(1 for v in d.values() if v.get('listeners')),'with listeners')"
```

Expected: `1157 artists, 1148 with listeners`

- [ ] **Step 6: Ignore the data directory**

Append to `.gitignore`:

```
# Enrichment caches (regenerable, and large)
backend/data/
```

- [ ] **Step 7: Commit**

```bash
git add backend/artist_meta.py backend/tests/test_artist_meta.py .gitignore
git commit -m "Add shared artist metadata store and non-artist heuristic"
```

---

### Task 3: Last.fm artist fetcher

**Files:**
- Create: `backend/enrich/__init__.py`, `backend/enrich/lastfm_artist.py`
- Create: `backend/tests/test_lastfm_artist.py`

**Interfaces:**
- Consumes: `artist_meta.load_meta`, `artist_meta.save_meta`
- Produces:
  - `normalize_for_lookup(name: str) -> str`
  - `parse_artist_info(payload: dict) -> dict` — maps a Last.fm JSON body to a meta entry
  - `fetch_missing(names: Iterable[str], api_key: str, save_every: int = 100) -> dict`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_lastfm_artist.py`:

```python
from enrich.lastfm_artist import normalize_for_lookup, parse_artist_info


def test_normalize_strips_slash_separators():
    # "Axwell /\\ Ingrosso" fails Last.fm lookup purely on the slashes.
    assert normalize_for_lookup(r"Axwell /\ Ingrosso") == "Axwell Ingrosso"


def test_normalize_collapses_whitespace():
    assert normalize_for_lookup("  Seven   Lions ") == "Seven Lions"


def test_normalize_leaves_ordinary_names_alone():
    assert normalize_for_lookup("Fred again..") == "Fred again.."


def test_parse_extracts_stats_and_tags():
    payload = {
        "artist": {
            "name": "Seven Lions",
            "stats": {"listeners": "530426", "playcount": "39000000"},
            "tags": {"tag": [{"name": "Melodic Dubstep"}, {"name": "Electronic"}]},
        }
    }
    assert parse_artist_info(payload) == {
        "lastfm_name": "Seven Lions",
        "listeners": 530426,
        "playcount": 39000000,
        "tags": ["melodic dubstep", "electronic"],
    }


def test_parse_marks_missing_artist():
    assert parse_artist_info({"error": 6, "message": "not found"}) == {"missing": True}


def test_parse_tolerates_absent_stats():
    payload = {"artist": {"name": "Nobody"}}
    assert parse_artist_info(payload) == {
        "lastfm_name": "Nobody", "listeners": 0, "playcount": 0, "tags": []
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_lastfm_artist.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'enrich'`

- [ ] **Step 3: Write the implementation**

`backend/enrich/__init__.py` — empty file.

`backend/enrich/lastfm_artist.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_lastfm_artist.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/enrich backend/tests/test_lastfm_artist.py
git commit -m "Add resumable Last.fm artist metadata fetcher"
```

---

### Task 4: Genre reference distributions

**Files:**
- Create: `backend/enrich/lastfm_tags.py`, `backend/tests/test_lastfm_tags.py`

**Interfaces:**
- Consumes: `enrich.lastfm_artist._Throttle`
- Produces:
  - `GENRE_TAG_QUERIES: dict[str, str]` — maps a `GENRE_VOCABULARY` entry to the Last.fm tag to query
  - `parse_top_artists(payload: dict) -> list[int]` — listener counts, descending
  - `build_reference(api_key: str, limit: int = 500) -> dict[str, list[int]]`
  - Writes `backend/data/genre_reference.json`

Scene-relative obscurity needs a population that is not the user's own library. Querying Last.fm's top artists per tag supplies an external, stable one.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_lastfm_tags.py`:

```python
import pytest

from enrich.lastfm_tags import GENRE_TAG_QUERIES, parse_top_artists


@pytest.mark.xfail(reason="GENRE_VOCABULARY lands in Task 7; remove this marker there")
def test_every_query_maps_to_a_known_genre():
    from taste_profile import GENRE_VOCABULARY
    assert set(GENRE_TAG_QUERIES).issubset(set(GENRE_VOCABULARY))


def test_parse_returns_descending_listener_counts():
    payload = {"topartists": {"artist": [
        {"name": "A", "listeners": "100"},
        {"name": "B", "listeners": "5000"},
        {"name": "C", "listeners": "300"},
    ]}}
    assert parse_top_artists(payload) == [5000, 300, 100]


def test_parse_skips_entries_without_listeners():
    payload = {"topartists": {"artist": [
        {"name": "A", "listeners": "0"},
        {"name": "B", "listeners": "42"},
    ]}}
    assert parse_top_artists(payload) == [42]


def test_parse_handles_empty_payload():
    assert parse_top_artists({}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_lastfm_tags.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'enrich.lastfm_tags'`

- [ ] **Step 3: Write the implementation**

`backend/enrich/lastfm_tags.py`:

```python
"""Build per-genre listener distributions from Last.fm's top artists per tag.

Scene-relative obscurity compares a person's artists against others in the
same scene; using their own library as that population would be circular.
"""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from artist_meta import DATA_DIR  # noqa: E402
from enrich.lastfm_artist import API_URL, _Throttle, REQUESTS_PER_SECOND  # noqa: E402

REFERENCE_PATH = DATA_DIR / "genre_reference.json"

# Only genres with a real Last.fm tag equivalent. Buckets like "Other",
# "Mix/Compilation", and "Sample Pack" have no scene to compare against.
GENRE_TAG_QUERIES = {
    "Ambient": "ambient",
    "Bass House": "bass house",
    "Classical": "classical",
    "Country/Folk": "folk",
    "Drum & Bass": "drum and bass",
    "Dubstep/Bass": "dubstep",
    "Electronic": "electronic",
    "Eurodance": "eurodance",
    "Funk/Soul": "funk",
    "Future Bass": "future bass",
    "Hardstyle": "hardstyle",
    "Hip Hop": "hip-hop",
    "House": "house",
    "Hyperpop": "hyperpop",
    "Indie": "indie",
    "J-Pop": "j-pop",
    "Jazz": "jazz",
    "K-Pop": "k-pop",
    "Melodic Bass": "melodic dubstep",
    "Pop": "pop",
    "Progressive House": "progressive house",
    "R&B": "rnb",
    "Reggaeton": "reggaeton",
    "Rock": "rock",
    "Synthwave": "synthwave",
    "Tech House": "tech house",
    "Techno": "techno",
    "Trance": "trance",
    "World Music": "world",
}


def parse_top_artists(payload: dict) -> list[int]:
    artists = (payload.get("topartists", {}) or {}).get("artist", []) or []
    counts = [int(a.get("listeners", 0) or 0) for a in artists]
    return sorted((c for c in counts if c > 0), reverse=True)


def build_reference(api_key: str, limit: int = 500) -> dict:
    throttle = _Throttle(REQUESTS_PER_SECOND)
    reference = {}
    if REFERENCE_PATH.exists():
        with open(REFERENCE_PATH) as f:
            reference = json.load(f)

    for genre, tag in GENRE_TAG_QUERIES.items():
        if genre in reference:
            continue
        throttle.wait()
        try:
            response = requests.get(
                API_URL,
                params={"method": "tag.gettopartists", "tag": tag,
                        "api_key": api_key, "format": "json", "limit": limit},
                timeout=15,
            )
            reference[genre] = parse_top_artists(response.json())
        except Exception as exc:
            print(f"  {genre}: {exc}", flush=True)
            continue
        DATA_DIR.mkdir(exist_ok=True)
        with open(REFERENCE_PATH, "w") as f:
            json.dump(reference, f)

    return reference
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_lastfm_tags.py -v`
Expected: 3 passed, 1 xfailed. The xfail is `test_every_query_maps_to_a_known_genre`, which needs `GENRE_VOCABULARY` from Task 7; that task removes the marker.

- [ ] **Step 5: Commit**

```bash
git add backend/enrich/lastfm_tags.py backend/tests/test_lastfm_tags.py
git commit -m "Build per-genre listener reference distributions from Last.fm tags"
```

---

### Task 5: MusicBrainz release-year fetcher

**Files:**
- Create: `backend/enrich/musicbrainz_years.py`, `backend/tests/test_musicbrainz_years.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `track_key(artist: str, title: str) -> str`
  - `parse_year(payload: dict) -> int | None`
  - `fetch_missing(pairs: Iterable[tuple[str, str]], save_every: int = 50) -> dict[str, int]`
  - Writes `backend/data/track_years.json`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_musicbrainz_years.py`:

```python
from enrich.musicbrainz_years import track_key, parse_year


def test_track_key_is_case_insensitive_and_stable():
    assert track_key("Seven Lions", "Strangers") == track_key("seven lions", "STRANGERS")


def test_track_key_separates_artist_and_title():
    assert track_key("A", "B") == "a|b"


def test_parse_year_takes_earliest_release():
    payload = {"recordings": [
        {"first-release-date": "2016-05-20"},
        {"first-release-date": "2014-01-01"},
    ]}
    assert parse_year(payload) == 2014


def test_parse_year_accepts_year_only_dates():
    assert parse_year({"recordings": [{"first-release-date": "1973"}]}) == 1973


def test_parse_year_returns_none_when_absent():
    assert parse_year({"recordings": [{}]}) is None


def test_parse_year_returns_none_for_empty_result():
    assert parse_year({"recordings": []}) is None


def test_parse_year_ignores_malformed_dates():
    assert parse_year({"recordings": [{"first-release-date": "not-a-date"}]}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_musicbrainz_years.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'enrich.musicbrainz_years'`

- [ ] **Step 3: Write the implementation**

`backend/enrich/musicbrainz_years.py`:

```python
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


def fetch_missing(pairs, save_every: int = 50) -> dict:
    years = {}
    if YEARS_PATH.exists():
        with open(YEARS_PATH) as f:
            years = json.load(f)

    todo = [(a, t) for a, t in pairs if track_key(a, t) not in years]
    done = 0
    for artist, title in todo:
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
            year = parse_year(response.json())
        except Exception:
            year = None
        # Record misses too, so a rerun does not retry every unmatched track.
        years[key] = year
        done += 1
        if done % save_every == 0:
            DATA_DIR.mkdir(exist_ok=True)
            with open(YEARS_PATH, "w") as f:
                json.dump(years, f)
            print(f"  {done}/{len(todo)}", flush=True)

    DATA_DIR.mkdir(exist_ok=True)
    with open(YEARS_PATH, "w") as f:
        json.dump(years, f)
    return years
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_musicbrainz_years.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/enrich/musicbrainz_years.py backend/tests/test_musicbrainz_years.py
git commit -m "Add MusicBrainz release-year fetcher"
```

---

### Task 6: Library adapter

**Files:**
- Create: `backend/library.py`, `backend/tests/test_library.py`

**Interfaces:**
- Consumes: `collab_split.split_artist_name`
- Produces:
  - `library_from_graph_data(graph: dict) -> dict` — `{"liked_songs": [{"title", "album", "artists": [{"name"}]}]}`
  - `artist_song_counts(library: dict) -> dict[str, int]` — collab-split, songs credited to every component
  - `track_pairs(library: dict) -> list[tuple[str, str]]` — unique (artist, title) for year lookup

The real library lives in `frontend/graph_data.json`; `backend/music_data.json` is empty. This adapter is what makes the existing profile machinery see real data.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_library.py`:

```python
from library import library_from_graph_data, artist_song_counts, track_pairs

GRAPH = {"nodes": [
    {"name": "Seven Lions", "song_count": 2,
     "songs": [{"title": "Strangers", "album": "&"}, {"title": "Rush Over Me", "album": ""}]},
    {"name": "ILLENIUM, Wooli, & Grabbitz", "song_count": 1,
     "songs": [{"title": "Sad Songs", "album": ","}]},
]}


def test_liked_songs_are_flattened():
    library = library_from_graph_data(GRAPH)
    assert len(library["liked_songs"]) == 3
    assert library["liked_songs"][0]["title"] == "Strangers"


def test_junk_album_values_are_dropped():
    # 39% of album values are separator fragments from a broken importer.
    library = library_from_graph_data(GRAPH)
    assert all(s["album"] is None for s in library["liked_songs"])


def test_collaborations_credit_every_component():
    counts = artist_song_counts(library_from_graph_data(GRAPH))
    assert counts["ILLENIUM"] == 1
    assert counts["Wooli"] == 1
    assert counts["Grabbitz"] == 1


def test_solo_artist_counts_accumulate():
    counts = artist_song_counts(library_from_graph_data(GRAPH))
    assert counts["Seven Lions"] == 2


def test_the_combined_string_is_not_itself_an_artist():
    counts = artist_song_counts(library_from_graph_data(GRAPH))
    assert "ILLENIUM, Wooli, & Grabbitz" not in counts


def test_track_pairs_are_unique():
    pairs = track_pairs(library_from_graph_data(GRAPH))
    assert len(pairs) == len(set(pairs)) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_library.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'library'`

- [ ] **Step 3: Write the implementation**

`backend/library.py`:

```python
"""Adapter from the D3 graph export to the liked-songs shape the profile and
similarity code consumes."""

from collections import Counter

from collab_split import split_artist_name

# The paste importer wrote separator fragments into the album column, so these
# values carry no information.
_JUNK_ALBUMS = {"", ",", "&", None}


def library_from_graph_data(graph: dict) -> dict:
    liked = []
    for node in graph.get("nodes", []):
        for song in node.get("songs") or []:
            album = song.get("album")
            liked.append({
                "title": song.get("title"),
                "album": None if album in _JUNK_ALBUMS else album,
                "artists": [{"name": node["name"]}],
            })
    return {"liked_songs": liked}


def artist_song_counts(library: dict) -> dict:
    counts = Counter()
    for song in library.get("liked_songs", []):
        for credit in song.get("artists", []):
            for artist in split_artist_name(credit.get("name", "")):
                if artist:
                    counts[artist] += 1
    return dict(counts)


def track_pairs(library: dict) -> list:
    seen = []
    unique = set()
    for song in library.get("liked_songs", []):
        for credit in song.get("artists", []):
            pair = (credit.get("name", ""), song.get("title", ""))
            if pair not in unique:
                unique.add(pair)
                seen.append(pair)
    return seen
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_library.py -v`
Expected: 6 passed

- [ ] **Step 5: Verify against the real library**

Run:

```bash
cd backend && python -c "
import json
from library import library_from_graph_data, artist_song_counts
g = json.load(open('../frontend/graph_data.json'))
lib = library_from_graph_data(g)
counts = artist_song_counts(lib)
print(len(lib['liked_songs']), 'songs;', len(counts), 'artists')
print('Seven Lions:', counts['Seven Lions'])
"
```

Expected: `3039 songs; 1157 artists` and `Seven Lions: 95`

- [ ] **Step 6: Commit**

```bash
git add backend/library.py backend/tests/test_library.py
git commit -m "Add graph-data to liked-songs library adapter"
```

---

### Task 7: Obscurity, diversity, and genre metrics

**Files:**
- Create: `backend/taste_profile.py`, `backend/tests/test_taste_profile.py`
- Modify: `backend/tests/test_lastfm_tags.py` (remove the xfail marker)

**Interfaces:**
- Consumes: `artist_meta.is_non_artist`, `artist_meta.trusted_tags`
- Produces:
  - `GENRE_VOCABULARY: tuple[str, ...]` (51 entries)
  - `OBSCURITY_MIN_LISTENERS = 10`, `OBSCURITY_MAX_LISTENERS = 10_000_000`
  - `artist_obscurity(listeners: int) -> float`
  - `library_obscurity(counts: dict, meta: dict) -> float | None`
  - `genre_distribution(counts: dict, meta: dict) -> dict[str, float]`
  - `diversity_score(distribution: dict) -> float`
  - `scene_relative_obscurity(counts, meta, reference) -> float | None`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_taste_profile.py`:

```python
import math
import pytest

from taste_profile import (
    GENRE_VOCABULARY, artist_obscurity, library_obscurity,
    genre_distribution, diversity_score, scene_relative_obscurity,
)


def test_vocabulary_has_51_entries():
    assert len(GENRE_VOCABULARY) == 51
    assert len(set(GENRE_VOCABULARY)) == 51


def test_obscurity_floor_at_upper_bound():
    assert artist_obscurity(10_000_000) == 0.0


def test_obscurity_ceiling_at_lower_bound():
    assert artist_obscurity(10) == 100.0


def test_obscurity_clamps_beyond_bounds():
    assert artist_obscurity(50_000_000) == 0.0
    assert artist_obscurity(1) == 100.0


def test_obscurity_is_monotonic():
    assert artist_obscurity(1_000) > artist_obscurity(100_000) > artist_obscurity(5_000_000)


def test_obscurity_midpoint_is_log_scaled():
    # 10^4 listeners sits halfway between 10^1 and 10^7.
    assert artist_obscurity(10_000) == pytest.approx(50.0)


def test_obscurity_of_zero_listeners_is_none():
    assert artist_obscurity(0) is None


def test_library_obscurity_is_song_weighted():
    meta = {
        "Popular": {"listeners": 1_000_000, "tags": ["pop"]},
        "Obscure": {"listeners": 1_000, "tags": ["indie"]},
    }
    heavy_on_popular = library_obscurity({"Popular": 99, "Obscure": 1}, meta)
    heavy_on_obscure = library_obscurity({"Popular": 1, "Obscure": 99}, meta)
    assert heavy_on_obscure > heavy_on_popular


def test_library_obscurity_excludes_non_artists():
    meta = {
        "Real": {"listeners": 1_000_000, "tags": ["pop"]},
        "Repost Channel": {"listeners": 169, "tags": []},
    }
    with_channel = library_obscurity({"Real": 10, "Repost Channel": 10}, meta)
    without = library_obscurity({"Real": 10}, meta)
    assert with_channel == without


def test_library_obscurity_is_none_without_data():
    assert library_obscurity({"Unknown": 5}, {}) is None


def test_genre_distribution_is_song_weighted_and_normalised():
    meta = {"A": {"genre": "Pop"}, "B": {"genre": "Rock"}}
    dist = genre_distribution({"A": 30, "B": 10}, meta)
    assert dist["Pop"] == pytest.approx(0.75)
    assert dist["Rock"] == pytest.approx(0.25)
    assert sum(dist.values()) == pytest.approx(1.0)


def test_genre_distribution_defaults_unknown_to_other():
    dist = genre_distribution({"A": 1}, {})
    assert dist == {"Other": 1.0}


def test_diversity_uses_the_fixed_vocabulary_not_genres_present():
    # The old formula scored an even two-genre split as a perfect 1.0.
    two_genres = diversity_score({"Pop": 0.5, "Rock": 0.5})
    assert two_genres < 0.25
    assert two_genres == pytest.approx(math.log(2) / math.log(51))


def test_diversity_of_a_single_genre_is_zero():
    assert diversity_score({"Pop": 1.0}) == 0.0


def test_diversity_of_a_perfectly_even_library_is_one():
    even = {g: 1 / 51 for g in GENRE_VOCABULARY}
    assert diversity_score(even) == pytest.approx(1.0)


def test_scene_relative_ranks_within_genre_population():
    meta = {"Small": {"listeners": 5_000, "tags": ["dubstep"], "genre": "Dubstep/Bass"}}
    reference = {"Dubstep/Bass": [1_000, 10_000, 100_000, 1_000_000]}
    # One of four reference artists is smaller, so this sits at the 75th
    # obscurity percentile within the scene.
    assert scene_relative_obscurity({"Small": 1}, meta, reference) == pytest.approx(75.0)


def test_scene_relative_is_none_without_a_reference():
    meta = {"A": {"listeners": 5_000, "tags": ["x"], "genre": "Dubstep/Bass"}}
    assert scene_relative_obscurity({"A": 1}, meta, {}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_taste_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'taste_profile'`

- [ ] **Step 3: Write the implementation**

`backend/taste_profile.py`:

```python
"""Taste metrics. Pure functions over (artist counts, artist metadata,
track years, genre reference) so they can be tested without I/O."""

import math
from collections import Counter

from artist_meta import is_non_artist, trusted_tags

GENRE_VOCABULARY = (
    "Ambient", "Bass House", "Cinematic", "City Pop", "Classical", "Comedy",
    "Country/Folk", "Drum & Bass", "Dubstep/Bass", "Electronic",
    "Electronic/Experimental", "Eurodance", "Funk/Electronic", "Funk/Soul",
    "Future Bass", "Game Music", "Hardcore/Hardstyle", "Hardstyle", "Hip Hop",
    "Hip-Hop/Rap", "House", "Hyperpop", "Indie", "Indie/Alternative", "J-Pop",
    "Jam/Electronic", "Jazz", "K-Pop", "Lo-Fi/Chill", "Lo-fi", "Mandopop",
    "Melodic Bass", "Midtempo", "Mix/Compilation", "Other", "Pop", "Pop/EDM",
    "Progressive House", "R&B", "R&B/Soul", "Reggaeton", "Rock",
    "Sample Pack", "Soundtrack", "Synthwave", "Tech House", "Techno", "Trance",
    "Trap/Bass", "UK House", "World Music",
)

# Calibrated against a real 1,157-artist library: these bounds clip 23 artists,
# where 100..5M clipped 113 and 50..20M clipped 49.
OBSCURITY_MIN_LISTENERS = 10
OBSCURITY_MAX_LISTENERS = 10_000_000

_LOG_MIN = math.log10(OBSCURITY_MIN_LISTENERS)
_LOG_MAX = math.log10(OBSCURITY_MAX_LISTENERS)


def artist_obscurity(listeners: int):
    """0 means everybody knows them, 100 means nobody does."""
    if not listeners:
        return None
    position = (math.log10(listeners) - _LOG_MIN) / (_LOG_MAX - _LOG_MIN)
    return max(0.0, min(100.0, 100.0 * (1.0 - position)))


def _scored_artists(counts: dict, meta: dict):
    for artist, songs in counts.items():
        entry = meta.get(artist)
        if not entry or is_non_artist(entry):
            continue
        score = artist_obscurity(entry.get("listeners", 0))
        if score is not None:
            yield artist, songs, score


def library_obscurity(counts: dict, meta: dict):
    total = weighted = 0
    for _, songs, score in _scored_artists(counts, meta):
        total += songs
        weighted += songs * score
    return weighted / total if total else None


def genre_distribution(counts: dict, meta: dict) -> dict:
    totals = Counter()
    for artist, songs in counts.items():
        genre = (meta.get(artist) or {}).get("genre") or "Other"
        totals[genre] += songs
    grand = sum(totals.values())
    if not grand:
        return {}
    return {genre: songs / grand for genre, songs in totals.items()}


def diversity_score(distribution: dict) -> float:
    """Genre entropy normalised by the fixed vocabulary, not by the genres
    present — otherwise an even two-genre library scores a perfect 1.0."""
    entropy = -sum(p * math.log(p) for p in distribution.values() if p > 0)
    return entropy / math.log(len(GENRE_VOCABULARY))


def scene_relative_obscurity(counts: dict, meta: dict, reference: dict):
    """Percentile within the artist's own genre population."""
    total = weighted = 0
    for artist, songs, _ in _scored_artists(counts, meta):
        genre = (meta.get(artist) or {}).get("genre")
        population = reference.get(genre)
        if not population:
            continue
        listeners = meta[artist]["listeners"]
        smaller = sum(1 for value in population if value < listeners)
        percentile = 100.0 - (100.0 * smaller / len(population))
        total += songs
        weighted += songs * percentile
    return weighted / total if total else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_taste_profile.py -v`
Expected: 17 passed

- [ ] **Step 5: Remove the xfail marker from Task 4**

Delete the `@pytest.mark.xfail(...)` line above `test_every_query_maps_to_a_known_genre` in `backend/tests/test_lastfm_tags.py`.

Run: `cd backend && python -m pytest tests/ -v`
Expected: all pass

- [ ] **Step 6: Sanity-check against the real library**

Run:

```bash
cd backend && python -c "
import json
from library import library_from_graph_data, artist_song_counts
from artist_meta import load_meta
from taste_profile import library_obscurity, genre_distribution, diversity_score
g = json.load(open('../frontend/graph_data.json'))
counts = artist_song_counts(library_from_graph_data(g))
meta = load_meta()
print('obscurity', round(library_obscurity(counts, meta), 1))
print('diversity', round(diversity_score(genre_distribution(counts, meta)), 3))
"
```

Expected: obscurity near `20.3`. (Genre distribution reads `meta[...]['genre']`, which is not populated until Task 8, so diversity will read `0.0` here. That is expected at this point.)

- [ ] **Step 7: Commit**

```bash
git add backend/taste_profile.py backend/tests/test_taste_profile.py backend/tests/test_lastfm_tags.py
git commit -m "Add obscurity, diversity, and genre-distribution metrics"
```

---

### Task 8: Genre resolution and backfill

**Files:**
- Modify: `backend/artist_meta.py`
- Modify: `backend/tests/test_artist_meta.py`
- Create: `backend/backfill_genres.py`

**Interfaces:**
- Consumes: `artist_meta.trusted_tags`, `taste_profile.GENRE_VOCABULARY`
- Produces: `resolve_genre(name: str, entry: dict, curated: dict) -> str`

Resolution order: the curated `genre_map.json` wins; then trusted Last.fm tags mapped through `TAG_TO_GENRE`; otherwise `"Other"`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_artist_meta.py`:

```python
from artist_meta import resolve_genre


def test_curated_map_wins():
    entry = {"listeners": 900000, "tags": ["pop"]}
    assert resolve_genre("Seven Lions", entry, {"Seven Lions": "Melodic Bass"}) == "Melodic Bass"


def test_trusted_tags_are_used_when_curated_is_silent():
    entry = {"listeners": 900000, "tags": ["dubstep", "electronic"]}
    assert resolve_genre("Someone", entry, {}) == "Dubstep/Bass"


def test_untrusted_tags_fall_through_to_other():
    # 4981 listeners is below the trust threshold.
    entry = {"listeners": 4981, "tags": ["dubstep"]}
    assert resolve_genre("DubstepGutter", entry, {}) == "Other"


def test_unmappable_tags_fall_through_to_other():
    entry = {"listeners": 900000, "tags": ["seen live", "favourites"]}
    assert resolve_genre("Someone", entry, {}) == "Other"


def test_first_mappable_tag_wins():
    entry = {"listeners": 900000, "tags": ["seen live", "k-pop", "pop"]}
    assert resolve_genre("Someone", entry, {}) == "K-Pop"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_artist_meta.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_genre'`

- [ ] **Step 3: Write the implementation**

Append to `backend/artist_meta.py`:

```python
# Last.fm tag to GENRE_VOCABULARY entry. Only unambiguous tags are mapped;
# anything else falls through to "Other" rather than guessing.
TAG_TO_GENRE = {
    "ambient": "Ambient",
    "bass house": "Bass House",
    "classical": "Classical",
    "folk": "Country/Folk",
    "country": "Country/Folk",
    "drum and bass": "Drum & Bass",
    "dnb": "Drum & Bass",
    "dubstep": "Dubstep/Bass",
    "brostep": "Dubstep/Bass",
    "riddim": "Dubstep/Bass",
    "melodic dubstep": "Melodic Bass",
    "future bass": "Future Bass",
    "electronic": "Electronic",
    "electronica": "Electronic",
    "edm": "Electronic",
    "eurodance": "Eurodance",
    "funk": "Funk/Soul",
    "soul": "Funk/Soul",
    "hardstyle": "Hardstyle",
    "hardcore": "Hardcore/Hardstyle",
    "hip-hop": "Hip Hop",
    "hip hop": "Hip Hop",
    "rap": "Hip Hop",
    "house": "House",
    "progressive house": "Progressive House",
    "tech house": "Tech House",
    "techno": "Techno",
    "trance": "Trance",
    "hyperpop": "Hyperpop",
    "indie": "Indie",
    "j-pop": "J-Pop",
    "jazz": "Jazz",
    "k-pop": "K-Pop",
    "lo-fi": "Lo-fi",
    "lofi": "Lo-fi",
    "pop": "Pop",
    "rnb": "R&B",
    "r&b": "R&B",
    "reggaeton": "Reggaeton",
    "rock": "Rock",
    "classic rock": "Rock",
    "metal": "Rock",
    "synthwave": "Synthwave",
    "trap": "Trap/Bass",
    "soundtrack": "Soundtrack",
    "world": "World Music",
}


def resolve_genre(name: str, entry: dict, curated: dict) -> str:
    curated_genre = curated.get(name)
    if curated_genre:
        return curated_genre
    for tag in trusted_tags(entry):
        mapped = TAG_TO_GENRE.get(tag)
        if mapped:
            return mapped
    return "Other"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_artist_meta.py -v`
Expected: 13 passed

- [ ] **Step 5: Write the backfill script**

`backend/backfill_genres.py`:

```python
#!/usr/bin/env python3
"""Populate the genre field on every artist_meta entry."""

import json
from pathlib import Path

from artist_meta import load_meta, save_meta, resolve_genre

curated_path = Path(__file__).parent / "genre_map.json"
curated = json.loads(curated_path.read_text()) if curated_path.exists() else {}

meta = load_meta()
for name, entry in meta.items():
    entry["genre"] = resolve_genre(name, entry, curated)
save_meta(meta)

other = sum(1 for e in meta.values() if e["genre"] == "Other")
print(f"{len(meta)} artists, {other} still Other ({100 * other / len(meta):.0f}%)")
```

- [ ] **Step 6: Run the backfill**

Run: `cd backend && python backfill_genres.py`
Expected: the "still Other" share drops well below the 33% baseline (381 of 1,157).

- [ ] **Step 7: Commit**

```bash
git add backend/artist_meta.py backend/tests/test_artist_meta.py backend/backfill_genres.py
git commit -m "Resolve artist genres from curated map then trusted Last.fm tags"
```

---

### Task 9: Eras, moods, clusters, and the assembled stats object

**Files:**
- Modify: `backend/taste_profile.py`
- Modify: `backend/tests/test_taste_profile.py`

**Interfaces:**
- Consumes: everything from Tasks 6-8
- Produces:
  - `MOOD_TAGS: dict[str, str]`
  - `decade_distribution(library: dict, years: dict) -> dict | None`
  - `mood_distribution(counts: dict, meta: dict) -> dict`
  - `taste_clusters(graph: dict, counts: dict, meta: dict, min_size: int = 10) -> list[dict]`
  - `build_profile_stats(library, meta, years, reference, graph) -> dict`

`build_profile_stats` returns keys: `artist_count`, `song_count`, `obscurity`, `scene_obscurity`, `diversity`, `genres`, `top_artists`, `decades`, `median_year`, `year_coverage`, `moods`, `clusters`, `one_song_share`, `top_genre_share`, `largest_artist_songs`, `gini`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_taste_profile.py`:

```python
from taste_profile import (
    decade_distribution, mood_distribution, taste_clusters, build_profile_stats,
)

LIBRARY = {"liked_songs": [
    {"title": "Old", "album": None, "artists": [{"name": "A"}]},
    {"title": "New", "album": None, "artists": [{"name": "A"}]},
    {"title": "Unknown", "album": None, "artists": [{"name": "B"}]},
]}
YEARS = {"a|old": 1975, "a|new": 2021, "b|unknown": None}


def test_decades_bucket_by_ten_years():
    dist = decade_distribution(LIBRARY, YEARS)
    assert dist["decades"] == {1970: 1, 2020: 1}


def test_decade_coverage_reports_the_known_share():
    assert decade_distribution(LIBRARY, YEARS)["coverage"] == pytest.approx(2 / 3)


def test_decades_are_none_below_forty_percent_coverage():
    sparse = {"a|old": 1975}
    assert decade_distribution(LIBRARY, sparse) is None


def test_median_year_uses_known_years_only():
    assert decade_distribution(LIBRARY, YEARS)["median_year"] == 1998


def test_moods_come_from_trusted_tags_only():
    meta = {
        "Loud": {"listeners": 900000, "tags": ["energetic"]},
        "Tiny": {"listeners": 100, "tags": ["chill"]},
    }
    moods = mood_distribution({"Loud": 5, "Tiny": 5}, meta)
    assert moods == {"Energetic": 1.0}


def test_moods_are_empty_without_mappable_tags():
    meta = {"A": {"listeners": 900000, "tags": ["seen live"]}}
    assert mood_distribution({"A": 1}, meta) == {}


def test_clusters_are_named_and_sorted_by_size():
    graph = {
        "nodes": [{"name": n} for n in ["A", "B", "C", "D", "E", "F"]],
        "links": [
            {"source": "A", "target": "B"}, {"source": "B", "target": "C"},
            {"source": "D", "target": "E"}, {"source": "E", "target": "F"},
        ],
    }
    meta = {n: {"genre": "Pop" if n in "ABC" else "Rock"} for n in "ABCDEF"}
    counts = {n: 1 for n in "ABCDEF"}
    clusters = taste_clusters(graph, counts, meta, min_size=3)
    assert len(clusters) == 2
    assert clusters[0]["size"] >= clusters[1]["size"]
    assert {c["genre"] for c in clusters} == {"Pop", "Rock"}


def test_small_clusters_are_dropped():
    graph = {"nodes": [{"name": "A"}, {"name": "B"}], "links": [{"source": "A", "target": "B"}]}
    assert taste_clusters(graph, {"A": 1, "B": 1}, {}, min_size=3) == []


def test_build_profile_stats_has_every_documented_key():
    graph = {"nodes": [{"name": "A", "song_count": 2, "songs": [{"title": "x"}, {"title": "y"}]}],
             "links": []}
    meta = {"A": {"listeners": 900000, "tags": ["pop"], "genre": "Pop"}}
    stats = build_profile_stats(LIBRARY, meta, YEARS, {}, graph)
    for key in ("artist_count", "song_count", "obscurity", "scene_obscurity",
                "diversity", "genres", "top_artists", "decades", "median_year",
                "year_coverage", "moods", "clusters", "one_song_share",
                "top_genre_share", "largest_artist_songs", "gini"):
        assert key in stats


def test_one_song_share_matches_the_long_tail():
    graph = {"nodes": [], "links": []}
    library = {"liked_songs": (
        [{"title": f"s{i}", "artists": [{"name": "Heavy"}]} for i in range(5)]
        + [{"title": "t", "artists": [{"name": "Light"}]}]
    )}
    stats = build_profile_stats(library, {}, {}, {}, graph)
    assert stats["one_song_share"] == pytest.approx(0.5)
    assert stats["largest_artist_songs"] == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_taste_profile.py -v`
Expected: FAIL with `ImportError: cannot import name 'decade_distribution'`

- [ ] **Step 3: Write the implementation**

Append to `backend/taste_profile.py`:

```python
import statistics

import networkx as nx

from library import artist_song_counts, track_pairs

# Last.fm tags are scene labels more than feeling labels, so this vocabulary
# stays deliberately small and the UI labels the section as tag-derived.
MOOD_TAGS = {
    "chill": "Chill", "chillout": "Chill", "relaxing": "Chill",
    "energetic": "Energetic", "party": "Energetic", "banger": "Energetic",
    "dark": "Dark", "melancholy": "Melancholy", "sad": "Melancholy",
    "happy": "Upbeat", "uplifting": "Upbeat", "feel good": "Upbeat",
    "aggressive": "Aggressive", "heavy": "Aggressive",
    "dreamy": "Dreamy", "atmospheric": "Dreamy", "ethereal": "Dreamy",
}

MIN_YEAR_COVERAGE = 0.40
MIN_CLUSTER_SIZE = 10


def decade_distribution(library: dict, years: dict):
    from enrich.musicbrainz_years import track_key

    known = []
    total = 0
    for artist, title in track_pairs(library):
        total += 1
        year = years.get(track_key(artist, title))
        if year:
            known.append(year)
    if not total or len(known) / total < MIN_YEAR_COVERAGE:
        return None
    buckets = Counter((year // 10) * 10 for year in known)
    return {
        "decades": dict(buckets),
        "median_year": int(statistics.median(known)),
        "coverage": len(known) / total,
    }


def mood_distribution(counts: dict, meta: dict) -> dict:
    totals = Counter()
    for artist, songs in counts.items():
        entry = meta.get(artist)
        if not entry or is_non_artist(entry):
            continue
        for tag in trusted_tags(entry):
            mood = MOOD_TAGS.get(tag)
            if mood:
                totals[mood] += songs
                break
    grand = sum(totals.values())
    if not grand:
        return {}
    return {mood: songs / grand for mood, songs in totals.items()}


def taste_clusters(graph: dict, counts: dict, meta: dict,
                   min_size: int = MIN_CLUSTER_SIZE) -> list:
    g = nx.Graph()
    for node in graph.get("nodes", []):
        g.add_node(node["name"])
    for link in graph.get("links", []):
        source, target = link.get("source"), link.get("target")
        source = source if isinstance(source, str) else (source or {}).get("id")
        target = target if isinstance(target, str) else (target or {}).get("id")
        if g.has_node(source) and g.has_node(target):
            g.add_edge(source, target)

    clusters = []
    for component in nx.connected_components(g):
        subgraph = g.subgraph(component)
        groups = ([component] if subgraph.number_of_edges() == 0
                  else nx.community.greedy_modularity_communities(subgraph))
        for group in groups:
            members = sorted(group, key=lambda n: -counts.get(n, 0))
            if len(members) < min_size:
                continue
            genres = Counter((meta.get(m) or {}).get("genre") or "Other" for m in members)
            clusters.append({
                "size": len(members),
                "genre": genres.most_common(1)[0][0],
                "members": members[:8],
                "songs": sum(counts.get(m, 0) for m in members),
            })
    clusters.sort(key=lambda c: -c["size"])
    return clusters


def _gini(values: list) -> float:
    if not values or sum(values) == 0:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    cumulative = sum((i + 1) * v for i, v in enumerate(ordered))
    return (2 * cumulative) / (n * sum(ordered)) - (n + 1) / n


def build_profile_stats(library: dict, meta: dict, years: dict,
                        reference: dict, graph: dict) -> dict:
    counts = artist_song_counts(library)
    genres = genre_distribution(counts, meta)
    eras = decade_distribution(library, years)
    song_total = sum(counts.values())
    one_song = sum(1 for c in counts.values() if c <= 1)

    return {
        "artist_count": len(counts),
        "song_count": len(library.get("liked_songs", [])),
        "obscurity": library_obscurity(counts, meta),
        "scene_obscurity": scene_relative_obscurity(counts, meta, reference),
        "diversity": diversity_score(genres) if genres else 0.0,
        "genres": genres,
        "top_artists": sorted(counts.items(), key=lambda kv: -kv[1])[:30],
        "decades": eras["decades"] if eras else None,
        "median_year": eras["median_year"] if eras else None,
        "year_coverage": eras["coverage"] if eras else 0.0,
        "moods": mood_distribution(counts, meta),
        "clusters": taste_clusters(graph, counts, meta),
        "one_song_share": one_song / len(counts) if counts else 0.0,
        "top_genre_share": max(genres.values()) if genres else 0.0,
        "largest_artist_songs": max(counts.values()) if counts else 0,
        "gini": _gini(list(counts.values())),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_taste_profile.py -v`
Expected: 27 passed

- [ ] **Step 5: Commit**

```bash
git add backend/taste_profile.py backend/tests/test_taste_profile.py
git commit -m "Add era, mood, and cluster metrics with assembled stats object"
```

---

### Task 10: Archetype and badges

**Files:**
- Create: `backend/archetype.py`, `backend/tests/test_archetype.py`

**Interfaces:**
- Consumes: the `build_profile_stats` object
- Produces:
  - `obscurity_axis(value) -> str` in `{"mainstream", "balanced", "underground"}`
  - `diversity_axis(value) -> str` in `{"focused", "broad", "omnivore"}`
  - `era_axis(median_year) -> str` in `{"retro", "mixed", "current", "unknown"}`
  - `resolve_archetype(stats: dict) -> dict` with keys `name`, `tagline`
  - `compute_badges(stats: dict, peers: list[dict] | None = None) -> list[dict]`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_archetype.py`:

```python
import pytest

from archetype import (
    obscurity_axis, diversity_axis, era_axis, resolve_archetype, compute_badges,
)


def test_obscurity_axis_buckets():
    assert obscurity_axis(10.0) == "mainstream"
    assert obscurity_axis(45.0) == "balanced"
    assert obscurity_axis(80.0) == "underground"


def test_obscurity_axis_boundaries_are_inclusive_downward():
    assert obscurity_axis(30.0) == "mainstream"
    assert obscurity_axis(30.1) == "balanced"
    assert obscurity_axis(65.0) == "balanced"
    assert obscurity_axis(65.1) == "underground"


def test_obscurity_axis_handles_missing_data():
    assert obscurity_axis(None) == "balanced"


def test_diversity_axis_buckets():
    assert diversity_axis(0.20) == "focused"
    assert diversity_axis(0.50) == "broad"
    assert diversity_axis(0.80) == "omnivore"


def test_era_axis_buckets():
    assert era_axis(1985) == "retro"
    assert era_axis(2008) == "mixed"
    assert era_axis(2023) == "current"
    assert era_axis(None) == "unknown"


def test_archetype_names_the_dominant_genre():
    stats = {"obscurity": 20.0, "diversity": 0.7, "median_year": 2021,
             "genres": {"Dubstep/Bass": 0.5, "Pop": 0.5}}
    result = resolve_archetype(stats)
    assert "Dubstep/Bass" in result["tagline"]
    assert isinstance(result["name"], str) and result["name"]


def test_archetype_is_deterministic():
    stats = {"obscurity": 20.0, "diversity": 0.7, "median_year": 2021,
             "genres": {"Pop": 1.0}}
    assert resolve_archetype(stats) == resolve_archetype(stats)


def test_archetype_differs_across_obscurity_buckets():
    base = {"diversity": 0.5, "median_year": 2020, "genres": {"Pop": 1.0}}
    mainstream = resolve_archetype({**base, "obscurity": 10.0})["name"]
    underground = resolve_archetype({**base, "obscurity": 90.0})["name"]
    assert mainstream != underground


def test_archetype_survives_an_empty_genre_map():
    result = resolve_archetype({"obscurity": None, "diversity": 0.0,
                                "median_year": None, "genres": {}})
    assert result["name"]


def test_badges_trigger_on_fixed_thresholds():
    stats = {"one_song_share": 0.64, "top_genre_share": 0.15, "gini": 0.54,
             "largest_artist_songs": 95, "clusters": [], "song_count": 3039}
    badges = compute_badges(stats)
    assert any("one" in b["id"] for b in badges)


def test_badges_are_capped_at_three():
    stats = {"one_song_share": 0.9, "top_genre_share": 0.9, "gini": 0.9,
             "largest_artist_songs": 500, "clusters": [{"size": 20}] * 8,
             "song_count": 1000}
    assert len(compute_badges(stats)) <= 3


def test_badges_are_empty_when_nothing_is_notable():
    stats = {"one_song_share": 0.1, "top_genre_share": 0.1, "gini": 0.1,
             "largest_artist_songs": 2, "clusters": [], "song_count": 100}
    assert compute_badges(stats) == []


def test_badges_carry_a_label_and_value():
    stats = {"one_song_share": 0.64, "top_genre_share": 0.1, "gini": 0.1,
             "largest_artist_songs": 2, "clusters": [], "song_count": 100}
    badge = compute_badges(stats)[0]
    assert set(badge) >= {"id", "label", "value"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_archetype.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'archetype'`

- [ ] **Step 3: Write the implementation**

`backend/archetype.py`:

```python
"""Deterministic archetype and badge rules. No LLM: the page must never
attribute an artist or trait the library does not support."""

MIN_PEERS_FOR_RELATIVE_RANKING = 5


def obscurity_axis(value):
    if value is None:
        return "balanced"
    if value <= 30.0:
        return "mainstream"
    if value <= 65.0:
        return "balanced"
    return "underground"


def diversity_axis(value):
    if value is None or value <= 0.35:
        return "focused"
    if value <= 0.65:
        return "broad"
    return "omnivore"


def era_axis(median_year):
    if median_year is None:
        return "unknown"
    if median_year < 2000:
        return "retro"
    if median_year < 2015:
        return "mixed"
    return "current"


_NAMES = {
    ("mainstream", "focused"): "Main Stage Loyalist",
    ("mainstream", "broad"): "Main Stage Completionist",
    ("mainstream", "omnivore"): "Chart Omnivore",
    ("balanced", "focused"): "Scene Regular",
    ("balanced", "broad"): "Crate Digger",
    ("balanced", "omnivore"): "Restless Listener",
    ("underground", "focused"): "Deep Cut Specialist",
    ("underground", "broad"): "Basement Archivist",
    ("underground", "omnivore"): "Signal Hunter",
}

_ERA_PHRASES = {
    "retro": "anchored well before the streaming era",
    "mixed": "spread across two decades",
    "current": "firmly in the present",
    "unknown": "of no fixed era",
}


def resolve_archetype(stats: dict) -> dict:
    obscurity = obscurity_axis(stats.get("obscurity"))
    diversity = diversity_axis(stats.get("diversity"))
    era = era_axis(stats.get("median_year"))

    genres = stats.get("genres") or {}
    top_genre = max(genres, key=genres.get) if genres else None

    name = _NAMES[(obscurity, diversity)]
    if top_genre:
        tagline = f"Built on {top_genre}, {_ERA_PHRASES[era]}."
    else:
        tagline = f"A library {_ERA_PHRASES[era]}."

    return {"name": name, "tagline": tagline,
            "axes": {"obscurity": obscurity, "diversity": diversity, "era": era}}


# (id, predicate, label template, value extractor, priority)
_BADGE_RULES = [
    ("one_and_done", lambda s: s.get("one_song_share", 0) >= 0.50,
     "{pct}% of your artists have exactly one song",
     lambda s: round(s["one_song_share"] * 100), 10),
    ("genre_monogamist", lambda s: s.get("top_genre_share", 0) >= 0.40,
     "{pct}% of your library is a single genre",
     lambda s: round(s["top_genre_share"] * 100), 9),
    ("completionist", lambda s: s.get("largest_artist_songs", 0) >= 40,
     "{n} songs by one artist",
     lambda s: s["largest_artist_songs"], 8),
    ("lopsided", lambda s: s.get("gini", 0) >= 0.50,
     "Heavily lopsided listening (gini {n})",
     lambda s: round(s["gini"], 2), 7),
    ("many_worlds", lambda s: len(s.get("clusters") or []) >= 6,
     "{n} distinct musical worlds",
     lambda s: len(s["clusters"]), 6),
]


def compute_badges(stats: dict, peers=None) -> list:
    triggered = []
    for badge_id, predicate, template, extract, priority in _BADGE_RULES:
        if not predicate(stats):
            continue
        value = extract(stats)
        triggered.append({
            "id": badge_id,
            "label": template.format(pct=value, n=value),
            "value": value,
            "priority": priority,
        })

    if peers and len(peers) >= MIN_PEERS_FOR_RELATIVE_RANKING:
        # Rank by distance from the peer median rather than fixed priority.
        for badge in triggered:
            values = [p.get(badge["id"]) for p in peers if p.get(badge["id"]) is not None]
            if values:
                median = sorted(values)[len(values) // 2]
                badge["priority"] = abs(badge["value"] - median)

    triggered.sort(key=lambda b: -b["priority"])
    return triggered[:3]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_archetype.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add backend/archetype.py backend/tests/test_archetype.py
git commit -m "Add deterministic archetype and badge rules"
```

---

### Task 11: Rarity-weighted compatibility

**Files:**
- Modify: `backend/taste_similarity.py`
- Create: `backend/tests/test_taste_similarity.py`

**Interfaces:**
- Consumes: `taste_profile.artist_obscurity`
- Produces: `rarity_weighted_overlap(counts1: dict, counts2: dict, meta: dict) -> float`, and `calculate_similarity` gains an optional `artist_meta: dict | None = None` keyword.

Sharing an artist with 3,000 listeners says more than both liking Coldplay; the current formula treats them identically.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_taste_similarity.py`:

```python
import pytest

from taste_similarity import rarity_weighted_overlap, calculate_similarity

META = {
    "Coldplay": {"listeners": 9_251_718, "tags": ["pop"]},
    "Obscure Act": {"listeners": 3_000, "tags": ["dubstep"]},
}


def test_sharing_an_obscure_artist_scores_higher_than_a_famous_one():
    famous = rarity_weighted_overlap({"Coldplay": 1}, {"Coldplay": 1}, META)
    obscure = rarity_weighted_overlap({"Obscure Act": 1}, {"Obscure Act": 1}, META)
    assert obscure > famous


def test_identical_libraries_score_one():
    assert rarity_weighted_overlap(
        {"Coldplay": 2, "Obscure Act": 1}, {"Coldplay": 2, "Obscure Act": 1}, META
    ) == pytest.approx(1.0)


def test_disjoint_libraries_score_zero():
    assert rarity_weighted_overlap({"Coldplay": 1}, {"Obscure Act": 1}, META) == 0.0


def test_empty_libraries_score_one():
    assert rarity_weighted_overlap({}, {}, META) == 1.0


def test_unknown_artists_still_contribute():
    # No metadata must not silently drop an artist from the comparison.
    assert rarity_weighted_overlap({"Ghost": 1}, {"Ghost": 1}, {}) == pytest.approx(1.0)


def test_calculate_similarity_without_meta_matches_previous_behaviour():
    p1 = {"liked_songs": [{"title": "a", "artists": [{"name": "Coldplay"}]}]}
    p2 = {"liked_songs": [{"title": "b", "artists": [{"name": "Coldplay"}]}]}
    assert calculate_similarity(p1, p2)["overall"] == pytest.approx(100.0)


def test_calculate_similarity_accepts_artist_meta():
    p1 = {"liked_songs": [{"title": "a", "artists": [{"name": "Obscure Act"}]}]}
    p2 = {"liked_songs": [{"title": "b", "artists": [{"name": "Obscure Act"}]}]}
    result = calculate_similarity(p1, p2, artist_meta=META)
    assert 0.0 <= result["overall"] <= 100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_taste_similarity.py -v`
Expected: FAIL with `ImportError: cannot import name 'rarity_weighted_overlap'`

- [ ] **Step 3: Write the implementation**

Add to `backend/taste_similarity.py`:

```python
def rarity_weighted_overlap(counts1: Dict[str, int], counts2: Dict[str, int],
                            artist_meta: Dict[str, dict]) -> float:
    """Weighted overlap where each artist's contribution scales with how few
    people listen to them. Unknown artists get neutral weight."""
    from taste_profile import artist_obscurity

    all_artists = set(counts1) | set(counts2)
    if not all_artists:
        return 1.0

    min_sum = max_sum = 0.0
    for artist in all_artists:
        entry = artist_meta.get(artist) or {}
        score = artist_obscurity(entry.get("listeners", 0))
        # Neutral weight of 1.0 for unknowns; obscure artists reach 2.0.
        weight = 1.0 + (score / 100.0) if score is not None else 1.0
        c1, c2 = counts1.get(artist, 0), counts2.get(artist, 0)
        min_sum += weight * min(c1, c2)
        max_sum += weight * max(c1, c2)

    return min_sum / max_sum if max_sum > 0 else 0.0
```

Then change the signature and blend inside `calculate_similarity`:

```python
def calculate_similarity(profile1: dict, profile2: dict, genre_map: dict = None,
                         artist_meta: dict = None) -> dict:
```

and replace the `artist_weighted` assignment with:

```python
    if artist_meta:
        artist_weighted = rarity_weighted_overlap(counts1, counts2, artist_meta)
    else:
        artist_weighted = weighted_overlap(counts1, counts2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_taste_similarity.py -v`
Expected: 7 passed

- [ ] **Step 5: Run the whole suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/taste_similarity.py backend/tests/test_taste_similarity.py
git commit -m "Weight shared artists by rarity in compatibility scoring"
```

---

### Task 12: Fix profile creation, identity, and privacy

**Files:**
- Modify: `backend/profile_manager.py`
- Modify: `backend/server.py:283-305` (`api_create_profile`), `backend/server.py:365-392` (`api_compare_with_current`)
- Modify: `frontend/js/graph.js:2373-2406` (`createAndShareProfile`)
- Modify: `frontend/js/compare.js:51-90`
- Create: `backend/tests/test_profile_manager.py`

**Interfaces:**
- Consumes: `library.library_from_graph_data`
- Produces: `create_profile(music_data, name="", public=False)` — default flipped; `/api/compare/with-current/<id>` removed.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_profile_manager.py`:

```python
import json

import profile_manager


def test_profiles_are_private_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    data = {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]}

    result = profile_manager.create_profile(data, name="Test")
    stored = json.loads((tmp_path / "profiles" / f"{result['id']}.json").read_text())
    assert stored["public"] is False


def test_public_index_is_not_written_for_private_profiles(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    data = {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]}

    profile_manager.create_profile(data, name="Test")
    assert not (tmp_path / "profiles" / "_public_index.json").exists()


def test_opting_in_writes_the_public_index(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    data = {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]}

    profile_manager.create_profile(data, name="Test", public=True)
    assert (tmp_path / "profiles" / "_public_index.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_profile_manager.py -v`
Expected: FAIL — `stored["public"]` is `True`

- [ ] **Step 3: Flip the default**

In `backend/profile_manager.py`, change:

```python
def create_profile(music_data: dict, name: str = "", public: bool = False) -> dict:
```

and update its docstring line to read `public: Whether the profile opts in to leaderboards (default off)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_profile_manager.py -v`
Expected: 3 passed

- [ ] **Step 5: Require music_data on the create endpoint**

Replace the fallback block in `api_create_profile` (`backend/server.py`) with:

```python
    music_data = data.get("music_data")
    name = data.get("name", "")
    public = bool(data.get("public", False))

    if not music_data or not music_data.get("liked_songs"):
        return jsonify({"error": "No music data provided"}), 400
```

The `music_data.json` fallback is removed: on a deployed instance that file is
whichever visitor uploaded last, not the caller.

- [ ] **Step 6: Delete the server-global comparison endpoint**

Remove the entire `api_compare_with_current` function and its `@app.route("/api/compare/with-current/<profile_id>")` decorator from `backend/server.py`.

- [ ] **Step 7: Send the real library when sharing**

In `frontend/js/graph.js`, replace the body of `createAndShareProfile` with:

```javascript
async function createAndShareProfile() {
    const name = prompt('Enter your display name (optional):') || '';
    const optIn = confirm('List this profile on the public leaderboard?\n\nCancel keeps it link-only.');

    const musicData = graph.toLibrary();
    if (!musicData.liked_songs.length) {
        alert('Load your music first.');
        return;
    }

    try {
        const response = await fetch('/api/profile/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, public: optIn, music_data: musicData })
        });
        const data = await response.json();
        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }
        localStorage.setItem('myProfileId', data.id);
        const shareUrl = window.location.origin + '/p/' + data.id;
        const copied = await copyToClipboard(shareUrl);
        if (copied) {
            alert(`Profile created! Share link copied:\n\n${shareUrl}`);
        } else {
            prompt('Profile created! Share this link:', shareUrl);
        }
    } catch (error) {
        alert('Error creating profile: ' + error.message);
    }
}
```

- [ ] **Step 8: Add the graph-to-library method**

Add to the graph class in `frontend/js/graph.js`, next to `getTotalSongCount()`:

```javascript
    toLibrary() {
        const liked = [];
        (this.nodes || []).forEach(node => {
            (node.songs || []).forEach(song => {
                liked.push({
                    title: song.title,
                    album: [',', '&', ''].includes(song.album) ? null : song.album,
                    artists: [{ name: node.name }]
                });
            });
        });
        return { liked_songs: liked };
    }
```

- [ ] **Step 9: Point comparison at two profile IDs**

In `frontend/js/compare.js`, replace `loadComparisonWithCurrent(targetProfileId)` with:

```javascript
async function loadComparisonWithCurrent(targetProfileId) {
    const myId = localStorage.getItem('myProfileId');
    if (!myId) {
        showCreateModal();
        return;
    }
    return loadComparison(myId, targetProfileId);
}
```

- [ ] **Step 10: Verify manually**

Run: `cd backend && python server.py`, open `http://localhost:5050`, click "Load My Music" then "Share My Taste". Confirm the resulting profile JSON in `backend/profiles/` contains a non-empty `liked_songs` and `"public": false`.

- [ ] **Step 11: Commit**

```bash
git add backend/profile_manager.py backend/server.py frontend/js/graph.js frontend/js/compare.js backend/tests/test_profile_manager.py
git commit -m "Send real library on profile creation and make profiles private by default"
```

---

### Task 13: Stats endpoint

**Files:**
- Modify: `backend/server.py`
- Create: `backend/tests/test_stats_endpoint.py`

**Interfaces:**
- Consumes: `taste_profile.build_profile_stats`, `archetype.resolve_archetype`, `archetype.compute_badges`
- Produces: `GET /api/profile/<profile_id>/stats` returning `{profile: {...}, stats: {...}, archetype: {...}, badges: [...], peer_percentile: float | None}`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_stats_endpoint.py`:

```python
import pytest

import server


@pytest.fixture
def client():
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


def test_missing_profile_returns_404(client):
    assert client.get("/api/profile/doesnotexist/stats").status_code == 404


def test_stats_payload_has_the_documented_shape(client, monkeypatch):
    monkeypatch.setattr(server, "get_profile", lambda pid, **kw: {
        "id": pid, "name": "Test", "stats": {},
        "music_data": {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]},
    })
    monkeypatch.setattr(server, "list_public_profiles", lambda limit=100: [])

    body = client.get("/api/profile/abc12345/stats").get_json()
    assert set(body) >= {"profile", "stats", "archetype", "badges", "peer_percentile"}
    assert body["profile"]["id"] == "abc12345"


def test_peer_percentile_is_none_below_five_profiles(client, monkeypatch):
    monkeypatch.setattr(server, "get_profile", lambda pid, **kw: {
        "id": pid, "name": "Test", "stats": {},
        "music_data": {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]},
    })
    monkeypatch.setattr(server, "list_public_profiles", lambda limit=100: [{}, {}])

    assert client.get("/api/profile/abc12345/stats").get_json()["peer_percentile"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_stats_endpoint.py -v`
Expected: FAIL with 404 on the shape test (route not registered)

- [ ] **Step 3: Write the implementation**

Add near the other profile routes in `backend/server.py`:

```python
from artist_meta import load_meta
from taste_profile import build_profile_stats
from archetype import resolve_archetype, compute_badges, MIN_PEERS_FOR_RELATIVE_RANKING


def _load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


@app.route("/api/profile/<profile_id>/stats")
def api_profile_stats(profile_id):
    profile = get_profile(profile_id, include_music_data=True)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    meta = load_meta()
    years = _load_json("data/track_years.json", {})
    reference = _load_json("data/genre_reference.json", {})
    graph = _load_json("../frontend/graph_data.json", {"nodes": [], "links": []})

    stats = build_profile_stats(profile["music_data"], meta, years, reference, graph)

    peers = list_public_profiles(limit=500)
    percentile = None
    if len(peers) >= MIN_PEERS_FOR_RELATIVE_RANKING and stats["obscurity"] is not None:
        scores = [p.get("stats", {}).get("obscurity") for p in peers]
        scores = [s for s in scores if s is not None]
        if scores:
            below = sum(1 for s in scores if s < stats["obscurity"])
            percentile = round(100.0 * below / len(scores), 1)

    return jsonify({
        "profile": {"id": profile["id"], "name": profile["name"]},
        "stats": stats,
        "archetype": resolve_archetype(stats),
        "badges": compute_badges(stats),
        "peer_percentile": percentile,
    })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_stats_endpoint.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_stats_endpoint.py
git commit -m "Add profile stats endpoint"
```

---

### Task 14: Profile page

**Files:**
- Create: `frontend/profile.html`, `frontend/js/profile.js`
- Modify: `backend/server.py` (add the `/p/<profile_id>` route)
- Modify: `frontend/css/styles.css` (append the profile section styles)

**Interfaces:**
- Consumes: `GET /api/profile/<id>/stats`
- Produces: the rendered page

Sections render only when their data exists: the era section is skipped when
`stats.decades` is null, moods when `stats.moods` is empty, scene obscurity when
`stats.scene_obscurity` is null, peer percentile when it is null.

- [ ] **Step 1: Add the route**

In `backend/server.py`, next to `@app.route("/compare/<profile_id>")`:

```python
@app.route("/p/<profile_id>")
def profile_page(profile_id):
    return send_from_directory(app.static_folder, "profile.html")
```

- [ ] **Step 2: Create the page shell**

`frontend/profile.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Music Taste Profile</title>
    <link rel="stylesheet" href="/css/styles.css?v=122">
</head>
<body>
    <div class="profile-page">
        <header class="profile-hero">
            <div class="profile-archetype" id="archetypeName">Loading…</div>
            <div class="profile-tagline" id="archetypeTagline"></div>
            <div class="profile-owner" id="profileName"></div>
            <div class="profile-badges" id="badges"></div>
        </header>

        <section class="profile-stats" id="headlineStats"></section>
        <section class="profile-section" id="obscuritySection" hidden></section>
        <section class="profile-section" id="genreSection" hidden></section>
        <section class="profile-section" id="clusterSection" hidden></section>
        <section class="profile-section" id="eraSection" hidden></section>
        <section class="profile-section" id="moodSection" hidden></section>
        <section class="profile-section" id="topArtistSection" hidden></section>

        <footer class="profile-footer">
            <a class="btn btn-secondary" href="/">Open the map</a>
            <button class="btn btn-secondary" id="copyLink">Copy share link</button>
            <button class="btn btn-danger" id="deleteProfile">Delete this profile</button>
        </footer>
    </div>
    <script src="/js/profile.js?v=1"></script>
</body>
</html>
```

- [ ] **Step 3: Write the page script**

`frontend/js/profile.js`:

```javascript
const profileId = window.location.pathname.split('/').pop();

const el = id => document.getElementById(id);
const pct = v => `${Math.round(v * 100)}%`;

function bars(entries, total) {
    return entries.map(([label, value]) => `
        <div class="bar-row">
            <span class="bar-label">${label}</span>
            <span class="bar-track"><span class="bar-fill" style="width:${(value / total) * 100}%"></span></span>
            <span class="bar-value">${pct(value / total)}</span>
        </div>`).join('');
}

function section(node, title, html) {
    node.innerHTML = `<h2>${title}</h2>${html}`;
    node.hidden = false;
}

async function load() {
    const response = await fetch(`/api/profile/${profileId}/stats`);
    if (!response.ok) {
        el('archetypeName').textContent = 'Profile not found';
        return;
    }
    const { profile, stats, archetype, badges, peer_percentile } = await response.json();

    el('archetypeName').textContent = archetype.name;
    el('archetypeTagline').textContent = archetype.tagline;
    el('profileName').textContent = profile.name;
    el('badges').innerHTML = badges
        .map(b => `<span class="badge">${b.label}</span>`).join('');

    el('headlineStats').innerHTML = `
        <div class="stat-tile"><span>${stats.artist_count}</span><label>Artists</label></div>
        <div class="stat-tile"><span>${stats.song_count}</span><label>Songs</label></div>
        <div class="stat-tile"><span>${Math.round(stats.diversity * 100)}</span><label>Diversity</label></div>`;

    if (stats.obscurity !== null) {
        let html = `<p class="big-number">${stats.obscurity.toFixed(1)}<small>/100</small></p>
                    <p class="muted">0 means everyone knows them. 100 means nobody does.</p>`;
        if (peer_percentile !== null) {
            html += `<p>More obscure than <strong>${peer_percentile}%</strong> of profiles here.</p>`;
        }
        if (stats.scene_obscurity !== null) {
            html += `<p>Within your own scenes you sit at the
                     <strong>${stats.scene_obscurity.toFixed(0)}th</strong> obscurity percentile.</p>`;
        }
        section(el('obscuritySection'), 'Obscurity', html);
    }

    const genres = Object.entries(stats.genres).sort((a, b) => b[1] - a[1]).slice(0, 10);
    if (genres.length) {
        section(el('genreSection'), 'Genres', bars(genres, 1));
    }

    if (stats.clusters.length) {
        section(el('clusterSection'), 'Your musical worlds', stats.clusters.slice(0, 6).map(c => `
            <div class="cluster">
                <strong>${c.genre}</strong>
                <span class="muted">${c.size} artists</span>
                <div class="muted">${c.members.slice(0, 4).join(', ')}</div>
            </div>`).join(''));
    }

    if (stats.decades) {
        const decades = Object.entries(stats.decades).sort((a, b) => a[0] - b[0]);
        const total = decades.reduce((sum, [, n]) => sum + n, 0);
        section(el('eraSection'), 'Eras',
            bars(decades.map(([d, n]) => [`${d}s`, n]), total) +
            `<p class="muted">Median release year ${stats.median_year}.
             Year data covers ${pct(stats.year_coverage)} of your songs.</p>`);
    }

    const moods = Object.entries(stats.moods).sort((a, b) => b[1] - a[1]);
    if (moods.length) {
        section(el('moodSection'), 'Moods',
            bars(moods, 1) + `<p class="muted">Derived from Last.fm tags, not audio analysis.</p>`);
    }

    if (stats.top_artists.length) {
        section(el('topArtistSection'), 'Most played', `<ol class="top-artists">${
            stats.top_artists.slice(0, 20)
                .map(([name, n]) => `<li><span>${name}</span><span class="muted">${n}</span></li>`)
                .join('')}</ol>`);
    }
}

el('copyLink').addEventListener('click', () => {
    navigator.clipboard.writeText(window.location.href);
    el('copyLink').textContent = 'Copied';
});

el('deleteProfile').addEventListener('click', async () => {
    if (!confirm('Delete this profile permanently? The share link will stop working.')) return;
    await fetch(`/api/profile/${profileId}`, { method: 'DELETE' });
    if (localStorage.getItem('myProfileId') === profileId) {
        localStorage.removeItem('myProfileId');
    }
    window.location.href = '/';
});

load();
```

- [ ] **Step 4: Append the styles**

Append to `frontend/css/styles.css`:

```css
.profile-page { max-width: 860px; margin: 0 auto; padding: 32px 20px 64px; }
.profile-hero { text-align: center; padding: 40px 0 28px; }
.profile-archetype { font-size: 2.4rem; font-weight: 700; letter-spacing: -0.02em; }
.profile-tagline { opacity: 0.75; margin-top: 8px; }
.profile-owner { margin-top: 14px; font-size: 0.9rem; opacity: 0.6; }
.profile-badges { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 20px; }
.badge { border: 1px solid currentColor; border-radius: 999px; padding: 5px 12px; font-size: 0.8rem; opacity: 0.85; }
.profile-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 24px 0 8px; }
.stat-tile { text-align: center; padding: 16px 8px; border-radius: 10px; background: rgba(255,255,255,0.04); }
.stat-tile span { display: block; font-size: 1.8rem; font-weight: 700; }
.stat-tile label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.6; }
.profile-section { margin-top: 34px; }
.profile-section h2 { font-size: 1.1rem; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.7; margin-bottom: 14px; }
.big-number { font-size: 3rem; font-weight: 700; margin: 0; }
.big-number small { font-size: 1rem; opacity: 0.5; }
.muted { opacity: 0.6; font-size: 0.88rem; }
.bar-row { display: grid; grid-template-columns: 150px 1fr 52px; gap: 10px; align-items: center; margin-bottom: 7px; }
.bar-label { font-size: 0.85rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { height: 8px; border-radius: 4px; background: rgba(255,255,255,0.08); overflow: hidden; }
.bar-fill { display: block; height: 100%; background: currentColor; opacity: 0.65; }
.bar-value { font-size: 0.8rem; text-align: right; opacity: 0.6; }
.cluster { padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.07); }
.cluster strong { margin-right: 10px; }
.top-artists { list-style: decimal inside; padding: 0; margin: 0; }
.top-artists li { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.06); }
.profile-footer { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; margin-top: 44px; }

@media (max-width: 600px) {
    .profile-archetype { font-size: 1.7rem; }
    .bar-row { grid-template-columns: 96px 1fr 44px; }
}
```

- [ ] **Step 5: Verify in the browser**

Run: `cd backend && python server.py`. Create a profile from the map, then open `http://localhost:5050/p/<id>`.

Confirm: the archetype and tagline render; obscurity reads near 20; genre and cluster sections populate; the era and mood sections are absent (no year data fetched yet, and mood tags are sparse); the top-artist list shows Seven Lions first.

- [ ] **Step 6: Commit**

```bash
git add frontend/profile.html frontend/js/profile.js frontend/css/styles.css backend/server.py
git commit -m "Add the taste profile page"
```

---

### Task 15: Run the enrichment pipeline end to end

**Files:**
- Create: `backend/run_enrichment.py`

**Interfaces:**
- Consumes: every fetcher and the library adapter
- Produces: populated `backend/data/` stores

- [ ] **Step 1: Write the runner**

`backend/run_enrichment.py`:

```python
#!/usr/bin/env python3
"""Populate every enrichment store for the current library. Safe to rerun:
each fetcher skips what it already has."""

import json
import os
import sys
from pathlib import Path

from collab_split import split_artist_name
from library import library_from_graph_data, track_pairs
from enrich.lastfm_artist import fetch_missing as fetch_artists
from enrich.lastfm_tags import build_reference
from enrich.musicbrainz_years import fetch_missing as fetch_years

api_key = os.environ.get("LASTFM_API_KEY", "")
env_path = Path(__file__).parent / ".env"
if not api_key and env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("LASTFM_API_KEY"):
            api_key = line.split("=", 1)[1].strip().strip("\"'")
if not api_key:
    sys.exit("LASTFM_API_KEY is not set")

graph = json.loads(Path("../frontend/graph_data.json").read_text())
library = library_from_graph_data(graph)

names = set()
for node in graph["nodes"]:
    names.add(node["name"])
    names.update(split_artist_name(node["name"]))

print(f"1/4 artist metadata ({len(names)} names)")
fetch_artists(names, api_key)

print("2/4 genre backfill")
os.system(f"{sys.executable} backfill_genres.py")

print("3/4 genre reference distributions")
build_reference(api_key)

pairs = track_pairs(library)
print(f"4/4 release years ({len(pairs)} tracks, ~1/sec — this takes a while)")
fetch_years(pairs)

print("done")
```

- [ ] **Step 2: Run it**

Run: `cd backend && python run_enrichment.py`

Steps 1-3 finish in minutes since `artist_meta.json` is already seeded. Step 4 is the slow one: MusicBrainz allows one request per second, so roughly 2,730 tracks takes about 45 minutes. It is resumable — interrupt and rerun freely.

- [ ] **Step 3: Confirm the stores populated**

Run:

```bash
cd backend && python -c "
import json
for name in ('artist_meta', 'track_years', 'genre_reference'):
    d = json.load(open(f'data/{name}.json'))
    print(f'{name}: {len(d)} entries')
"
```

- [ ] **Step 4: Reload the profile page**

Open `http://localhost:5050/p/<id>` again and confirm the era section now renders with a decade histogram and median year, and that scene-relative obscurity appears in the obscurity section.

- [ ] **Step 5: Commit**

```bash
git add backend/run_enrichment.py
git commit -m "Add end-to-end enrichment runner"
```

---

## Verification

After Task 15, confirm:

- [ ] `cd backend && python -m pytest tests/ -v` passes with no failures
- [ ] `/p/<id>` renders archetype, badges, obscurity, genres, clusters, eras, moods, top artists
- [ ] A profile created from the map has non-empty `liked_songs` and `"public": false`
- [ ] `/api/compare/with-current/<id>` returns 404 (endpoint removed)
- [ ] Deleting a profile from the page removes its JSON and clears `myProfileId`
- [ ] With `backend/data/` emptied, the page still renders — obscurity, era, mood, and scene sections hide rather than erroring
