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


def test_full_date_and_year_only_agree():
    full = parse_year({"recordings": [{"first-release-date": "1994-08-01"}]})
    year_only = parse_year({"recordings": [{"first-release-date": "1994"}]})
    assert full == year_only == 1994


class _FakeResponse:
    def __init__(self, payload, status_ok=True):
        self._payload = payload
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise RuntimeError("503 Service Unavailable")

    def json(self):
        return self._payload


def _isolate(monkeypatch, tmp_path):
    """Point the store at tmp_path and make the rate limiter instant."""
    from enrich import musicbrainz_years as mb
    monkeypatch.setattr(mb, "DATA_DIR", tmp_path)
    monkeypatch.setattr(mb, "YEARS_PATH", tmp_path / "track_years.json")
    monkeypatch.setattr(mb.time, "sleep", lambda _s: None)
    return mb


def test_genuine_miss_is_cached_and_not_refetched(monkeypatch, tmp_path):
    mb = _isolate(monkeypatch, tmp_path)
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        return _FakeResponse({"recordings": [{}]})    # found, but no date

    monkeypatch.setattr(mb.requests, "get", fake_get)

    years = mb.fetch_missing([("Artist", "Track")])
    key = mb.track_key("Artist", "Track")
    assert key in years and years[key] is None
    assert len(calls) == 1

    # Second run must skip it: a genuine miss is settled, not retried.
    mb.fetch_missing([("Artist", "Track")])
    assert len(calls) == 1


def test_transient_failure_is_not_cached_and_is_retried(monkeypatch, tmp_path):
    mb = _isolate(monkeypatch, tmp_path)
    calls = []

    def failing_get(*args, **kwargs):
        calls.append(1)
        return _FakeResponse({}, status_ok=False)

    monkeypatch.setattr(mb.requests, "get", failing_get)

    years = mb.fetch_missing([("Artist", "Track")])
    assert mb.track_key("Artist", "Track") not in years
    assert len(calls) == 1

    # Second run must try again, because nothing was recorded.
    mb.fetch_missing([("Artist", "Track")])
    assert len(calls) == 2


def test_successful_year_is_persisted_to_disk(monkeypatch, tmp_path):
    mb = _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(mb.requests, "get",
                        lambda *a, **k: _FakeResponse(
                            {"recordings": [{"first-release-date": "2016-05-20"}]}))

    mb.fetch_missing([("Seven Lions", "Strangers")])

    import json
    stored = json.loads((tmp_path / "track_years.json").read_text())
    assert stored[mb.track_key("Seven Lions", "Strangers")] == 2016
