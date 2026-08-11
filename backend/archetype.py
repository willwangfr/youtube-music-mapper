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
    ("mainstream", "omnivore"): "Main Stage Omnivore",
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
