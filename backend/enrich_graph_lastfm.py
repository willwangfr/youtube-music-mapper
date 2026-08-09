"""Enrich graph_data.json with similar-artist edges from Last.fm.

Only adds edges between artists already in the user's library
(does not introduce new nodes). Caches Last.fm responses to disk.
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import requests

API_KEY = os.environ.get("LASTFM_API_KEY") or open(Path(__file__).parent / ".env").read().split("=", 1)[1].strip()
CACHE_PATH = Path(__file__).parent / "lastfm_similar_cache.json"
GRAPH_PATH = Path(__file__).parent.parent / "frontend" / "graph_data.json"


def load_cache():
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def save_cache(cache):
    CACHE_PATH.write_text(json.dumps(cache))


def fetch_similar(name, session):
    url = (
        f"http://ws.audioscrobbler.com/2.0/?method=artist.getsimilar"
        f"&artist={quote(name)}&api_key={API_KEY}&format=json&limit=50"
    )
    r = session.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    similars = data.get("similarartists", {}).get("artist", []) or []
    return [{"name": a.get("name", ""), "match": float(a.get("match", 0))} for a in similars]


def main():
    graph = json.loads(GRAPH_PATH.read_text())
    nodes = graph.get("nodes", [])
    name_to_id = {n["name"].lower(): n["id"] for n in nodes if n.get("name")}
    print(f"loaded graph: {len(nodes)} artists")

    cache = load_cache()
    todo = [n["name"] for n in nodes if n["name"].lower() not in {k.lower() for k in cache}]
    print(f"cached: {len(cache)}; need to fetch: {len(todo)}")

    if todo:
        session = requests.Session()
        completed = 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(fetch_similar, name, session): name for name in todo}
            for f in as_completed(futures):
                name = futures[f]
                try:
                    cache[name] = f.result()
                except Exception as e:
                    cache[name] = []
                    print(f"  err {name}: {e}", file=sys.stderr)
                completed += 1
                if completed % 50 == 0:
                    print(f"  fetched {completed}/{len(todo)}")
                    save_cache(cache)
        save_cache(cache)
        print(f"fetched all; cache size: {len(cache)}")

    existing_edges = {(e["source"], e["target"]) for e in graph.get("edges", graph.get("links", []))}
    new_edges = []
    edge_count_by_threshold = {}
    for src_node in nodes:
        src_name = src_node["name"]
        src_id = src_node["id"]
        for sim in cache.get(src_name, []):
            tgt_name_lc = sim["name"].lower()
            tgt_id = name_to_id.get(tgt_name_lc)
            if not tgt_id or tgt_id == src_id:
                continue
            match = sim["match"]
            if match < 0.3:
                continue
            key = (src_id, tgt_id)
            rev = (tgt_id, src_id)
            if key in existing_edges or rev in existing_edges:
                continue
            existing_edges.add(key)
            new_edges.append({"source": src_id, "target": tgt_id, "weight": match, "type": "similar"})

    edges_field = "edges" if "edges" in graph else "links"
    graph[edges_field] = list(graph.get(edges_field, [])) + new_edges
    GRAPH_PATH.write_text(json.dumps(graph, indent=2))
    print(f"added {len(new_edges)} similar-artist edges; total: {len(graph[edges_field])}")


if __name__ == "__main__":
    main()
