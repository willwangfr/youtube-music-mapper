#!/usr/bin/env python3
"""
Profile Manager for Music Taste Social Comparison.
Handles profile creation, storage, and retrieval.
"""

import json
import hashlib
import time
import os
from pathlib import Path
from typing import Optional, List, Dict
from taste_similarity import compute_taste_vector, extract_artist_counts


# Profiles directory
PROFILES_DIR = Path(__file__).parent / "profiles"
GROUPS_DIR = Path(__file__).parent / "groups"


def ensure_dirs():
    """Ensure storage directories exist."""
    PROFILES_DIR.mkdir(exist_ok=True)
    GROUPS_DIR.mkdir(exist_ok=True)


def generate_profile_id(music_data: dict, name: str = "") -> str:
    """
    Generate a unique 8-character profile ID.
    Based on hash of music data + timestamp for uniqueness.
    """
    # Create hash from music data signature
    artists = sorted(extract_artist_counts(music_data).keys())
    content = f"{name}:{len(artists)}:{','.join(artists[:20])}:{time.time()}"
    full_hash = hashlib.sha256(content.encode()).hexdigest()
    return full_hash[:8]


def create_profile(music_data: dict, name: str = "", public: bool = True) -> dict:
    """
    Create a new profile from music data.

    Args:
        music_data: User's music data (liked_songs, etc.)
        name: Optional display name
        public: Whether profile appears in leaderboards

    Returns:
        Profile metadata including shareable ID
    """
    ensure_dirs()

    # Load genre map for taste vector
    genre_map = {}
    genre_map_path = Path(__file__).parent / "genre_map.json"
    if genre_map_path.exists():
        with open(genre_map_path) as f:
            genre_map = json.load(f)

    # Generate ID and compute taste vector
    profile_id = generate_profile_id(music_data, name)
    taste_vector = compute_taste_vector(music_data, genre_map)

    # Get artist counts for stats
    artist_counts = extract_artist_counts(music_data)

    profile = {
        "id": profile_id,
        "name": name or f"Music Fan #{profile_id[:4].upper()}",
        "created_at": int(time.time()),
        "public": public,
        "stats": {
            "artist_count": len(artist_counts),
            "song_count": sum(artist_counts.values()),
            "top_genre": taste_vector.get("top_genre", "Unknown"),
            "diversity_score": taste_vector.get("diversity_score", 0)
        },
        "taste_vector": taste_vector,
        "music_data": music_data
    }

    # Save profile
    profile_path = PROFILES_DIR / f"{profile_id}.json"
    with open(profile_path, 'w') as f:
        json.dump(profile, f, indent=2)

    # Update public index if public
    if public:
        update_public_index(profile)

    return {
        "id": profile_id,
        "name": profile["name"],
        "stats": profile["stats"],
        "share_url": f"/compare/{profile_id}"
    }


def get_profile(profile_id: str, include_music_data: bool = False) -> Optional[dict]:
    """
    Retrieve a profile by ID.

    Args:
        profile_id: The profile's unique ID
        include_music_data: Whether to include full music data (heavy)

    Returns:
        Profile dict or None if not found
    """
    ensure_dirs()
    profile_path = PROFILES_DIR / f"{profile_id}.json"

    if not profile_path.exists():
        return None

    with open(profile_path) as f:
        profile = json.load(f)

    if not include_music_data:
        # Return lightweight version
        return {
            "id": profile["id"],
            "name": profile["name"],
            "created_at": profile["created_at"],
            "stats": profile["stats"],
            "taste_vector": profile["taste_vector"]
        }

    return profile


def get_profile_music_data(profile_id: str) -> Optional[dict]:
    """Get just the music_data for a profile."""
    profile = get_profile(profile_id, include_music_data=True)
    return profile.get("music_data") if profile else None


def list_public_profiles(limit: int = 100) -> List[dict]:
    """List all public profiles (for leaderboard)."""
    ensure_dirs()
    index_path = PROFILES_DIR / "_public_index.json"

    if not index_path.exists():
        return []

    with open(index_path) as f:
        index = json.load(f)

    return index.get("profiles", [])[:limit]


def update_public_index(profile: dict):
    """Add or update a profile in the public index."""
    ensure_dirs()
    index_path = PROFILES_DIR / "_public_index.json"

    if index_path.exists():
        with open(index_path) as f:
            index = json.load(f)
    else:
        index = {"profiles": [], "updated_at": 0}

    # Remove existing entry for this profile
    index["profiles"] = [p for p in index["profiles"] if p["id"] != profile["id"]]

    # Add new entry
    index["profiles"].append({
        "id": profile["id"],
        "name": profile["name"],
        "created_at": profile["created_at"],
        "stats": profile["stats"],
        "top_artists": profile["taste_vector"].get("top_artists", [])[:10]
    })

    index["updated_at"] = int(time.time())

    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)


def delete_profile(profile_id: str) -> bool:
    """Delete a profile."""
    ensure_dirs()
    profile_path = PROFILES_DIR / f"{profile_id}.json"

    if not profile_path.exists():
        return False

    # Remove from public index
    index_path = PROFILES_DIR / "_public_index.json"
    if index_path.exists():
        with open(index_path) as f:
            index = json.load(f)
        index["profiles"] = [p for p in index["profiles"] if p["id"] != profile_id]
        with open(index_path, 'w') as f:
            json.dump(index, f, indent=2)

    # Delete profile file
    profile_path.unlink()
    return True


# ============ Group Management ============

def generate_group_id() -> str:
    """Generate unique group ID."""
    content = f"group:{time.time()}"
    return hashlib.sha256(content.encode()).hexdigest()[:8]


def create_group(name: str = "") -> dict:
    """Create a new comparison group."""
    ensure_dirs()

    group_id = generate_group_id()
    group = {
        "id": group_id,
        "name": name or f"Group #{group_id[:4].upper()}",
        "created_at": int(time.time()),
        "members": []  # List of profile IDs
    }

    group_path = GROUPS_DIR / f"{group_id}.json"
    with open(group_path, 'w') as f:
        json.dump(group, f, indent=2)

    return {
        "id": group_id,
        "name": group["name"],
        "join_url": f"/group/{group_id}/join"
    }


def get_group(group_id: str) -> Optional[dict]:
    """Get a group by ID."""
    ensure_dirs()
    group_path = GROUPS_DIR / f"{group_id}.json"

    if not group_path.exists():
        return None

    with open(group_path) as f:
        return json.load(f)


def join_group(group_id: str, profile_id: str) -> Optional[dict]:
    """Add a profile to a group."""
    group = get_group(group_id)
    if not group:
        return None

    # Verify profile exists
    if not get_profile(profile_id):
        return None

    # Add if not already member
    if profile_id not in group["members"]:
        group["members"].append(profile_id)

        group_path = GROUPS_DIR / f"{group_id}.json"
        with open(group_path, 'w') as f:
            json.dump(group, f, indent=2)

    return group


def get_group_profiles(group_id: str) -> List[dict]:
    """Get all profiles in a group with their music data."""
    group = get_group(group_id)
    if not group:
        return []

    profiles = []
    for profile_id in group["members"]:
        profile = get_profile(profile_id, include_music_data=True)
        if profile:
            profiles.append(profile)

    return profiles


def leave_group(group_id: str, profile_id: str) -> bool:
    """Remove a profile from a group."""
    group = get_group(group_id)
    if not group or profile_id not in group["members"]:
        return False

    group["members"].remove(profile_id)

    group_path = GROUPS_DIR / f"{group_id}.json"
    with open(group_path, 'w') as f:
        json.dump(group, f, indent=2)

    return True


if __name__ == "__main__":
    # Test profile creation
    test_music_data = {
        "liked_songs": [
            {"title": "Song 1", "artists": [{"name": "Test Artist"}]},
            {"title": "Song 2", "artists": [{"name": "Test Artist"}]},
            {"title": "Song 3", "artists": [{"name": "Another Artist"}]},
        ]
    }

    print("Creating test profile...")
    result = create_profile(test_music_data, name="Test User")
    print(f"Created: {result}")

    print("\nRetrieving profile...")
    profile = get_profile(result["id"])
    print(f"Retrieved: {profile}")

    print("\nCreating group...")
    group = create_group("Test Group")
    print(f"Created group: {group}")

    print("\nJoining group...")
    joined = join_group(group["id"], result["id"])
    print(f"Joined: {joined}")

    print("\nCleaning up...")
    delete_profile(result["id"])
    print("Done!")
