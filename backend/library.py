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
