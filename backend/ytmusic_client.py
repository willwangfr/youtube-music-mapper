"""
YouTube Music API client for extracting user music data.
Uses ytmusicapi for authentication and data retrieval.
"""

from ytmusicapi import YTMusic
import json
from pathlib import Path


class YTMusicClient:
    def __init__(self, auth_file: str = "browser.json"):
        """
        Initialize YouTube Music client.

        Args:
            auth_file: Path to authentication file (browser.json)
        """
        self.auth_file = auth_file
        self.ytmusic = None

    def authenticate(self):
        """Load authentication from browser.json file."""
        if Path(self.auth_file).exists():
            self.ytmusic = YTMusic(self.auth_file)
            return True
        return False

    def setup_auth(self):
        """
        Interactive setup for browser authentication.
        Run this once to create browser.json
        """
        print("Setting up YouTube Music authentication...")
        print("1. Open YouTube Music in your browser")
        print("2. Open Developer Tools (F12) -> Network tab")
        print("3. Filter by 'browse' and click any request")
        print("4. Copy the 'cookie' and other headers")
        YTMusic.setup(filepath=self.auth_file)

    def get_library_artists(self, limit: int = 500) -> list:
        """Get artists from user's library."""
        if not self.ytmusic:
            return []
        try:
            artists = self.ytmusic.get_library_artists(limit=limit)
            return [
                {
                    "id": a.get("browseId", ""),
                    "name": a.get("artist", ""),
                    "thumbnail": a.get("thumbnails", [{}])[-1].get("url", "") if a.get("thumbnails") else ""
                }
                for a in artists
            ]
        except Exception as e:
            print(f"Error fetching library artists: {e}")
            return []

    def get_library_songs(self, limit: int = 500) -> list:
        """Get liked/saved songs from user's library."""
        if not self.ytmusic:
            return []
        try:
            songs = self.ytmusic.get_library_songs(limit=limit)
            return [
                {
                    "id": s.get("videoId", ""),
                    "title": s.get("title", ""),
                    "artists": [{"id": a.get("id", ""), "name": a.get("name", "")} for a in s.get("artists", [])],
                    "album": s.get("album", {}).get("name", "") if s.get("album") else "",
                    "duration": s.get("duration", "")
                }
                for s in songs
            ]
        except Exception as e:
            print(f"Error fetching library songs: {e}")
            return []

    def get_liked_songs(self, limit: int = 500) -> list:
        """Get liked songs playlist."""
        if not self.ytmusic:
            return []
        try:
            playlist = self.ytmusic.get_liked_songs(limit=limit)
            tracks = playlist.get("tracks", [])
            return [
                {
                    "id": t.get("videoId", ""),
                    "title": t.get("title", ""),
                    "artists": [{"id": a.get("id", ""), "name": a.get("name", "")} for a in t.get("artists", [])],
                    "album": t.get("album", {}).get("name", "") if t.get("album") else "",
                    "duration": t.get("duration", "")
                }
                for t in tracks
            ]
        except Exception as e:
            print(f"Error fetching liked songs: {e}")
            return []

    def get_artist_info(self, artist_id: str) -> dict:
        """Get detailed artist information including related artists."""
        if not self.ytmusic:
            return {}
        try:
            artist = self.ytmusic.get_artist(artist_id)
            return {
                "id": artist_id,
                "name": artist.get("name", ""),
                "description": artist.get("description", ""),
                "subscribers": artist.get("subscribers", ""),
                "thumbnail": artist.get("thumbnails", [{}])[-1].get("url", "") if artist.get("thumbnails") else "",
                "related_artists": [
                    {"id": r.get("browseId", ""), "name": r.get("title", "")}
                    for r in artist.get("related", {}).get("results", [])
                ] if artist.get("related") else []
            }
        except Exception as e:
            print(f"Error fetching artist {artist_id}: {e}")
            return {}

    def get_history(self) -> list:
        """Get recently played songs."""
        if not self.ytmusic:
            return []
        try:
            history = self.ytmusic.get_history()
            return [
                {
                    "id": h.get("videoId", ""),
                    "title": h.get("title", ""),
                    "artists": [{"id": a.get("id", ""), "name": a.get("name", "")} for a in h.get("artists", [])]
                }
                for h in history
            ]
        except Exception as e:
            print(f"Error fetching history: {e}")
            return []

    def search_artist(self, query: str) -> list:
        """Search for artists."""
        if not self.ytmusic:
            return []
        try:
            results = self.ytmusic.search(query, filter="artists", limit=10)
            return [
                {
                    "id": r.get("browseId", ""),
                    "name": r.get("artist", ""),
                    "thumbnail": r.get("thumbnails", [{}])[-1].get("url", "") if r.get("thumbnails") else ""
                }
                for r in results
            ]
        except Exception as e:
            print(f"Error searching: {e}")
            return []


def export_user_data(client: YTMusicClient, output_file: str = "music_data.json"):
    """Export all user music data to JSON."""
    data = {
        "library_artists": client.get_library_artists(limit=200),
        "liked_songs": client.get_liked_songs(limit=1000),
        "history": client.get_history()
    }

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Exported data to {output_file}")
    return data


if __name__ == "__main__":
    client = YTMusicClient()

    if not client.authenticate():
        print("No authentication found. Running setup...")
        client.setup_auth()
        client.authenticate()

    # Export user data
    data = export_user_data(client)
    print(f"Found {len(data['library_artists'])} artists")
    print(f"Found {len(data['liked_songs'])} liked songs")
