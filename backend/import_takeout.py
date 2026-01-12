"""
Import YouTube Music data from Google Takeout export.

Usage:
    python import_takeout.py /path/to/Takeout/folder

Google Takeout export structure:
    Takeout/
    └── YouTube and YouTube Music/
        ├── playlists/
        │   ├── Liked music.csv
        │   ├── Playlist1.csv
        │   └── ...
        ├── history/
        │   └── watch-history.json
        └── music-library-songs.csv (optional)
"""

import os
import sys
import json
import csv
import re
from pathlib import Path


def find_takeout_folder(base_path):
    """Find the YouTube and YouTube Music folder in Takeout."""
    base = Path(base_path)

    # Direct path
    if (base / "playlists").exists() or (base / "history").exists():
        return base

    # Check for "YouTube and YouTube Music" subfolder
    yt_folder = base / "YouTube and YouTube Music"
    if yt_folder.exists():
        return yt_folder

    # Check inside Takeout folder
    takeout_folder = base / "Takeout" / "YouTube and YouTube Music"
    if takeout_folder.exists():
        return takeout_folder

    # Search recursively for playlists folder
    for p in base.rglob("playlists"):
        if p.is_dir():
            return p.parent

    return None


def parse_playlist_csv(filepath):
    """Parse a YouTube Music playlist CSV file."""
    songs = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Skip header rows (YouTube exports have multiple header lines)
            content = f.read()
            lines = content.strip().split('\n')

            # Find the actual data (skip metadata rows)
            data_start = 0
            for i, line in enumerate(lines):
                if 'Video Id' in line or 'Video ID' in line or line.startswith('Video Id'):
                    data_start = i
                    break

            if data_start == 0:
                # Try to find CSV header
                for i, line in enumerate(lines):
                    if ',' in line and not line.startswith('#'):
                        data_start = i
                        break

            # Parse as CSV from data_start
            csv_content = '\n'.join(lines[data_start:])
            reader = csv.DictReader(csv_content.split('\n'))

            for row in reader:
                # Handle different column naming conventions
                video_id = row.get('Video Id') or row.get('Video ID') or row.get('video_id', '')
                title = row.get('Title') or row.get('title', '')

                # Sometimes the URL is provided instead of ID
                if not video_id and 'URL' in row:
                    url = row.get('URL', '')
                    match = re.search(r'[?&]v=([^&]+)', url)
                    if match:
                        video_id = match.group(1)

                if video_id and video_id != 'Video Id':
                    songs.append({
                        'id': video_id,
                        'title': title,
                        'playlist_title': row.get('Playlist Title', ''),
                        'channel': row.get('Channel Title') or row.get('Channel', ''),
                    })
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")

    return songs


def parse_watch_history(filepath):
    """Parse watch-history.json for listening history."""
    history = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for item in data:
            # Filter for music.youtube.com URLs
            url = item.get('titleUrl', '')
            if 'music.youtube.com' in url or 'youtube.com/watch' in url:
                video_id = ''
                match = re.search(r'[?&]v=([^&]+)', url)
                if match:
                    video_id = match.group(1)

                if video_id:
                    history.append({
                        'id': video_id,
                        'title': item.get('title', '').replace('Watched ', ''),
                        'time': item.get('time', ''),
                        'channel': item.get('subtitles', [{}])[0].get('name', '') if item.get('subtitles') else ''
                    })
    except Exception as e:
        print(f"Error parsing watch history: {e}")

    return history


def parse_music_library_csv(filepath):
    """Parse music-library-songs.csv for full library info."""
    songs = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get('URL', '') or row.get('url', '')
                video_id = ''
                match = re.search(r'[?&]v=([^&]+)', url)
                if match:
                    video_id = match.group(1)

                songs.append({
                    'id': video_id,
                    'title': row.get('Title') or row.get('Song') or row.get('title', ''),
                    'artist': row.get('Artist') or row.get('artist', ''),
                    'album': row.get('Album') or row.get('album', ''),
                    'duration': row.get('Duration') or row.get('duration', ''),
                })
    except Exception as e:
        print(f"Error parsing music library: {e}")

    return songs


def import_takeout(takeout_path, output_file='music_data.json'):
    """Import all data from Google Takeout export."""

    base_path = Path(takeout_path)
    yt_folder = find_takeout_folder(base_path)

    if not yt_folder:
        print(f"Error: Could not find YouTube Music data in {takeout_path}")
        print("Expected folder structure: Takeout/YouTube and YouTube Music/")
        return None

    print(f"Found YouTube Music data at: {yt_folder}")

    # Initialize data structure
    data = {
        'library_artists': [],
        'liked_songs': [],
        'history': [],
        'source': 'google_takeout'
    }

    # Find and parse liked music playlist
    playlists_folder = yt_folder / "playlists"
    if playlists_folder.exists():
        print(f"\nSearching for playlists in: {playlists_folder}")

        for csv_file in playlists_folder.glob("*.csv"):
            print(f"  Found: {csv_file.name}")

            # Check if it's the liked music playlist
            if 'liked' in csv_file.name.lower() or 'like' in csv_file.name.lower():
                print(f"  -> Parsing as liked songs...")
                songs = parse_playlist_csv(csv_file)

                # Convert to our format
                for s in songs:
                    if s.get('id'):
                        data['liked_songs'].append({
                            'id': s['id'],
                            'title': s.get('title', 'Unknown'),
                            'artists': [{'name': s.get('channel', 'Unknown'), 'id': ''}],
                            'album': '',
                            'duration': '',
                        })

                print(f"     Added {len(songs)} liked songs")

    # Parse watch history
    history_folder = yt_folder / "history"
    if history_folder.exists():
        watch_history_file = history_folder / "watch-history.json"
        if watch_history_file.exists():
            print(f"\nParsing watch history...")
            history = parse_watch_history(watch_history_file)

            for h in history:
                if h.get('id'):
                    data['history'].append({
                        'id': h['id'],
                        'title': h.get('title', ''),
                        'artists': [{'name': h.get('channel', ''), 'id': ''}],
                        'played': h.get('time', ''),
                    })

            print(f"  Added {len(history)} history entries")

    # Try to find music-library-songs.csv
    library_file = yt_folder / "music-library-songs.csv"
    if library_file.exists():
        print(f"\nParsing music library CSV...")
        library_songs = parse_music_library_csv(library_file)

        # Merge with liked songs (add artist/album info)
        liked_ids = {s['id'] for s in data['liked_songs']}
        for ls in library_songs:
            if ls.get('id') and ls['id'] not in liked_ids:
                data['liked_songs'].append({
                    'id': ls['id'],
                    'title': ls.get('title', 'Unknown'),
                    'artists': [{'name': ls.get('artist', 'Unknown'), 'id': ''}],
                    'album': ls.get('album', ''),
                    'duration': ls.get('duration', ''),
                })

        print(f"  Library has {len(library_songs)} songs")

    # Extract unique artists
    artist_names = set()
    for song in data['liked_songs']:
        for artist in song.get('artists', []):
            name = artist.get('name', '')
            if name and name != 'Unknown':
                artist_names.add(name)

    data['library_artists'] = [{'name': name, 'id': ''} for name in sorted(artist_names)]

    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Import complete!")
    print(f"  Liked songs: {len(data['liked_songs'])}")
    print(f"  Artists: {len(data['library_artists'])}")
    print(f"  History entries: {len(data['history'])}")
    print(f"\nSaved to: {output_file}")
    print(f"\nNext steps:")
    print(f"  1. python assign_genres.py")
    print(f"  2. python rebuild_graph.py")
    print(f"  3. python server.py")

    return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_takeout.py /path/to/Takeout/folder")
        print("\nTo get your data:")
        print("  1. Go to https://takeout.google.com")
        print("  2. Deselect all, then select 'YouTube and YouTube Music'")
        print("  3. Click 'All YouTube data included' and select:")
        print("     - playlists (includes Liked Music)")
        print("     - history")
        print("  4. Export and download the ZIP")
        print("  5. Extract and run this script on the Takeout folder")
        sys.exit(1)

    import_takeout(sys.argv[1])
