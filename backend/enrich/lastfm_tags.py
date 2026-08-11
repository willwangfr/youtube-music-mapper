"""Build per-genre listener distributions from Last.fm's top artists per tag.

Scene-relative obscurity compares a person's artists against others in the
same scene; using their own library as that population would be circular.
"""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from artist_meta import DATA_DIR, load_meta  # noqa: E402
from enrich.lastfm_artist import API_URL, _Throttle, REQUESTS_PER_SECOND  # noqa: E402
from enrich.lastfm_artist import fetch_missing as fetch_artists  # noqa: E402

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


class LastfmError(RuntimeError):
    """Last.fm reports failures as a 200 with an error envelope."""


def parse_top_artist_names(payload: dict) -> list:
    """tag.gettopartists returns names only - no listener counts - so the
    population has to be assembled from artist.getInfo afterwards."""
    if "error" in payload:
        raise LastfmError(str(payload.get("message", payload["error"]))[:120])
    if "topartists" not in payload:
        raise LastfmError("no topartists in response")
    artists = (payload.get("topartists", {}) or {}).get("artist", []) or []
    return [a["name"] for a in artists if a.get("name")]


def _save(reference: dict) -> None:
    """Atomic, so an interrupt cannot leave a half-written store behind."""
    DATA_DIR.mkdir(exist_ok=True)
    tmp = REFERENCE_PATH.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(reference, f)
    tmp.replace(REFERENCE_PATH)


def build_reference(api_key: str, limit: int = 100) -> dict:
    throttle = _Throttle(REQUESTS_PER_SECOND)
    reference = {}
    if REFERENCE_PATH.exists():
        try:
            with open(REFERENCE_PATH) as f:
                reference = json.load(f)
        except ValueError:
            # A corrupt store is worth rebuilding, not crashing over.
            print("  genre_reference.json unreadable; rebuilding", flush=True)

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
            response.raise_for_status()
            names = parse_top_artist_names(response.json())
        except Exception as exc:
            # Left absent rather than cached, so the next run retries it.
            print(f"  {genre}: {exc}", flush=True)
            continue
        # Listener counts come from artist.getInfo, which caches them into the
        # shared store so the cost is paid once across all genres.
        fetch_artists(names, api_key)
        meta = load_meta()
        population = sorted(
            (meta[n]["listeners"] for n in names
             if n in meta and meta[n].get("listeners")),
            reverse=True,
        )
        if not population:
            print(f"  {genre}: no listener data resolved, leaving for retry", flush=True)
            continue
        reference[genre] = population
        _save(reference)

    return reference
