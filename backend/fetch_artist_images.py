#!/usr/bin/env python3
"""
Fetch artist images from Last.fm API.
Get your free API key at: https://www.last.fm/api/account/create
"""

import json
import os
import time
import requests
from pathlib import Path

# Load from .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

LASTFM_API_KEY = os.environ.get('LASTFM_API_KEY', '')

def get_artist_image(artist_name, api_key):
    """Fetch artist image URL from Last.fm."""
    try:
        url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={requests.utils.quote(artist_name)}&api_key={api_key}&format=json"
        response = requests.get(url, timeout=10)
        data = response.json()

        if 'error' in data:
            return None

        images = data.get('artist', {}).get('image', [])
        # Get the largest image (extralarge or large)
        for img in reversed(images):
            if img.get('#text'):
                return img['#text']
        return None
    except Exception as e:
        print(f"  Error fetching {artist_name}: {e}")
        return None

def main():
    if not LASTFM_API_KEY:
        print("ERROR: No LASTFM_API_KEY environment variable set!")
        print("Get your free API key at: https://www.last.fm/api/account/create")
        print("Then run: LASTFM_API_KEY=your_key python fetch_artist_images.py")
        return

    # Load music data to get artist list
    music_data_path = Path(__file__).parent / "music_data.json"
    if not music_data_path.exists():
        print("No music_data.json found!")
        return

    with open(music_data_path, 'r') as f:
        data = json.load(f)

    # Get unique artists sorted by song count
    from collections import Counter
    artist_counts = Counter()
    for song in data.get('liked_songs', []):
        for artist in song.get('artists', []):
            name = artist.get('name', '')
            if name:
                artist_counts[name] += 1

    # Load existing image map if it exists
    image_map_path = Path(__file__).parent / "artist_images.json"
    if image_map_path.exists():
        with open(image_map_path, 'r') as f:
            image_map = json.load(f)
    else:
        image_map = {}

    # Fetch images for top artists (that we don't already have)
    artists_to_fetch = [
        (name, count) for name, count in artist_counts.most_common(500)
        if name not in image_map
    ]

    print(f"Fetching images for {len(artists_to_fetch)} artists...")
    print(f"Already have {len(image_map)} artist images cached.")

    new_count = 0
    for i, (artist_name, count) in enumerate(artists_to_fetch):
        print(f"[{i+1}/{len(artists_to_fetch)}] {artist_name} ({count} songs)...", end=" ")

        image_url = get_artist_image(artist_name, LASTFM_API_KEY)

        if image_url:
            image_map[artist_name] = image_url
            new_count += 1
            print(f"OK")
        else:
            print(f"No image")

        # Rate limit: ~5 requests per second
        time.sleep(0.2)

        # Save every 50 artists
        if (i + 1) % 50 == 0:
            with open(image_map_path, 'w') as f:
                json.dump(image_map, f, indent=2)
            print(f"  Saved {len(image_map)} images so far...")

    # Final save
    with open(image_map_path, 'w') as f:
        json.dump(image_map, f, indent=2)

    print(f"\nDone! Fetched {new_count} new images.")
    print(f"Total images cached: {len(image_map)}")
    print(f"Saved to: {image_map_path}")

if __name__ == "__main__":
    main()
