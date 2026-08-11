import pytest

from archetype import (
    obscurity_axis, diversity_axis, era_axis, resolve_archetype, compute_badges,
)


def test_obscurity_axis_buckets():
    assert obscurity_axis(10.0) == "mainstream"
    assert obscurity_axis(45.0) == "balanced"
    assert obscurity_axis(80.0) == "underground"


def test_obscurity_axis_boundaries_are_inclusive_downward():
    assert obscurity_axis(30.0) == "mainstream"
    assert obscurity_axis(30.1) == "balanced"
    assert obscurity_axis(65.0) == "balanced"
    assert obscurity_axis(65.1) == "underground"


def test_obscurity_axis_handles_missing_data():
    assert obscurity_axis(None) == "balanced"


def test_diversity_axis_buckets():
    assert diversity_axis(0.20) == "focused"
    assert diversity_axis(0.50) == "broad"
    assert diversity_axis(0.80) == "omnivore"


def test_era_axis_buckets():
    assert era_axis(1985) == "retro"
    assert era_axis(2008) == "mixed"
    assert era_axis(2023) == "current"
    assert era_axis(None) == "unknown"


def test_archetype_names_the_dominant_genre():
    stats = {"obscurity": 20.0, "diversity": 0.7, "median_year": 2021,
             "genres": {"Dubstep/Bass": 0.5, "Pop": 0.5}}
    result = resolve_archetype(stats)
    assert "Dubstep/Bass" in result["tagline"]
    assert isinstance(result["name"], str) and result["name"]


def test_archetype_is_deterministic():
    stats = {"obscurity": 20.0, "diversity": 0.7, "median_year": 2021,
             "genres": {"Pop": 1.0}}
    assert resolve_archetype(stats) == resolve_archetype(stats)


def test_archetype_differs_across_obscurity_buckets():
    base = {"diversity": 0.5, "median_year": 2020, "genres": {"Pop": 1.0}}
    mainstream = resolve_archetype({**base, "obscurity": 10.0})["name"]
    underground = resolve_archetype({**base, "obscurity": 90.0})["name"]
    assert mainstream != underground


def test_archetype_survives_an_empty_genre_map():
    result = resolve_archetype({"obscurity": None, "diversity": 0.0,
                                "median_year": None, "genres": {}})
    assert result["name"]


def test_badges_trigger_on_fixed_thresholds():
    stats = {"one_song_share": 0.64, "top_genre_share": 0.15, "gini": 0.54,
             "largest_artist_songs": 95, "clusters": [], "song_count": 3039}
    badges = compute_badges(stats)
    assert any("one" in b["id"] for b in badges)


def test_badges_are_capped_at_three():
    stats = {"one_song_share": 0.9, "top_genre_share": 0.9, "gini": 0.9,
             "largest_artist_songs": 500, "clusters": [{"size": 20}] * 8,
             "song_count": 1000}
    assert len(compute_badges(stats)) <= 3


def test_badges_are_empty_when_nothing_is_notable():
    stats = {"one_song_share": 0.1, "top_genre_share": 0.1, "gini": 0.1,
             "largest_artist_songs": 2, "clusters": [], "song_count": 100}
    assert compute_badges(stats) == []


def test_badges_carry_a_label_and_value():
    stats = {"one_song_share": 0.64, "top_genre_share": 0.1, "gini": 0.1,
             "largest_artist_songs": 2, "clusters": [], "song_count": 100}
    badge = compute_badges(stats)[0]
    assert set(badge) >= {"id", "label", "value"}


def test_other_never_appears_in_the_tagline():
    stats = {"obscurity": 20.0, "diversity": 0.7, "median_year": 2021,
             "genres": {"Other": 0.6, "Dubstep/Bass": 0.4}}
    result = resolve_archetype(stats)
    assert "Other" not in result["tagline"]
    assert "Dubstep/Bass" in result["tagline"]


def test_an_entirely_unresolved_library_names_no_genre():
    result = resolve_archetype({"obscurity": 20.0, "diversity": 0.7,
                                "median_year": 2021, "genres": {"Other": 1.0}})
    assert "Other" not in result["tagline"]
    assert result["name"]
