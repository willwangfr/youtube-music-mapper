import json

import profile_manager


def test_profiles_are_private_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    data = {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]}

    result = profile_manager.create_profile(data, name="Test")
    stored = json.loads((tmp_path / "profiles" / f"{result['id']}.json").read_text())
    assert stored["public"] is False


def test_public_index_is_not_written_for_private_profiles(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    data = {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]}

    profile_manager.create_profile(data, name="Test")
    assert not (tmp_path / "profiles" / "_public_index.json").exists()


def test_opting_in_writes_the_public_index(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    data = {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]}

    profile_manager.create_profile(data, name="Test", public=True)
    assert (tmp_path / "profiles" / "_public_index.json").exists()


# ============ Ownership token ============

def test_create_profile_returns_owner_token_but_stores_only_its_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    data = {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]}

    result = profile_manager.create_profile(data, name="Test")
    assert "owner_token" in result
    assert result["owner_token"]

    stored = json.loads((tmp_path / "profiles" / f"{result['id']}.json").read_text())
    assert stored["owner_token_hash"] == profile_manager._hash_token(result["owner_token"])
    assert "owner_token" not in stored


def test_delete_profile_with_correct_token_deletes_it(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    data = {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]}
    result = profile_manager.create_profile(data, name="Test")
    profile_path = tmp_path / "profiles" / f"{result['id']}.json"

    outcome = profile_manager.delete_profile(result["id"], result["owner_token"])
    assert outcome == "deleted"
    assert not profile_path.exists()


def test_delete_profile_with_wrong_token_is_forbidden_and_keeps_file(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    data = {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]}
    result = profile_manager.create_profile(data, name="Test")
    profile_path = tmp_path / "profiles" / f"{result['id']}.json"

    outcome = profile_manager.delete_profile(result["id"], "not-the-real-token")
    assert outcome == "forbidden"
    assert profile_path.exists()


def test_delete_profile_without_owner_token_hash_is_forbidden(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    profile_path = profiles_dir / "legacy123.json"
    profile_path.write_text(json.dumps({
        "id": "legacy123", "name": "Legacy", "created_at": 0, "public": False,
        "stats": {}, "taste_vector": {}, "music_data": {}
    }))

    outcome = profile_manager.delete_profile("legacy123", "any-token-at-all")
    assert outcome == "forbidden"
    assert profile_path.exists()


def test_delete_profile_missing_id_is_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")

    assert profile_manager.delete_profile("doesnotexist", "whatever") == "not_found"


def test_get_profile_full_does_not_leak_owner_token_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    data = {"liked_songs": [{"title": "s", "artists": [{"name": "A"}]}]}
    result = profile_manager.create_profile(data, name="Test")

    full = profile_manager.get_profile(result["id"], include_music_data=True)
    assert "owner_token_hash" not in full
