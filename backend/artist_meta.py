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
