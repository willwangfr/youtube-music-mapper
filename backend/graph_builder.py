"""
Builds artist relationship graph from YouTube Music data.
Creates nodes (artists) and edges (relationships) for visualization.
"""

import json
import networkx as nx
from collections import defaultdict
from typing import Dict, List, Set
from ytmusic_client import YTMusicClient


class MusicGraphBuilder:
    def __init__(self):
        self.graph = nx.Graph()
        self.artist_songs = defaultdict(list)  # artist_id -> [songs]
        self.artist_info = {}  # artist_id -> {name, thumbnail, etc}
        self.genre_clusters = defaultdict(set)  # genre -> {artist_ids}

    def load_from_json(self, filepath: str):
        """Load user music data from JSON export."""
        with open(filepath, "r") as f:
            data = json.load(f)

        self._process_liked_songs(data.get("liked_songs", []))
        self._process_library_artists(data.get("library_artists", []))
        self._build_co_occurrence_edges()

    def _process_liked_songs(self, songs: List[dict]):
        """Process liked songs to build artist-song relationships."""
        for song in songs:
            for artist in song.get("artists", []):
                artist_id = artist.get("id", "")
                artist_name = artist.get("name", "")

                if artist_id and artist_name:
                    self.artist_songs[artist_id].append(song)

                    if artist_id not in self.artist_info:
                        self.artist_info[artist_id] = {
                            "id": artist_id,
                            "name": artist_name,
                            "song_count": 0
                        }
                    self.artist_info[artist_id]["song_count"] += 1

    def _process_library_artists(self, artists: List[dict]):
        """Process library artists."""
        for artist in artists:
            artist_id = artist.get("id", "")
            if artist_id:
                if artist_id not in self.artist_info:
                    self.artist_info[artist_id] = {
                        "id": artist_id,
                        "name": artist.get("name", ""),
                        "song_count": 0
                    }
                self.artist_info[artist_id]["thumbnail"] = artist.get("thumbnail", "")
                self.artist_info[artist_id]["in_library"] = True

    def _build_co_occurrence_edges(self):
        """Build edges based on song co-occurrence (collaborations)."""
        # Track which songs have multiple artists (collaborations)
        song_artists = defaultdict(list)

        for artist_id, songs in self.artist_songs.items():
            for song in songs:
                song_id = song.get("id", "")
                if song_id:
                    for a in song.get("artists", []):
                        if a.get("id"):
                            song_artists[song_id].append(a.get("id"))

        # Create edges between artists who collaborated
        for song_id, artists in song_artists.items():
            if len(artists) > 1:
                for i, a1 in enumerate(artists):
                    for a2 in artists[i+1:]:
                        if a1 != a2:
                            if self.graph.has_edge(a1, a2):
                                self.graph[a1][a2]["weight"] += 1
                                self.graph[a1][a2]["songs"].append(song_id)
                            else:
                                self.graph.add_edge(a1, a2, weight=1, songs=[song_id], type="collaboration")

    def add_related_artists(self, client: YTMusicClient, limit_per_artist: int = 5):
        """Fetch and add related artists from YouTube Music API."""
        artist_ids = list(self.artist_info.keys())[:50]  # Limit API calls

        for artist_id in artist_ids:
            if not artist_id:
                continue

            info = client.get_artist_info(artist_id)
            if info:
                # Update artist info
                self.artist_info[artist_id].update({
                    "description": info.get("description", ""),
                    "subscribers": info.get("subscribers", ""),
                    "thumbnail": info.get("thumbnail", self.artist_info[artist_id].get("thumbnail", ""))
                })

                # Add related artist edges
                for related in info.get("related_artists", [])[:limit_per_artist]:
                    related_id = related.get("id", "")
                    if related_id:
                        # Add related artist to info if not exists
                        if related_id not in self.artist_info:
                            self.artist_info[related_id] = {
                                "id": related_id,
                                "name": related.get("name", ""),
                                "song_count": 0,
                                "is_related": True
                            }

                        # Add edge
                        if self.graph.has_edge(artist_id, related_id):
                            self.graph[artist_id][related_id]["weight"] += 0.5
                        else:
                            self.graph.add_edge(artist_id, related_id, weight=0.5, type="similar")

    def build_graph_nodes(self):
        """Add all artists as nodes in the graph."""
        for artist_id, info in self.artist_info.items():
            self.graph.add_node(
                artist_id,
                name=info.get("name", ""),
                song_count=info.get("song_count", 0),
                thumbnail=info.get("thumbnail", ""),
                in_library=info.get("in_library", False),
                is_related=info.get("is_related", False)
            )

    def calculate_node_importance(self):
        """Calculate importance scores for nodes based on various factors."""
        # Use PageRank for importance
        if len(self.graph.nodes()) > 0:
            pagerank = nx.pagerank(self.graph, weight="weight")
            for node, score in pagerank.items():
                self.graph.nodes[node]["importance"] = score

        # Also factor in song count
        for node in self.graph.nodes():
            song_count = self.graph.nodes[node].get("song_count", 0)
            base_importance = self.graph.nodes[node].get("importance", 0.01)
            # Boost importance based on how many songs user has from this artist
            self.graph.nodes[node]["importance"] = base_importance * (1 + song_count * 0.1)

    def export_for_visualization(self, output_file: str = "graph_data.json"):
        """Export graph data in format suitable for D3.js visualization."""
        self.build_graph_nodes()
        self.calculate_node_importance()

        nodes = []
        for node_id in self.graph.nodes():
            node_data = self.graph.nodes[node_id]
            nodes.append({
                "id": node_id,
                "name": node_data.get("name", ""),
                "song_count": node_data.get("song_count", 0),
                "thumbnail": node_data.get("thumbnail", ""),
                "importance": node_data.get("importance", 0.01),
                "in_library": node_data.get("in_library", False),
                "is_related": node_data.get("is_related", False)
            })

        links = []
        for u, v, data in self.graph.edges(data=True):
            links.append({
                "source": u,
                "target": v,
                "weight": data.get("weight", 1),
                "type": data.get("type", "unknown")
            })

        graph_data = {
            "nodes": nodes,
            "links": links,
            "stats": {
                "total_artists": len(nodes),
                "total_connections": len(links),
                "library_artists": sum(1 for n in nodes if n.get("in_library")),
                "related_artists": sum(1 for n in nodes if n.get("is_related"))
            }
        }

        with open(output_file, "w") as f:
            json.dump(graph_data, f, indent=2)

        print(f"Exported graph to {output_file}")
        print(f"  - {len(nodes)} artists")
        print(f"  - {len(links)} connections")

        return graph_data


if __name__ == "__main__":
    builder = MusicGraphBuilder()

    # Load from exported data
    try:
        builder.load_from_json("music_data.json")

        # Optionally add related artists (requires auth)
        # client = YTMusicClient()
        # if client.authenticate():
        #     builder.add_related_artists(client)

        builder.export_for_visualization("../frontend/graph_data.json")
    except FileNotFoundError:
        print("No music_data.json found. Run ytmusic_client.py first to export your data.")
