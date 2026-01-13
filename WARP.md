# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Common commands

### Setup (Python)
Most scripts use relative paths and assume you run them from `backend/`.

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt

# If you hit ModuleNotFoundError: requests when running server.py:
python -m pip install requests
```

### Run the app (backend serves the frontend)
```bash
cd backend
python server.py
# Open http://localhost:5050
```

### Quick start helper
`run.sh` bootstraps `backend/venv`, installs deps, runs auth setup if `backend/browser.json` is missing, and starts the server.

```bash
./run.sh
```

### Authentication (YouTube Music)
Two paths exist in the repo:

- In-repo script:

```bash
cd backend
python setup_auth.py
```

- `ytmusicapi` CLI (also referenced in README):

```bash
cd backend
ytmusicapi browser
```

### Import / refresh your library data
Produces/updates `backend/music_data.json`.

- Option A: Google Takeout

```bash
cd backend
python import_takeout.py /path/to/Takeout
```

- Option B: YouTube Music API (requires auth)

```bash
cd backend
python ytmusic_client.py
```

### Enrich song metadata (optional)
Adds `year` and `views` to entries in `backend/music_data.json` by calling `ytmusicapi.get_song` per track.

```bash
cd backend
python fetch_song_metadata.py
```

### Build / rebuild the graph used by the frontend
Primary artifact: `frontend/graph_data.json`.

```bash
cd backend
# Base graph export (nodes/links + PageRank importance)
python graph_builder.py

# Assign genres (edits frontend/graph_data.json in place)
python assign_genres.py

# Add per-artist song lists + play counts (edits frontend/graph_data.json in place)
python rebuild_graph.py
```

### Demo mode (no auth/data)
```bash
cd backend
python server.py
# In the UI, click “Load Demo Data” (served by /api/demo/graph)
```

### Last.fm similar artists (optional)
The UI button “Find Similar Artists (Last.fm)” calls `/api/similar/<artist>`.

```bash
export LASTFM_API_KEY=...   # backend/server.py reads this
```

## Tests / linting
No automated test suite or lint configuration was found (no `tests/`, `pytest.ini`, `pyproject.toml`, etc.). Most changes are validated by running the Flask server and exercising the UI.

## Architecture (big picture)

### Data flow
1. **Source data** → `backend/music_data.json`
   - Created by `backend/ytmusic_client.py` (YouTube Music API via `ytmusicapi`), or `backend/import_takeout.py` (Google Takeout).
2. **Graph build** → `frontend/graph_data.json`
   - Built/updated by a small pipeline of scripts in `backend/`:
     - `backend/graph_builder.py`: builds a NetworkX graph (collaboration edges, optional related-artist edges) and exports `{nodes, links, stats}` for D3.
     - `backend/assign_genres.py`: assigns/inferes `node.genre` (large curated mapping + heuristics) and writes back to `frontend/graph_data.json`.
     - `backend/rebuild_graph.py`: merges song lists and play counts into nodes (`node.songs[]`, `node.total_plays`) while preserving existing fields like `genre` / `cluster`.
3. **Visualization/UI**
   - `frontend/index.html` loads D3 (CDN) and `frontend/js/graph.js`, which fetches `/api/graph` (or `/api/demo/graph`) and renders a force-directed artist network.

### Backend (Flask)
- `backend/server.py` serves the static frontend (`../frontend`) and exposes JSON endpoints used by `frontend/js/graph.js`:
  - `/api/status`: checks if `backend/browser.json` exists and can be loaded.
  - `/api/export`: exports library/liked/history via `ytmusicapi` into `backend/music_data.json`.
  - `/api/graph`: serves `frontend/graph_data.json` if present; otherwise tries to build it from `backend/music_data.json`.
  - `/api/demo/graph`: demo dataset.
  - `/api/similar/<artist_name>`: Last.fm similar artists (requires `LASTFM_API_KEY`).

### Frontend (static)
- `frontend/js/graph.js` contains most of the product logic:
  - graph rendering + interactions (search, genre filter, artist side panel)
  - DJ tools (mix-path BFS, bridge artists, set builder, export)
  - recommendations based on graph connections
  - Last.fm “Discover Similar” panel calling the backend.

### Data formats (fields that matter)
- `backend/music_data.json`: `{ library_artists[], liked_songs[], history[] }`
- `frontend/graph_data.json`:
  - `nodes[]`: `{ id, name, song_count, importance, genre?, cluster?, songs?, total_plays? }`
  - `links[]`: `{ source, target, weight, type }`

## Repo-specific gotchas
- Run Python scripts from `backend/` (many paths are relative: `music_data.json`, `browser.json`, `../frontend/graph_data.json`, and Flask’s static path).
- `backend/server.py` imports `requests` for the Last.fm endpoint, but `backend/requirements.txt` doesn’t currently list it.
- `run.sh` prints `http://localhost:5000`, but `backend/server.py` actually starts on port `5050`.
- `backend/import_takeout.py` currently writes artists with empty `id` fields; `backend/graph_builder.py` expects artist IDs to build nodes/edges (you may need a fallback ID strategy for Takeout-based graphs).
