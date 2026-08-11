import pytest

from enrich.lastfm_tags import GENRE_TAG_QUERIES, parse_top_artist_names


def test_every_query_maps_to_a_known_genre():
    from taste_profile import GENRE_VOCABULARY
    assert set(GENRE_TAG_QUERIES).issubset(set(GENRE_VOCABULARY))


def test_parse_returns_artist_names_in_order():
    payload = {"topartists": {"artist": [{"name": "A"}, {"name": "B"}]}}
    assert parse_top_artist_names(payload) == ["A", "B"]


def test_parse_skips_entries_without_a_name():
    payload = {"topartists": {"artist": [{"mbid": "x"}, {"name": "B"}]}}
    assert parse_top_artist_names(payload) == ["B"]


def test_parse_handles_empty_payload():
    from enrich.lastfm_tags import LastfmError
    with pytest.raises(LastfmError):
        parse_top_artist_names({})


def test_error_envelope_raises():
    from enrich.lastfm_tags import LastfmError
    with pytest.raises(LastfmError):
        parse_top_artist_names({"error": 6, "message": "invalid tag"})


def test_missing_topartists_key_raises():
    from enrich.lastfm_tags import LastfmError
    with pytest.raises(LastfmError):
        parse_top_artist_names({"something": "else"})


def test_genuinely_empty_population_is_not_an_error():
    assert parse_top_artist_names({"topartists": {"artist": []}}) == []


def test_redact_removes_the_api_key():
    from enrich.lastfm_tags import redact
    msg = "403 for url: https://ws.audioscrobbler.com/2.0/?method=x&api_key=abc123secret&format=json"
    out = redact(msg)
    assert "abc123secret" not in out
    assert "<redacted>" in out
