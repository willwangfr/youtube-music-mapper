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
