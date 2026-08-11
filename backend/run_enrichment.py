#!/usr/bin/env python3
"""Populate every enrichment store for the current library. Safe to rerun:
each fetcher skips what it already has.

Steps 1-3 hit the Last.fm API and finish in minutes. Step 4 (MusicBrainz
release years) is strictly serial at one request per second, so ~2,730
tracks takes roughly 45 minutes. Pass --skip-years to run only steps 1-3,
then invoke this script again without the flag (or run
`enrich/musicbrainz_years.py` directly) to do step 4 on its own later.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from collab_split import split_artist_name
from library import library_from_graph_data, track_pairs
from enrich.lastfm_artist import fetch_missing as fetch_artists
from enrich.lastfm_tags import build_reference
from enrich.musicbrainz_years import fetch_missing as fetch_years

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--skip-years",
    action="store_true",
    help="Run steps 1-3 only; skip the slow MusicBrainz year fetch (step 4).",
)
args = parser.parse_args()

api_key = os.environ.get("LASTFM_API_KEY", "")
env_path = Path(__file__).parent / ".env"
if not api_key and env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("LASTFM_API_KEY"):
            api_key = line.split("=", 1)[1].strip().strip("\"'")
if not api_key:
    sys.exit("LASTFM_API_KEY is not set")

graph = json.loads(Path("../frontend/graph_data.json").read_text())
library = library_from_graph_data(graph)

names = set()
for node in graph["nodes"]:
    names.add(node["name"])
    names.update(split_artist_name(node["name"]))

print(f"1/4 artist metadata ({len(names)} names)")
fetch_artists(names, api_key)

print("2/4 genre backfill")
os.system(f"{sys.executable} backfill_genres.py")

print("3/4 genre reference distributions")
build_reference(api_key)

if args.skip_years:
    print("skip-years set; stopping after step 3")
else:
    pairs = track_pairs(library)
    print(f"4/4 release years ({len(pairs)} tracks, ~1/sec — this takes a while)")
    fetch_years(pairs)

print("done")
