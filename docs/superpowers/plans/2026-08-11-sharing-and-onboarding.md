# Sharing & Onboarding (Spec B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a profile shareable and a share link self-serve. A link to `/p/<id>` previews in iMessage, Discord, and Slack as a constellation card carrying the archetype and the headline numbers; the same PNG is what the owner downloads. A visitor arriving with no data of their own can get from the link to a side-by-side comparison through any of four import paths. An optional LLM paragraph adds prose over the computed stats without the page ever depending on it.

**Architecture:** The card is rendered server-side by one function and served at one URL, which is simultaneously the OpenGraph `og:image` and the user-facing download — one code path, so the preview and the download cannot drift. Layout is a pure function (artist counts → positioned circles) with no Pillow import, so it is unit-testable without touching a framebuffer; drawing is a thin shell over it. Constellation edges come from the profile's **own** library (co-credited artists on the same track), never from the server's `graph_data.json` — that file is the host's private library and reading it per-visitor is exactly the privacy defect the Spec A final review caught. OG tags are injected into `profile.html` at request time by string replacement on a placeholder comment, so the file stays a working static page for local development. Onboarding endpoints are stateless: the bookmarklet ships its payload via a top-level cross-origin form POST, which needs no CORS preflight and no server-side import store.

**Tech Stack:** Python 3.11 (production) / 3.10 (venv), Flask, Pillow, networkx, requests, pytest. Vanilla JS on the frontend. Anthropic Messages API (`claude-sonnet-5`) for the optional write-up.

**Parent spec:** `docs/superpowers/specs/2026-08-08-taste-profile-design.md`. Spec A's plan is `docs/superpowers/plans/2026-08-08-taste-profile.md`; its execution ledger is `.superpowers/sdd/2026-08-08-taste-profile/progress.md`. Read the ledger before starting — every fetcher bug in Spec A came from code written against an assumed API shape.

**Scope judgment:** Spec B is four features (cards, OG previews, onboarding, write-up) and fits in one plan of 13 tasks at Spec A's granularity, which ran 15. It is not split. The tasks are ordered so cards (1–6), the write-up (7–8), onboarding (9–11), and the carried-over fixes (12–13) are four independent runs — a reviewer can reject any one of the four without blocking the others.

---

## Global Constraints

These are carried verbatim from Spec A's execution. They are not suggestions; each one cost a debugging session.

- **Run tests with `backend/venv/bin/python -m pytest`.** The project venv (Python 3.10.14) is the only interpreter with both pytest and the project's dependencies. The bare `python3` is 3.9 with no pytest; `/opt/homebrew/bin/pytest` has pytest but lacks networkx and Flask. Read every test command below as `cd backend && ./venv/bin/python -m pytest ...`.
- **The Flask server binds IPv4 only — use `http://127.0.0.1:5050`, never `localhost`** — and it needs roughly 8 seconds to answer the first request because of the reloader. A curl that fails immediately after `python server.py` has not proven anything.
- **`backend/data/`, `frontend/graph_data.json`, and `backend/profiles/` are gitignored real user data. Never commit or modify them.** Reading them is fine; `git add`-ing them is not.
- **Verify every external API's actual response shape before writing code against it.** In Spec A this caused four separate bugs, including one where `tag.gettopartists` returned no `listeners` field at all and every genre population silently cached empty — invisible to unit tests because the tests fed hand-written payloads matching the assumption.
- **Any store written to disk must be written atomically (`.tmp` then `Path.replace`) and must distinguish a transient failure (retry) from a settled negative result (cache).**
- **Escape all user-supplied strings reaching the DOM.** `profile.js` uses an `esc()` helper; follow it.
- **Profiles are private by default; nothing may silently re-enable public listing.**

Constraints specific to this spec, established by direct verification during planning:

- **Pillow is not installed.** Task 1 adds it to `backend/requirements.txt` and installs it into `backend/venv`. Verified against Pillow 12.3.0: `ImageDraw.textsize()` **no longer exists** (removed in Pillow 10) — measure with `draw.textbbox((0, 0), text, font=font)` or `draw.textlength(...)`. Most Pillow code you may recall uses `textsize` and will `AttributeError`.
- **`ImageFont.load_default(size=N)` is the only font that is guaranteed present.** Verified: on this Mac, `/System/Library/Fonts/Helvetica.ttc` loads (index 0 Regular, index 1 Bold) and the DejaVu paths do not exist. The deployment image is `python:3.11-slim`, whose font inventory could **not** be verified during planning (the local Docker daemon was not running), so the resolver must walk a candidate list and fall back to `load_default` rather than assume any path exists. Task 1 also adds `fonts-dejavu-core` to the Dockerfile so the deployed card gets a real typeface, but correctness must not depend on that apt line succeeding.
- **`networkx.spring_layout` returns `{node: numpy.ndarray([x, y])}` with coordinates roughly in [-1, 1]** (verified on networkx 3.4.2). Cast with `float(v[0])`. Two edge cases bite: an empty graph returns `{}`, and a single node returns exactly `array([0., 0.])`, so normalising by `(max_x - min_x)` divides by zero. Both must be guarded.
- **`parse_liked_songs_paste.parse()` raises `SystemExit`, which `except Exception` does not catch** (verified). Any request handler calling it must catch `SystemExit` explicitly or a malformed paste takes down the request with an unhandled `BaseException`.
- **Non-default `temperature`, `top_p`, and `top_k` are rejected with a 400 on `claude-sonnet-5`.** Do not add them to the write-up call. Manual `budget_tokens` is likewise removed; use `thinking` plus `output_config.effort`.
- The reference library's real numbers, for sanity checks: 3,039 liked songs / 1,156 artists via `library_from_graph_data`; the raw paste file parses to 3,040 songs / 1,133 artists; obscurity 20.3 absolute and 39.6 scene-relative; diversity 0.741; 8 clusters; archetype "Main Stage Omnivore". Top 40 artists run Seven Lions (95 songs) down to 12 songs, spanning 13 genres with 11 co-credit edges between them.

---

### Task 1: Pillow dependency, font resolution, and the card palette

**Files:**
- Create: `backend/card_render.py`, `backend/tests/test_card_render.py`
- Modify: `backend/requirements.txt`, `Dockerfile`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `CARD_WIDTH = 1200`, `CARD_HEIGHT = 630`, `SUPERSAMPLE = 2`
  - `FONT_CANDIDATES_REGULAR`, `FONT_CANDIDATES_BOLD` — lists of `(path, ttc_index)`
  - `load_font(size: int, bold: bool = False)` — never raises
  - `GENRE_COLORS: dict[str, tuple]`, `genre_color(genre) -> tuple`
  - `BACKGROUND`, `INK`, `MUTED`, `PANEL` colour constants

1200×630 is the OpenGraph standard aspect (1.91:1); iMessage, Discord, and Slack all render it uncropped.

- [ ] **Step 1: Add Pillow to requirements and install it**

Append to `backend/requirements.txt`:

```
Pillow>=11.0.0
```

The floor is deliberately conservative. The fallback path calls `ImageFont.load_default(size=...)`, and the release that added that keyword could not be confirmed during planning — `>=11.0.0` is known-good rather than minimal.

Run:

```bash
cd backend && ./venv/bin/python -m pip install -r requirements.txt
./venv/bin/python -c "import PIL; print('Pillow', PIL.__version__)"
```

Expected: `Pillow 12.3.0` or newer.

- [ ] **Step 2: Give the deployment image a real typeface**

In `Dockerfile`, insert before the `pip install` line:

```dockerfile
# Pillow needs a TrueType face to render the share card; python:*-slim ships none.
# card_render falls back to Pillow's bitmap font if this is ever absent, so a
# failure here degrades the card's looks rather than breaking the endpoint.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 3: Write the failing test**

`backend/tests/test_card_render.py`:

```python
import card_render
from card_render import genre_color, load_font


def test_load_font_returns_a_measurable_font():
    font = load_font(40)
    # Every downstream call measures text; a font that cannot be measured is
    # useless regardless of which candidate produced it.
    assert font.getbbox("Main Stage Omnivore")[2] > 0


def test_load_font_bold_is_also_measurable():
    assert load_font(40, bold=True).getbbox("Seven Lions")[2] > 0


def test_load_font_falls_back_when_no_candidate_exists(monkeypatch):
    # The deployment image's font inventory is not guaranteed. A missing file
    # must degrade to Pillow's built-in face, never raise.
    monkeypatch.setattr(card_render, "FONT_CANDIDATES_REGULAR",
                        [("/nonexistent/nope.ttf", 0)])
    monkeypatch.setattr(card_render, "FONT_CANDIDATES_BOLD",
                        [("/nonexistent/nope.ttf", 0)])
    assert load_font(30).getbbox("x")[2] > 0
    assert load_font(30, bold=True).getbbox("x")[2] > 0


def test_load_font_survives_a_path_that_exists_but_is_not_a_font(tmp_path):
    junk = tmp_path / "notafont.ttf"
    junk.write_text("this is not a font")
    import card_render as cr
    original = cr.FONT_CANDIDATES_REGULAR
    cr.FONT_CANDIDATES_REGULAR = [(str(junk), 0)]
    try:
        assert cr.load_font(20).getbbox("x")[2] > 0
    finally:
        cr.FONT_CANDIDATES_REGULAR = original


def test_known_genres_have_distinct_colours():
    picked = [genre_color(g) for g in
              ("Dubstep/Bass", "Melodic Bass", "Progressive House", "Pop")]
    assert len(set(picked)) == 4


def test_unknown_genre_falls_back_without_raising():
    assert genre_color("Sea Shanty Revival") == genre_color(None)


def test_card_is_opengraph_sized():
    assert (card_render.CARD_WIDTH, card_render.CARD_HEIGHT) == (1200, 630)
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_card_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'card_render'`

- [ ] **Step 5: Write the implementation**

`backend/card_render.py`:

```python
"""Server-rendered share card. This module owns every pixel of the PNG that is
both the OpenGraph preview and the user-facing download, so the two cannot
drift apart."""

from PIL import ImageFont

CARD_WIDTH = 1200
CARD_HEIGHT = 630
# Draw at 2x and downsample with LANCZOS; Pillow has no antialiased primitives,
# so this is what keeps circle edges and small text from looking ragged.
SUPERSAMPLE = 2

BACKGROUND = (11, 13, 20)
PANEL = (19, 22, 33)
INK = (238, 241, 248)
MUTED = (146, 154, 174)
ACCENT = (108, 196, 255)

# (path, ttc face index). Ordered best-first. macOS paths come first because
# that is where this is developed; the Debian paths are what the deployed
# image has after the Dockerfile's fonts-dejavu-core install.
FONT_CANDIDATES_REGULAR = [
    ("/System/Library/Fonts/Helvetica.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
]
FONT_CANDIDATES_BOLD = [
    ("/System/Library/Fonts/Helvetica.ttc", 1),
    ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
]


def load_font(size: int, bold: bool = False):
    """Best available face at `size`, degrading to Pillow's built-in font.

    Font availability differs between this Mac and the deployment image, and a
    card endpoint that 500s because a .ttf moved is worse than an ugly card.
    """
    candidates = FONT_CANDIDATES_BOLD if bold else FONT_CANDIDATES_REGULAR
    for path, index in candidates:
        try:
            return ImageFont.truetype(path, size, index=index)
        except (OSError, ValueError):
            # OSError: absent or unreadable. ValueError: present but not a font.
            continue
    return ImageFont.load_default(size=size)


# Only genres that actually show up in real libraries get a hand-picked hue;
# everything else shares the neutral. Colour is decoration here — the card
# never asks the reader to decode it without the genre also being written out.
GENRE_COLORS = {
    "Dubstep/Bass": (124, 92, 255),
    "Melodic Bass": (94, 160, 255),
    "Progressive House": (255, 138, 76),
    "Future Bass": (255, 106, 193),
    "House": (255, 196, 84),
    "UK House": (240, 176, 64),
    "Tech House": (196, 170, 96),
    "Trance": (110, 220, 232),
    "Techno": (150, 150, 165),
    "Drum & Bass": (86, 220, 160),
    "Hardstyle": (255, 90, 90),
    "Trap/Bass": (168, 108, 255),
    "Hip Hop": (255, 214, 92),
    "Pop": (255, 122, 158),
    "K-Pop": (255, 148, 200),
    "J-Pop": (236, 160, 236),
    "Rock": (226, 106, 84),
    "Indie": (150, 200, 120),
    "Lo-fi": (140, 190, 190),
    "Electronic": (120, 178, 255),
    "Funk/Electronic": (200, 160, 255),
    "Funk/Soul": (255, 176, 120),
    "R&B": (214, 132, 200),
    "Classical": (208, 200, 176),
    "Soundtrack": (170, 190, 220),
    "Country/Folk": (196, 176, 128),
    "Synthwave": (255, 110, 220),
    "World Music": (128, 208, 176),
}
NEUTRAL = (108, 118, 140)


def genre_color(genre):
    return GENRE_COLORS.get(genre, NEUTRAL)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_card_render.py -v`
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add backend/card_render.py backend/tests/test_card_render.py backend/requirements.txt Dockerfile
git commit -m "Add Pillow with a font resolver that degrades instead of failing"
```

---

### Task 2: Constellation layout

**Files:**
- Create: `backend/constellation.py`, `backend/tests/test_constellation.py`

**Interfaces:**
- Consumes: `collab_split.split_artist_name`, `networkx`
- Produces:
  - `co_credit_edges(library: dict, names: set) -> list[tuple[str, str]]`
  - `layout(counts: dict, meta: dict, library: dict, width: int, height: int, limit: int = 40, seed: int = 7) -> dict`
    returning `{"nodes": [{"name", "songs", "genre", "x", "y", "r"}], "edges": [(i, j)]}`

Pure geometry, no Pillow import — so the layout can be asserted numerically instead of by eyeballing a PNG. Edges come from the profile's own library, never from `frontend/graph_data.json`: that file is the *host's* library, and the Spec A final review found a Critical privacy leak from exactly that mistake (`taste_clusters` was seeding a visitor's clusters from the host's 1,133 artists).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_constellation.py`:

```python
import pytest

from constellation import co_credit_edges, layout

LIBRARY = {"liked_songs": [
    {"title": "Strangers", "artists": [{"name": "Seven Lions"}]},
    {"title": "Rush Over Me", "artists": [{"name": "Seven Lions"}]},
    {"title": "Sad Songs", "artists": [{"name": "ILLENIUM, Wooli, & Grabbitz"}]},
    {"title": "Nightlight", "artists": [{"name": "Illenium"}]},
]}
COUNTS = {"Seven Lions": 95, "ILLENIUM": 67, "Wooli": 20, "Grabbitz": 12}
META = {
    "Seven Lions": {"genre": "Melodic Bass"},
    "ILLENIUM": {"genre": "Melodic Bass"},
    "Wooli": {"genre": "Dubstep/Bass"},
    "Grabbitz": {"genre": "Future Bass"},
}


def test_collaboration_becomes_edges_between_every_pair():
    edges = co_credit_edges(LIBRARY, {"ILLENIUM", "Wooli", "Grabbitz"})
    assert sorted(edges) == [("Grabbitz", "ILLENIUM"), ("Grabbitz", "Wooli"),
                             ("ILLENIUM", "Wooli")]


def test_edges_are_restricted_to_the_selected_names():
    # Grabbitz is not on the card, so no edge may mention it.
    edges = co_credit_edges(LIBRARY, {"ILLENIUM", "Wooli"})
    assert edges == [("ILLENIUM", "Wooli")]


def test_a_solo_credit_produces_no_edge():
    assert co_credit_edges(
        {"liked_songs": [{"title": "x", "artists": [{"name": "Seven Lions"}]}]},
        {"Seven Lions"}) == []


def test_edges_are_deduplicated_across_repeated_collaborations():
    doubled = {"liked_songs": LIBRARY["liked_songs"] + LIBRARY["liked_songs"]}
    assert len(co_credit_edges(doubled, {"ILLENIUM", "Wooli"})) == 1


def test_layout_keeps_the_biggest_artists_and_ranks_them_first():
    result = layout(COUNTS, META, LIBRARY, 500, 500, limit=2)
    assert [n["name"] for n in result["nodes"]] == ["Seven Lions", "ILLENIUM"]


def test_radius_grows_with_song_count():
    nodes = layout(COUNTS, META, LIBRARY, 500, 500)["nodes"]
    by_name = {n["name"]: n["r"] for n in nodes}
    assert by_name["Seven Lions"] > by_name["ILLENIUM"] > by_name["Grabbitz"]


def test_every_node_lands_inside_the_box_including_its_radius():
    nodes = layout(COUNTS, META, LIBRARY, 400, 300)["nodes"]
    for n in nodes:
        assert 0 <= n["x"] - n["r"] and n["x"] + n["r"] <= 400
        assert 0 <= n["y"] - n["r"] and n["y"] + n["r"] <= 300


def test_layout_is_deterministic_for_the_same_seed():
    a = layout(COUNTS, META, LIBRARY, 500, 500, seed=7)
    b = layout(COUNTS, META, LIBRARY, 500, 500, seed=7)
    assert a == b


def test_edges_are_index_pairs_into_nodes():
    result = layout(COUNTS, META, LIBRARY, 500, 500)
    names = [n["name"] for n in result["nodes"]]
    for i, j in result["edges"]:
        assert names[i] != names[j]


def test_a_single_artist_is_centred_rather_than_dividing_by_zero():
    # networkx returns exactly array([0., 0.]) for one node, so the coordinate
    # range is zero and naive normalisation is a ZeroDivisionError.
    result = layout({"Solo": 5}, {}, {"liked_songs": []}, 400, 300)
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["x"] == pytest.approx(200.0)
    assert result["nodes"][0]["y"] == pytest.approx(150.0)


def test_an_empty_library_lays_out_nothing():
    assert layout({}, {}, {"liked_songs": []}, 400, 300) == {"nodes": [], "edges": []}


def test_genre_travels_with_the_node():
    nodes = layout(COUNTS, META, LIBRARY, 500, 500)["nodes"]
    assert next(n for n in nodes if n["name"] == "Wooli")["genre"] == "Dubstep/Bass"


def test_missing_metadata_yields_other_not_a_crash():
    nodes = layout({"Nobody": 3}, {}, {"liked_songs": []}, 400, 300)["nodes"]
    assert nodes[0]["genre"] == "Other"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_constellation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'constellation'`

- [ ] **Step 3: Write the implementation**

`backend/constellation.py`:

```python
"""Positions for the share card's mini-constellation.

Pure geometry — no Pillow — so the layout can be asserted numerically.

Edges are derived from the profile's OWN library (artists co-credited on the
same track). The server's frontend/graph_data.json is the host's private
library; using it to shape a visitor's card would leak the host's artists,
which is the defect the Spec A final review found in taste_clusters.
"""

import math

import networkx as nx

from collab_split import split_artist_name

MIN_RADIUS = 7.0
MAX_RADIUS = 34.0


def co_credit_edges(library: dict, names) -> list:
    """Pairs of selected artists that share a credit on some track."""
    selected = set(names)
    found = set()
    for song in library.get("liked_songs", []):
        for credit in song.get("artists", []):
            parts = [p for p in split_artist_name(credit.get("name", ""))
                     if p in selected]
            for i in range(len(parts)):
                for j in range(i + 1, len(parts)):
                    if parts[i] != parts[j]:
                        found.add(tuple(sorted((parts[i], parts[j]))))
    return sorted(found)


def layout(counts: dict, meta: dict, library: dict, width: int, height: int,
           limit: int = 40, seed: int = 7) -> dict:
    """Place the top `limit` artists in a width x height box."""
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    if not top:
        return {"nodes": [], "edges": []}

    names = [name for name, _ in top]
    index = {name: i for i, name in enumerate(names)}
    edges = [(index[a], index[b]) for a, b in co_credit_edges(library, set(names))]

    graph = nx.Graph()
    graph.add_nodes_from(names)
    graph.add_edges_from((names[i], names[j]) for i, j in edges)
    # seed makes the layout reproducible, so the same profile always renders the
    # same card and the byte-equality test in Task 3 means something.
    positions = nx.spring_layout(graph, seed=seed, k=0.9, iterations=60)

    largest = max(songs for _, songs in top)
    radii = {name: MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) *
             math.sqrt(songs / largest) for name, songs in top}
    pad = max(radii.values()) + 2.0

    xs = [float(positions[n][0]) for n in names]
    ys = [float(positions[n][1]) for n in names]

    def scale(values, extent):
        low, high = min(values), max(values)
        span = high - low
        if span <= 0:
            # One node, or every node stacked: networkx returns array([0., 0.])
            # for a single node, so normalising by the span divides by zero.
            return [extent / 2.0 for _ in values]
        usable = extent - 2 * pad
        return [pad + usable * (v - low) / span for v in values]

    placed_x = scale(xs, width)
    placed_y = scale(ys, height)

    nodes = [{
        "name": name,
        "songs": songs,
        "genre": (meta.get(name) or {}).get("genre") or "Other",
        "x": placed_x[i],
        "y": placed_y[i],
        "r": radii[name],
    } for i, (name, songs) in enumerate(top)]

    return {"nodes": nodes, "edges": edges}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_constellation.py -v`
Expected: 13 passed

- [ ] **Step 5: Check the layout against the real library**

Run:

```bash
cd backend && ./venv/bin/python -c "
import json
from library import library_from_graph_data, artist_song_counts
from artist_meta import load_meta
from constellation import layout
g = json.load(open('../frontend/graph_data.json'))
lib = library_from_graph_data(g)
result = layout(artist_song_counts(lib), load_meta(), lib, 540, 510)
print(len(result['nodes']), 'nodes,', len(result['edges']), 'edges')
print('genres:', len({n['genre'] for n in result['nodes']}))
print('largest:', result['nodes'][0]['name'], result['nodes'][0]['songs'],
      round(result['nodes'][0]['r'], 1))
print('smallest r:', round(min(n['r'] for n in result['nodes']), 1))
"
```

Expected: `40 nodes, 11 edges`, `genres: 13`, largest `Seven Lions 95 34.0`, smallest radius near `16.6`. The edge count is low because only 11 of the top-40 pairs ever share a track — the constellation reads as mostly-separate stars with a few clusters, which is correct for this library.

- [ ] **Step 6: Commit**

```bash
git add backend/constellation.py backend/tests/test_constellation.py
git commit -m "Lay out the share card constellation from the profile's own collaborations"
```

---

### Task 3: Draw the card

**Files:**
- Modify: `backend/card_render.py`, `backend/tests/test_card_render.py`

**Interfaces:**
- Consumes: `constellation.layout`, `card_render.load_font`, `card_render.genre_color`
- Produces:
  - `wrap_text(draw, text, font, max_width) -> list[str]`
  - `fit_text(draw, text, font, max_width) -> str`
  - `render_card(profile_name, archetype, stats, meta, library) -> bytes`

`stats` is the dict from `build_profile_stats`; `archetype` is the dict from `resolve_archetype`. `render_card` returns PNG bytes and must never raise for any profile that `build_profile_stats` accepted.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_card_render.py`:

```python
import io

from PIL import Image

from card_render import fit_text, render_card, wrap_text

ARCHETYPE = {"name": "Main Stage Omnivore",
             "tagline": "Built on Dubstep/Bass, firmly in the present."}
STATS = {
    "artist_count": 1156, "song_count": 3039, "obscurity": 20.26,
    "scene_obscurity": 39.6, "diversity": 0.741,
    "top_artists": [("Seven Lions", 95), ("ILLENIUM", 67), ("Subtronics", 62)],
}
META = {"Seven Lions": {"genre": "Melodic Bass"},
        "ILLENIUM": {"genre": "Melodic Bass"},
        "Subtronics": {"genre": "Dubstep/Bass"}}
LIBRARY = {"liked_songs": [{"title": "t", "artists": [{"name": "Seven Lions"}]}]}


def _draw():
    from PIL import ImageDraw
    return ImageDraw.Draw(Image.new("RGB", (10, 10)))


def test_wrap_breaks_on_width_not_on_character_count():
    font = load_font(40)
    lines = wrap_text(_draw(), "Main Stage Completionist", font, 200)
    assert len(lines) > 1
    assert " ".join(lines) == "Main Stage Completionist"


def test_wrap_leaves_short_text_on_one_line():
    assert wrap_text(_draw(), "Pop", load_font(40), 400) == ["Pop"]


def test_fit_text_truncates_with_an_ellipsis():
    out = fit_text(_draw(), "An extremely long profile name that cannot fit",
                   load_font(40), 120)
    assert out.endswith("…") and out != "An extremely long profile name that cannot fit"


def test_fit_text_leaves_text_that_already_fits():
    assert fit_text(_draw(), "Alex", load_font(24), 400) == "Alex"


def test_render_returns_a_png_of_opengraph_size():
    png = render_card("Alex", ARCHETYPE, STATS, META, LIBRARY)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert Image.open(io.BytesIO(png)).size == (1200, 630)


def test_render_is_byte_identical_for_identical_input():
    # The OG image and the download are the same URL; a card that changes on
    # every render would defeat crawler caching and make diffs meaningless.
    assert render_card("Alex", ARCHETYPE, STATS, META, LIBRARY) == \
           render_card("Alex", ARCHETYPE, STATS, META, LIBRARY)


def test_render_survives_a_profile_with_no_artists():
    empty = dict(STATS, artist_count=0, song_count=0, obscurity=None,
                 scene_obscurity=None, diversity=0.0, top_artists=[])
    png = render_card("Nobody", ARCHETYPE, empty, {}, {"liked_songs": []})
    assert Image.open(io.BytesIO(png)).size == (1200, 630)


def test_render_survives_a_hostile_profile_name():
    png = render_card("<script>alert(1)</script>" * 5, ARCHETYPE, STATS, META, LIBRARY)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_survives_a_missing_obscurity():
    png = render_card("Alex", ARCHETYPE, dict(STATS, obscurity=None),
                      META, LIBRARY)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_card_render.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_card' from 'card_render'`

- [ ] **Step 3: Write the implementation**

Append to `backend/card_render.py` (add `import io` and `from PIL import Image, ImageDraw` to the imports at the top, and `from constellation import layout as constellation_layout`):

```python
def wrap_text(draw, text: str, font, max_width: float) -> list:
    """Greedy word wrap measured in pixels.

    Pillow 10 removed ImageDraw.textsize; textlength is the replacement and
    returns a float advance width.
    """
    words = str(text).split()
    if not words:
        return [""]
    lines, current = [], words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def fit_text(draw, text: str, font, max_width: float) -> str:
    """Truncate to a pixel width, with an ellipsis when anything was dropped."""
    text = str(text)
    if draw.textlength(text, font=font) <= max_width:
        return text
    ellipsis = "…"
    trimmed = text
    while trimmed and draw.textlength(trimmed + ellipsis, font=font) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + ellipsis) if trimmed else ellipsis


def _draw_constellation(image, draw, stats, meta, library, box):
    left, top, width, height = box
    counts = dict(stats.get("top_artists") or [])
    placed = constellation_layout(counts, meta, library, width, height)
    nodes = placed["nodes"]
    if not nodes:
        return

    # Links first so circles sit on top of them. "RGBA" draw mode is what makes
    # the alpha in the fill actually blend rather than being ignored. The image
    # is passed in rather than reached for via draw._image, which is private.
    overlay = ImageDraw.Draw(image, "RGBA")
    for i, j in placed["edges"]:
        a, b = nodes[i], nodes[j]
        overlay.line([(left + a["x"], top + a["y"]), (left + b["x"], top + b["y"])],
                     fill=(150, 170, 210, 90), width=2 * SUPERSAMPLE)

    for node in nodes:
        cx, cy, r = left + node["x"], top + node["y"], node["r"] * SUPERSAMPLE
        box_xy = [cx - r, cy - r, cx + r, cy + r]
        draw.ellipse(box_xy, fill=genre_color(node["genre"]))
        # A background-coloured ring separates overlapping circles.
        draw.ellipse(box_xy, outline=BACKGROUND, width=max(2, SUPERSAMPLE))

    # Name only the largest node. More labels overlap unpredictably at this size.
    biggest = nodes[0]
    label_font = load_font(20 * SUPERSAMPLE, bold=True)
    draw.text((left + biggest["x"], top + biggest["y"] + biggest["r"] * SUPERSAMPLE + 8 * SUPERSAMPLE),
              fit_text(draw, biggest["name"], label_font, 260 * SUPERSAMPLE),
              font=label_font, fill=INK, anchor="ma")


def _draw_stat_tiles(draw, stats, left, top, width):
    tiles = [
        (f"{stats.get('artist_count', 0)}", "Artists"),
        (f"{stats.get('song_count', 0)}", "Songs"),
        (f"{round((stats.get('diversity') or 0.0) * 100)}", "Diversity"),
    ]
    obscurity = stats.get("obscurity")
    if obscurity is not None:
        tiles.append((f"{obscurity:.0f}", "Obscurity"))

    value_font = load_font(40 * SUPERSAMPLE, bold=True)
    label_font = load_font(17 * SUPERSAMPLE)
    step = width / len(tiles)
    for i, (value, label) in enumerate(tiles):
        x = left + i * step
        draw.text((x, top), value, font=value_font, fill=INK)
        draw.text((x, top + 48 * SUPERSAMPLE), label.upper(), font=label_font, fill=MUTED)


def render_card(profile_name: str, archetype: dict, stats: dict,
                meta: dict, library: dict) -> bytes:
    """Render the share card and return PNG bytes.

    Drawn at SUPERSAMPLE scale and downsampled, because Pillow's primitives are
    not antialiased.
    """
    width, height = CARD_WIDTH * SUPERSAMPLE, CARD_HEIGHT * SUPERSAMPLE
    image = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)

    panel = [620 * SUPERSAMPLE, 40 * SUPERSAMPLE,
             1160 * SUPERSAMPLE, 590 * SUPERSAMPLE]
    draw.rounded_rectangle(panel, radius=24 * SUPERSAMPLE, fill=PANEL)
    _draw_constellation(image, draw, stats, meta, library,
                        (panel[0] + 20 * SUPERSAMPLE, panel[1] + 20 * SUPERSAMPLE,
                         500 * SUPERSAMPLE, 510 * SUPERSAMPLE))

    text_left = 64 * SUPERSAMPLE
    text_width = 500 * SUPERSAMPLE

    name_font = load_font(56 * SUPERSAMPLE, bold=True)
    y = 96 * SUPERSAMPLE
    for line in wrap_text(draw, archetype.get("name", ""), name_font, text_width)[:2]:
        draw.text((text_left, y), line, font=name_font, fill=INK)
        y += 66 * SUPERSAMPLE

    tagline_font = load_font(25 * SUPERSAMPLE)
    y += 8 * SUPERSAMPLE
    for line in wrap_text(draw, archetype.get("tagline", ""), tagline_font, text_width)[:3]:
        draw.text((text_left, y), line, font=tagline_font, fill=MUTED)
        y += 34 * SUPERSAMPLE

    _draw_stat_tiles(draw, stats, text_left, 400 * SUPERSAMPLE, text_width)

    owner_font = load_font(22 * SUPERSAMPLE, bold=True)
    draw.text((text_left, 546 * SUPERSAMPLE),
              fit_text(draw, profile_name or "", owner_font, text_width),
              font=owner_font, fill=ACCENT)

    image = image.resize((CARD_WIDTH, CARD_HEIGHT), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_card_render.py -v`
Expected: 16 passed

- [ ] **Step 5: Render the real library's card and look at it**

Run:

```bash
cd backend && ./venv/bin/python -c "
import json
from library import library_from_graph_data
from artist_meta import load_meta
from taste_profile import build_profile_stats
from archetype import resolve_archetype
from card_render import render_card

def load(path, default):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return default

g = load('../frontend/graph_data.json', {'nodes': [], 'links': []})
lib = library_from_graph_data(g)
meta = load_meta()
stats = build_profile_stats(lib, meta, load('data/track_years.json', {}),
                            load('data/genre_reference.json', {}), g)
png = render_card('Will', resolve_archetype(stats), stats, meta, lib)
open('/tmp/card.png', 'wb').write(png)
print(len(png), 'bytes ->', '/tmp/card.png')
"
```

Then open `/tmp/card.png` and confirm: the archetype reads "Main Stage Omnivore", the tagline is a real sentence rather than "Built on Other", the four tiles are legible, and the constellation shows roughly 40 circles of visibly different sizes and colours with a handful of connecting lines. Write it to `/tmp`, **not** into the repo — `.gitignore` blocks `*.png` except `screenshot.png`, and a card of real data must not be committed regardless.

- [ ] **Step 6: Commit**

```bash
git add backend/card_render.py backend/tests/test_card_render.py
git commit -m "Draw the share card over a constellation of the profile's top artists"
```

---

### Task 4: Serve the card at `GET /p/<id>/card.png`

**Files:**
- Modify: `backend/server.py`
- Create: `backend/tests/test_card_endpoint.py`

**Interfaces:**
- Consumes: `card_render.render_card`, `profile_manager.get_profile`
- Produces:
  - `_stats_bundle(profile) -> dict` — the shared loader for stats, archetype, and badges
  - route `GET /p/<profile_id>/card.png`

`_stats_bundle` is extracted from the existing `api_profile_stats` body so the card endpoint, the stats endpoint, the OG tags, and profile creation all compute stats one way. Four call sites drifting apart is how the tagline bug in Spec A's Task 13 survived as long as it did.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_card_endpoint.py`:

```python
import io

import pytest
from PIL import Image

import profile_manager
import server


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Never touch backend/profiles/ — it holds real user data.
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    server.app.config["TESTING"] = True
    return server.app.test_client()


@pytest.fixture
def profile_id():
    return profile_manager.create_profile(
        {"liked_songs": [
            {"title": "Strangers", "artists": [{"name": "Seven Lions"}]},
            {"title": "Sad Songs", "artists": [{"name": "ILLENIUM, Wooli"}]},
        ]}, name="Test Listener")["id"]


def test_unknown_profile_is_404(client):
    assert client.get("/p/deadbeef/card.png").status_code == 404


def test_card_is_a_png_of_the_right_size(client, profile_id):
    response = client.get(f"/p/{profile_id}/card.png")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/png"
    assert Image.open(io.BytesIO(response.data)).size == (1200, 630)


def test_card_is_cacheable(client, profile_id):
    # Crawlers refetch the OG image; without this every preview re-renders.
    assert "max-age" in client.get(f"/p/{profile_id}/card.png").headers["Cache-Control"]


def test_card_does_not_leak_the_host_library(client, profile_id, monkeypatch):
    # A visitor's card must be built from their own data. If the endpoint were
    # reading the server's graph_data.json for structure, replacing it with an
    # unrelated graph would change the bytes.
    first = client.get(f"/p/{profile_id}/card.png").data
    monkeypatch.setattr(server, "_load_json",
                        lambda path, default: {"nodes": [
                            {"name": "Some Stranger", "song_count": 900,
                             "songs": [{"title": "x", "album": ""}]}],
                            "links": []} if "graph_data" in path else default)
    assert client.get(f"/p/{profile_id}/card.png").data == first
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_card_endpoint.py -v`
Expected: FAIL — `/p/<id>/card.png` returns 404 for the real profile too, because the route does not exist yet.

- [ ] **Step 3: Refactor the stats loader out of the endpoint**

In `backend/server.py`, add `from card_render import render_card` and `from flask import Response` to the imports, then replace the body of `api_profile_stats` with a call to a new shared helper. Insert immediately above `api_profile_stats`:

```python
def _stats_bundle(profile: dict) -> dict:
    """Everything derived from a stored profile: stats, archetype, badges.

    One loader for the stats endpoint, the card, the OpenGraph tags, and
    profile creation — four call sites computing this separately is how the
    archetype tagline and the genre chart disagreed in Spec A.
    """
    meta = load_meta()
    years = _load_json("data/track_years.json", {})
    reference = _load_json("data/genre_reference.json", {})
    graph = _load_json("../frontend/graph_data.json", {"nodes": [], "links": []})
    stats = build_profile_stats(profile["music_data"], meta, years, reference, graph)
    return {
        "meta": meta,
        "stats": stats,
        "archetype": resolve_archetype(stats),
        "badges": compute_badges(stats),
    }
```

Then rewrite `api_profile_stats` to use it:

```python
@app.route("/api/profile/<profile_id>/stats")
def api_profile_stats(profile_id):
    profile = get_profile(profile_id, include_music_data=True)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    bundle = _stats_bundle(profile)
    stats = bundle["stats"]

    peers = list_public_profiles(limit=500)
    percentile = None
    if len(peers) >= MIN_PEERS_FOR_RELATIVE_RANKING and stats["obscurity"] is not None:
        scores = [p.get("stats", {}).get("obscurity") for p in peers]
        scores = [s for s in scores if s is not None]
        if scores:
            below = sum(1 for s in scores if s < stats["obscurity"])
            percentile = round(100.0 * below / len(scores), 1)

    return jsonify({
        "profile": {"id": profile["id"], "name": profile["name"]},
        "stats": stats,
        "archetype": bundle["archetype"],
        "badges": bundle["badges"],
        "peer_percentile": percentile,
        "writeup": profile.get("writeup"),
    })
```

The `writeup` key is wired up in Task 8; returning `None` until then is correct and the page must already tolerate it.

- [ ] **Step 4: Add the card route**

Insert after `profile_page` in `backend/server.py`:

```python
@app.route("/p/<profile_id>/card.png")
def profile_card(profile_id):
    """The share card. This one URL is both the OpenGraph image and the
    user-facing download, so the preview and the download cannot drift."""
    profile = get_profile(profile_id, include_music_data=True)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    bundle = _stats_bundle(profile)
    png = render_card(profile["name"], bundle["archetype"], bundle["stats"],
                      bundle["meta"], profile["music_data"])
    response = Response(png, mimetype="image/png")
    # Crawlers refetch this on every unfurl; the card only changes if the
    # profile does, and profiles are immutable once created.
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_card_endpoint.py tests/ -v`
Expected: 4 passed in the new file, and the whole suite still green.

- [ ] **Step 6: Verify against the running server**

Run:

```bash
cd backend && ./venv/bin/python server.py &
sleep 10
ID=$(ls profiles/*.json | grep -v _public_index | head -1 | xargs basename | sed 's/.json//')
curl -s -o /tmp/live-card.png -w "%{http_code} %{content_type} %{size_download}\n" \
  "http://127.0.0.1:5050/p/$ID/card.png"
file /tmp/live-card.png
kill %1
```

Expected: `200 image/png` with a size in the tens of kilobytes, and `file` reporting `PNG image data, 1200 x 630`. Use `127.0.0.1`, not `localhost` — the server binds IPv4 only — and keep the `sleep`, because the reloader needs roughly 8 seconds before it answers.

- [ ] **Step 7: Commit**

```bash
git add backend/server.py backend/tests/test_card_endpoint.py
git commit -m "Serve the share card as PNG and unify the stats loader"
```

---

### Task 5: Server-rendered OpenGraph tags on `/p/<id>`

**Files:**
- Modify: `backend/server.py`, `frontend/profile.html`
- Create: `backend/tests/test_og_tags.py`

**Interfaces:**
- Consumes: `_stats_bundle`, `markupsafe.escape`
- Produces:
  - `_external_base() -> str`
  - `_render_og_tags(profile_id, name, archetype, stats) -> str`
  - `profile_page` now returns injected HTML rather than the raw static file

`profile.html` is static and fetches its data client-side, so a crawler currently sees the literal string "Loading…" and no image. Crawlers do not run JavaScript, so the tags must be in the bytes the server sends. Injection is done by replacing a placeholder comment rather than by moving the page into Jinja templates: the file keeps working when opened directly, and the diff stays small.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_og_tags.py`:

```python
import pytest

import profile_manager
import server


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    server.app.config["TESTING"] = True
    return server.app.test_client()


def _make(name="Test Listener"):
    return profile_manager.create_profile(
        {"liked_songs": [{"title": "Strangers", "artists": [{"name": "Seven Lions"}]}]},
        name=name)["id"]


def test_crawler_sees_the_archetype_without_running_javascript(client):
    html = client.get(f"/p/{_make()}").get_data(as_text=True)
    assert 'property="og:title"' in html
    # The page's own JS never ran, so this can only have come from the server.
    assert "Main Stage" in html or "Scene Regular" in html or "Loyalist" in html


def test_og_image_is_an_absolute_url_to_the_card(client):
    profile_id = _make()
    html = client.get(f"/p/{profile_id}").get_data(as_text=True)
    assert f'content="http://localhost/p/{profile_id}/card.png"' in html


def test_og_image_honours_the_forwarded_protocol(client):
    profile_id = _make()
    html = client.get(f"/p/{profile_id}",
                      headers={"X-Forwarded-Proto": "https"}).get_data(as_text=True)
    assert f"https://localhost/p/{profile_id}/card.png" in html


def test_profile_name_is_escaped_into_the_meta_tags(client):
    html = client.get(f'/p/{_make(chr(34) + "><script>alert(1)</script>")}') \
                 .get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_twitter_card_is_declared_large(client):
    html = client.get(f"/p/{_make()}").get_data(as_text=True)
    assert 'name="twitter:card"' in html and "summary_large_image" in html


def test_unknown_profile_still_serves_the_page(client):
    # The client-side code renders "Profile not found"; the route must not 500.
    response = client.get("/p/deadbeef")
    assert response.status_code == 200
    assert "og:title" not in response.get_data(as_text=True)


def test_the_placeholder_is_gone_from_the_served_html(client):
    assert "<!--og-meta-->" not in client.get(f"/p/{_make()}").get_data(as_text=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_og_tags.py -v`
Expected: FAIL — the served HTML contains no `og:title`.

- [ ] **Step 3: Add the placeholder to the page**

In `frontend/profile.html`, insert immediately after the `<title>` line:

```html
    <!--og-meta-->
```

The comment is inert when the file is opened directly and is what the server replaces.

- [ ] **Step 4: Write the implementation**

In `backend/server.py`, add `from markupsafe import escape` to the imports, then replace `profile_page` with:

```python
def _external_base() -> str:
    """Scheme and host as the outside world sees them.

    Railway and Render terminate TLS at the proxy, so request.scheme is http
    even when the public URL is https. An http og:image on an https page is
    dropped by several unfurlers, so trust the forwarded header when present.
    """
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
    host = request.headers.get("X-Forwarded-Host", request.host)
    return f"{scheme}://{host}"


def _render_og_tags(profile_id: str, name: str, archetype: dict, stats: dict) -> str:
    base = _external_base()
    page_url = f"{base}/p/{profile_id}"
    card_url = f"{page_url}/card.png"
    artists = stats.get("artist_count", 0)
    songs = stats.get("song_count", 0)
    description = f"{archetype['tagline']} {artists} artists, {songs} songs."
    # Every interpolated value is either an integer we computed or a string a
    # user supplied; escape() covers both rather than trusting the source.
    tags = [
        ("og:type", "website"),
        ("og:site_name", "Music Taste Profile"),
        ("og:title", f"{name} — {archetype['name']}"),
        ("og:description", description),
        ("og:url", page_url),
        ("og:image", card_url),
        ("og:image:width", "1200"),
        ("og:image:height", "630"),
        ("og:image:alt", f"{archetype['name']} taste card"),
    ]
    lines = [f'<meta property="{key}" content="{escape(value)}">' for key, value in tags]
    lines += [
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{escape(name)} — {escape(archetype["name"])}">',
        f'<meta name="twitter:description" content="{escape(description)}">',
        f'<meta name="twitter:image" content="{escape(card_url)}">',
        f'<meta name="description" content="{escape(description)}">',
    ]
    return "\n    ".join(lines)


@app.route("/p/<profile_id>")
def profile_page(profile_id):
    """Serve the taste-profile page with OpenGraph tags rendered in.

    profile.html fetches its data client-side and crawlers do not run
    JavaScript, so without this an unfurled link shows "Loading…" and no image.
    """
    page = os.path.join(app.static_folder, "profile.html")
    with open(page) as f:
        html = f.read()

    profile = get_profile(profile_id, include_music_data=True)
    if not profile:
        # Unknown id: serve the page unchanged and let the client render its
        # own "Profile not found" rather than inventing tags for nothing.
        return Response(html.replace("<!--og-meta-->", ""), mimetype="text/html")

    bundle = _stats_bundle(profile)
    tags = _render_og_tags(profile_id, profile["name"],
                           bundle["archetype"], bundle["stats"])
    return Response(html.replace("<!--og-meta-->", tags), mimetype="text/html")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_og_tags.py tests/ -v`
Expected: 7 passed in the new file; the full suite still green.

- [ ] **Step 6: Verify what a crawler actually receives**

Run:

```bash
cd backend && ./venv/bin/python server.py &
sleep 10
ID=$(ls profiles/*.json | grep -v _public_index | head -1 | xargs basename | sed 's/.json//')
curl -s -H 'X-Forwarded-Proto: https' "http://127.0.0.1:5050/p/$ID" | grep -o '<meta[^>]*og:[^>]*>'
kill %1
```

Expected: nine `og:` meta tags, with `og:image` pointing at an `https://.../card.png` URL and `og:title` naming the archetype.

- [ ] **Step 7: Commit**

```bash
git add backend/server.py frontend/profile.html backend/tests/test_og_tags.py
git commit -m "Render OpenGraph tags into the profile page so links unfurl"
```

---

### Task 6: Show and download the card from the profile page

**Files:**
- Modify: `frontend/profile.html`, `frontend/js/profile.js`, `frontend/css/styles.css`

**Interfaces:**
- Consumes: `GET /p/<id>/card.png`
- Produces: a card preview and a "Download card" link on the profile page

The download link points at the same URL the crawler fetches. No client-side canvas rendering — a second renderer is a second thing to keep in sync, and Spec B exists partly to prevent that.

- [ ] **Step 1: Add the card section to the page**

In `frontend/profile.html`, insert immediately before the `<footer class="profile-footer">` line:

```html
        <section class="profile-section profile-card-share" id="cardSection" hidden>
            <h2>Your card</h2>
            <img id="cardPreview" class="card-preview" alt="Your taste card" loading="lazy">
            <p class="muted">This is exactly what people see when you paste your link
               into iMessage, Discord, or Slack.</p>
            <a class="btn btn-secondary" id="downloadCard" download>Download card</a>
        </section>
```

- [ ] **Step 2: Wire it up**

In `frontend/js/profile.js`, add inside `load()` immediately after the `el('badges').innerHTML = ...` assignment:

```javascript
    // Same URL the crawler fetches for og:image — one renderer, no drift.
    const cardUrl = `/p/${profileId}/card.png`;
    el('cardPreview').src = cardUrl;
    el('downloadCard').href = cardUrl;
    el('downloadCard').setAttribute('download', `taste-card-${profileId}.png`);
    el('cardSection').hidden = false;
```

`profileId` comes from the pathname at the top of the file and is not user-controlled beyond the URL, but it is interpolated into an attribute rather than into `innerHTML`, so no escaping is required here. Anything of yours that does reach `innerHTML` must still go through `esc()`.

- [ ] **Step 3: Style it**

Append to `frontend/css/styles.css`:

```css
.profile-card-share .card-preview {
    display: block;
    width: 100%;
    max-width: 600px;
    height: auto;
    border-radius: 12px;
    margin: 12px 0;
}
```

- [ ] **Step 4: Verify in a browser**

Run the server, open `http://127.0.0.1:5050/p/<id>`, and confirm the card preview renders inline, the download link saves a PNG named `taste-card-<id>.png`, and the page still looks right at a 375px-wide viewport.

- [ ] **Step 5: Commit**

```bash
git add frontend/profile.html frontend/js/profile.js frontend/css/styles.css
git commit -m "Show the share card on the profile page and offer it as a download"
```

---

### Task 7: LLM taste write-up

**Files:**
- Create: `backend/taste_writeup.py`, `backend/tests/test_taste_writeup.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: the stats dict, the archetype dict
- Produces:
  - `MODEL = "claude-sonnet-5"`, `SYSTEM_PROMPT`, `MAX_WORDS = 60`
  - `build_facts(stats, archetype) -> str`
  - `generate_writeup(stats, archetype) -> str | None`

Gated on `ANTHROPIC_API_KEY`. Fed only computed numbers and artist names that are already in the profile. Returns `None` on absent key, on any API failure, and on a refusal — the page must render identically without it.

`claude-sonnet-5` is the right tier here: the output is two or three sentences, it is generated once per profile and cached, and Sonnet 5 is near-Opus on this kind of constrained rewriting at a fraction of the cost.

- [ ] **Step 1: Add the SDK**

Append to `backend/requirements.txt`:

```
anthropic>=0.69.0
```

Run: `cd backend && ./venv/bin/python -m pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

`backend/tests/test_taste_writeup.py`:

```python
import pytest

import taste_writeup
from taste_writeup import build_facts, generate_writeup

STATS = {
    "artist_count": 1156, "song_count": 3039, "obscurity": 20.26,
    "scene_obscurity": 39.6, "diversity": 0.741, "median_year": 2020,
    "genres": {"Dubstep/Bass": 0.15, "Progressive House": 0.12, "Other": 0.04},
    "top_artists": [("Seven Lions", 95), ("ILLENIUM", 67)],
    "moods": {"Chill": 0.64, "Dark": 0.30},
    "one_song_share": 0.635,
}
ARCHETYPE = {"name": "Main Stage Omnivore",
             "tagline": "Built on Dubstep/Bass, firmly in the present."}


def test_facts_carry_the_real_numbers():
    facts = build_facts(STATS, ARCHETYPE)
    assert "1156" in facts and "3039" in facts and "Seven Lions" in facts


def test_facts_omit_dimensions_that_are_missing():
    # A null must not appear as the word "None" for the model to narrate.
    facts = build_facts(dict(STATS, median_year=None, scene_obscurity=None), ARCHETYPE)
    assert "None" not in facts
    assert "median release year" not in facts.lower()


def test_facts_never_mention_the_unresolved_genre_bucket():
    # "Other" is the absence of a genre. Spec A shipped a tagline reading
    # "Built on Other" by ranking it alongside real genres.
    assert "Other" not in build_facts(STATS, ARCHETYPE)


def test_no_key_means_no_writeup(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert generate_writeup(STATS, ARCHETYPE) is None


def test_an_api_failure_returns_none_rather_than_raising(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("connection reset")

    monkeypatch.setattr(taste_writeup, "_client_factory", Boom)
    assert generate_writeup(STATS, ARCHETYPE) is None


def test_a_refusal_returns_none(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    class Response:
        stop_reason = "refusal"
        content = []

    monkeypatch.setattr(taste_writeup, "_client_factory",
                        lambda **kw: _FakeClient(Response()))
    assert generate_writeup(STATS, ARCHETYPE) is None


def test_a_normal_response_is_returned_stripped(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    class Block:
        type = "text"
        text = "  You lean on melodic bass.  "

    class Response:
        stop_reason = "end_turn"
        content = [Block()]

    monkeypatch.setattr(taste_writeup, "_client_factory",
                        lambda **kw: _FakeClient(Response()))
    assert generate_writeup(STATS, ARCHETYPE) == "You lean on melodic bass."


def test_the_request_never_sends_rejected_sampling_parameters(monkeypatch):
    # temperature / top_p / top_k are a 400 on claude-sonnet-5.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    captured = {}

    class Block:
        type = "text"
        text = "ok"

    class Response:
        stop_reason = "end_turn"
        content = [Block()]

    client = _FakeClient(Response(), captured)
    monkeypatch.setattr(taste_writeup, "_client_factory", lambda **kw: client)
    generate_writeup(STATS, ARCHETYPE)
    assert not {"temperature", "top_p", "top_k"} & set(captured)
    assert captured["model"] == "claude-sonnet-5"


class _FakeMessages:
    def __init__(self, response, captured=None):
        self._response = response
        self._captured = captured

    def create(self, **kwargs):
        if self._captured is not None:
            self._captured.update(kwargs)
        return self._response


class _FakeClient:
    def __init__(self, response, captured=None):
        self.messages = _FakeMessages(response, captured)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_taste_writeup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'taste_writeup'`

- [ ] **Step 4: Write the implementation**

`backend/taste_writeup.py`:

```python
"""Optional LLM paragraph over the computed statistics.

Generated once at profile creation and cached into the profile JSON, so a page
view never waits on an API call. Everything here is best-effort: no key, a
network failure, or a refusal all return None and the page renders unchanged.

The model sees only numbers this codebase computed and artist names already in
the profile. It is told to invent nothing, because the whole page's credibility
rests on every claim being traceable to the library.
"""

import os

MODEL = "claude-sonnet-5"
MAX_WORDS = 60

SYSTEM_PROMPT = (
    "You write one short paragraph about someone's music taste for their "
    "profile page. You are given only computed statistics about their library.\n"
    "\n"
    "Rules, in order of importance:\n"
    "1. Invent nothing. Every claim must be traceable to a number or a name in "
    "the data you are given. Do not name an artist that is not listed, a genre "
    "that is not listed, a song, an album, a year, a chart position, or a "
    "record label. Do not describe the person's mood, age, personality, "
    "profession, or when and where they listen. Do not guess what an artist "
    "sounds like beyond the genre label given.\n"
    "2. If a statistic is absent from the data, say nothing about that "
    "dimension. Absence is not a fact to report.\n"
    "3. Two or three sentences, at most " + str(MAX_WORDS) + " words total. "
    "Address the reader as \"you\". Plain declarative prose.\n"
    "4. No markdown, no bullet points, no headings, no emoji, no quotation "
    "marks around names, and no preamble such as \"Here is\" or \"Based on\". "
    "Output only the paragraph itself.\n"
    "5. The page already displays the archetype name and tagline directly "
    "above your text. Do not repeat either verbatim; add something the "
    "numbers support that those two lines do not already say.\n"
    "6. Be specific rather than flattering. Do not tell the reader their taste "
    "is great, eclectic, or impressive. Describe the shape of the library."
)


def _client_factory(**kwargs):
    # Indirected so tests can substitute a fake without importing anthropic.
    import anthropic
    return anthropic.Anthropic(**kwargs)


def build_facts(stats: dict, archetype: dict) -> str:
    """Render the model's entire view of the library.

    Every line is a number this codebase computed. A dimension that is None is
    omitted rather than rendered as "None", so the model cannot narrate a gap.
    """
    lines = [
        f"Archetype already shown on the page: {archetype.get('name')}",
        f"Tagline already shown on the page: {archetype.get('tagline')}",
        f"Distinct artists: {stats.get('artist_count', 0)}",
        f"Liked songs: {stats.get('song_count', 0)}",
    ]

    obscurity = stats.get("obscurity")
    if obscurity is not None:
        lines.append(
            f"Obscurity: {obscurity:.1f} out of 100, where 0 means every artist "
            f"is a household name and 100 means none of them are")
    scene = stats.get("scene_obscurity")
    if scene is not None:
        lines.append(
            f"Obscurity measured only against other artists in the same genres: "
            f"{scene:.0f}th percentile")

    diversity = stats.get("diversity")
    if diversity is not None:
        lines.append(
            f"Genre diversity: {diversity:.2f} out of 1, entropy across a fixed "
            f"51-genre vocabulary")

    # "Other" is the unresolved bucket - the absence of a genre, not a genre.
    genres = {g: w for g, w in (stats.get("genres") or {}).items() if g != "Other"}
    if genres:
        ranked = sorted(genres.items(), key=lambda kv: -kv[1])[:5]
        lines.append("Top genres by share of library: " +
                     ", ".join(f"{g} {w * 100:.0f}%" for g, w in ranked))

    top_artists = stats.get("top_artists") or []
    if top_artists:
        lines.append("Most played artists, with song counts: " +
                     ", ".join(f"{n} ({c})" for n, c in top_artists[:10]))

    moods = stats.get("moods") or {}
    if moods:
        ranked = sorted(moods.items(), key=lambda kv: -kv[1])[:3]
        lines.append("Mood tags, from Last.fm tags rather than audio analysis: " +
                     ", ".join(f"{m} {w * 100:.0f}%" for m, w in ranked))

    median_year = stats.get("median_year")
    if median_year is not None:
        lines.append(f"Median release year: {median_year}")

    one_song = stats.get("one_song_share")
    if one_song is not None:
        lines.append(f"Share of artists represented by exactly one song: "
                     f"{one_song * 100:.0f}%")

    return "\n".join(lines)


def generate_writeup(stats: dict, archetype: dict):
    """Return the paragraph, or None if it cannot be produced.

    Never raises: the profile page is required to render without this.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        client = _client_factory(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            # Thinking off and effort low: this is a short constrained rewrite
            # of facts that are already computed, not a reasoning task.
            # temperature / top_p / top_k are rejected with a 400 on this model.
            thinking={"type": "disabled"},
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": build_facts(stats, archetype)}],
        )
        if getattr(response, "stop_reason", None) == "refusal":
            return None
        for block in response.content:
            if getattr(block, "type", None) == "text" and block.text.strip():
                return block.text.strip()
        return None
    except Exception as exc:
        # A missing paragraph is a cosmetic loss; a 500 on profile creation is not.
        print(f"  write-up skipped: {type(exc).__name__}: {str(exc)[:120]}", flush=True)
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_taste_writeup.py -v`
Expected: 8 passed

- [ ] **Step 6: Print the real prompt and read it**

Run:

```bash
cd backend && ./venv/bin/python -c "
import json
from library import library_from_graph_data
from artist_meta import load_meta
from taste_profile import build_profile_stats
from archetype import resolve_archetype
from taste_writeup import build_facts

def load(p, d):
    try: return json.load(open(p))
    except (OSError, ValueError): return d

g = load('../frontend/graph_data.json', {'nodes': [], 'links': []})
lib = library_from_graph_data(g)
stats = build_profile_stats(lib, load_meta(), load('data/track_years.json', {}),
                            load('data/genre_reference.json', {}), g)
print(build_facts(stats, resolve_archetype(stats)))
"
```

Read the output and confirm every line is a number this codebase computed, that no line says `None`, and that `Other` does not appear. If `ANTHROPIC_API_KEY` is set in your shell, also make one live call and read the paragraph — check specifically that it names no artist absent from the "Most played artists" line. **Do not** commit the paragraph or the facts block; the reference library is real user data.

- [ ] **Step 7: Commit**

```bash
git add backend/taste_writeup.py backend/tests/test_taste_writeup.py backend/requirements.txt
git commit -m "Add the optional LLM taste write-up, fed only computed statistics"
```

---

### Task 8: Cache the write-up at profile creation and render it

**Files:**
- Modify: `backend/profile_manager.py`, `backend/server.py`, `frontend/profile.html`, `frontend/js/profile.js`
- Create: `backend/tests/test_profile_writeup.py`

**Interfaces:**
- Consumes: `taste_writeup.generate_writeup`, `_stats_bundle`
- Produces: `create_profile(..., writeup=None, extra_stats=None)`; `writeup` on the stats response; a rendered paragraph

Generated once, at creation, then stored. A page view must never wait on the API, and a profile created before the key existed must keep working.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_profile_writeup.py`:

```python
import json

import pytest

import profile_manager
import server


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    server.app.config["TESTING"] = True
    return tmp_path / "profiles"


MUSIC = {"liked_songs": [{"title": "Strangers", "artists": [{"name": "Seven Lions"}]}]}


def test_writeup_is_persisted_into_the_profile(isolated):
    result = profile_manager.create_profile(MUSIC, name="A", writeup="You like bass.")
    stored = json.loads((isolated / f"{result['id']}.json").read_text())
    assert stored["writeup"] == "You like bass."


def test_absent_writeup_stores_none(isolated):
    result = profile_manager.create_profile(MUSIC, name="A")
    stored = json.loads((isolated / f"{result['id']}.json").read_text())
    assert stored["writeup"] is None


def test_extra_stats_are_merged_into_the_stored_stats(isolated):
    result = profile_manager.create_profile(MUSIC, name="A",
                                            extra_stats={"obscurity": 20.3})
    stored = json.loads((isolated / f"{result['id']}.json").read_text())
    assert stored["stats"]["obscurity"] == 20.3
    # The pre-existing keys must survive the merge.
    assert "artist_count" in stored["stats"]


def test_the_stats_endpoint_serves_the_cached_writeup(isolated):
    profile_id = profile_manager.create_profile(MUSIC, name="A",
                                                writeup="You like bass.")["id"]
    body = server.app.test_client().get(f"/api/profile/{profile_id}/stats").get_json()
    assert body["writeup"] == "You like bass."


def test_a_legacy_profile_without_the_field_serves_none(isolated):
    profile_id = profile_manager.create_profile(MUSIC, name="A")["id"]
    path = isolated / f"{profile_id}.json"
    stored = json.loads(path.read_text())
    del stored["writeup"]
    path.write_text(json.dumps(stored))
    body = server.app.test_client().get(f"/api/profile/{profile_id}/stats").get_json()
    assert body["writeup"] is None


def test_creation_succeeds_when_the_write_up_call_fails(isolated, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    # Patch the name server.py bound at import time. Patching
    # taste_writeup.generate_writeup would not work: server.py does
    # "from taste_writeup import generate_writeup", so it holds its own
    # reference and never looks the attribute up again.
    monkeypatch.setattr(server, "generate_writeup", boom)
    client = server.app.test_client()
    response = client.post("/api/profile/create",
                           json={"music_data": MUSIC, "name": "A"})
    assert response.status_code == 200
    assert response.get_json()["id"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_profile_writeup.py -v`
Expected: FAIL with `TypeError: create_profile() got an unexpected keyword argument 'writeup'`

- [ ] **Step 3: Accept the two new fields in profile_manager**

In `backend/profile_manager.py`, change the signature and the profile dict:

```python
def create_profile(music_data: dict, name: str = "", public: bool = False,
                   writeup: Optional[str] = None,
                   extra_stats: Optional[Dict] = None) -> dict:
```

Extend the docstring's Args block with:

```
        writeup: Optional cached LLM paragraph. Generated once by the caller so
            a page view never waits on an API call.
        extra_stats: Extra computed values merged into stats — notably
            "obscurity", which the public index needs for peer percentiles.
```

Then, in the `profile` dict literal, replace the `"stats"` entry and add `"writeup"`:

```python
        "stats": {
            "artist_count": len(artist_counts),
            "song_count": sum(artist_counts.values()),
            "top_genre": taste_vector.get("top_genre", "Unknown"),
            "diversity_score": taste_vector.get("diversity_score", 0),
            **(extra_stats or {}),
        },
        "writeup": writeup,
```

- [ ] **Step 4: Generate it at creation**

In `backend/server.py`, add `from taste_writeup import generate_writeup` to the imports and replace the body of `api_create_profile`:

```python
@app.route("/api/profile/create", methods=["POST"])
def api_create_profile():
    """Create a new taste profile from music data."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    music_data = data.get("music_data")
    name = data.get("name", "")
    public = bool(data.get("public", False))

    if not music_data or not music_data.get("liked_songs"):
        return jsonify({"error": "No music data provided"}), 400

    # Compute once here so the write-up and the stored obscurity come from the
    # same numbers the profile page will later show.
    bundle = _stats_bundle({"music_data": music_data})
    try:
        writeup = generate_writeup(bundle["stats"], bundle["archetype"])
    except Exception as exc:
        # generate_writeup already swallows its own failures; this is the belt
        # to that braces. A missing paragraph must never fail profile creation.
        print(f"  write-up skipped: {type(exc).__name__}", flush=True)
        writeup = None

    result = create_profile(music_data, name=name, public=public,
                            writeup=writeup,
                            extra_stats={"obscurity": bundle["stats"]["obscurity"]})
    return jsonify(result)
```

- [ ] **Step 5: Render it on the page**

In `frontend/profile.html`, insert immediately after the `headlineStats` section:

```html
        <section class="profile-section" id="writeupSection" hidden></section>
```

In `frontend/js/profile.js`, destructure `writeup` from the response and render it after the badges are set:

```javascript
    const { profile, stats, archetype, badges, peer_percentile, writeup } =
        await response.json();
```

```javascript
    // Optional: absent whenever ANTHROPIC_API_KEY was unset at creation, and
    // absent on every profile created before this existed.
    if (writeup) {
        section(el('writeupSection'), 'In a sentence',
            `<p class="writeup">${esc(writeup)}</p>
             <p class="muted">Written by Claude from the statistics on this page.</p>`);
    }
```

The `esc()` call is not optional. The paragraph is model output, and model output that reaches `innerHTML` unescaped is an injection sink regardless of how it was produced.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/ -v`
Expected: everything green, including the 6 new tests.

- [ ] **Step 7: Commit**

```bash
git add backend/profile_manager.py backend/server.py backend/tests/test_profile_writeup.py \
        frontend/profile.html frontend/js/profile.js
git commit -m "Cache the taste write-up at creation and render it when present"
```

---

### Task 9: The onboarding page — paste and file upload

**Files:**
- Create: `frontend/onboard.html`, `frontend/js/onboard.js`, `backend/onboard_import.py`, `backend/tests/test_onboard_import.py`
- Modify: `backend/server.py`

**Interfaces:**
- Consumes: `parse_liked_songs_paste.parse`, `parse_liked_songs_paste.to_music_data`
- Produces:
  - `LibraryImportError`
  - `parse_library_text(text, fallback=None) -> dict` — music_data, raising `LibraryImportError` on unparseable input
  - route `GET /onboard`
  - route `POST /api/onboard/paste`

A visitor who lands on a share link with no data of their own needs a path from zero to a comparison. This task builds the page and the two paths that need no browser extension: paste and file upload.

`parse()` raises `SystemExit`, which `except Exception` does **not** catch — verified during planning. A handler that does not catch it explicitly lets a `BaseException` escape on any malformed paste.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_onboard_import.py`:

```python
import pytest

from onboard_import import LibraryImportError, parse_library_text

PAGE = """Liked songs
Music you like in any YouTube app will show here

Strangers
Seven Lions
Strangers
3:41

Sad Songs
ILLENIUM, Wooli, & Grabbitz
Sad Songs
3:20
"""


def test_a_real_page_paste_parses_into_music_data():
    music = parse_library_text(PAGE)
    assert len(music["liked_songs"]) == 2
    assert music["liked_songs"][0]["title"] == "Strangers"
    assert music["liked_songs"][0]["artists"][0]["name"] == "Seven Lions"


def test_the_collaboration_string_survives_intact_for_later_splitting():
    music = parse_library_text(PAGE)
    assert music["liked_songs"][1]["artists"][0]["name"] == "ILLENIUM, Wooli, & Grabbitz"


def test_a_missing_marker_raises_our_error_not_systemexit():
    # parse() raises SystemExit, which "except Exception" does NOT catch. If
    # this leaks, a bad paste takes down the request with a BaseException.
    with pytest.raises(LibraryImportError):
        parse_library_text("just some words")


def test_the_fallback_parser_is_tried_when_the_marker_is_absent():
    def fallback(text):
        return [{"title": "Fallback Song", "artist": "Fallback Artist"}]

    music = parse_library_text("no marker here", fallback=fallback)
    assert music["liked_songs"][0]["title"] == "Fallback Song"
    assert music["liked_songs"][0]["artists"][0]["name"] == "Fallback Artist"


def test_a_fallback_that_finds_nothing_still_raises():
    with pytest.raises(LibraryImportError):
        parse_library_text("no marker here", fallback=lambda text: [])


def test_a_fallback_that_explodes_is_treated_as_no_result():
    def boom(text):
        raise ValueError("nope")

    with pytest.raises(LibraryImportError):
        parse_library_text("no marker here", fallback=boom)


def test_empty_input_raises():
    with pytest.raises(LibraryImportError):
        parse_library_text("   ")


def test_a_page_with_the_marker_but_no_songs_raises():
    with pytest.raises(LibraryImportError):
        parse_library_text("Music you like in any YouTube app will show here\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_onboard_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'onboard_import'`

- [ ] **Step 3: Write the parser wrapper**

`backend/onboard_import.py`:

```python
"""Turn a visitor's pasted or scraped library text into music_data.

Two parsers in order: the strict YouTube Music page parser, then whatever
tolerant parser the caller supplies. The strict one signals failure by raising
SystemExit — a BaseException that "except Exception" does not catch — so it is
caught by name here and never allowed to reach a request handler.
"""

import parse_liked_songs_paste


class LibraryImportError(Exception):
    """The text could not be read as a music library.

    Deliberately not named ImportError: shadowing the builtin inside a module
    that imports things would make a genuine import failure catchable here.
    """


def parse_library_text(text: str, fallback=None) -> dict:
    """Parse `text` into music_data, or raise LibraryImportError."""
    if not text or not text.strip():
        raise LibraryImportError("Nothing to import.")

    songs = []
    try:
        songs = parse_liked_songs_paste.parse(text)
    except SystemExit:
        # No header marker: this is not a YouTube Music page paste.
        songs = []
    except Exception:
        songs = []

    if songs:
        return parse_liked_songs_paste.to_music_data(songs)

    if fallback is not None:
        try:
            rows = fallback(text) or []
        except Exception:
            rows = []
        liked = [{
            "id": "",
            "title": row.get("title", ""),
            "artists": [{"id": "", "name": row.get("artist", "")}],
            "album": {"name": row["album"]} if row.get("album") else {},
            "duration": row.get("duration", ""),
        } for row in rows if row.get("title") and row.get("artist")]
        if liked:
            artists = {}
            for song in liked:
                name = song["artists"][0]["name"]
                artists.setdefault(name, {"id": "", "name": name, "thumbnail": ""})
            return {"library_artists": list(artists.values()),
                    "liked_songs": liked, "history": []}

    raise LibraryImportError(
        "Couldn't find any songs in that. Open your YouTube Music liked-songs "
        "page, scroll to the bottom so every song loads, select all, and paste.")
```

- [ ] **Step 4: Add the routes**

In `backend/server.py`, add `import onboard_import` to the imports and insert after `profile_card`:

```python
@app.route("/onboard")
def onboard_page():
    """Landing page for a visitor who arrived from someone's share link."""
    return send_from_directory(app.static_folder, "onboard.html")


@app.route("/api/onboard/paste", methods=["POST"])
def api_onboard_paste():
    """Parse pasted library text into music_data without creating anything."""
    data = request.get_json(silent=True) or {}
    try:
        music_data = onboard_import.parse_library_text(
            data.get("text", ""), fallback=parse_youtube_music_paste)
    except onboard_import.LibraryImportError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "success": True,
        "song_count": len(music_data["liked_songs"]),
        "artist_count": len(music_data["library_artists"]),
        "music_data": music_data,
    })
```

- [ ] **Step 5: Build the page**

`frontend/onboard.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Compare your music taste</title>
    <link rel="stylesheet" href="/css/styles.css?v=123">
    <style>body { overflow: auto; }</style>
</head>
<body>
    <div class="profile-page">
        <header class="profile-hero">
            <div class="profile-archetype">Compare your taste</div>
            <div class="profile-tagline" id="onboardIntro">
                Bring your own library and see how the two of you line up.
            </div>
        </header>

        <section class="profile-section">
            <h2>1. Paste your liked songs</h2>
            <p class="muted">Open YouTube Music's Liked Music page, scroll to the
               bottom so every song loads, select all, copy, and paste here.</p>
            <textarea id="pasteBox" rows="8"
                      placeholder="Paste the whole page here…"></textarea>
            <button class="btn btn-primary" id="pasteSubmit">Use this</button>
        </section>

        <section class="profile-section">
            <h2>2. Or upload an export</h2>
            <p class="muted">A Google Takeout ZIP, or any CSV or JSON of your
               library.</p>
            <input type="file" id="onboardFile" accept=".zip,.csv,.json">
        </section>

        <section class="profile-section">
            <h2>3. Or use the one-click bookmarklet</h2>
            <p class="muted" id="bookmarkletHelp">Drag this to your bookmarks bar,
               open YouTube Music's Liked Music page, and click it.</p>
            <a class="btn btn-secondary" id="bookmarklet" href="#">Grab my songs</a>
        </section>

        <section class="profile-section">
            <h2>4. Or connect Spotify</h2>
            <p class="muted">Spotify's API is in Development Mode, which caps this
               at five approved listeners and needs the app owner to hold Premium.
               If you have not been added, use one of the options above.</p>
            <button class="btn btn-secondary" id="spotifyBtn">Connect Spotify</button>
        </section>

        <section class="profile-section" id="confirmSection" hidden></section>
        <p class="muted" id="onboardStatus"></p>
    </div>
    <script src="/js/onboard.js?v=1"></script>
</body>
</html>
```

`frontend/js/onboard.js`:

```javascript
const params = new URLSearchParams(window.location.search);
const compareWith = params.get('with') || '';

const el = id => document.getElementById(id);

// Artist and track names come from a file the visitor supplied; anything of
// theirs that reaches innerHTML is escaped, same rule as profile.js.
function esc(s) {
    return String(s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

function status(message) {
    el('onboardStatus').textContent = message;
}

let pendingLibrary = null;

function offerToCreate(musicData, songCount, artistCount) {
    pendingLibrary = musicData;
    el('confirmSection').innerHTML = `
        <h2>Found ${songCount} songs by ${artistCount} artists</h2>
        <label class="muted" for="onboardName">What should we call you?</label>
        <input type="text" id="onboardName" maxlength="40" placeholder="Your name">
        <button class="btn btn-primary" id="createProfile">Build my profile</button>`;
    el('confirmSection').hidden = false;
    el('createProfile').addEventListener('click', createProfile);
}

async function createProfile() {
    if (!pendingLibrary) return;
    status('Building your profile…');
    const response = await fetch('/api/profile/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            name: el('onboardName').value.trim(),
            music_data: pendingLibrary
        })
    });
    const data = await response.json();
    if (data.error) {
        status('Error: ' + data.error);
        return;
    }
    localStorage.setItem('myProfileId', data.id);
    localStorage.setItem('ownerToken:' + data.id, data.owner_token);
    window.location.href = compareWith
        ? `/compare/${data.id}?with=${encodeURIComponent(compareWith)}`
        : `/p/${data.id}`;
}

el('pasteSubmit').addEventListener('click', async () => {
    const text = el('pasteBox').value;
    if (!text.trim()) {
        status('Paste your liked songs first.');
        return;
    }
    status('Reading your library…');
    const response = await fetch('/api/onboard/paste', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
    });
    const data = await response.json();
    if (data.error) {
        status(data.error);
        return;
    }
    status('');
    offerToCreate(data.music_data, data.song_count, data.artist_count);
});

el('onboardFile').addEventListener('change', async event => {
    const file = event.target.files[0];
    if (!file) return;
    status('Reading your file…');
    const form = new FormData();
    form.append('file', file);
    const response = await fetch('/api/upload', { method: 'POST', body: form });
    const data = await response.json();
    if (data.error) {
        status(data.error);
        return;
    }
    // /api/upload returns graph_data; flatten it to the liked-songs shape the
    // profile endpoint expects, mirroring library_from_graph_data on the server.
    const liked = [];
    (data.graph_data.nodes || []).forEach(node => {
        (node.songs || []).forEach(song => {
            liked.push({
                title: song.title,
                album: [',', '&', ''].includes(song.album) ? null : song.album,
                artists: [{ name: node.name }]
            });
        });
    });
    status('');
    offerToCreate({ liked_songs: liked }, liked.length, data.artist_count);
});

el('spotifyBtn').addEventListener('click', async () => {
    const response = await fetch('/api/spotify/auth');
    const data = await response.json();
    if (data.error) {
        status(data.error);
        return;
    }
    window.location.href = data.auth_url;
});

if (compareWith) {
    el('onboardIntro').textContent =
        'Bring your own library and see how you line up with this profile.';
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_onboard_import.py -v`
Expected: 8 passed

- [ ] **Step 7: Verify the paste path end to end with the real export**

Run:

```bash
cd backend && ./venv/bin/python server.py &
sleep 10
python3 - <<'PY'
import json, urllib.request
text = open('../youtube-music-liked-songs-5-10-2026.txt').read()
req = urllib.request.Request(
    'http://127.0.0.1:5050/api/onboard/paste',
    data=json.dumps({'text': text}).encode(),
    headers={'Content-Type': 'application/json'})
body = json.load(urllib.request.urlopen(req))
print(body['song_count'], 'songs,', body['artist_count'], 'artists')
PY
kill %1
```

Expected: `3040 songs, 1133 artists`. Also POST a deliberate junk string and confirm the response is a 400 with the guidance message rather than a 500 — that is the `SystemExit` path.

- [ ] **Step 8: Commit**

```bash
git add frontend/onboard.html frontend/js/onboard.js backend/onboard_import.py \
        backend/tests/test_onboard_import.py backend/server.py
git commit -m "Add the onboarding page with paste and upload import paths"
```

---

### Task 10: The one-click bookmarklet

**Files:**
- Modify: `backend/server.py`, `frontend/js/onboard.js`
- Create: `backend/tests/test_onboard_scrape.py`

**Interfaces:**
- Consumes: `onboard_import.parse_library_text`
- Produces:
  - `BOOKMARKLET_TEMPLATE` served by `GET /api/onboard/bookmarklet`
  - route `POST /onboard/scrape` accepting a cross-origin form POST

The bookmarklet scrolls the liked-songs page until it stops growing, then submits `document.body.innerText` to our server via a top-level form POST in a new tab. A form POST is deliberate: it is a navigation, not a `fetch`, so there is no CORS preflight, no `Access-Control-Allow-Origin` dependence, and no server-side import store to expire. It also means the bookmarklet reads no DOM structure at all — YouTube Music's class names and element tags change without notice, and the innerText of the page is the one thing that stays stable, which is the same input the paste path already handles.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_onboard_scrape.py`:

```python
import pytest

import server

PAGE = """Liked songs
Music you like in any YouTube app will show here

Strangers
Seven Lions
Strangers
3:41
"""


@pytest.fixture
def client():
    server.app.config["TESTING"] = True
    return server.app.test_client()


def test_scrape_accepts_a_form_post_and_returns_a_page(client):
    response = client.post("/onboard/scrape", data={"scraped": PAGE})
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/html")
    assert "Strangers" in response.get_data(as_text=True)


def test_scrape_carries_the_comparison_target_through(client):
    html = client.post("/onboard/scrape?with=abc12345",
                       data={"scraped": PAGE}).get_data(as_text=True)
    assert "abc12345" in html


def test_a_hostile_comparison_target_is_escaped(client):
    html = client.post('/onboard/scrape?with=%22%3E%3Cscript%3E',
                       data={"scraped": PAGE}).get_data(as_text=True)
    assert "<script>" not in html


def test_junk_input_is_a_readable_error_not_a_crash(client):
    # parse() raises SystemExit here; if it escapes, this is a 500.
    response = client.post("/onboard/scrape", data={"scraped": "hello"})
    assert response.status_code == 400
    assert "Couldn't find any songs" in response.get_data(as_text=True)


def test_an_empty_post_is_a_readable_error(client):
    assert client.post("/onboard/scrape", data={}).status_code == 400


def test_the_bookmarklet_embeds_this_origin_and_the_target(client):
    body = client.get("/api/onboard/bookmarklet?with=abc12345").get_json()
    assert body["bookmarklet"].startswith("javascript:")
    assert "/onboard/scrape" in body["bookmarklet"]
    assert "abc12345" in body["bookmarklet"]


def test_the_bookmarklet_rejects_a_bogus_target(client):
    # Profile ids are 8 hex characters; anything else is not interpolated.
    body = client.get('/api/onboard/bookmarklet?with="><script>').get_json()
    assert "<script>" not in body["bookmarklet"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_onboard_scrape.py -v`
Expected: FAIL — both routes 404.

- [ ] **Step 3: Write the implementation**

In `backend/server.py`, insert after `api_onboard_paste`:

```python
# A top-level form POST rather than fetch(): it is a navigation, so there is no
# CORS preflight to satisfy and no import store to expire. The scraper reads
# innerText rather than any DOM structure, because YouTube Music's markup
# changes without notice while its rendered text does not.
BOOKMARKLET_TEMPLATE = (
    "javascript:(async()=>{{"
    "let last=0,still=0;"
    "while(still<3){{"
    "window.scrollTo(0,document.body.scrollHeight);"
    "await new Promise(r=>setTimeout(r,900));"
    "const h=document.body.scrollHeight;"
    "if(h===last){{still++;}}else{{still=0;last=h;}}"
    "}}"
    "const f=document.createElement('form');"
    "f.method='POST';f.action='{action}';f.target='_blank';"
    "f.style.display='none';"
    "const t=document.createElement('textarea');"
    "t.name='scraped';t.value=document.body.innerText;"
    "f.appendChild(t);document.body.appendChild(f);f.submit();"
    "}})()"
)

_PROFILE_ID = re.compile(r"^[0-9a-f]{8}$")


def _safe_target(raw):
    """Profile ids are 8 hex characters. Anything else is not a profile id and
    must not be interpolated into a URL or into HTML."""
    return raw if raw and _PROFILE_ID.match(raw) else ""


@app.route("/api/onboard/bookmarklet")
def api_onboard_bookmarklet():
    target = _safe_target(request.args.get("with", ""))
    action = f"{_external_base()}/onboard/scrape"
    if target:
        action = f"{action}?with={target}"
    return jsonify({"bookmarklet": BOOKMARKLET_TEMPLATE.format(action=action)})


@app.route("/onboard/scrape", methods=["POST"])
def onboard_scrape():
    """Receive the bookmarklet's payload and hand back a confirmation page."""
    try:
        music_data = onboard_import.parse_library_text(
            request.form.get("scraped", ""), fallback=parse_youtube_music_paste)
    except onboard_import.LibraryImportError as exc:
        return Response(
            f"<!doctype html><meta charset=utf-8>"
            f"<title>Import failed</title>"
            f"<body style='font-family:system-ui;padding:40px;max-width:640px'>"
            f"<h1>Import failed</h1><p>{escape(str(exc))}</p>"
            f"<p><a href='{escape(_external_base())}/onboard'>Paste it manually"
            f"</a> instead.</p>",
            status=400, mimetype="text/html")

    target = _safe_target(request.args.get("with", ""))
    # The payload is handed to the page as JSON in a script tag rather than
    # POSTed onward, so nothing is stored server-side before the visitor has
    # decided to create a profile.
    payload = json.dumps(music_data).replace("<", "\\u003c")
    return Response(
        f"<!doctype html><meta charset=utf-8>"
        f"<title>Import your library</title>"
        f"<link rel=stylesheet href='/css/styles.css'>"
        f"<body class='profile-page'>"
        f"<h1>Found {len(music_data['liked_songs'])} songs</h1>"
        f"<p class='muted'>by {len(music_data['library_artists'])} artists.</p>"
        f"<label for='n'>What should we call you?</label>"
        f"<input id='n' maxlength='40' placeholder='Your name'>"
        f"<button class='btn btn-primary' id='go'>Build my profile</button>"
        f"<p class='muted' id='s'></p>"
        f"<script>window.__IMPORTED__={payload};"
        f"window.__COMPARE_WITH__='{escape(target)}';</script>"
        f"<script src='/js/onboard_scrape.js'></script>",
        mimetype="text/html")
```

Add `import re` to `backend/server.py` if it is not already imported — it is, at line 26.

- [ ] **Step 4: Add the confirmation script**

`frontend/js/onboard_scrape.js`:

```javascript
// Runs on the page /onboard/scrape returns. The library was handed over in a
// script tag; nothing is stored server-side until the visitor clicks through.
document.getElementById('go').addEventListener('click', async () => {
    const status = document.getElementById('s');
    status.textContent = 'Building your profile…';
    const response = await fetch('/api/profile/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            name: document.getElementById('n').value.trim(),
            music_data: window.__IMPORTED__
        })
    });
    const data = await response.json();
    if (data.error) {
        status.textContent = 'Error: ' + data.error;
        return;
    }
    localStorage.setItem('myProfileId', data.id);
    localStorage.setItem('ownerToken:' + data.id, data.owner_token);
    const target = window.__COMPARE_WITH__;
    window.location.href = target
        ? `/compare/${data.id}?with=${encodeURIComponent(target)}`
        : `/p/${data.id}`;
});
```

- [ ] **Step 5: Offer the bookmarklet on the onboarding page**

Append to `frontend/js/onboard.js`:

```javascript
(async () => {
    const url = '/api/onboard/bookmarklet' +
        (compareWith ? `?with=${encodeURIComponent(compareWith)}` : '');
    const { bookmarklet } = await (await fetch(url)).json();
    // The href is a javascript: URL by design — that is what a bookmarklet is.
    // It is built server-side from a fixed template with only a validated
    // 8-hex-character profile id interpolated.
    el('bookmarklet').setAttribute('href', bookmarklet);
})();
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_onboard_scrape.py tests/ -v`
Expected: 7 passed in the new file; the whole suite green.

- [ ] **Step 7: Verify the bookmarklet against the live page**

This is the one step in the plan that cannot be verified from a test fixture: YouTube Music's rendered text is only observable in a logged-in browser. Do this manually.

1. Start the server, open `http://127.0.0.1:5050/onboard`, and drag "Grab my songs" to the bookmarks bar.
2. Open `https://music.youtube.com/playlist?list=LM` in the same browser, logged in.
3. Click the bookmarklet. It should scroll to the bottom on its own — this takes a while on a large library, because the list is virtualised and only renders what has been scrolled past — and then open a new tab on `127.0.0.1:5050/onboard/scrape`.
4. Confirm the reported song count is within a few of your real liked-songs count.

If the count is far too low, the auto-scroll finished before the list did; raise the `still<3` threshold or the 900 ms delay in `BOOKMARKLET_TEMPLATE` and retry. If the page reports "Import failed", the header marker string in `parse_liked_songs_paste.HEADER_MARKER` no longer appears on the page — capture the first 40 lines of `document.body.innerText` from the console and record what the marker should now be **in the task report**, not in this plan. Record the observed song count in the report either way; it is the only evidence this path works.

- [ ] **Step 8: Commit**

```bash
git add backend/server.py frontend/js/onboard_scrape.js frontend/js/onboard.js \
        backend/tests/test_onboard_scrape.py
git commit -m "Add a bookmarklet that scrapes liked songs via a cross-origin form post"
```

---

### Task 11: Route the visitor from a share link into a comparison

**Files:**
- Modify: `frontend/profile.html`, `frontend/js/profile.js`, `frontend/js/compare.js`
- Create: `backend/tests/test_compare_handoff.py`

**Interfaces:**
- Consumes: `GET /api/compare/<id1>/<id2>`
- Produces: a "Compare with me" call to action on `/p/<id>`; `/compare/<id>?with=<id>` resolving to a two-profile comparison

Closes the loop: the share link now leads somewhere for a reader who has nothing of their own. Task 12 of Spec A left an open UX gap here — `compare.js`'s modal now correctly refuses to create an empty profile, but a visitor clicking "create profile" got an alert and a redirect. This replaces that dead end.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_compare_handoff.py`:

```python
import pytest

import profile_manager
import server


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    server.app.config["TESTING"] = True
    return server.app.test_client()


def _make(name, artist):
    return profile_manager.create_profile(
        {"liked_songs": [{"title": "t", "artists": [{"name": artist}]}]},
        name=name)["id"]


def test_two_real_profiles_compare(client):
    a, b = _make("A", "Seven Lions"), _make("B", "Seven Lions")
    body = client.get(f"/api/compare/{a}/{b}").get_json()
    assert body["profile1"]["name"] == "A"
    assert body["profile2"]["name"] == "B"
    assert body["overall"] == 100.0


def test_comparing_against_a_missing_profile_is_404(client):
    assert client.get(f"/api/compare/{_make('A', 'X')}/deadbeef").status_code == 404


def test_the_compare_page_is_served_for_any_id(client):
    assert client.get(f"/compare/{_make('A', 'X')}").status_code == 200
```

- [ ] **Step 2: Run test to verify it passes for the endpoint and fails for nothing**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_compare_handoff.py -v`
Expected: 3 passed. This task's endpoint already exists; the test pins the contract the frontend is about to depend on. If any of the three fails, stop — the frontend work below is built on it.

- [ ] **Step 3: Add the call to action to the profile page**

In `frontend/profile.html`, replace the footer with:

```html
        <footer class="profile-footer">
            <a class="btn btn-primary" id="compareWithMe" href="#">Compare your taste with mine</a>
            <a class="btn btn-secondary" href="/">Open the map</a>
            <button class="btn btn-secondary" id="copyLink">Copy share link</button>
            <button class="btn btn-danger" id="deleteProfile">Delete this profile</button>
        </footer>
```

In `frontend/js/profile.js`, append near the bottom, beside the existing `copyLink` handler:

```javascript
// A visitor who already has a profile goes straight to the comparison; one who
// does not goes to onboarding, which comes back here once they have data.
const mine = localStorage.getItem('myProfileId');
el('compareWithMe').href = (mine && mine !== profileId)
    ? `/compare/${mine}?with=${encodeURIComponent(profileId)}`
    : `/onboard?with=${encodeURIComponent(profileId)}`;
if (mine === profileId) {
    el('compareWithMe').remove();
}
```

- [ ] **Step 4: Teach the compare page to read `?with=`**

In `frontend/js/compare.js`, find where the page decides what to load from the URL and add support for the `with` parameter. Replace the `createProfile` function — the dead end left by Spec A's Task 12 — with:

```javascript
function createProfile() {
    // This page has no importer of its own. Onboarding does, and it comes back
    // here with both ids once the visitor has a library.
    const target = new URLSearchParams(window.location.search).get('with') || '';
    window.location.href = '/onboard' + (target ? `?with=${encodeURIComponent(target)}` : '');
}
```

And where the page resolves which two profiles to compare, honour `?with=`:

```javascript
const search = new URLSearchParams(window.location.search);
const otherId = search.get('with');
if (otherId) {
    loadComparison(profileId, otherId);
}
```

Place this beside the existing dispatch rather than replacing it, so the group and single-profile paths keep working. Read the file's existing entry point before editing — it handles `/compare/<id>`, `/group/<id>`, and `/group/<id>/join` from the same script.

- [ ] **Step 5: Verify the whole loop in a browser**

Start the server, then:

1. Open `/p/<an existing id>` in a private window (so `localStorage` is empty). The footer shows "Compare your taste with mine".
2. Click it. You land on `/onboard?with=<id>`.
3. Paste the contents of `youtube-music-liked-songs-5-10-2026.txt`, click through, and name yourself.
4. You should land on `/compare/<new id>?with=<original id>` showing a real compatibility percentage and shared artists.

Record the compatibility number in the task report.

- [ ] **Step 6: Commit**

```bash
git add frontend/profile.html frontend/js/profile.js frontend/js/compare.js \
        backend/tests/test_compare_handoff.py
git commit -m "Route share-link visitors through onboarding into a comparison"
```

---

### Task 12: Escape profile names on the compare and leaderboard pages

**Files:**
- Modify: `frontend/js/compare.js`, `frontend/leaderboard.html`

**Interfaces:**
- Consumes: nothing
- Produces: no unescaped user string reaching `innerHTML` on either page

The project has no JavaScript test runner, so this task is verified by the exhaustive grep in Step 4 and the browser check in Step 5 rather than by a test file. Do not add a runner for it.

Pre-existing, and now load-bearing: onboarding lets a stranger choose their own display name, and that name is rendered on both pages. `compare.js` already defines `escapeHtml()` at the bottom of the file and never calls it; `leaderboard.html` has no helper at all.

- [ ] **Step 1: Find every site**

Run:

```bash
cd frontend && grep -n 'profile1\.name\|profile2\.name\|\${m\.name}\|\${profile\.name}\|getInitials(' js/compare.js leaderboard.html
```

Expected: six sites in `compare.js` (two `data.profileN.name`, two `getInitials(data.profileN.name)`, one `m.name`, one `getInitials(m.name)`) and four in `leaderboard.html` (two `profile.name`, two `getInitials(profile.name)`), plus the `top_shared` artist tags around line 462 of `leaderboard.html`.

- [ ] **Step 2: Wire up the existing helper in compare.js**

In `frontend/js/compare.js`, wrap every interpolation of a name. In `renderComparison`:

```javascript
                <div class="profile-card">
                    <div class="profile-avatar">${escapeHtml(getInitials(data.profile1.name))}</div>
                    <div class="profile-name">${escapeHtml(data.profile1.name)}</div>
                    <div class="profile-stats">${data.profile1_artist_count} artists</div>
                </div>
                <div class="vs-badge">VS</div>
                <div class="profile-card">
                    <div class="profile-avatar" style="background: linear-gradient(135deg, #48dbfb, #0abde3);">
                        ${escapeHtml(getInitials(data.profile2.name))}
                    </div>
                    <div class="profile-name">${escapeHtml(data.profile2.name)}</div>
                    <div class="profile-stats">${data.profile2_artist_count} artists</div>
                </div>
```

And in `renderGroupMembers`:

```javascript
                ${members.map(m => `
                    <div class="profile-card">
                        <div class="profile-avatar">${escapeHtml(getInitials(m.name))}</div>
                        <div class="profile-name">${escapeHtml(m.name)}</div>
                        <div class="profile-stats">${m.stats.song_count || 0} songs</div>
                    </div>
                `).join('')}
```

`getInitials` calls `name.split(' ').map(w => w[0])`, which returns `undefined` for an empty segment and throws on an empty name. Harden it:

```javascript
function getInitials(name) {
    return String(name || '?')
        .split(' ')
        .filter(Boolean)
        .map(w => w[0])
        .join('')
        .toUpperCase()
        .slice(0, 2) || '?';
}
```

- [ ] **Step 3: Add a helper to leaderboard.html and use it**

In `frontend/leaderboard.html`, add beside the existing `getInitials` definition near line 489:

```javascript
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text ?? '';
            return div.innerHTML;
        }
```

Apply the same hardening to `getInitials` as in Step 2, then wrap the four name sites and the shared-artist tags:

```javascript
                    <div class="profile-avatar">${escapeHtml(getInitials(profile.name))}</div>
                    <div class="profile-info">
                        <div class="profile-name">${escapeHtml(profile.name)} ${isMe ? '(You)' : ''}</div>
```

```javascript
                                    ${escapeHtml(getInitials(profile.name))}
                                </div>
                                <div class="profile-info">
                                    <div class="profile-name">${escapeHtml(profile.name)}</div>
                                    <div class="profile-meta">${profile.shared_count} shared artists</div>
                                    <div class="top-artists">
                                        ${profile.top_shared.map(a => `<span class="artist-tag">${escapeHtml(a)}</span>`).join('')}
                                    </div>
```

Artist names are user-supplied too — they come from an imported library — so `top_shared` needs the same treatment as the profile name.

- [ ] **Step 4: Verify no site was missed**

Run:

```bash
cd frontend && grep -n '\${[^}]*\.name}\|\${getInitials(' js/compare.js leaderboard.html | grep -v escapeHtml
```

Expected: no output. Any line that appears is an unescaped interpolation that still needs wrapping.

- [ ] **Step 5: Verify the fix in a browser**

Create a profile named `<img src=x onerror=alert(1)>` through `/onboard`, mark it public via the leaderboard flow, then open `/leaderboard` and a `/compare/<a>?with=<b>` page involving it. The literal text must appear on screen and no dialog may fire.

- [ ] **Step 6: Commit**

```bash
git add frontend/js/compare.js frontend/leaderboard.html
git commit -m "Escape profile and artist names on the compare and leaderboard pages"
```

---

### Task 13: Peer-relative badges, and closing out peer_percentile

**Files:**
- Modify: `backend/archetype.py`, `backend/server.py`
- Create: `backend/tests/test_peer_percentile.py`

**Interfaces:**
- Consumes: `extra_stats` from Task 8
- Produces:
  - `archetype.badge_values(stats) -> dict[str, float]`
  - `peer_percentile` returning a number once five public profiles exist
  - `compute_badges` actually receiving its `peers` argument

Two known-open items from Spec A's final review, resolved together.

**`peer_percentile` needs no code change beyond Task 8.** Verified during planning: `update_public_index` already copies `profile["stats"]` wholesale into the index entry, so the moment Task 8 stores `obscurity` in `stats`, the public index carries it and the percentile computes. The tests below are characterisation tests that pin that behaviour — expect them to pass on first run, and treat a failure as evidence that Task 8 regressed rather than as work to do here.

**Peer-relative badge ranking has never run.** `archetype.compute_badges(stats, peers=None)` supports ranking badges by distance from the peer median, but `server.py` has always called it as `compute_badges(stats)` — so all of that logic has been dead since it was written, exactly like the rarity-weighted similarity that the Spec A final review found unreachable. `peers` wants a list of dicts keyed by badge id, which nothing currently produces. That is the real work in this task.

One wart is carried forward deliberately rather than fixed here: the peer-distance ranking compares a percentage-valued badge against a song-count-valued badge without normalising, so `completionist` (values in the tens or hundreds) will tend to outrank `one_and_done` (values 0–100) whenever peers are supplied. Note it in the task report; changing the ranking formula is a design decision, not a bug fix, and does not belong in a task whose job is to make the existing path reachable.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_peer_percentile.py`:

```python
import json

import pytest

import profile_manager
import server
from archetype import badge_values, compute_badges

LOPSIDED = {"one_song_share": 0.63, "top_genre_share": 0.15,
            "largest_artist_songs": 95, "gini": 0.56, "clusters": []}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_manager, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_manager, "GROUPS_DIR", tmp_path / "groups")
    server.app.config["TESTING"] = True
    return server.app.test_client()


def _public(artist, obscurity, extra=None):
    return profile_manager.create_profile(
        {"liked_songs": [{"title": "t", "artists": [{"name": artist}]}]},
        name=artist, public=True,
        extra_stats={"obscurity": obscurity, **(extra or {})})["id"]


# --- badge_values: the missing piece ---

def test_badge_values_returns_only_the_rules_that_fired():
    values = badge_values(LOPSIDED)
    assert set(values) == {"one_and_done", "completionist", "lopsided"}
    assert values["one_and_done"] == 63
    assert values["completionist"] == 95


def test_badge_values_of_an_unremarkable_library_is_empty():
    assert badge_values({"one_song_share": 0.1, "top_genre_share": 0.1,
                         "largest_artist_songs": 1, "gini": 0.1,
                         "clusters": []}) == {}


def test_badge_values_agrees_with_the_values_compute_badges_reports():
    values = badge_values(LOPSIDED)
    for badge in compute_badges(LOPSIDED):
        assert values[badge["id"]] == badge["value"]


def test_supplying_peers_changes_the_ranking():
    # compute_badges has always supported peer-relative priority and has never
    # been called with peers. If this passes trivially, the wiring is a no-op.
    peers = [{"one_and_done": 10, "completionist": 5, "lopsided": 0.1}] * 5
    without = [b["priority"] for b in compute_badges(LOPSIDED)]
    with_peers = [b["priority"] for b in compute_badges(LOPSIDED, peers=peers)]
    assert without != with_peers


# --- the endpoint ---

def test_badge_values_are_stored_on_creation(client):
    profile_id = _public("A", 20.0, badge_values({"one_song_share": 0.63,
                                                  "largest_artist_songs": 95,
                                                  "gini": 0.56, "clusters": []}))
    stored = json.loads(
        (profile_manager.PROFILES_DIR / f"{profile_id}.json").read_text())
    assert "one_and_done" in stored["stats"]


def test_the_endpoint_ranks_badges_against_peers(client, monkeypatch):
    calls = []
    original = server.compute_badges

    def spy(stats, peers=None):
        calls.append(peers)
        return original(stats, peers=peers)

    monkeypatch.setattr(server, "compute_badges", spy)
    for i in range(5):
        _public(f"A{i}", 10.0 * i, {"one_and_done": 10 * i})
    client.get(f"/api/profile/{_public('Me', 99.0)}/stats")
    # Order-independent: some call must have received a non-empty peer list.
    assert any(peers for peers in calls), \
        "compute_badges was called without peers again"


# --- peer_percentile: characterisation, expected to pass immediately ---

def test_the_public_index_carries_obscurity(client):
    _public("A", 20.0)
    assert profile_manager.list_public_profiles()[0]["stats"]["obscurity"] == 20.0


def test_percentile_is_none_below_the_peer_floor(client):
    for i in range(4):
        _public(f"A{i}", 10.0 * i)
    target = _public("Me", 99.0)
    assert client.get(f"/api/profile/{target}/stats").get_json()["peer_percentile"] is None


def test_percentile_is_computed_once_there_are_enough_peers(client):
    for i in range(5):
        _public(f"A{i}", 10.0 * i)
    target = _public("Me", 99.0)
    body = client.get(f"/api/profile/{target}/stats").get_json()
    assert body["peer_percentile"] is not None
    assert 0.0 <= body["peer_percentile"] <= 100.0


def test_legacy_peers_without_obscurity_are_skipped_not_crashed_on(client):
    for i in range(5):
        _public(f"A{i}", 10.0 * i)
    legacy = _public("Legacy", 50.0)
    index_path = profile_manager.PROFILES_DIR / "_public_index.json"
    index = json.loads(index_path.read_text())
    for entry in index["profiles"]:
        if entry["id"] == legacy:
            del entry["stats"]["obscurity"]
    index_path.write_text(json.dumps(index))
    body = client.get(f"/api/profile/{_public('Me', 99.0)}/stats").get_json()
    assert body["peer_percentile"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_peer_percentile.py -v`
Expected: the four `badge_values` tests fail with `ImportError: cannot import name 'badge_values' from 'archetype'`, and `test_the_endpoint_ranks_badges_against_peers` fails on the assertion. The four `peer_percentile` tests should **pass** — they characterise what Task 8 already fixed. If any of those four fails, stop and check Task 8 rather than editing anything here.

- [ ] **Step 3: Expose the badge values**

Append to `backend/archetype.py`:

```python
def badge_values(stats: dict) -> dict:
    """Badge id -> value for every rule that fires.

    compute_badges' peers argument wants exactly this shape, and until now
    nothing produced it — so the peer-relative ranking below has never run.
    """
    return {badge_id: extract(stats)
            for badge_id, predicate, _template, extract, _priority in _BADGE_RULES
            if predicate(stats)}
```

- [ ] **Step 4: Store them and pass them through**

In `backend/server.py`, add `badge_values` to the `archetype` import, then extend the `extra_stats` in `api_create_profile`:

```python
    result = create_profile(music_data, name=name, public=public,
                            writeup=writeup,
                            extra_stats={"obscurity": bundle["stats"]["obscurity"],
                                         **badge_values(bundle["stats"])})
```

The badge values go in flat alongside `obscurity` because `update_public_index` copies `profile["stats"]` wholesale — verified — so anything stored there reaches the peer list with no index migration.

Then in `api_profile_stats`, build the peer list and use it:

```python
    peers = list_public_profiles(limit=500)
    peer_badges = [
        {k: v for k, v in (p.get("stats") or {}).items() if k in _BADGE_IDS}
        for p in peers
    ]
    peer_badges = [p for p in peer_badges if p]
```

and change the badges line in the response from `bundle["badges"]` to:

```python
        "badges": compute_badges(stats, peers=peer_badges),
```

Define the id set once near the top of `server.py`:

```python
# Badge ids, so peer stats can be filtered down to just the rankable values.
_BADGE_IDS = frozenset(rule[0] for rule in _BADGE_RULES)
```

which needs `_BADGE_RULES` added to the `archetype` import. If exporting a private name reads badly, add a public `BADGE_IDS = frozenset(...)` to `archetype.py` instead and import that — either is fine, but do not duplicate the id list by hand in two files.

- [ ] **Step 5: Replace the known-incomplete comment**

In `backend/server.py`, inside `api_profile_stats`, delete the six-line comment beginning "Known-incomplete: profile_manager.create_profile never wrote..." and replace it with:

```python
    # Obscurity is stored at creation (see api_create_profile), so peers now
    # carry it. Peers created before that still do not, and are filtered out
    # below rather than counted as zero.
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/ -v`
Expected: 9 passed in the new file; the whole suite green.

- [ ] **Step 7: Confirm nothing broke for the real stored profiles**

Run:

```bash
cd backend && ./venv/bin/python -c "
import json, glob
for path in glob.glob('profiles/*.json'):
    if '_public_index' in path: continue
    p = json.load(open(path))
    print(p['id'], 'public' if p.get('public') else 'private',
          'obscurity' in p.get('stats', {}))
"
```

Expected: the existing profiles report `False` — they predate the field. That is correct and is exactly what the filter in `api_profile_stats` handles; do not backfill them, because recomputing obscurity for a stored library would silently rewrite user data.

- [ ] **Step 8: Commit**

```bash
git add backend/archetype.py backend/server.py backend/tests/test_peer_percentile.py
git commit -m "Rank badges against peers and close out the peer percentile"
```

---

## Closing checks

After Task 13, before declaring the branch done:

- [ ] Full suite: `cd backend && ./venv/bin/python -m pytest tests/ -v`. Spec A ended at 121 passing; this plan adds 81 more across nine new test files.
- [ ] `git status --short` shows nothing under `backend/data/`, `backend/profiles/`, or `frontend/graph_data.json`. If it does, the file was added by mistake — unstage it, do not commit it.
- [ ] Paste a real `/p/<id>` link into iMessage or Discord and confirm the card unfurls with the archetype and the constellation. This needs a publicly reachable URL, so it can only be done after a deploy; if the branch is not deployed, record that this check is outstanding rather than marking it done.
- [ ] `grep -rn "textsize" backend/` returns nothing. `ImageDraw.textsize` does not exist in Pillow 10+, and it is the single most likely thing for a later edit to reintroduce from memory.
- [ ] `grep -rn "temperature\|top_p\|top_k" backend/taste_writeup.py` returns nothing. Those parameters are a 400 on `claude-sonnet-5`.
