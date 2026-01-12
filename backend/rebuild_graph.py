"""
Rebuild graph_data.json with full song lists (no limit).
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

    # Build artist -> songs map from music data
    artist_songs = defaultdict(list)
    for song in music_data.get('liked_songs', []):
        for artist in song.get('artists', []):
            artist_id = artist.get('id', '')
            if artist_id:
                artist_songs[artist_id].append({
                    'title': song.get('title', ''),
                    'album': song.get('album', ''),
                    'duration': song.get('duration', '')
                })

    # Update graph nodes with full song lists
    updated = 0
    for node in graph_data['nodes']:
        artist_id = node['id']
        songs = artist_songs.get(artist_id, [])

        # Remove duplicates by title
        seen_titles = set()
        unique_songs = []
        for s in songs:
            if s['title'] not in seen_titles:
                seen_titles.add(s['title'])
                unique_songs.append(s)

        if len(unique_songs) > len(node.get('songs', [])):
            node['songs'] = unique_songs
            updated += 1

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
