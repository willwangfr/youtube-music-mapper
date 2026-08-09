"""Parse a raw page-paste of YouTube Music's Liked Music page into music_data.json."""
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

DURATION_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
HEADER_MARKER = "Music you like in any YouTube app will show here"
FOOTER_MARKERS = ("Saved to liked music", "Liked Music")


def parse(text: str):
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if HEADER_MARKER in line),
        None,
    )
    if start is None:
        raise SystemExit(f"Couldn't find marker: {HEADER_MARKER!r}")

    blocks = []
    cur = []
    for raw in lines[start + 1 :]:
        line = raw.strip()
        if line:
            cur.append(line)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)

    songs = []
    pending = None
    for block in blocks:
        # Drop the trailing "currently playing" widget block(s).
        if any(b in block for b in FOOTER_MARKERS):
            break
        # A solo duration line attaches to the previous pending song.
        if len(block) == 1 and DURATION_RE.match(block[0]):
            if pending is not None:
                pending["duration"] = block[0]
                songs.append(pending)
                pending = None
            continue
        # Flush a previous pending without a duration (rare).
        if pending is not None:
            songs.append(pending)
            pending = None
        if len(block) >= 2:
            pending = {
                "title": block[0],
                "artist": block[1],
                "album": block[2] if len(block) >= 3 else "",
                "duration": "",
            }
    if pending is not None:
        songs.append(pending)

    return songs


def to_music_data(songs):
    liked = []
    artists = OrderedDict()
    for s in songs:
        artist_name = s["artist"]
        liked.append({
            "id": "",
            "title": s["title"],
            "artists": [{"id": "", "name": artist_name}],
            "album": {"name": s["album"]} if s["album"] else {},
            "duration": s["duration"],
        })
        artists.setdefault(artist_name, {"id": "", "name": artist_name, "thumbnail": ""})
    return {
        "library_artists": list(artists.values()),
        "liked_songs": liked,
        "history": [],
    }


if __name__ == "__main__":
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("music_data.json")
    songs = parse(src.read_text())
    data = to_music_data(songs)
    out.write_text(json.dumps(data, indent=2))
    print(f"parsed {len(songs)} songs into {len(data['library_artists'])} unique artists -> {out}")
