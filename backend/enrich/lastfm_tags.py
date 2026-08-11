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
