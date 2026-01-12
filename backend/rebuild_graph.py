"""
Rebuild graph_data.json with full song lists, years, and play counts.
"""

import json
from collections import defaultdict

def rebuild_graph():
    # Load music data
    with open('music_data.json', 'r') as f:
        music_data = json.load(f)

    # Load existing graph data to preserve genres
    with open('../frontend/graph_data.json', 'r') as f:
        graph_data = json.load(f)

    # Process listening history for play counts
    history = music_data.get('history', [])
    song_plays = defaultdict(int)  # song_id -> play count
    artist_plays = defaultdict(int)  # artist_id -> play count

    for h in history:
        song_id = h.get('id', '')
        if song_id:
            song_plays[song_id] += 1
        for artist in h.get('artists', []):
            artist_id = artist.get('id', '')
            if artist_id:
                artist_plays[artist_id] += 1

    print(f"Processed {len(history)} history entries")
    print(f"Found plays for {len(artist_plays)} artists")

    # Build artist -> songs map from music data
    artist_songs = defaultdict(list)
    for song in music_data.get('liked_songs', []):
        song_id = song.get('id', '')
        for artist in song.get('artists', []):
            artist_id = artist.get('id', '')
            if artist_id:
                artist_songs[artist_id].append({
                    'title': song.get('title', ''),
                    'album': song.get('album', ''),
                    'duration': song.get('duration', ''),
                    'year': song.get('year', ''),
                    'views': song.get('views', 0),
                    'plays': song_plays.get(song_id, 0)
                })

    # Update graph nodes with full song lists and play counts
    updated = 0
    for node in graph_data['nodes']:
        artist_id = node['id']
        songs = artist_songs.get(artist_id, [])

        # Remove duplicates by title, keep the one with highest play count
        seen_titles = {}
        for s in songs:
            title = s['title']
            if title not in seen_titles or s.get('plays', 0) > seen_titles[title].get('plays', 0):
                seen_titles[title] = s

        unique_songs = list(seen_titles.values())
        # Sort by play count (highest first)
        unique_songs.sort(key=lambda x: x.get('plays', 0), reverse=True)

        if len(unique_songs) > 0:
            node['songs'] = unique_songs
            updated += 1

        # Add artist-level play count
        node['total_plays'] = artist_plays.get(artist_id, 0)

    # Save updated graph
    with open('../frontend/graph_data.json', 'w') as f:
        json.dump(graph_data, f, indent=2)

    print(f"Updated {updated} artists with full song lists")

    # Verify
    mismatches = []
    for n in graph_data['nodes']:
        song_count = n.get('song_count', 0)
        songs_list = n.get('songs', [])
        if song_count != len(songs_list) and song_count > 0:
            mismatches.append((n['name'], song_count, len(songs_list)))

    if mismatches:
        print(f"\nRemaining mismatches (may be due to duplicate songs):")
        for name, count, actual in sorted(mismatches, key=lambda x: x[1] - x[2], reverse=True)[:5]:
            print(f"  {name}: count={count}, actual={actual}")
    else:
        print("\nAll song counts match!")


if __name__ == "__main__":
    rebuild_graph()
