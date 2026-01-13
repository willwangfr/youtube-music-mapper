#!/usr/bin/env python3
"""
Taste Similarity Algorithms for Music Profile Comparison.
Implements Jaccard, Cosine, and Weighted similarity metrics.
"""

import math
from collections import Counter
from typing import Dict, List, Tuple, Set


def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """
    Calculate Jaccard similarity: |A ∩ B| / |A ∪ B|
    Returns value between 0 and 1.
    """
    if not set1 and not set2:
        return 1.0  # Both empty = identical
    if not set1 or not set2:
        return 0.0

    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
    """
    Calculate cosine similarity between two sparse vectors.
    Vectors are dicts mapping keys to weights.
    Returns value between 0 and 1.
    """
    # Get all keys
    all_keys = set(vec1.keys()) | set(vec2.keys())
    if not all_keys:
        return 1.0

    # Calculate dot product and magnitudes
    dot_product = 0.0
    mag1 = 0.0
    mag2 = 0.0

    for key in all_keys:
        v1 = vec1.get(key, 0.0)
        v2 = vec2.get(key, 0.0)
        dot_product += v1 * v2
        mag1 += v1 * v1
        mag2 += v2 * v2

    mag1 = math.sqrt(mag1)
    mag2 = math.sqrt(mag2)

    if mag1 == 0 or mag2 == 0:
        return 0.0

    return dot_product / (mag1 * mag2)


def weighted_overlap(counts1: Dict[str, int], counts2: Dict[str, int]) -> float:
    """
    Calculate weighted overlap based on song counts per artist.
    Uses min/max to measure how much listening overlap exists.
    Returns value between 0 and 1.
    """
    all_artists = set(counts1.keys()) | set(counts2.keys())
    if not all_artists:
        return 1.0

    min_sum = 0
    max_sum = 0

    for artist in all_artists:
        c1 = counts1.get(artist, 0)
        c2 = counts2.get(artist, 0)
        min_sum += min(c1, c2)
        max_sum += max(c1, c2)

    return min_sum / max_sum if max_sum > 0 else 0.0


def extract_artist_counts(music_data: dict) -> Dict[str, int]:
    """Extract artist -> song count mapping from music data."""
    counts = Counter()
    for song in music_data.get('liked_songs', []):
        for artist in song.get('artists', []):
            name = artist.get('name', '')
            if name:
                counts[name] += 1
    return dict(counts)


def extract_genre_vector(music_data: dict, genre_map: dict) -> Dict[str, float]:
    """
    Create normalized genre distribution vector.
    Returns dict of genre -> weight (0-1, sums to 1).
    """
    genre_counts = Counter()
    total = 0

    for song in music_data.get('liked_songs', []):
        for artist in song.get('artists', []):
            name = artist.get('name', '')
            genre = genre_map.get(name, 'Other')
            genre_counts[genre] += 1
            total += 1

    if total == 0:
        return {}

    # Normalize to sum to 1
    return {genre: count / total for genre, count in genre_counts.items()}


def calculate_similarity(profile1: dict, profile2: dict, genre_map: dict = None) -> dict:
    """
    Calculate comprehensive similarity between two music profiles.

    Args:
        profile1: First user's music_data
        profile2: Second user's music_data
        genre_map: Optional artist -> genre mapping

    Returns:
        dict with similarity scores and shared/unique artists
    """
    genre_map = genre_map or {}

    # Extract artist data
    counts1 = extract_artist_counts(profile1)
    counts2 = extract_artist_counts(profile2)

    artists1 = set(counts1.keys())
    artists2 = set(counts2.keys())

    # Calculate individual metrics
    artist_jaccard = jaccard_similarity(artists1, artists2)
    artist_weighted = weighted_overlap(counts1, counts2)

    # Genre similarity
    genre_vec1 = extract_genre_vector(profile1, genre_map)
    genre_vec2 = extract_genre_vector(profile2, genre_map)
    genre_cosine = cosine_similarity(genre_vec1, genre_vec2)

    # Overall score (weighted combination)
    overall = (
        0.40 * artist_jaccard +
        0.30 * artist_weighted +
        0.30 * genre_cosine
    )

    # Find shared and unique artists
    shared_artists = artists1 & artists2
    unique_to_1 = artists1 - artists2
    unique_to_2 = artists2 - artists1

    # Sort shared by combined listening (most listened first)
    shared_sorted = sorted(
        shared_artists,
        key=lambda a: counts1.get(a, 0) + counts2.get(a, 0),
        reverse=True
    )

    # Sort unique by listening count
    unique_1_sorted = sorted(unique_to_1, key=lambda a: counts1.get(a, 0), reverse=True)
    unique_2_sorted = sorted(unique_to_2, key=lambda a: counts2.get(a, 0), reverse=True)

    return {
        "overall": round(overall * 100, 1),  # 0-100%
        "artist_overlap": round(artist_jaccard * 100, 1),
        "weighted_overlap": round(artist_weighted * 100, 1),
        "genre_match": round(genre_cosine * 100, 1),
        "shared_artists": shared_sorted[:50],  # Top 50
        "shared_count": len(shared_artists),
        "unique_to_profile1": unique_1_sorted[:30],
        "unique_to_profile2": unique_2_sorted[:30],
        "profile1_artist_count": len(artists1),
        "profile2_artist_count": len(artists2),
        "genre_breakdown": {
            "profile1": genre_vec1,
            "profile2": genre_vec2
        }
    }


def calculate_group_similarity(profiles: List[dict], genre_map: dict = None) -> dict:
    """
    Calculate pairwise similarity matrix for a group of profiles.

    Args:
        profiles: List of dicts with 'id', 'name', 'music_data'
        genre_map: Optional artist -> genre mapping

    Returns:
        dict with pairwise matrix, consensus artists, and stats
    """
    genre_map = genre_map or {}
    n = len(profiles)

    if n < 2:
        return {"error": "Need at least 2 profiles to compare"}

    # Extract all artist counts
    all_counts = []
    all_artists_sets = []
    for p in profiles:
        counts = extract_artist_counts(p['music_data'])
        all_counts.append(counts)
        all_artists_sets.append(set(counts.keys()))

    # Pairwise similarity matrix
    matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(100.0)  # Self-similarity
            elif i < j:
                result = calculate_similarity(
                    profiles[i]['music_data'],
                    profiles[j]['music_data'],
                    genre_map
                )
                row.append(result['overall'])
            else:
                row.append(matrix[j][i])  # Symmetric
        matrix.append(row)

    # Find consensus artists (in everyone's library)
    if all_artists_sets:
        consensus = set.intersection(*all_artists_sets)
    else:
        consensus = set()

    # Sort consensus by total listening across group
    consensus_sorted = sorted(
        consensus,
        key=lambda a: sum(c.get(a, 0) for c in all_counts),
        reverse=True
    )

    # Find bridge artists (connect different people)
    # Artists that appear in some but not all profiles
    all_artists = set.union(*all_artists_sets) if all_artists_sets else set()
    bridge_artists = []
    for artist in all_artists:
        in_profiles = sum(1 for s in all_artists_sets if artist in s)
        if 1 < in_profiles < n:  # In some but not all
            bridge_artists.append({
                "name": artist,
                "in_profiles": in_profiles,
                "total_songs": sum(c.get(artist, 0) for c in all_counts)
            })

    bridge_artists.sort(key=lambda x: (-x['in_profiles'], -x['total_songs']))

    # Calculate average compatibility for each person
    avg_compatibility = []
    for i in range(n):
        others = [matrix[i][j] for j in range(n) if i != j]
        avg = sum(others) / len(others) if others else 0
        avg_compatibility.append({
            "id": profiles[i]['id'],
            "name": profiles[i].get('name', f'Profile {i+1}'),
            "avg_compatibility": round(avg, 1)
        })

    return {
        "matrix": matrix,
        "profile_ids": [p['id'] for p in profiles],
        "profile_names": [p.get('name', f'Profile {i+1}') for i, p in enumerate(profiles)],
        "consensus_artists": consensus_sorted[:20],
        "bridge_artists": bridge_artists[:20],
        "avg_compatibility": avg_compatibility,
        "group_avg": round(
            sum(matrix[i][j] for i in range(n) for j in range(i+1, n)) / (n * (n-1) / 2)
            if n > 1 else 0,
            1
        )
    }


def compute_taste_vector(music_data: dict, genre_map: dict = None) -> dict:
    """
    Precompute a taste vector for fast similarity search.
    Used for leaderboard/discovery features.
    """
    genre_map = genre_map or {}

    counts = extract_artist_counts(music_data)
    genre_vec = extract_genre_vector(music_data, genre_map)

    # Get top artists (for quick comparison)
    top_artists = sorted(counts.keys(), key=lambda a: counts[a], reverse=True)[:100]

    # Diversity score: how spread across genres (entropy-like)
    total_songs = sum(counts.values())
    diversity = 0.0
    if genre_vec:
        for weight in genre_vec.values():
            if weight > 0:
                diversity -= weight * math.log(weight)
        # Normalize by max possible entropy
        max_entropy = math.log(len(genre_vec)) if len(genre_vec) > 1 else 1
        diversity = diversity / max_entropy if max_entropy > 0 else 0

    return {
        "genre_weights": genre_vec,
        "top_artists": top_artists,
        "artist_count": len(counts),
        "song_count": total_songs,
        "diversity_score": round(diversity, 3),
        "top_genre": max(genre_vec.items(), key=lambda x: x[1])[0] if genre_vec else "Unknown"
    }


if __name__ == "__main__":
    # Test with sample data
    profile1 = {
        "liked_songs": [
            {"title": "Song 1", "artists": [{"name": "Artist A"}]},
            {"title": "Song 2", "artists": [{"name": "Artist A"}]},
            {"title": "Song 3", "artists": [{"name": "Artist B"}]},
            {"title": "Song 4", "artists": [{"name": "Artist C"}]},
        ]
    }

    profile2 = {
        "liked_songs": [
            {"title": "Song 5", "artists": [{"name": "Artist A"}]},
            {"title": "Song 6", "artists": [{"name": "Artist B"}]},
            {"title": "Song 7", "artists": [{"name": "Artist D"}]},
            {"title": "Song 8", "artists": [{"name": "Artist D"}]},
        ]
    }

    result = calculate_similarity(profile1, profile2)
    print("Similarity Test:")
    print(f"  Overall: {result['overall']}%")
    print(f"  Artist Overlap: {result['artist_overlap']}%")
    print(f"  Shared: {result['shared_artists']}")
    print(f"  Unique to P1: {result['unique_to_profile1']}")
    print(f"  Unique to P2: {result['unique_to_profile2']}")
