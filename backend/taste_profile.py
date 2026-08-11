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
