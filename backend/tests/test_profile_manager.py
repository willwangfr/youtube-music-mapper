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
