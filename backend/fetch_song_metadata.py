"""
Fetch song years and view counts from YouTube Music API.
"""

import json
import time
from ytmusicapi import YTMusic

def fetch_metadata():
    """Fetch year and view count for each song."""

    yt = YTMusic('browser.json')

    # Load current music data
    with open('music_data.json', 'r') as f:
        data = json.load(f)

    liked_songs = data.get('liked_songs', [])
    print(f"Processing {len(liked_songs)} songs...")

    updated_years = 0
    updated_views = 0
    errors = 0

    for i, song in enumerate(liked_songs):
        if i % 50 == 0:
            print(f"Progress: {i}/{len(liked_songs)}")

        video_id = song.get('id', '')

        # Skip if we already have year (only fetch missing years)
        if not video_id or song.get('year'):
            continue

        try:
            song_info = yt.get_song(video_id)

            # Get year from publishDate in microformat
            mf = song_info.get('microformat', {})
            mf_data = mf.get('microformatDataRenderer', {})
            publish_date = mf_data.get('publishDate', '')
            if publish_date:
                year = publish_date[:4]  # Extract year from "2021-05-20T03:03:56-07:00"
                song['year'] = year
                updated_years += 1

            # Update views if we don't have them
            if not song.get('views'):
                vd = song_info.get('videoDetails', {})
                views = vd.get('viewCount', '')
                if views:
                    song['views'] = int(views)
                    updated_views += 1

            time.sleep(0.05)  # Rate limit
        except Exception as e:
            errors += 1
            if errors < 5:
                print(f"Error fetching {song.get('title', '?')}: {e}")

    # Save updated data
    with open('music_data.json', 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\nUpdated {updated_years} songs with year")
    print(f"Updated {updated_views} songs with views")
    print(f"Errors: {errors}")

    # Show sample
    sample = liked_songs[:5]
    print("\nSample songs:")
    for s in sample:
        print(f"  {s.get('title')} - Year: {s.get('year', 'N/A')}, Views: {s.get('views', 'N/A')}")


if __name__ == "__main__":
    fetch_metadata()
