# Frontend V2 - "Vinyl Noir" Theme

This is a complete redesign of the Music Mapper frontend with a distinctive warm, moody aesthetic inspired by late-night record stores.

## Design Philosophy

**Theme:** Vinyl Noir - warm amber/gold accents on deep dark backgrounds with grain textures and ambient glow effects.

**Typography:**
- Display: Playfair Display (elegant serif for headings)
- Body: Archivo (clean sans-serif)
- Mono: JetBrains Mono (for stats/numbers)

**Color Palette:**
- Background: Deep blacks (#0a0908, #141210, #1c1917)
- Accent: Warm amber (#d4a574, #f0c794)
- Secondary: Rust (#a65d3f), Wine (#722f37), Gold (#c9a227)
- Genre colors: Vibrant saturated colors for different music genres

## File Structure

```
frontend-v2/
├── index.html          # Main HTML with semantic structure
├── css/
│   └── styles.css      # ~2000 lines of polished CSS
└── js/
    └── graph.js        # D3.js visualization with animations
```

## Key Features

### Visual Polish
- **Grain overlay** - Subtle noise texture across the entire UI
- **Ambient glows** - Floating colored orbs in the background
- **Button shimmer** - Shine effect on primary button hover
- **Animated stats** - Counting animation when values change

### Empty State
- **Turntable visualization** - Realistic turntable with:
  - Spinning vinyl record with grooves
  - Animated tonearm that hovers
  - Control knobs and speed indicators
  - "Drop the Needle" messaging

### Loading State
- **Concentric rings** - Three rotating rings at different speeds
- **Central vinyl spinner** - Small vinyl in the center
- **Animated dots** - Pulsing dots after "Mapping your universe"

### Micro-interactions
- **Nav buttons** - Radial gradient on hover, icon scaling
- **Genre chips** - Lift effect with gradient backgrounds
- **Toggle switches** - Glow effect when active
- **Range sliders** - Gradient thumb with grab cursor
- **Search input** - Icon color change, focus glow
- **Footer links** - Underline animation on hover

### Animations
- **Sidebar sections** - Staggered fade-in from left
- **Title shimmer** - Slow gradient animation
- **Turntable float-in** - Bounce entrance
- **Stat pop** - Scale animation when values update

## Technical Notes

### D3.js Graph
- Force-directed layout with customizable physics
- Genre-based node coloring
- Collaboration vs. similar artist link types
- Click to select, drag to move nodes
- Zoom and pan support

### Drag & Drop
- Drop JSON/CSV/ZIP files directly onto the graph area
- Visual feedback with dashed border animation

### Responsive Design
- Sidebar collapses on mobile
- Stats bar wraps on small screens
- Legend hidden on mobile

## Running Locally

```bash
cd frontend-v2
python3 -m http.server 8765
# Open http://localhost:8765
```

## Data Format

The graph expects data in this format:
```json
{
  "nodes": [
    {
      "id": "artist-id",
      "name": "Artist Name",
      "genre": "Electronic",
      "song_count": 5,
      "in_library": true,
      "songs": [{"title": "Song", "album": "Album"}]
    }
  ],
  "links": [
    {
      "source": "artist-1",
      "target": "artist-2",
      "type": "collaboration"
    }
  ]
}
```

## Differences from V1

| Feature | V1 | V2 |
|---------|----|----|
| Theme | Dark blue/purple | Warm amber/noir |
| Empty state | Simple vinyl | Full turntable |
| Loading | Basic spinner | Ring animation |
| Animations | Minimal | Extensive |
| Typography | System fonts | Custom fonts |
| Textures | None | Grain overlay |

## Credits

Crafted with the frontend-design skill's "Vinyl Noir" aesthetic direction.
