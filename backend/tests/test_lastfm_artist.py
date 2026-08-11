from enrich.lastfm_artist import normalize_for_lookup, parse_artist_info


def test_normalize_strips_slash_separators():
    # "Axwell /\\ Ingrosso" fails Last.fm lookup purely on the slashes.
    assert normalize_for_lookup(r"Axwell /\ Ingrosso") == "Axwell Ingrosso"


def test_normalize_collapses_whitespace():
    assert normalize_for_lookup("  Seven   Lions ") == "Seven Lions"


def test_normalize_leaves_ordinary_names_alone():
    assert normalize_for_lookup("Fred again..") == "Fred again.."


def test_parse_extracts_stats_and_tags():
    payload = {
        "artist": {
            "name": "Seven Lions",
            "stats": {"listeners": "530426", "playcount": "39000000"},
            "tags": {"tag": [{"name": "Melodic Dubstep"}, {"name": "Electronic"}]},
        }
    }
    assert parse_artist_info(payload) == {
        "lastfm_name": "Seven Lions",
        "listeners": 530426,
        "playcount": 39000000,
        "tags": ["melodic dubstep", "electronic"],
    }


def test_parse_marks_missing_artist():
    assert parse_artist_info({"error": 6, "message": "not found"}) == {"missing": True}


def test_parse_tolerates_absent_stats():
    payload = {"artist": {"name": "Nobody"}}
    assert parse_artist_info(payload) == {
        "lastfm_name": "Nobody", "listeners": 0, "playcount": 0, "tags": []
    }
