"""
Flask API server for YouTube Music Mapper.
Provides endpoints for fetching music data and graph visualization.
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from ytmusic_client import YTMusicClient, export_user_data
from graph_builder import MusicGraphBuilder
from profile_manager import (
    create_profile, get_profile, get_profile_music_data, list_public_profiles,
    delete_profile, create_group, get_group, join_group, get_group_profiles, leave_group
)
from taste_similarity import calculate_similarity, calculate_group_similarity, compute_taste_vector
import spotify_client
import os
import json
import requests
import urllib.parse
import zipfile
import csv
import io
import re
import tempfile

# Last.fm API - get your free key at https://www.last.fm/api/account/create
LASTFM_API_KEY = os.environ.get('LASTFM_API_KEY', '')

# Store Spotify tokens in memory (in production, use a proper session store)
spotify_tokens = {}

app = Flask(__name__, static_folder="../frontend")
CORS(app)

client = YTMusicClient()
graph_builder = MusicGraphBuilder()


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(os.path.join(app.static_folder, "js"), filename)


@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(os.path.join(app.static_folder, "css"), filename)


@app.route("/api/status")
def status():
    """Check authentication status."""
    # Check if we have imported data
    has_data = os.path.exists("music_data.json")
    if has_data:
        with open("music_data.json", "r") as f:
            data = json.load(f)
            song_count = len(data.get("liked_songs", []))
            artist_count = len(data.get("library_artists", []))
        return jsonify({
            "authenticated": True,
            "message": f"Using imported data: {song_count} songs, {artist_count} artists",
            "mode": "imported"
        })

    # Fall back to ytmusicapi auth
    try:
        authenticated = client.authenticate()
        return jsonify({
            "authenticated": authenticated,
            "message": "Connected to YouTube Music" if authenticated else "Not authenticated",
            "mode": "api"
        })
    except Exception as e:
        return jsonify({
            "authenticated": False,
            "message": f"Not authenticated: {str(e)}",
            "mode": "none"
        })


@app.route("/api/auth/setup", methods=["POST"])
def setup_auth():
    """Receive authentication headers from browser."""
    headers = request.json
    if not headers:
        return jsonify({"error": "No headers provided"}), 400

    # Save headers to browser.json
    with open("browser.json", "w") as f:
        json.dump(headers, f)

    # Try to authenticate
    if client.authenticate():
        return jsonify({"success": True, "message": "Authentication successful"})
    else:
        return jsonify({"error": "Authentication failed"}), 401


@app.route("/api/export")
def export_data():
    """Export user's music data to JSON."""
    if not client.authenticate():
        return jsonify({"error": "Not authenticated"}), 401

    data = export_user_data(client, "music_data.json")
    return jsonify({
        "success": True,
        "stats": {
            "artists": len(data["library_artists"]),
            "liked_songs": len(data["liked_songs"]),
            "history": len(data["history"])
        }
    })


@app.route("/api/graph")
def get_graph():
    """Get graph data for visualization."""
    # Check if we have pre-built graph data
    graph_file = "../frontend/graph_data.json"
    if os.path.exists(graph_file):
        with open(graph_file, "r") as f:
            return jsonify(json.load(f))

    # Try to build from music_data.json
    if os.path.exists("music_data.json"):
        builder = MusicGraphBuilder()
        builder.load_from_json("music_data.json")

        # Add related artists if authenticated (optional)
        try:
            if client.authenticate():
                builder.add_related_artists(client, limit_per_artist=3)
        except Exception:
            pass  # Skip related artists if auth fails

        graph_data = builder.export_for_visualization(graph_file)
        return jsonify(graph_data)

    return jsonify({"error": "No music data available. Run /api/export first"}), 404


@app.route("/api/artist/<artist_id>")
def get_artist(artist_id):
    """Get detailed artist information."""
    if not client.authenticate():
        return jsonify({"error": "Not authenticated"}), 401

    info = client.get_artist_info(artist_id)
    if info:
        return jsonify(info)
    return jsonify({"error": "Artist not found"}), 404


@app.route("/api/search")
def search():
    """Search for artists."""
    if not client.authenticate():
        return jsonify({"error": "Not authenticated"}), 401

    query = request.args.get("q", "")
    if not query:
        return jsonify({"error": "No query provided"}), 400

    results = client.search_artist(query)
    return jsonify({"results": results})


@app.route("/api/library/artists")
def get_library_artists():
    """Get user's library artists."""
    if not client.authenticate():
        return jsonify({"error": "Not authenticated"}), 401

    artists = client.get_library_artists(limit=100)
    return jsonify({"artists": artists})


@app.route("/api/library/liked")
def get_liked_songs():
    """Get user's liked songs."""
    if not client.authenticate():
        return jsonify({"error": "Not authenticated"}), 401

    songs = client.get_liked_songs(limit=200)
    return jsonify({"songs": songs})


@app.route("/api/similar/<artist_name>")
def get_similar_artists(artist_name):
    """Get similar artists from Last.fm API."""
    if not LASTFM_API_KEY:
        return jsonify({"error": "Last.fm API key not configured. Set LASTFM_API_KEY environment variable."}), 500

    try:
        # URL encode the artist name
        encoded_name = urllib.parse.quote(artist_name)
        url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist={encoded_name}&api_key={LASTFM_API_KEY}&format=json&limit=20"

        response = requests.get(url, timeout=10)
        data = response.json()

        if 'error' in data:
            return jsonify({"error": data.get('message', 'Artist not found')}), 404

        similar = data.get('similarartists', {}).get('artist', [])

        # Format the response
        artists = []
        for a in similar:
            artists.append({
                'name': a.get('name', ''),
                'match': float(a.get('match', 0)),
                'url': a.get('url', ''),
                'image': next((img.get('#text') for img in a.get('image', []) if img.get('size') == 'medium'), '')
            })

        return jsonify({
            'artist': artist_name,
            'similar': artists
        })
    except requests.exceptions.Timeout:
        return jsonify({"error": "Last.fm API timeout"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/lastfm/status")
def lastfm_status():
    """Check if Last.fm API is configured."""
    return jsonify({
        "configured": bool(LASTFM_API_KEY),
        "message": "Last.fm API ready" if LASTFM_API_KEY else "Set LASTFM_API_KEY to enable similar artists"
    })


# ============ Social Comparison Routes ============

def load_genre_map():
    """Load genre map for similarity calculations."""
    genre_map_path = "genre_map.json"
    if os.path.exists(genre_map_path):
        with open(genre_map_path) as f:
            return json.load(f)
    return {}


@app.route("/compare/<profile_id>")
def compare_page(profile_id):
    """Serve the comparison page."""
    return send_from_directory(app.static_folder, "compare.html")


@app.route("/group/<group_id>")
@app.route("/group/<group_id>/join")
def group_page(group_id):
    """Serve the group comparison page."""
    return send_from_directory(app.static_folder, "compare.html")


@app.route("/leaderboard")
def leaderboard_page():
    """Serve the leaderboard/discovery page."""
    return send_from_directory(app.static_folder, "leaderboard.html")


@app.route("/api/profile/create", methods=["POST"])
def api_create_profile():
    """Create a new taste profile from music data."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Accept either direct music_data or use current user's data
    music_data = data.get("music_data")
    name = data.get("name", "")
    public = data.get("public", True)

    if not music_data:
        # Try to use current user's music_data.json
        if os.path.exists("music_data.json"):
            with open("music_data.json") as f:
                music_data = json.load(f)
        else:
            return jsonify({"error": "No music data provided or available"}), 400

    result = create_profile(music_data, name=name, public=public)
    return jsonify(result)


@app.route("/api/profile/<profile_id>")
def api_get_profile(profile_id):
    """Get profile metadata (without full music data)."""
    profile = get_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify(profile)


@app.route("/api/profile/<profile_id>/full")
def api_get_profile_full(profile_id):
    """Get full profile including music data."""
    profile = get_profile(profile_id, include_music_data=True)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify(profile)


@app.route("/api/profile/<profile_id>", methods=["DELETE"])
def api_delete_profile(profile_id):
    """Delete a profile."""
    if delete_profile(profile_id):
        return jsonify({"success": True})
    return jsonify({"error": "Profile not found"}), 404


@app.route("/api/compare/<profile_id1>/<profile_id2>")
def api_compare_profiles(profile_id1, profile_id2):
    """Compare two profiles and return similarity metrics."""
    # Get music data for both profiles
    music_data1 = get_profile_music_data(profile_id1)
    music_data2 = get_profile_music_data(profile_id2)

    if not music_data1:
        return jsonify({"error": f"Profile {profile_id1} not found"}), 404
    if not music_data2:
        return jsonify({"error": f"Profile {profile_id2} not found"}), 404

    # Get profile metadata
    profile1 = get_profile(profile_id1)
    profile2 = get_profile(profile_id2)

    genre_map = load_genre_map()
    result = calculate_similarity(music_data1, music_data2, genre_map)

    # Add profile info
    result["profile1"] = {
        "id": profile_id1,
        "name": profile1.get("name", "Unknown")
    }
    result["profile2"] = {
        "id": profile_id2,
        "name": profile2.get("name", "Unknown")
    }

    return jsonify(result)


@app.route("/api/compare/with-current/<profile_id>")
def api_compare_with_current(profile_id):
    """Compare a profile with current user's music data."""
    # Get target profile's music data
    target_music_data = get_profile_music_data(profile_id)
    if not target_music_data:
        return jsonify({"error": "Profile not found"}), 404

    # Get current user's music data
    if not os.path.exists("music_data.json"):
        return jsonify({"error": "No local music data. Create a profile first."}), 400

    with open("music_data.json") as f:
        current_music_data = json.load(f)

    target_profile = get_profile(profile_id)
    genre_map = load_genre_map()

    result = calculate_similarity(current_music_data, target_music_data, genre_map)

    result["profile1"] = {"id": "current", "name": "You"}
    result["profile2"] = {
        "id": profile_id,
        "name": target_profile.get("name", "Unknown")
    }

    return jsonify(result)


# ============ Group Comparison Routes ============

@app.route("/api/group/create", methods=["POST"])
def api_create_group():
    """Create a new comparison group."""
    data = request.json or {}
    name = data.get("name", "")
    result = create_group(name)
    return jsonify(result)


@app.route("/api/group/<group_id>")
def api_get_group(group_id):
    """Get group info and member list."""
    group = get_group(group_id)
    if not group:
        return jsonify({"error": "Group not found"}), 404

    # Add profile names for each member
    members = []
    for profile_id in group["members"]:
        profile = get_profile(profile_id)
        if profile:
            members.append({
                "id": profile_id,
                "name": profile.get("name", "Unknown"),
                "stats": profile.get("stats", {})
            })

    return jsonify({
        "id": group["id"],
        "name": group["name"],
        "created_at": group["created_at"],
        "members": members,
        "member_count": len(members)
    })


@app.route("/api/group/<group_id>/join", methods=["POST"])
def api_join_group(group_id):
    """Join a group with a profile."""
    data = request.json
    if not data or "profile_id" not in data:
        return jsonify({"error": "profile_id required"}), 400

    result = join_group(group_id, data["profile_id"])
    if not result:
        return jsonify({"error": "Group or profile not found"}), 404

    return jsonify({"success": True, "members": result["members"]})


@app.route("/api/group/<group_id>/leave", methods=["POST"])
def api_leave_group(group_id):
    """Leave a group."""
    data = request.json
    if not data or "profile_id" not in data:
        return jsonify({"error": "profile_id required"}), 400

    if leave_group(group_id, data["profile_id"]):
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/group/<group_id>/results")
def api_group_results(group_id):
    """Get group comparison results with pairwise matrix."""
    profiles = get_group_profiles(group_id)
    if not profiles:
        return jsonify({"error": "Group not found or empty"}), 404

    if len(profiles) < 2:
        return jsonify({"error": "Need at least 2 members to compare"}), 400

    genre_map = load_genre_map()

    # Format profiles for group similarity
    formatted = [
        {"id": p["id"], "name": p.get("name", "Unknown"), "music_data": p["music_data"]}
        for p in profiles
    ]

    result = calculate_group_similarity(formatted, genre_map)
    result["group_id"] = group_id
    result["group_name"] = get_group(group_id).get("name", "")

    return jsonify(result)


# ============ Discovery & Leaderboard Routes ============

@app.route("/api/discover/similar/<profile_id>")
def api_discover_similar(profile_id):
    """Find profiles most similar to the given profile."""
    target = get_profile(profile_id, include_music_data=True)
    if not target:
        return jsonify({"error": "Profile not found"}), 404

    # Get all public profiles
    public_profiles = list_public_profiles(limit=200)
    genre_map = load_genre_map()

    # Calculate similarity to each
    results = []
    for other in public_profiles:
        if other["id"] == profile_id:
            continue

        other_music_data = get_profile_music_data(other["id"])
        if not other_music_data:
            continue

        similarity = calculate_similarity(target["music_data"], other_music_data, genre_map)
        results.append({
            "id": other["id"],
            "name": other["name"],
            "stats": other["stats"],
            "similarity": similarity["overall"],
            "shared_count": similarity["shared_count"],
            "top_shared": similarity["shared_artists"][:5]
        })

    # Sort by similarity
    results.sort(key=lambda x: x["similarity"], reverse=True)

    return jsonify({
        "profile_id": profile_id,
        "similar_profiles": results[:20]
    })


@app.route("/api/leaderboard/<leaderboard_type>")
def api_leaderboard(leaderboard_type):
    """Get various leaderboards."""
    profiles = list_public_profiles(limit=100)

    if leaderboard_type == "diverse":
        # Most diverse taste (high diversity score)
        profiles.sort(key=lambda p: p["stats"].get("diversity_score", 0), reverse=True)
        return jsonify({
            "type": "diverse",
            "title": "Most Diverse Taste",
            "profiles": profiles[:20]
        })

    elif leaderboard_type == "popular":
        # Most songs
        profiles.sort(key=lambda p: p["stats"].get("song_count", 0), reverse=True)
        return jsonify({
            "type": "popular",
            "title": "Biggest Music Lovers",
            "profiles": profiles[:20]
        })

    elif leaderboard_type == "unique":
        # Calculate uniqueness (avg low similarity to others)
        genre_map = load_genre_map()
        uniqueness_scores = []

        for profile in profiles[:50]:  # Limit for performance
            music_data = get_profile_music_data(profile["id"])
            if not music_data:
                continue

            similarities = []
            for other in profiles[:50]:
                if other["id"] == profile["id"]:
                    continue
                other_data = get_profile_music_data(other["id"])
                if other_data:
                    sim = calculate_similarity(music_data, other_data, genre_map)
                    similarities.append(sim["overall"])

            if similarities:
                avg_similarity = sum(similarities) / len(similarities)
                uniqueness_scores.append({
                    **profile,
                    "uniqueness": round(100 - avg_similarity, 1)
                })

        uniqueness_scores.sort(key=lambda x: x["uniqueness"], reverse=True)
        return jsonify({
            "type": "unique",
            "title": "Most Unique Taste",
            "profiles": uniqueness_scores[:20]
        })

    elif leaderboard_type.startswith("genre-"):
        # Genre-specific leaderboard
        genre = leaderboard_type.replace("genre-", "").replace("-", " ").title()
        genre_profiles = []

        for profile in profiles:
            taste_vector = profile.get("taste_vector", {})
            genre_weights = taste_vector.get("genre_weights", {})
            weight = genre_weights.get(genre, 0)
            if weight > 0.1:  # At least 10% of their taste
                genre_profiles.append({
                    **profile,
                    "genre_weight": round(weight * 100, 1)
                })

        genre_profiles.sort(key=lambda x: x["genre_weight"], reverse=True)
        return jsonify({
            "type": f"genre-{genre}",
            "title": f"Top {genre} Fans",
            "profiles": genre_profiles[:20]
        })

    else:
        return jsonify({"error": "Unknown leaderboard type"}), 400


@app.route("/api/profiles/public")
def api_public_profiles():
    """List all public profiles."""
    profiles = list_public_profiles()
    return jsonify({"profiles": profiles})


# Demo mode with sample data
@app.route("/api/demo/graph")
def demo_graph():
    """Return sample graph data for demo/testing."""
    sample_data = {
        "nodes": [
            {"id": "1", "name": "Taylor Swift", "song_count": 45, "importance": 0.15, "in_library": True},
            {"id": "2", "name": "Ed Sheeran", "song_count": 32, "importance": 0.12, "in_library": True},
            {"id": "3", "name": "The Weeknd", "song_count": 28, "importance": 0.11, "in_library": True},
            {"id": "4", "name": "Dua Lipa", "song_count": 22, "importance": 0.09, "in_library": True},
            {"id": "5", "name": "Post Malone", "song_count": 18, "importance": 0.08, "in_library": True},
            {"id": "6", "name": "Ariana Grande", "song_count": 15, "importance": 0.07, "in_library": True},
            {"id": "7", "name": "Drake", "song_count": 25, "importance": 0.10, "in_library": True},
            {"id": "8", "name": "Billie Eilish", "song_count": 20, "importance": 0.08, "in_library": True},
            {"id": "9", "name": "Justin Bieber", "song_count": 12, "importance": 0.06, "in_library": False, "is_related": True},
            {"id": "10", "name": "Shawn Mendes", "song_count": 8, "importance": 0.05, "in_library": False, "is_related": True},
            {"id": "11", "name": "Khalid", "song_count": 10, "importance": 0.05, "in_library": True},
            {"id": "12", "name": "SZA", "song_count": 14, "importance": 0.06, "in_library": True},
            {"id": "13", "name": "Doja Cat", "song_count": 16, "importance": 0.07, "in_library": True},
            {"id": "14", "name": "Bad Bunny", "song_count": 11, "importance": 0.05, "in_library": True},
            {"id": "15", "name": "Olivia Rodrigo", "song_count": 9, "importance": 0.04, "in_library": True},
        ],
        "links": [
            {"source": "1", "target": "2", "weight": 3, "type": "collaboration"},
            {"source": "1", "target": "6", "weight": 1, "type": "similar"},
            {"source": "2", "target": "9", "weight": 2, "type": "collaboration"},
            {"source": "2", "target": "10", "weight": 1, "type": "similar"},
            {"source": "3", "target": "6", "weight": 2, "type": "collaboration"},
            {"source": "3", "target": "7", "weight": 3, "type": "collaboration"},
            {"source": "4", "target": "13", "weight": 2, "type": "collaboration"},
            {"source": "4", "target": "3", "weight": 1, "type": "similar"},
            {"source": "5", "target": "7", "weight": 2, "type": "similar"},
            {"source": "5", "target": "3", "weight": 1, "type": "similar"},
            {"source": "6", "target": "3", "weight": 2, "type": "collaboration"},
            {"source": "6", "target": "13", "weight": 1, "type": "similar"},
            {"source": "7", "target": "5", "weight": 2, "type": "collaboration"},
            {"source": "7", "target": "14", "weight": 1, "type": "collaboration"},
            {"source": "8", "target": "11", "weight": 2, "type": "collaboration"},
            {"source": "8", "target": "15", "weight": 1, "type": "similar"},
            {"source": "9", "target": "10", "weight": 2, "type": "similar"},
            {"source": "11", "target": "12", "weight": 1, "type": "similar"},
            {"source": "12", "target": "13", "weight": 2, "type": "collaboration"},
            {"source": "12", "target": "7", "weight": 1, "type": "collaboration"},
            {"source": "13", "target": "14", "weight": 1, "type": "similar"},
            {"source": "15", "target": "1", "weight": 1, "type": "similar"},
        ],
        "stats": {
            "total_artists": 15,
            "total_connections": 22,
            "library_artists": 13,
            "related_artists": 2
        }
    }
    return jsonify(sample_data)


# ==================== Upload Endpoints ====================

def parse_youtube_music_paste(text):
    """Parse pasted YouTube Music playlist text."""
    songs = []
    lines = text.strip().split('\n')

    # YouTube Music paste format can vary, but typically:
    # "Song Title\nArtist Name\n3:45\n" or "Song Title - Artist Name"
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Skip time stamps like "3:45" or "12:34"
        if re.match(r'^\d{1,2}:\d{2}$', line):
            i += 1
            continue

        # Skip common non-song lines
        if line.lower() in ['liked music', 'shuffle', 'radio', 'add to library', 'share', 'download']:
            i += 1
            continue

        # Try to detect "Song - Artist" format
        if ' - ' in line:
            parts = line.split(' - ', 1)
            title = parts[0].strip()
            artist = parts[1].strip() if len(parts) > 1 else 'Unknown Artist'
            songs.append({'title': title, 'artist': artist})
            i += 1
            continue

        # YouTube Music often has Title on one line, Artist on next
        title = line
        artist = 'Unknown Artist'

        # Look ahead for artist
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # Check if next line is likely an artist (not a timestamp, not empty)
            if next_line and not re.match(r'^\d{1,2}:\d{2}$', next_line):
                if next_line.lower() not in ['liked music', 'shuffle', 'radio', 'add to library', 'share', 'download']:
                    artist = next_line
                    i += 1  # Skip the artist line too

        songs.append({'title': title, 'artist': artist})
        i += 1

    return songs


def parse_csv_file(content):
    """Parse Google Takeout CSV file."""
    songs = []

    # Try to decode as utf-8
    try:
        text = content.decode('utf-8')
    except:
        text = content.decode('latin-1')

    reader = csv.DictReader(io.StringIO(text))

    for row in reader:
        # Google Takeout format: "Song Title", "Artist Name 1", "Artist Name 2", etc.
        title = row.get('Song Title', row.get('Title', row.get('title', row.get('Song', ''))))

        # Handle multiple artist columns
        artist = row.get('Artist Name 1', row.get('Artist', row.get('artist', row.get('Artists', ''))))

        # Get additional artists for collaboration detection
        all_artists = [artist] if artist else []
        for i in range(2, 6):  # Check Artist Name 2 through 5
            extra_artist = row.get(f'Artist Name {i}', '')
            if extra_artist and extra_artist.strip():
                all_artists.append(extra_artist.strip())

        if title and artist:
            songs.append({
                'title': title,
                'artist': artist,
                'all_artists': all_artists,
                'album': row.get('Album Title', row.get('Album', ''))
            })

    return songs


def parse_json_file(content):
    """Parse JSON file (playlist export or our format)."""
    songs = []

    try:
        data = json.loads(content)
    except:
        return []

    # Handle different JSON formats
    if isinstance(data, list):
        # Simple list of songs
        for item in data:
            if isinstance(item, dict):
                title = item.get('title', item.get('name', ''))
                artist = item.get('artist', item.get('artists', ''))
                if isinstance(artist, list):
                    artist = ', '.join(artist)
                if title:
                    songs.append({'title': title, 'artist': artist or 'Unknown Artist'})
    elif isinstance(data, dict):
        # Maybe it's our exported format or YouTube Music format
        if 'liked_songs' in data:
            for song in data['liked_songs']:
                songs.append({'title': song.get('title', ''), 'artist': song.get('artist', 'Unknown Artist')})
        elif 'items' in data:
            for item in data['items']:
                title = item.get('title', '')
                artist = item.get('artist', item.get('artists', 'Unknown Artist'))
                if isinstance(artist, list):
                    artist = ', '.join(artist)
                if title:
                    songs.append({'title': title, 'artist': artist})

    return songs


def parse_zip_file(file_content):
    """Parse Google Takeout ZIP file."""
    songs = []

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name

    try:
        with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
            for filename in zip_ref.namelist():
                # Look for music-related files
                lower_name = filename.lower()
                if 'music-library-songs' in lower_name and lower_name.endswith('.csv'):
                    content = zip_ref.read(filename)
                    songs.extend(parse_csv_file(content))
                elif 'liked' in lower_name and lower_name.endswith('.csv'):
                    content = zip_ref.read(filename)
                    songs.extend(parse_csv_file(content))
                elif lower_name.endswith('.json') and 'music' in lower_name:
                    content = zip_ref.read(filename)
                    songs.extend(parse_json_file(content))
    finally:
        os.unlink(tmp_path)

    return songs


def load_genre_map():
    """Load the genre mapping file."""
    genre_map_path = os.path.join(os.path.dirname(__file__), 'genre_map.json')
    if os.path.exists(genre_map_path):
        with open(genre_map_path, 'r') as f:
            return json.load(f)
    return {}


def get_artist_genre(artist_name, genre_map):
    """Get genre for an artist, trying various name formats."""
    # Direct match
    if artist_name in genre_map:
        return genre_map[artist_name]

    # Case-insensitive match
    lower_name = artist_name.lower()
    for mapped_artist, genre in genre_map.items():
        if mapped_artist.lower() == lower_name:
            return genre

    # Try without "The " prefix
    if lower_name.startswith('the '):
        check_name = artist_name[4:]
        for mapped_artist, genre in genre_map.items():
            if mapped_artist.lower() == check_name.lower():
                return genre

    return None


def fetch_genre_from_lastfm(artist_name):
    """Fetch genre from Last.fm API."""
    if not LASTFM_API_KEY:
        return None

    try:
        url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={urllib.parse.quote(artist_name)}&api_key={LASTFM_API_KEY}&format=json"
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            tags = data.get('artist', {}).get('tags', {}).get('tag', [])
            if tags:
                # Map common Last.fm tags to our genres
                tag_map = {
                    'electronic': 'Electronic',
                    'edm': 'Electronic',
                    'dubstep': 'Dubstep/Bass',
                    'bass': 'Dubstep/Bass',
                    'house': 'House',
                    'deep house': 'House',
                    'tech house': 'Tech House',
                    'progressive house': 'Progressive House',
                    'trance': 'Trance',
                    'future bass': 'Future Bass',
                    'trap': 'Trap/Bass',
                    'hip-hop': 'Hip-Hop',
                    'hip hop': 'Hip-Hop',
                    'rap': 'Hip-Hop',
                    'pop': 'Pop',
                    'rock': 'Rock',
                    'indie': 'Electronic/Indie',
                    'k-pop': 'K-Pop',
                    'kpop': 'K-Pop',
                    'drum and bass': 'Drum & Bass',
                    'dnb': 'Drum & Bass',
                    'jazz': 'Jazz',
                    'funk': 'Funk/Electronic',
                    'r&b': 'Pop',
                    'rnb': 'Pop'
                }

                for tag in tags:
                    tag_name = tag.get('name', '').lower()
                    if tag_name in tag_map:
                        return tag_map[tag_name]

                # Return first tag if no mapping found
                return tags[0].get('name', 'Other').title()
    except:
        pass

    return None


def build_graph_from_songs(songs):
    """Build graph data from parsed songs."""
    # Load genre map
    genre_map = load_genre_map()

    # Group songs by artist
    artist_songs = {}
    for song in songs:
        artist = song['artist']
        if artist not in artist_songs:
            artist_songs[artist] = []
        artist_songs[artist].append(song)

    # Create nodes
    nodes = []
    max_songs = max(len(s) for s in artist_songs.values()) if artist_songs else 1

    for artist, artist_song_list in artist_songs.items():
        importance = len(artist_song_list) / max_songs

        # Get genre from map or Last.fm
        genre = get_artist_genre(artist, genre_map)
        if not genre:
            genre = fetch_genre_from_lastfm(artist) or 'Other'

        nodes.append({
            'id': artist,
            'name': artist,
            'song_count': len(artist_song_list),
            'importance': importance,
            'in_library': True,
            'genre': genre,
            'songs': [{'title': s['title']} for s in artist_song_list[:20]]  # Limit songs
        })

    # Create links based on collaborations (from all_artists) and song title mentions
    links = []
    collab_counts = {}  # Track collaboration pairs

    # First pass: check explicit collaborations from all_artists field
    for artist, song_list in artist_songs.items():
        for song in song_list:
            all_artists = song.get('all_artists', [])
            if len(all_artists) > 1:
                # This song has multiple artists - create links between them
                for other_artist in all_artists[1:]:
                    if other_artist in artist_songs:  # Only if we have songs from this artist
                        pair = tuple(sorted([artist, other_artist]))
                        collab_counts[pair] = collab_counts.get(pair, 0) + 1

    # Second pass: check song titles for artist mentions
    artist_list = list(artist_songs.keys())
    for i, artist1 in enumerate(artist_list):
        for j, artist2 in enumerate(artist_list):
            if i >= j:
                continue

            pair = tuple(sorted([artist1, artist2]))

            # Check if any song title mentions the other artist
            for song in artist_songs[artist1]:
                title = song['title'].lower()
                if artist2.lower() in title:
                    collab_counts[pair] = collab_counts.get(pair, 0) + 1

            for song in artist_songs[artist2]:
                title = song['title'].lower()
                if artist1.lower() in title:
                    collab_counts[pair] = collab_counts.get(pair, 0) + 1

    # Create links from collaboration counts
    for (artist1, artist2), weight in collab_counts.items():
        if weight > 0:
            links.append({
                'source': artist1,
                'target': artist2,
                'weight': weight,
                'type': 'collaboration'
            })

    return {
        'nodes': nodes,
        'links': links,
        'stats': {
            'total_artists': len(nodes),
            'total_connections': len(links),
            'library_artists': len(nodes),
            'related_artists': 0
        }
    }


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """Handle file upload (ZIP, CSV, JSON)."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    filename = file.filename.lower()
    content = file.read()

    songs = []

    try:
        if filename.endswith('.zip'):
            songs = parse_zip_file(content)
        elif filename.endswith('.csv'):
            songs = parse_csv_file(content)
        elif filename.endswith('.json'):
            songs = parse_json_file(content)
        else:
            return jsonify({'error': 'Unsupported file type. Use ZIP, CSV, or JSON.'}), 400

        if not songs:
            return jsonify({'error': 'No songs found in file. Check the format.'}), 400

        # Build graph
        graph_data = build_graph_from_songs(songs)

        return jsonify({
            'success': True,
            'song_count': len(songs),
            'artist_count': len(graph_data['nodes']),
            'graph_data': graph_data
        })

    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500


@app.route("/api/upload/paste", methods=["POST"])
def upload_paste():
    """Handle pasted playlist text."""
    data = request.get_json()

    if not data or 'playlist_text' not in data:
        return jsonify({'error': 'No playlist text provided'}), 400

    text = data['playlist_text']

    try:
        songs = parse_youtube_music_paste(text)

        if not songs:
            return jsonify({'error': 'No songs found. Try copying the playlist differently.'}), 400

        # Build graph
        graph_data = build_graph_from_songs(songs)

        return jsonify({
            'success': True,
            'song_count': len(songs),
            'artist_count': len(graph_data['nodes']),
            'graph_data': graph_data
        })

    except Exception as e:
        return jsonify({'error': f'Error processing playlist: {str(e)}'}), 500


# ==================== Spotify Integration ====================

@app.route("/api/spotify/status")
def spotify_status():
    """Check if Spotify is configured and user is authenticated."""
    configured = spotify_client.is_configured()
    session_id = request.cookies.get('session_id', '')
    authenticated = session_id in spotify_tokens

    return jsonify({
        'configured': configured,
        'authenticated': authenticated
    })


@app.route("/api/spotify/auth")
def spotify_auth():
    """Redirect to Spotify authorization."""
    if not spotify_client.is_configured():
        return jsonify({'error': 'Spotify not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET.'}), 400

    import uuid
    state = str(uuid.uuid4())
    auth_url = spotify_client.get_auth_url(state)

    return jsonify({'auth_url': auth_url, 'state': state})


@app.route("/callback/spotify")
def spotify_callback():
    """Handle Spotify OAuth callback."""
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return f"""
        <html><body>
        <h1>Spotify Authorization Failed</h1>
        <p>Error: {error}</p>
        <script>setTimeout(() => window.close(), 3000);</script>
        </body></html>
        """

    if not code:
        return "No authorization code received", 400

    # Exchange code for token
    token_data, error = spotify_client.exchange_code_for_token(code)

    if error:
        return f"""
        <html><body>
        <h1>Token Exchange Failed</h1>
        <p>Error: {error}</p>
        <script>setTimeout(() => window.close(), 3000);</script>
        </body></html>
        """

    # Generate session ID and store token
    import uuid
    session_id = str(uuid.uuid4())
    spotify_tokens[session_id] = token_data

    # Return HTML that stores the session and redirects
    return f"""
    <html><body>
    <h1>Spotify Connected!</h1>
    <p>Loading your music library...</p>
    <script>
        document.cookie = "spotify_session={session_id}; path=/; max-age=3600";
        window.location.href = "/?spotify=connected";
    </script>
    </body></html>
    """


@app.route("/api/spotify/library")
def spotify_library():
    """Fetch user's Spotify library and return graph data."""
    session_id = request.cookies.get('spotify_session', '')

    if not session_id or session_id not in spotify_tokens:
        return jsonify({'error': 'Not authenticated with Spotify'}), 401

    token_data = spotify_tokens[session_id]
    access_token = token_data.get('access_token')

    if not access_token:
        return jsonify({'error': 'Invalid token'}), 401

    try:
        # Fetch saved tracks
        tracks = spotify_client.get_all_saved_tracks(access_token, max_tracks=1000)

        if not tracks:
            return jsonify({'error': 'No tracks found in your Spotify library'}), 404

        # Build graph with genre mapping
        graph_data = spotify_client.build_graph_from_spotify(tracks)

        # Apply our genre mapping
        genre_map = load_genre_map()
        for node in graph_data['nodes']:
            genre = get_artist_genre(node['name'], genre_map)
            if genre:
                node['genre'] = genre
            elif not node.get('genre'):
                node['genre'] = fetch_genre_from_lastfm(node['name']) or 'Other'

        return jsonify({
            'success': True,
            'song_count': len(tracks),
            'artist_count': len(graph_data['nodes']),
            'graph_data': graph_data
        })

    except Exception as e:
        return jsonify({'error': f'Error fetching Spotify library: {str(e)}'}), 500


@app.route("/api/spotify/disconnect")
def spotify_disconnect():
    """Disconnect Spotify (clear session)."""
    session_id = request.cookies.get('spotify_session', '')

    if session_id in spotify_tokens:
        del spotify_tokens[session_id]

    response = jsonify({'success': True})
    response.delete_cookie('spotify_session')
    return response


if __name__ == "__main__":
    print("Starting YouTube Music Mapper server...")
    print("Open http://localhost:5050 in your browser")
    app.run(debug=True, port=5050, host='0.0.0.0')
