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
