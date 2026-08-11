import pytest

import server


@pytest.fixture
def client():
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


def test_missing_profile_returns_404(client):
    assert client.get("/api/profile/doesnotexist/stats").status_code == 404


def test_stats_payload_has_the_documented_shape(client, monkeypatch):
    monkeypatch.setattr(server, "get_profile", lambda pid, **kw: {
        "id": pid, "name": "Test", "stats": {},
        "music_data": {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]},
    })
    monkeypatch.setattr(server, "list_public_profiles", lambda limit=100: [])

    body = client.get("/api/profile/abc12345/stats").get_json()
    assert set(body) >= {"profile", "stats", "archetype", "badges", "peer_percentile"}
    assert body["profile"]["id"] == "abc12345"


def test_peer_percentile_is_none_below_five_profiles(client, monkeypatch):
    monkeypatch.setattr(server, "get_profile", lambda pid, **kw: {
        "id": pid, "name": "Test", "stats": {},
        "music_data": {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]},
    })
    monkeypatch.setattr(server, "list_public_profiles", lambda limit=100: [{}, {}])

    assert client.get("/api/profile/abc12345/stats").get_json()["peer_percentile"] is None
