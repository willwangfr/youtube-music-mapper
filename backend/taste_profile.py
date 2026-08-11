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
    # Local import: enrich.musicbrainz_years imports artist_meta, and a
    # module-level import here risks a cycle with artist_meta's own
    # module-level import of taste_profile.
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
    """Assemble every metric the profile page and archetype rules consume.

    Three different song totals appear here and they legitimately disagree:

      song_count      raw entries in liked_songs (3039 on the reference library)
      year_coverage   fraction of UNIQUE (artist, title) pairs with a known year,
                      a ~10% smaller population because it dedups repeats
      one_song_share / gini / top_artists / largest_artist_songs
                      derived from artist-song appearances, a ~6% larger
                      population because a collaboration is credited to each
                      constituent artist

    Anything rendering these must label them accordingly — "share of your
    tracks" is not interchangeable with "share of your songs" here.
    """
    counts = artist_song_counts(library)
    genres = genre_distribution(counts, meta)
    eras = decade_distribution(library, years)
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
