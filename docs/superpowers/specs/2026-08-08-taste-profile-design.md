# Taste Profile (Spec A)

Date: 2026-08-08
Status: approved design, ready for implementation planning

## Goal

Give the app a profile page that says something true and specific about a person's
music library, in the spirit of musictaste.space. The page lives at `/p/<profile_id>`
and leads with a named archetype over a stats panel: obscurity, diversity, genre and
decade breakdown, taste clusters, and outlier badges.

This spec covers the engine and the page. A second spec (Spec B) covers share cards,
link previews, friend onboarding, and the optional LLM write-up. Spec A is a
prerequisite for Spec B: there is no point rendering a share card for a profile with
nothing to say.

## Non-goals

Out of scope for Spec A, deferred to Spec B: share card image rendering, OpenGraph
tags, the paste/bookmarklet/upload onboarding flows for visitors, and the LLM-written
taste description. Out of scope entirely: user accounts, passwords, a real database,
and any Spotify functionality beyond what already exists.

## Current state

The app is a Flask backend (`backend/server.py`) serving a static D3 frontend, with
profiles and groups stored as JSON files. `taste_similarity.py` already implements
Jaccard, cosine, and weighted-overlap comparison; `profile_manager.py` already mints
8-character share IDs; `/compare/<id>`, `/group/<id>`, and `/leaderboard` pages exist
and work. What is missing is the summary — a page about one person rather than a
number between two.

### Defects this spec fixes

These are blocking, and they come first.

**Share My Taste creates empty profiles.** `createAndShareProfile()` in
`frontend/js/graph.js` POSTs `{name, public}` with no `music_data`. The endpoint at
`backend/server.py:296` falls back to `backend/music_data.json`, which contains
`{"library_artists": [], "liked_songs": [], "history": []}`. The real library — 1,133
artist nodes, 3,039 song entries — exists only in `frontend/graph_data.json`.

**Comparison reads a server-global file.** `/api/compare/with-current/<id>` at
`backend/server.py:365` reads `backend/music_data.json` as "the current user". On a
deployed instance that file is whatever the last visitor uploaded, so two friends
comparing against each other get each other's leftovers. This makes every sharing
feature untrustworthy until fixed.

**Profiles default to public.** `create_profile(..., public=True)` plus a frontend
that passes `public: true` means every friend who creates a profile is published to
the leaderboard without choosing to be.

**The importer mangles multi-artist strings.** 114 of 1,133 nodes are unsplit
collaboration strings such as `"ILLENIUM, Wooli, & Grabbitz"`, and 1,182 of 3,039
song entries (39%) have an album value of `&`, `,`, or empty — leftover fragments
from splitting artist names on separators and writing the remainder into the album
field. Album-derived statistics are not viable and are excluded from this spec.

## Architecture

### Data stores

The organising decision: **artist metadata is global, not per-profile.** Skrillex has
the same listener count for everyone, so it lives in one shared store rather than
being duplicated into each profile. Existing profiles are already 533KB each.

Three JSON stores under `backend/data/`, all treated as caches that grow and are
never rebuilt from scratch:

- `artist_meta.json` — artist name to `{lastfm_name, listeners, playcount, tags[],
  genre, thumbnail, non_artist: bool}`. Populated by the Last.fm fetcher, extended
  whenever a new library introduces unseen artists.
- `track_years.json` — `"artist|title"` to release year, from MusicBrainz.
- `genre_reference.json` — per-genre listener distributions built from Last.fm
  `tag.getTopArtists`, used as the external population for scene-relative obscurity.

Profiles keep only their own track list plus a computed stats snapshot, so they
shrink rather than grow.

A working `artist_meta.json` covering 1,148 artists with listener counts already
exists in the session scratchpad and should be copied in rather than re-fetched.

### Modules

New backend modules, none of which import Flask, all independently testable:

- `collab_split.py` — splits `"A, B & C"` into component artists. Used at import time
  and when building artist stats. Songs by a collaboration are credited to every
  component.
- `artist_meta.py` — read/write the shared store; genre resolution; the non-artist
  heuristic.
- `enrich/lastfm_artist.py` — fetch `artist.getInfo` (listeners, playcount, tags).
- `enrich/lastfm_tags.py` — fetch `tag.getTopArtists` to build `genre_reference.json`.
- `enrich/musicbrainz_years.py` — fetch release years at 1 request/second.
- `taste_profile.py` — all metrics. Pure function from (library, artist_meta,
  track_years, genre_reference) to a profile stats object.
- `archetype.py` — deterministic rules from stats to archetype name, tagline, badges.

Flask routes stay thin wrappers over these. Frontend gets `frontend/profile.html` and
`frontend/js/profile.js`, matching the existing V1 design language and sitting
alongside `compare.html` and `leaderboard.html`. Nothing is added to the 100KB
`graph.js`.

All fetchers write incrementally and resume by scanning the existing store, so a run
that dies at artist 800 restarts at 800.

## Metrics

### Obscurity

Last.fm listener counts are log-normally distributed, so scores map onto a fixed log
scale rather than a linear one. **Bounds are 10 listeners (score 100) to 10,000,000
listeners (score 0).** These were chosen empirically: against the reference library
they clip only 23 of 1,157 artists, versus 113 for bounds of 100–5M and 49 for
50–20M.

```
obscurity(listeners) = clamp(0, 100, 100 * (1 - (log10(listeners) - 1) / 6))
```

Fixed rather than percentile-based, so a person's score does not move when someone
else joins, and two friends' scores are directly comparable.

Library obscurity is the **song-count-weighted mean** across artists that survive the
non-artist filter, so an artist with 95 songs counts more than one with a single
track. On the reference library this yields 20.3.

The page shows three views, all three required:

1. **Absolute** — the weighted mean above, on the fixed scale.
2. **Peer percentile** — rank of this profile's absolute score among all profiles on
   the instance. Hidden when fewer than 5 profiles exist, because with three friends
   the percentile is noise rather than information.
3. **Scene-relative** — for each artist, their percentile within the external
   listener distribution for their genre from `genre_reference.json`, averaged
   weighted by song count. This answers "do you pick deep cuts within the scenes you
   actually listen to". It requires the `tag.getTopArtists` fetch; without that
   reference the number is self-referential and the section stays hidden.

### Non-artist filter

Libraries imported from YouTube Music contain upload and repost channels rather than
artists. Left in, the "most obscure pick" badge surfaces things like *Lost Lands
Music Festival* (169 listeners) and *DubstepGutter*.

Rule: flag as `non_artist` when **listeners < 5,000 and Last.fm returns no tags.**
Against the reference library this flags 140 of 1,157 artists holding 172 songs
(5.7%), correctly catching *Music EDM Drops*, *EDM Kiwi*, *Bass Bangers*, *Windy City
Raves*, *Dubstep uNk*, *Lost Lands Music Festival*.

The rule has false positives, mostly featured vocalists separated out of collaboration
strings — *Brieanna Grace* (295 listeners, 1 song) is a real person. Because flagged
entries hold one or two songs each, the cost is low. Mitigation: an explicit
`is_artist: true` field on an `artist_meta.json` entry overrides the heuristic and is
never recomputed. The flag list is reviewed once at build time to seed these
overrides.

Flagged artists are excluded from obscurity, badges, and headline counts. They remain
in the library, the graph, and song lists. Nothing is deleted.

### Diversity

Genre entropy normalised by the size of the **fixed genre vocabulary**, not by the
number of genres present:

```
diversity = H(genre distribution) / log(len(GENRE_VOCABULARY))
```

`GENRE_VOCABULARY` is the fixed set of genre labels emitted by `assign_genres.py`,
51 entries in the current data. It is a constant in `taste_profile.py`, not derived
from any particular library.

The existing `compute_taste_vector` normalises by `log(genres present)`, which scores
a two-genre library split evenly as a perfect 1.0. Note that this fix does not change
the reference library's score — it spans all 51 genres, so both formulas give 0.709 —
but it matters for narrower libraries.

Genre distribution is weighted by song count, not artist count.

### Eras

Decade histogram, median release year, and interquartile spread, from
`track_years.json`. Hidden when year coverage falls below 40% of songs.

### Moods

Last.fm tags collapsed into a small mood vocabulary. **Tags are only trusted for
artists above 5,000 listeners**, because user-generated tags on small artists are
unreliable — DubstepGutter is tagged `fried vegan eggs saladcore`, and OAKS, an EDM
act, returns `stoner metal, shoegaze`. The section is labelled on the page as
tag-derived rather than measured.

### Taste clusters

Community detection over the artist graph via `networkx.community.
greedy_modularity_communities`, already a dependency. On the reference library this
finds 22 communities in the largest component that correspond to real scenes: 190
artists around Bruno Mars and The Weeknd, 155 around Martin Garrix and Knock2, 143
around Seven Lions and Subtronics, 76 around Pink Floyd and The Beatles, 52 around
Kanye and Kendrick, 46 around i-dle and IVE.

Each cluster is named by its dominant genre plus its highest-song-count members and
shown as "your musical worlds". Clusters below 10 artists are merged into an "other"
bucket.

### Badges

Outlier facts computed from the person's own numbers, at most three shown. Each badge
rule carries a fixed trigger threshold and a fixed priority, so badges work for the
first profile ever created. Once at least 5 profiles exist, ranking switches to how
far the value deviates from the median across stored profiles — the same threshold
used for peer percentile, for the same reason. The rule set includes:
share of artists with exactly one song, share of library in the top genre, largest
single-artist song count, gini coefficient of song counts, share of library in the
dominant cluster, and count of distinct clusters.

### Archetype

Deterministic rules, no LLM. Four axes, each bucketed: obscurity
(mainstream/balanced/underground), diversity (focused/broad/omnivore), era
(retro/mixed/current), and dominant genre family. These resolve through a lookup
table to a name and a one-line tagline, with badges beneath. The table is unit-tested
and lives in `archetype.py`.

### Compatibility

`taste_similarity.py` gains **rarity weighting**: shared artists contribute in
proportion to their obscurity, so two people both liking an artist with 3,000
listeners counts for more than both liking Coldplay. The existing overall score keeps
its current 40/30/30 blend of Jaccard, weighted overlap, and genre cosine; rarity
weighting applies within the Jaccard and weighted-overlap terms.

## API

- `GET /p/<profile_id>` — the profile page.
- `GET /api/profile/<profile_id>/stats` — the computed stats object.
- `POST /api/profile/create` — accepts `music_data` in the body; the server-global
  fallback is removed.
- `GET /api/compare/<id1>/<id2>` — unchanged shape, rarity-weighted internally.
- `/api/compare/with-current/<id>` — **removed.** Callers pass two profile IDs. The
  frontend supplies the visitor's own ID from `localStorage`.

## Privacy

`public` defaults to `false`; profiles are link-only unless the creator opts into the
leaderboard. The existing delete endpoint gets a reachable UI control on the profile
page.

## Failure behavior

Every profile section declares the data it requires and hides itself when that data
is absent, so a profile with no year coverage shows no era section rather than a
chart of zeros. Fetchers tolerate per-artist failures, log misses, and continue.
Artist names are normalised before lookup — `Axwell /\ Ingrosso` currently fails
purely on the `/\` characters, and 9 artists in the reference library have no
Last.fm match.

Rate limits: Last.fm at 5 requests/second, MusicBrainz at 1 request/second with a
required User-Agent.

## Testing

There is no test suite in the repo today. This spec adds `backend/tests/` with pytest
covering the pure functions:

- obscurity mapping at and beyond both scale boundaries
- diversity normalisation, including the two-genre case the current formula gets wrong
- collaboration splitting against the real malformed names in the reference data
- the non-artist heuristic against its known true and false positives
- archetype rule resolution across each axis bucket
- rarity-weighted similarity, including the Coldplay-versus-obscure-artist case

Network fetchers get mocked-response tests only. Flask routes get smoke tests.

## Phasing

1. Groundwork — library adapter from `graph_data.json`, per-visitor profile identity,
   fix profile creation, default `public` to false.
2. Enrichment — collab splitting, Last.fm artist fetch, genre backfill, non-artist
   filter, MusicBrainz years, genre reference distributions.
3. Metrics — `taste_profile.py` and `archetype.py`, with tests.
4. Page — `/p/<id>`, `profile.html`, `profile.js`, rarity-weighted compatibility.
