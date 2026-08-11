from enrich.musicbrainz_years import track_key, parse_year


def test_track_key_is_case_insensitive_and_stable():
    assert track_key("Seven Lions", "Strangers") == track_key("seven lions", "STRANGERS")


def test_track_key_separates_artist_and_title():
    assert track_key("A", "B") == "a|b"


def test_parse_year_takes_earliest_release():
    payload = {"recordings": [
        {"first-release-date": "2016-05-20"},
        {"first-release-date": "2014-01-01"},
    ]}
    assert parse_year(payload) == 2014


def test_parse_year_accepts_year_only_dates():
    assert parse_year({"recordings": [{"first-release-date": "1973"}]}) == 1973


def test_parse_year_returns_none_when_absent():
    assert parse_year({"recordings": [{}]}) is None


def test_parse_year_returns_none_for_empty_result():
    assert parse_year({"recordings": []}) is None


def test_parse_year_ignores_malformed_dates():
    assert parse_year({"recordings": [{"first-release-date": "not-a-date"}]}) is None


def test_genuine_miss_is_cached_as_none():
    # A track MusicBrainz has no date for should not be re-requested forever.
    assert parse_year({"recordings": [{}]}) is None


def test_year_from_full_date_and_year_only_agree():
    assert parse_year({"recordings": [{"first-release-date": "1994-08-01"}]}) == 1994
