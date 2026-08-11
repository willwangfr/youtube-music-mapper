import pytest

from enrich.lastfm_tags import GENRE_TAG_QUERIES, parse_top_artists


@pytest.mark.xfail(reason="GENRE_VOCABULARY lands in Task 7; remove this marker there")
def test_every_query_maps_to_a_known_genre():
    from taste_profile import GENRE_VOCABULARY
    assert set(GENRE_TAG_QUERIES).issubset(set(GENRE_VOCABULARY))


def test_parse_returns_descending_listener_counts():
    payload = {"topartists": {"artist": [
        {"name": "A", "listeners": "100"},
        {"name": "B", "listeners": "5000"},
        {"name": "C", "listeners": "300"},
    ]}}
    assert parse_top_artists(payload) == [5000, 300, 100]


def test_parse_skips_entries_without_listeners():
    payload = {"topartists": {"artist": [
        {"name": "A", "listeners": "0"},
        {"name": "B", "listeners": "42"},
    ]}}
    assert parse_top_artists(payload) == [42]


def test_parse_handles_empty_payload():
    assert parse_top_artists({}) == []
