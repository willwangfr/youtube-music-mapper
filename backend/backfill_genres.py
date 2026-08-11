#!/usr/bin/env python3
"""Populate the genre field on every artist_meta entry."""

import json
from pathlib import Path

from artist_meta import load_meta, save_meta, resolve_genre

curated_path = Path(__file__).parent / "genre_map.json"
curated = json.loads(curated_path.read_text()) if curated_path.exists() else {}

meta = load_meta()
for name, entry in meta.items():
    entry["genre"] = resolve_genre(name, entry, curated)
save_meta(meta)

other = sum(1 for e in meta.values() if e["genre"] == "Other")
print(f"{len(meta)} artists, {other} still Other ({100 * other / len(meta):.0f}%)")
