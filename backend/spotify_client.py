"""
Spotify API client for fetching user's music library.
Handles OAuth flow and library data retrieval.
"""

import os
import requests
import base64
from urllib.parse import urlencode

# Spotify API credentials - set these as environment variables
SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID', '')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', '')
SPOTIFY_REDIRECT_URI = os.environ.get('SPOTIFY_REDIRECT_URI', 'http://localhost:5050/callback/spotify')

# Spotify API endpoints
SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize'
SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'
SPOTIFY_API_BASE = 'https://api.spotify.com/v1'

# Scopes needed to read user's library
SCOPES = 'user-library-read user-top-read playlist-read-private'


def get_auth_url(state=None):
    """Generate Spotify OAuth authorization URL."""
    params = {
        'client_id': SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'scope': SCOPES,
        'show_dialog': 'true'
    }
    if state:
        params['state'] = state
    return f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code):
    """Exchange authorization code for access token."""
    auth_header = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()

    response = requests.post(
        SPOTIFY_TOKEN_URL,
        headers={
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': SPOTIFY_REDIRECT_URI
        }
    )

    if response.status_code != 200:
        return None, response.json().get('error_description', 'Authentication failed')

    return response.json(), None


def refresh_access_token(refresh_token):
    """Refresh an expired access token."""
    auth_header = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()

    response = requests.post(
        SPOTIFY_TOKEN_URL,
        headers={
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
    )

    if response.status_code != 200:
        return None, 'Token refresh failed'

    return response.json(), None


def get_user_profile(access_token):
    """Get current user's Spotify profile."""
    response = requests.get(
        f"{SPOTIFY_API_BASE}/me",
        headers={'Authorization': f'Bearer {access_token}'}
    )

    if response.status_code != 200:
        return None

    return response.json()


def get_saved_tracks(access_token, limit=50, offset=0):
    """Fetch user's saved/liked tracks."""
    response = requests.get(
        f"{SPOTIFY_API_BASE}/me/tracks",
        headers={'Authorization': f'Bearer {access_token}'},
        params={'limit': limit, 'offset': offset}
    )

    if response.status_code != 200:
        return None, response.json().get('error', {}).get('message', 'Failed to fetch tracks')

    return response.json(), None


def get_all_saved_tracks(access_token, max_tracks=2000):
    """Fetch all saved tracks (paginated)."""
    all_tracks = []
    offset = 0
    limit = 50

    while offset < max_tracks:
        data, error = get_saved_tracks(access_token, limit=limit, offset=offset)

        if error or not data:
            break

        items = data.get('items', [])
        if not items:
            break

        all_tracks.extend(items)

        # Check if there are more tracks
        if not data.get('next'):
            break

        offset += limit

    return all_tracks


def get_top_artists(access_token, time_range='medium_term', limit=50):
    """Fetch user's top artists."""
    response = requests.get(
        f"{SPOTIFY_API_BASE}/me/top/artists",
        headers={'Authorization': f'Bearer {access_token}'},
        params={'time_range': time_range, 'limit': limit}
    )

    if response.status_code != 200:
        return None

    return response.json().get('items', [])


def parse_spotify_tracks(tracks):
    """Parse Spotify track data into our format."""
    songs = []

    for item in tracks:
        track = item.get('track', {})
        if not track:
            continue

        # Get primary artist
        artists = track.get('artists', [])
        artist_name = artists[0]['name'] if artists else 'Unknown Artist'

        # Get all artist names for collaboration detection
        all_artists = [a['name'] for a in artists]

        song = {
            'title': track.get('name', 'Unknown'),
            'artist': artist_name,
            'all_artists': all_artists,
            'album': track.get('album', {}).get('name', ''),
            'duration_ms': track.get('duration_ms', 0),
            'popularity': track.get('popularity', 0),
            'spotify_id': track.get('id', ''),
            'preview_url': track.get('preview_url', ''),
            'added_at': item.get('added_at', '')
        }

        songs.append(song)

    return songs


def build_graph_from_spotify(tracks, top_artists=None):
    """Build graph data from Spotify tracks."""
    songs = parse_spotify_tracks(tracks)

    # Group songs by artist
    artist_data = {}

    for song in songs:
        artist = song['artist']
        if artist not in artist_data:
            artist_data[artist] = {
                'songs': [],
                'collaborators': set()
            }

        artist_data[artist]['songs'].append(song)

        # Track collaborators
        for collab in song.get('all_artists', [])[1:]:
            artist_data[artist]['collaborators'].add(collab)

    # Create nodes
    nodes = []
    max_songs = max(len(d['songs']) for d in artist_data.values()) if artist_data else 1

    for artist, data in artist_data.items():
        song_count = len(data['songs'])
        importance = song_count / max_songs

        # Get average popularity
        avg_popularity = sum(s.get('popularity', 0) for s in data['songs']) / song_count if song_count > 0 else 0

        nodes.append({
            'id': artist,
            'name': artist,
            'song_count': song_count,
            'importance': importance,
            'in_library': True,
            'popularity': avg_popularity,
            'songs': [{'title': s['title'], 'album': s.get('album', '')} for s in data['songs'][:20]]
        })

    # Create links based on collaborations
    links = []
    seen_pairs = set()

    for artist, data in artist_data.items():
        for collab in data['collaborators']:
            if collab in artist_data:
                pair = tuple(sorted([artist, collab]))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)

                    # Count collaboration songs
                    collab_count = sum(
                        1 for s in data['songs']
                        if collab in s.get('all_artists', [])
                    )

                    links.append({
                        'source': artist,
                        'target': collab,
                        'weight': collab_count,
                        'type': 'collaboration'
                    })

    return {
        'nodes': nodes,
        'links': links,
        'stats': {
            'total_artists': len(nodes),
            'total_connections': len(links),
            'library_artists': len(nodes),
            'related_artists': 0,
            'total_songs': len(songs)
        }
    }


def is_configured():
    """Check if Spotify credentials are configured."""
    return bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)
