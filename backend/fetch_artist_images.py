#!/usr/bin/env python3
"""
Fetch artist images from Deezer API (no API key required).
"""

import json
import time
import requests
from pathlib import Path
from urllib.parse import quote


def get_artist_image(artist_name):
    """Fetch artist image URL from Deezer."""
    try:
        url = f"https://api.deezer.com/search/artist?q={quote(artist_name)}&limit=1"
        response = requests.get(url, timeout=10)
        data = response.json()

        if 'error' in data or not data.get('data'):
            return None

        artist = data['data'][0]
        # Use picture_big (500x500) or picture_medium (250x250)
        image_url = artist.get('picture_big') or artist.get('picture_medium')

        # Verify it's not the default placeholder
        if image_url and 'user' not in image_url:
            return image_url
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def main():
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

    image_map_path = Path(__file__).parent / "artist_images.json"

    # Start fresh - clear old placeholder data
    image_map = {}

    # Fetch images for all artists
    artists_to_fetch = list(artist_counts.most_common())

    print(f"Fetching images for {len(artists_to_fetch)} artists from Deezer...")

    found_count = 0
    for i, (artist_name, count) in enumerate(artists_to_fetch):
        print(f"[{i+1}/{len(artists_to_fetch)}] {artist_name} ({count} songs)...", end=" ")

        image_url = get_artist_image(artist_name)

        if image_url:
            image_map[artist_name] = image_url
            found_count += 1
            print("OK")
        else:
            print("No image")

        # Rate limit: ~10 requests per second for Deezer
        time.sleep(0.1)

        # Save every 50 artists
        if (i + 1) % 50 == 0:
            with open(image_map_path, 'w') as f:
                json.dump(image_map, f, indent=2)
            print(f"  Saved {len(image_map)} images so far...")

    # Final save
    with open(image_map_path, 'w') as f:
        json.dump(image_map, f, indent=2)

    print(f"\nDone! Found images for {found_count}/{len(artists_to_fetch)} artists.")
    print(f"Saved to: {image_map_path}")


if __name__ == "__main__":
    main()
