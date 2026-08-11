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
