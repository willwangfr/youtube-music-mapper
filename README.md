# YouTube Music Mapper

Visualize your music library as an interactive network graph. See how artists connect through collaborations and similar styles, discover patterns in your music taste, and compare your taste with friends.

_Screenshot omitted: the previous one captured a full desktop. Run the app on the bundled sample data to see the visualization._

## Features

- **Interactive Network Graph**: Artists displayed as nodes, connected by collaborations and style similarities
- **Genre Classification**: Automatic genre detection with color-coded nodes
- **Search & Filter**: Find artists/songs quickly, filter by genre
- **Artist Panel**: Click any artist to see their songs with year, view count, and your play history
- **Multiple Data Sources**: Import from YouTube Music, Spotify, or upload your own data
- **Social Features**:
  - **Share Your Taste**: Create a shareable profile of your music taste
  - **Compare**: See how similar your taste is to friends
  - **Groups**: Create groups to compare multiple people
  - **Leaderboard**: See who has the most diverse or unique taste
- **Discover**: Get artist recommendations based on your library
- **Export**: Export your graph as an image
- **DJ Tools**:
  - **Mix Path Finder**: Find transition paths between two artists
  - **Bridge Artists**: Discover artists that connect different genres
  - **Set Builder**: Auto-generate DJ sets based on energy flow or genre journey
  - **Export**: Export sets to text or Nicotine++ format for Soulseek searching

## Sample data

A fresh clone ships `frontend/graph_data.sample.json` — a 150-artist sample so the
visualization renders before you import anything. Your own library builds to
`frontend/graph_data.json`, which is gitignored and takes precedence once it exists.

## Prerequisites

- Python 3.8+
- Music data from YouTube Music, Spotify, or your own files

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/willwangfr/youtube-music-mapper.git
   cd youtube-music-mapper
   ```

2. **Install Python dependencies**
   ```bash
   pip install ytmusicapi flask flask-cors requests
   ```

## Getting Your Data

There are several ways to get your music data into the app:

### Option A: Upload in Browser (Easiest)

Click "Upload Your Data" in the app and upload one of:
- **Google Takeout ZIP** - Export from [takeout.google.com](https://takeout.google.com)
- **CSV file** - Artist and song columns
- **JSON file** - With `liked_songs` array
- **Paste text** - Just paste a list of "Artist - Song" lines

### Option B: Google Takeout

Export your YouTube Music data from Google:

1. Go to [Google Takeout](https://takeout.google.com)
2. Click "Deselect all", then select only **"YouTube and YouTube Music"**
3. Click "All YouTube data included" and select:
   - **playlists** (includes your Liked Music)
   - **history** (your listening history)
4. Click "Next step" → "Create export"
5. Download and extract the ZIP file
6. Run the import:
   ```bash
   cd backend
   python import_takeout.py /path/to/Takeout
   ```

### Option C: Spotify

Connect your Spotify account to import your liked songs:

1. **Set up Spotify API credentials** (one-time):
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create an app (any name)
   - Add `http://localhost:5050/callback/spotify` to Redirect URIs
   - Copy Client ID and Secret

2. **Set environment variables**:
   ```bash
   export SPOTIFY_CLIENT_ID="your_client_id"
   export SPOTIFY_CLIENT_SECRET="your_client_secret"
   ```

3. **Start the server** and click the Spotify button in the app to connect

### Option D: YouTube Music API (More Data)

This method gets more metadata (album art, related artists) but requires auth setup:

1. **Authenticate with YouTube Music**
   ```bash
   cd backend
   ytmusicapi browser
   ```
   Follow the instructions to paste your request headers from YouTube Music.

2. **Fetch your data**
   ```bash
   python ytmusic_client.py
   ```

3. **Fetch song metadata (years and view counts)** *(optional)*
   ```bash
   python fetch_song_metadata.py
   ```
   Note: Makes API calls for each song, takes a few minutes for large libraries.

## Building the Graph

After importing your data via command line (Options B-D):

```bash
cd backend
python assign_genres.py
python rebuild_graph.py
```

This creates `frontend/graph_data.json`.

Note: If you upload data in the browser (Option A), the graph is built automatically.

## Running the App

1. **Start the backend server**
   ```bash
   cd backend
   python server.py
   ```
   Server runs on http://localhost:5050

2. **Open the frontend**

   Open `frontend/index.html` in your browser, or serve it:
   ```bash
   cd frontend
   python -m http.server 8000
   ```
   Then visit http://localhost:8000

## Usage

### Navigation
- **Pan**: Click and drag the background
- **Zoom**: Scroll wheel
- **Select Artist**: Click on a node to open the artist panel
- **Search**: Type in the search box to find artists or songs

### Buttons
- **Load Demo Data**: Load sample data to try the app
- **Upload Your Data**: Upload your own music files
- **Load My Music**: Load previously imported data
- **Refresh Layout**: Re-run the force simulation
- **Export Image**: Save the graph as a PNG image
- **Discover New**: Get artist recommendations based on your library

### Controls
- **Node Size**: Adjust the size of artist nodes
- **Link Strength**: Adjust how tightly connected artists cluster
- **Show Related Artists**: Toggle visibility of artists not in your library
- **Show Labels**: Toggle artist name labels
- **Show Genres**: Toggle genre-based coloring

### Social Features

#### Share Your Taste
Click "Share My Taste" to create a shareable profile. You'll get a unique link that others can use to compare their taste with yours.

#### Create a Group
Click "Create Group" to start a comparison group. Share the group link with friends and compare everyone's taste at once. See:
- Pairwise similarity matrix
- Shared artists across the group
- Individual taste profiles

#### Leaderboard
Click "Leaderboard" to see rankings by:
- Most diverse taste
- Biggest music libraries
- Most unique taste

### DJ Tools
1. **Mix Path Finder**: Enter two artists to find a transition path between them
2. **Bridge Artists**: Click to find artists that connect different genres
3. **Set Builder**: Select a starting genre and flow type (Energy Up, Wind Down, or Genre Journey)
4. **Your Set**: Click songs to add them to your set, then export

### Export Options
- **Export**: Copy your set as text
- **Nicotine Export**: Export in "Artist - Song [Album]" format for Soulseek batch searching

## File Structure

```
youtube-music-mapper/
├── backend/
│   ├── server.py              # Flask API server
│   ├── import_takeout.py      # Import from Google Takeout
│   ├── ytmusic_client.py      # Fetch data from YouTube Music API
│   ├── spotify_client.py      # Spotify OAuth and data fetching
│   ├── assign_genres.py       # Genre classification
│   ├── fetch_song_metadata.py # Fetch years/views
│   ├── rebuild_graph.py       # Build graph data
│   ├── graph_builder.py       # Graph construction utilities
│   ├── profile_manager.py     # Social profile management
│   ├── taste_similarity.py    # Similarity calculations
│   ├── genre_map.json         # Artist-to-genre mappings
│   ├── browser.json           # YTMusic auth (gitignored)
│   ├── music_data.json        # Your music data (gitignored)
│   ├── profiles/              # Stored user profiles
│   └── groups/                # Comparison groups
├── frontend/
│   ├── index.html             # Main page
│   ├── compare.html           # Profile comparison page
│   ├── leaderboard.html       # Leaderboards page
│   ├── js/graph.js            # D3.js visualization
│   ├── css/styles.css         # Styling
│   └── graph_data.json        # Graph data for visualization
└── README.md
```

## Refreshing Your Data

To update with new liked songs:
```bash
cd backend
python ytmusic_client.py
python assign_genres.py
python fetch_song_metadata.py
python rebuild_graph.py
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SPOTIFY_CLIENT_ID` | Spotify API client ID (for Spotify import) |
| `SPOTIFY_CLIENT_SECRET` | Spotify API client secret |
| `LASTFM_API_KEY` | Last.fm API key (for similar artist recommendations) |

Get a free Last.fm API key at https://www.last.fm/api/account/create

## Troubleshooting

**"Authentication failed" error (YouTube Music)**
- Re-run `ytmusicapi browser` to refresh your credentials

**Spotify not working**
- Verify environment variables are set
- Check that redirect URI matches exactly: `http://localhost:5050/callback/spotify`

**Songs missing year/views**
- Re-run `fetch_song_metadata.py` - some API calls may have failed

**"Other" genre too high**
- Add more artists to `genre_map.json`
- The app uses Last.fm to auto-detect genres if `LASTFM_API_KEY` is set

**Upload not working**
- Make sure the server is running (`python server.py`)
- Check browser console for errors

## License

MIT
