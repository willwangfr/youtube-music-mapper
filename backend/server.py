"""
Flask API server for YouTube Music Mapper.
Provides endpoints for fetching music data and graph visualization.
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from ytmusic_client import YTMusicClient, export_user_data
from graph_builder import MusicGraphBuilder
import os
import json

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
    authenticated = client.authenticate()
    return jsonify({
        "authenticated": authenticated,
        "message": "Connected to YouTube Music" if authenticated else "Not authenticated"
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

        # Add related artists if authenticated
        if client.authenticate():
            builder.add_related_artists(client, limit_per_artist=3)

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


if __name__ == "__main__":
    print("Starting YouTube Music Mapper server...")
    print("Open http://localhost:5050 in your browser")
    app.run(debug=True, port=5050, host='0.0.0.0')
