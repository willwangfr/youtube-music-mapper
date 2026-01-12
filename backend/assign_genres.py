"""
Improved genre assignment for music graph.
Uses extensive artist database and pattern matching.
"""

import json
import re

# Comprehensive artist-to-genre mapping
ARTIST_GENRES = {
    # Melodic Bass / Melodic Dubstep
    'Seven Lions': 'Melodic Bass',
    'Illenium': 'Melodic Bass',
    'Said The Sky': 'Melodic Bass',
    'Dabin': 'Melodic Bass',
    'SLANDER': 'Melodic Bass',
    'Jason Ross': 'Melodic Bass',
    'Crystal Skies': 'Melodic Bass',
    'Trivecta': 'Melodic Bass',
    'Last Heroes': 'Melodic Bass',
    'MitiS': 'Melodic Bass',
    'William Black': 'Melodic Bass',
    'Nurko': 'Melodic Bass',
    'Blanke': 'Melodic Bass',
    'ARMNHMR': 'Melodic Bass',
    'Xavi': 'Melodic Bass',
    'Fairlane': 'Melodic Bass',
    'Ophelia Records': 'Melodic Bass',
    'Mitis': 'Melodic Bass',
    'Adventure Club': 'Melodic Bass',
    'HALIENE': 'Melodic Bass',
    'RUNN': 'Melodic Bass',
    'Trivecta': 'Melodic Bass',
    'Au5': 'Melodic Bass',
    'Grabbitz': 'Melodic Bass',
    'Nevve': 'Melodic Bass',

    # Dubstep / Heavy Bass
    'Excision': 'Dubstep/Bass',
    'Subtronics': 'Dubstep/Bass',
    'Sullivan King': 'Dubstep/Bass',
    'SVDDEN DEATH': 'Dubstep/Bass',
    'Kompany': 'Dubstep/Bass',
    'Wooli': 'Dubstep/Bass',
    'Marauda': 'Dubstep/Bass',
    'MUST DIE!': 'Dubstep/Bass',
    'Zomboy': 'Dubstep/Bass',
    'Virtual Riot': 'Dubstep/Bass',
    'Skrillex': 'Dubstep/Bass',
    'Knife Party': 'Dubstep/Bass',
    'Midnight Tyrannosaurus': 'Dubstep/Bass',
    'Datsik': 'Dubstep/Bass',
    'Doctor P': 'Dubstep/Bass',
    'Flux Pavilion': 'Dubstep/Bass',
    'Pegboard Nerds': 'Dubstep/Bass',
    'Eptic': 'Dubstep/Bass',
    'NGHTMRE': 'Dubstep/Bass',
    'Dion Timmer': 'Dubstep/Bass',
    'Ray Volpe': 'Dubstep/Bass',
    'Riot Ten': 'Dubstep/Bass',
    'JSTJR': 'Dubstep/Bass',
    'Dubstep uNk': 'Dubstep/Bass',
    'ALLEYCVT': 'Dubstep/Bass',

    # Future Bass
    'Flume': 'Future Bass',
    'San Holo': 'Future Bass',
    'Slushii': 'Future Bass',
    'Marshmello': 'Future Bass',
    'Louis The Child': 'Future Bass',
    'Whethan': 'Future Bass',
    'Ekali': 'Future Bass',
    'ODESZA': 'Future Bass',
    'Kasbo': 'Future Bass',
    'Wave Racer': 'Future Bass',
    'Grant': 'Future Bass',
    'Laszlo': 'Future Bass',
    'Hyper Potions': 'Future Bass',

    # Progressive House
    'deadmau5': 'Progressive House',
    'Eric Prydz': 'Progressive House',
    'Above & Beyond': 'Progressive House',
    'Lane 8': 'Progressive House',
    'Ben Böhmer': 'Progressive House',
    'Nora En Pure': 'Progressive House',
    'Le Youth': 'Progressive House',
    'Yotto': 'Progressive House',
    'Spencer Brown': 'Progressive House',
    'Tinlicker': 'Progressive House',
    'Grum': 'Progressive House',
    'Avicii': 'Progressive House',
    'Swedish House Mafia': 'Progressive House',
    'Martin Garrix': 'Progressive House',
    'Alesso': 'Progressive House',
    'Axwell': 'Progressive House',
    'Sebastian Ingrosso': 'Progressive House',
    'Kygo': 'Progressive House',

    # Trance
    'Armin van Buuren': 'Trance',
    'Andrew Rayel': 'Trance',
    'Ferry Corsten': 'Trance',
    'Aly & Fila': 'Trance',
    'Cosmic Gate': 'Trance',
    'Paul van Dyk': 'Trance',
    'Markus Schulz': 'Trance',
    'Giuseppe Ottaviani': 'Trance',
    'Gareth Emery': 'Trance',
    'Dash Berlin': 'Trance',
    'Tritonal': 'Trance',
    'ALPHA 9': 'Trance',

    # House / Tech House
    'Fisher': 'Tech House',
    'Chris Lake': 'Tech House',
    'John Summit': 'Tech House',
    'Dom Dolla': 'Tech House',
    'ACRAZE': 'Tech House',
    'Matroda': 'Tech House',
    'TESTPILOT': 'Tech House',
    'Green Velvet': 'Tech House',
    'Lee Foss': 'Tech House',
    'Mau P': 'Tech House',
    'James Hype': 'Tech House',

    # UK House / Garage
    'Disclosure': 'UK House',
    'Tchami': 'UK House',
    'Habstrakt': 'UK House',
    'AC Slater': 'UK House',
    'Chris Lorenzo': 'UK House',
    'Wax Motif': 'UK House',
    'Noizu': 'UK House',

    # Bass House
    'JOYRYDE': 'Bass House',
    'Valentino Khan': 'Bass House',
    'Dr. Fresch': 'Bass House',
    'Jauz': 'Bass House',
    'Ghastly': 'Bass House',
    'Drezo': 'Bass House',
    'Moksi': 'Bass House',

    # Drum & Bass
    'Netsky': 'Drum & Bass',
    'Pendulum': 'Drum & Bass',
    'Sub Focus': 'Drum & Bass',
    'Andy C': 'Drum & Bass',
    'Chase & Status': 'Drum & Bass',
    'Dimension': 'Drum & Bass',
    'Camo & Krooked': 'Drum & Bass',
    'Fred V': 'Drum & Bass',
    'Maduk': 'Drum & Bass',
    'High Contrast': 'Drum & Bass',
    'Wilkinson': 'Drum & Bass',
    'Culture Shock': 'Drum & Bass',
    'Metrik': 'Drum & Bass',

    # Trap / Bass
    'ISOxo': 'Trap/Bass',
    'WAVEDASH': 'Dubstep/Bass',
    'Wavedash': 'Dubstep/Bass',
    'RL Grime': 'Trap/Bass',
    'Baauer': 'Trap/Bass',
    'What So Not': 'Trap/Bass',
    'Boombox Cartel': 'Trap/Bass',
    'UZ': 'Trap/Bass',
    'TroyBoi': 'Trap/Bass',
    'TNGHT': 'Trap/Bass',
    'Mr. Carmack': 'Trap/Bass',
    'G Jones': 'Trap/Bass',
    'Eprom': 'Trap/Bass',
    'Alison Wonderland': 'Trap/Bass',
    'Flosstradamus': 'Trap/Bass',

    # Electro House
    'Zedd': 'Electro House',
    'Porter Robinson': 'Electro House',
    'Wolfgang Gartner': 'Electro House',
    'Feed Me': 'Electro House',
    'Kill The Noise': 'Electro House',
    'Dillon Francis': 'Electro House',
    'Steve Aoki': 'Electro House',
    'Afrojack': 'Electro House',
    'R3HAB': 'Electro House',
    'Dimitri Vegas & Like Mike': 'Electro House',

    # Pop/EDM crossover
    'The Chainsmokers': 'Pop/EDM',
    'Calvin Harris': 'Pop/EDM',
    'David Guetta': 'Pop/EDM',
    'Tiësto': 'Pop/EDM',
    'DJ Snake': 'Pop/EDM',
    'Major Lazer': 'Pop/EDM',
    'Diplo': 'Pop/EDM',
    'Galantis': 'Pop/EDM',
    'Clean Bandit': 'Pop/EDM',
    'Alan Walker': 'Pop/EDM',
    'Jonas Blue': 'Pop/EDM',
    'Gryffin': 'Pop/EDM',
    'NOTD': 'Pop/EDM',
    'Quinn XCII': 'Pop/EDM',
    'Lauv': 'Pop/EDM',
    'Chelsea Cutler': 'Pop/EDM',
    'Jeremy Zucker': 'Pop/EDM',
    'Ellie Goulding': 'Pop/EDM',
    'Dua Lipa': 'Pop/EDM',
    'Sigala': 'Pop/EDM',
    'Riton': 'Pop/EDM',
    'RÜFÜS DU SOL': 'Pop/EDM',

    # Electronic/Indie
    'AURORA': 'Electronic/Indie',
    'Glass Animals': 'Electronic/Indie',
    'Tame Impala': 'Electronic/Indie',
    'M83': 'Electronic/Indie',
    'Sylvan Esso': 'Electronic/Indie',
    'Purity Ring': 'Electronic/Indie',
    'CHVRCHES': 'Electronic/Indie',
    'Phantogram': 'Electronic/Indie',
    'Tycho': 'Electronic/Indie',
    'Bonobo': 'Electronic/Indie',
    'Caribou': 'Electronic/Indie',
    'Jamie xx': 'Electronic/Indie',
    'Four Tet': 'Electronic/Indie',
    'Jai Wolf': 'Electronic/Indie',
    'Big Wild': 'Electronic/Indie',
    'Petit Biscuit': 'Electronic/Indie',
    'keshi': 'Electronic/Indie',
    'Home': 'Electronic/Indie',

    # K-Pop
    'BTS': 'K-Pop',
    'BLACKPINK': 'K-Pop',
    'TWICE': 'K-Pop',
    'Red Velvet': 'K-Pop',
    'EXO': 'K-Pop',
    'NCT': 'K-Pop',
    'NCT 127': 'K-Pop',
    'NCT DREAM': 'K-Pop',
    'Stray Kids': 'K-Pop',
    'ENHYPEN': 'K-Pop',
    'aespa': 'K-Pop',
    'IVE': 'K-Pop',
    'NewJeans': 'K-Pop',
    'LE SSERAFIM': 'K-Pop',
    'ITZY': 'K-Pop',
    'TXT': 'K-Pop',
    'SEVENTEEN': 'K-Pop',
    'GOT7': 'K-Pop',
    'MONSTA X': 'K-Pop',
    'ATEEZ': 'K-Pop',
    'THE BOYZ': 'K-Pop',
    '(G)I-DLE': 'K-Pop',
    'MAMAMOO': 'K-Pop',
    'LOONA': 'K-Pop',
    'TREASURE': 'K-Pop',
    'IU': 'K-Pop',
    'ROSÉ': 'K-Pop',
    'LISA': 'K-Pop',
    'Jennie': 'K-Pop',
    'Jungkook': 'K-Pop',
    'Jimin': 'K-Pop',
    'V': 'K-Pop',
    'j-hope': 'K-Pop',
    'Agust D': 'K-Pop',
    'RM': 'K-Pop',
    'SUGA': 'K-Pop',
    'Jin': 'K-Pop',
    'BIBI': 'K-Pop',
    'pH-1': 'K-Pop',
    'Jay Park': 'K-Pop',
    'DPR IAN': 'K-Pop',
    'DPR LIVE': 'K-Pop',
    'DEAN': 'K-Pop',

    # Hip-Hop/Rap
    'Drake': 'Hip-Hop',
    'Kendrick Lamar': 'Hip-Hop',
    'J. Cole': 'Hip-Hop',
    'Travis Scott': 'Hip-Hop',
    'Post Malone': 'Hip-Hop',
    'Juice WRLD': 'Hip-Hop',
    'XXXTentacion': 'Hip-Hop',
    'Lil Uzi Vert': 'Hip-Hop',
    'Playboi Carti': 'Hip-Hop',
    'Future': 'Hip-Hop',
    'Metro Boomin': 'Hip-Hop',
    '21 Savage': 'Hip-Hop',
    'Baby Keem': 'Hip-Hop',
    'Tyler, The Creator': 'Hip-Hop',
    'A$AP Rocky': 'Hip-Hop',
    'Mac Miller': 'Hip-Hop',
    'Kid Cudi': 'Hip-Hop',
    'Kanye West': 'Hip-Hop',
    'Ye': 'Hip-Hop',
    'JAY-Z': 'Hip-Hop',
    'Eminem': 'Hip-Hop',
    'Nas': 'Hip-Hop',
    'J.I.D': 'Hip-Hop',
    'Denzel Curry': 'Hip-Hop',
    'Joey Bada$$': 'Hip-Hop',
    'Vince Staples': 'Hip-Hop',
    'ScHoolboy Q': 'Hip-Hop',
    'BROCKHAMPTON': 'Hip-Hop',
    'Jack Harlow': 'Hip-Hop',
    'Lil Nas X': 'Hip-Hop',
    'Doja Cat': 'Hip-Hop',
    'Megan Thee Stallion': 'Hip-Hop',
    'Cardi B': 'Hip-Hop',
    'Nicki Minaj': 'Hip-Hop',
    'SZA': 'Hip-Hop',
    'The Weeknd': 'Hip-Hop',
    'Don Toliver': 'Hip-Hop',
    'Gunna': 'Hip-Hop',
    'Young Thug': 'Hip-Hop',
    'Lil Baby': 'Hip-Hop',
    'DaBaby': 'Hip-Hop',
    'Roddy Ricch': 'Hip-Hop',
    'Pop Smoke': 'Hip-Hop',

    # Pop
    'Taylor Swift': 'Pop',
    'Ed Sheeran': 'Pop',
    'Ariana Grande': 'Pop',
    'Justin Bieber': 'Pop',
    'Bruno Mars': 'Pop',
    'Billie Eilish': 'Pop',
    'Olivia Rodrigo': 'Pop',
    'Harry Styles': 'Pop',
    'Shawn Mendes': 'Pop',
    'Camila Cabello': 'Pop',
    'Selena Gomez': 'Pop',
    'Rihanna': 'Pop',
    'Lady Gaga': 'Pop',
    'Katy Perry': 'Pop',
    'Beyoncé': 'Pop',
    'Britney Spears': 'Pop',
    'Black Eyed Peas': 'Pop',
    'Miley Cyrus': 'Pop',
    'Halsey': 'Pop',
    'Demi Lovato': 'Pop',
    'Charlie Puth': 'Pop',
    'Khalid': 'Pop',
    'Bazzi': 'Pop',

    # Rock
    'twenty one pilots': 'Rock',
    'Imagine Dragons': 'Rock',
    'Panic! At The Disco': 'Rock',
    'Fall Out Boy': 'Rock',
    'My Chemical Romance': 'Rock',
    'Green Day': 'Rock',
    'Blink-182': 'Rock',
    'Linkin Park': 'Rock',
    'Arctic Monkeys': 'Rock',
    'The 1975': 'Rock',
    'Coldplay': 'Rock',
    'Muse': 'Rock',
    'Foo Fighters': 'Rock',
    'Radiohead': 'Rock',
    'The Killers': 'Rock',
    'Red Hot Chili Peppers': 'Rock',

    # Cinematic / Ambient
    'Hans Zimmer': 'Cinematic',
    'Thomas Bergersen': 'Cinematic',
    'Two Steps From Hell': 'Cinematic',
    'Audiomachine': 'Cinematic',
    'Artzie Music': 'Cinematic',

    # Tropical House
    'Thomas Jack': 'Tropical House',
    'Sam Feldt': 'Tropical House',
    'Felix Jaehn': 'Tropical House',
    'Lost Frequencies': 'Tropical House',
    'Robin Schulz': 'Tropical House',

    # Midtempo Bass
    'REZZ': 'Midtempo Bass',
    '1788-L': 'Midtempo Bass',
    'Deathpact': 'Midtempo Bass',
    'Blanke': 'Midtempo Bass',
    'Lucii': 'Midtempo Bass',

    # Labels/Channels (inherit from label genre)
    'Proximity': 'Pop/EDM',
    'NCS': 'Pop/EDM',
    'Trap Nation': 'Trap/Bass',
    'Bass Nation': 'Dubstep/Bass',
    'Monstercat': 'Electronic',
    'Revealed Recordings': 'Progressive House',
    'OWSLA': 'Dubstep/Bass',
    'Mad Decent': 'Trap/Bass',
    'Anjunabeats': 'Trance',
    'Anjunadeep': 'Progressive House',

    # More EDM Artists
    'Brooks': 'Progressive House',
    'Mesto': 'Progressive House',
    'Mike Williams': 'Progressive House',
    'Matisse & Sadko': 'Progressive House',
    'DubVision': 'Progressive House',
    'Nicky Romero': 'Progressive House',
    'Hardwell': 'Progressive House',
    'W&W': 'Progressive House',
    'Arty': 'Progressive House',
    'Audien': 'Progressive House',
    'Hoang': 'Pop/EDM',
    'Dylan Matthew': 'Melodic Bass',
    'Bipolar Sunshine': 'Pop/EDM',
    'Shaun Farrugia': 'Pop/EDM',
    'Disco Lines': 'House',

    # R&B
    'Frank Ocean': 'R&B',
    'Daniel Caesar': 'R&B',
    'Brent Faiyaz': 'R&B',
    'Summer Walker': 'R&B',
    'H.E.R.': 'R&B',
    'Snoh Aalegra': 'R&B',
    '6LACK': 'R&B',
    'Giveon': 'R&B',
    'Lucky Daye': 'R&B',
    'dvsn': 'R&B',
    'Anderson .Paak': 'R&B',
    'blackbear': 'R&B',

    # Additional EDM
    'HAYLA': 'Melodic Bass',
    'Ace Aura': 'Melodic Bass',
    'INZO': 'Melodic Bass',
    'SABAI': 'Progressive House',
    'TheFatRat': 'Pop/EDM',
    'Ganja White Night': 'Dubstep/Bass',
    'Timmy Trumpet': 'Progressive House',
    'Anyma': 'Progressive House',
    'Edward Maya': 'Pop/EDM',
    'K/DA': 'Pop/EDM',
    'Owl City': 'Electronic/Indie',
    'Lights': 'Electronic/Indie',
    'Beach House': 'Electronic/Indie',
    'Empire Of The Sun': 'Electronic/Indie',
    'Henry Fong': 'Electro House',
    'Lil Jon': 'Hip-Hop',
    'Sean Kingston': 'Pop',
    'Flowdan': 'Dubstep/Bass',
    'runThis': 'Pop/EDM',

    # Additional K-Pop
    'GFRIEND': 'K-Pop',
    '이달의 소녀': 'K-Pop',
    'Chuu': 'K-Pop',

    # Additional Pop
    'Cigarettes After Sex': 'Rock',
    'Jon Bellion': 'Pop',
    'Train': 'Pop',
    'Justin Timberlake': 'Pop',
    'Clairo': 'Pop',
    'PinkPantheress': 'Pop',
    'Shakira': 'Pop',
    'Madison Beer': 'Pop',
    'Carly Rae Jepsen': 'Pop',
    'Conan Gray': 'Pop',
    'Maroon 5': 'Pop',
    'Flo Rida': 'Pop',
    'Pitbull': 'Pop',
    'Sean Paul': 'Pop',
    'LMFAO': 'Pop',
    'will.i.am': 'Pop',
    'Chris Brown': 'Pop',
    'Usher': 'Pop',
    'Jason Derulo': 'Pop',
    'Ne-Yo': 'Pop',

    # Misclassification fixes
    'Bassjackers': 'Electro House',
    'Tove Lo': 'Pop',
    'Lost Lands Music Festival': 'Dubstep/Bass',
    'Vicetone': 'Progressive House',
    'David Bowie': 'Rock',
    'Angels & Airwaves': 'Rock',
    'wave to earth': 'R&B',
    'Creedence Clearwater Revival': 'Rock',
    'Avril Lavigne': 'Rock',
    'Tape B': 'Dubstep/Bass',
    'Sick Individuals': 'Progressive House',
    'Troye Sivan': 'Pop',
    'Far East Movement': 'Hip-Hop',
    'DEV': 'Pop',
    'Vika Jigulina': 'Pop/EDM',
    'Level Up': 'Dubstep/Bass',
    'Oliver Heldens': 'Tech House',
    'Sergei Rachmaninoff': 'Classical',
    'The Devil Wears Prada': 'Rock',
    'EVAN GIIA': 'Pop/EDM',
    'Kaivon': 'Melodic Bass',
    'Sammy Virji': 'UK House',
    'VALORANT': 'Electronic',
    'Riovaz': 'Electronic/Indie',
    'IVORY': 'Pop/EDM',
    'Vindaloo Singh': 'Pop/EDM',
    'Royal Philharmonic Orchestra': 'Classical',
    'Steve Angello': 'Progressive House',
    'Trevor Guthrie': 'Pop/EDM',
    'Levity': 'Melodic Bass',
    'Revive Music': 'Electronic',

    # Additional Rock
    'The Beatles': 'Rock',
    'Guns N\' Roses': 'Rock',
    'Fleetwood Mac': 'Rock',
    'Queen': 'Rock',
    'Led Zeppelin': 'Rock',
    'Pink Floyd': 'Rock',
    'Nirvana': 'Rock',
    'AC/DC': 'Rock',

    # Classical
    'Frédéric Chopin': 'Classical',
    'Ludwig van Beethoven': 'Classical',
    'Johann Sebastian Bach': 'Classical',
    'Wolfgang Amadeus Mozart': 'Classical',
    'Hans Zimmer': 'Cinematic',

    # UK Grime/Hip-Hop
    'Skepta': 'Hip-Hop',
    'Stormzy': 'Hip-Hop',
    'Dave': 'Hip-Hop',
    'Central Cee': 'Hip-Hop',
    'AJ Tracey': 'Hip-Hop',
    'slowthai': 'Hip-Hop',
    'PlaqueBoyMax': 'Hip-Hop',

    # More producers/vocalists
    'Casey Cook': 'Melodic Bass',
    'April Bender': 'Melodic Bass',
    'Jex': 'Melodic Bass',
    'fussy': 'Pop/EDM',
    'bbyclose': 'Pop/EDM',
    'ISOKNOCK': 'Pop/EDM',
    'cade clair': 'Pop/EDM',
    'A Little Sound': 'Pop/EDM',
    'DerekD2': 'Pop/EDM',
}

# Pattern-based genre detection
GENRE_PATTERNS = [
    (r'\b(dubstep|bass music|brostep)\b', 'Dubstep/Bass'),
    (r'\b(melodic dubstep|melodic bass)\b', 'Melodic Bass'),
    (r'\b(future bass)\b', 'Future Bass'),
    (r'\b(drum and bass|dnb|d&b|drum & bass)\b', 'Drum & Bass'),
    (r'\b(progressive house|prog house)\b', 'Progressive House'),
    (r'\b(tech house)\b', 'Tech House'),
    (r'\b(deep house)\b', 'UK House'),
    (r'\b(trance|psytrance)\b', 'Trance'),
    (r'\b(trap)\b', 'Trap/Bass'),
    (r'\b(k-?pop|korean pop)\b', 'K-Pop'),
    (r'\b(hip-?hop|rap)\b', 'Hip-Hop'),
]


def assign_genres(graph_file: str):
    """Load graph data and assign genres to nodes."""

    with open(graph_file, 'r') as f:
        data = json.load(f)

    # Track genre changes
    changed = 0
    still_other = 0

    for node in data['nodes']:
        name = node.get('name', '')
        current_genre = node.get('genre', 'Other')

        # First try exact match
        if name in ARTIST_GENRES:
            new_genre = ARTIST_GENRES[name]
            if current_genre != new_genre:
                node['genre'] = new_genre
                changed += 1
            continue

        # Try case-insensitive match
        name_lower = name.lower()
        matched = False
        for artist, genre in ARTIST_GENRES.items():
            if artist.lower() == name_lower:
                node['genre'] = genre
                matched = True
                changed += 1
                break

        if matched:
            continue

        # Try partial match for artist names (e.g., "feat. X" collaborations)
        for artist, genre in ARTIST_GENRES.items():
            if artist.lower() in name_lower or name_lower in artist.lower():
                node['genre'] = genre
                matched = True
                changed += 1
                break

        if matched:
            continue

        # Try pattern matching on description or other metadata
        for pattern, genre in GENRE_PATTERNS:
            if re.search(pattern, name_lower):
                node['genre'] = genre
                matched = True
                changed += 1
                break

        if not matched and current_genre == 'Other':
            still_other += 1

    # Save updated data
    with open(graph_file, 'w') as f:
        json.dump(data, f, indent=2)

    # Print summary
    print(f"Updated genres for {changed} artists")
    print(f"Still 'Other': {still_other} artists")

    # Count final genres
    genres = {}
    for node in data['nodes']:
        g = node.get('genre', 'Other')
        genres[g] = genres.get(g, 0) + 1

    print("\nGenre distribution:")
    for g, c in sorted(genres.items(), key=lambda x: -x[1]):
        print(f"  {c:4d} - {g}")


def infer_genres_from_connections(graph_file: str, min_connections: int = 2):
    """Infer genres for 'Other' artists based on their connections.

    IMPORTANT: Only infer within same genre family to avoid cross-contamination.
    E.g., don't infer K-Pop for EDM artists just because of one collab.
    """

    # Genre families - only infer within same family
    GENRE_FAMILIES = {
        'EDM': {'Melodic Bass', 'Dubstep/Bass', 'Future Bass', 'Progressive House',
                'Trance', 'Tech House', 'UK House', 'Bass House', 'Electro House',
                'Trap/Bass', 'Drum & Bass', 'Pop/EDM', 'Electronic/Indie', 'Midtempo Bass',
                'Tropical House', 'House', 'Electro Soul', 'Electronic'},
        'K-Pop': {'K-Pop'},
        'Hip-Hop': {'Hip-Hop', 'R&B'},
        'Pop': {'Pop'},
        'Rock': {'Rock'},
        'Classical': {'Classical', 'Cinematic'},
    }

    with open(graph_file, 'r') as f:
        data = json.load(f)

    # Build adjacency map
    connections = {}
    for link in data['links']:
        src = link['source'] if isinstance(link['source'], str) else link['source']['id']
        tgt = link['target'] if isinstance(link['target'], str) else link['target']['id']

        if src not in connections:
            connections[src] = []
        if tgt not in connections:
            connections[tgt] = []

        connections[src].append(tgt)
        connections[tgt].append(src)

    # Build id -> node map
    node_map = {n['id']: n for n in data['nodes']}

    # Infer genres for 'Other' nodes
    changed = 0
    for node in data['nodes']:
        if node.get('genre') != 'Other':
            continue

        node_id = node['id']
        if node_id not in connections:
            continue

        # Count genres of connected artists
        genre_counts = {}
        for conn_id in connections[node_id]:
            if conn_id in node_map:
                conn_genre = node_map[conn_id].get('genre', 'Other')
                if conn_genre != 'Other':
                    genre_counts[conn_genre] = genre_counts.get(conn_genre, 0) + 1

        # Only infer if there's a STRONG majority (3+ connections of same genre)
        # AND don't infer K-Pop from connections (too many false positives)
        if genre_counts:
            top_genre, top_count = max(genre_counts.items(), key=lambda x: x[1])
            total_conns = sum(genre_counts.values())

            # Skip K-Pop inference entirely - too error prone
            if top_genre == 'K-Pop':
                continue

            # Require 3+ connections AND >60% majority
            if top_count >= 3 and top_count / total_conns > 0.6:
                node['genre'] = top_genre
                changed += 1

    # Save
    with open(graph_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\nInferred genres for {changed} artists based on connections")

    # Recount
    genres = {}
    for node in data['nodes']:
        g = node.get('genre', 'Other')
        genres[g] = genres.get(g, 0) + 1

    still_other = genres.get('Other', 0)
    print(f"Still 'Other': {still_other} artists")


def assign_fallback_genre(graph_file: str):
    """For remaining 'Other' artists, assign 'Electronic' as fallback if they have connections to EDM genres."""

    edm_genres = {'Melodic Bass', 'Dubstep/Bass', 'Future Bass', 'Progressive House', 'Trance',
                  'Tech House', 'UK House', 'Bass House', 'Electro House', 'Trap/Bass', 'Drum & Bass',
                  'Pop/EDM', 'Electronic/Indie', 'Midtempo Bass', 'Tropical House', 'House'}

    with open(graph_file, 'r') as f:
        data = json.load(f)

    # Build adjacency map
    connections = {}
    for link in data['links']:
        src = link['source'] if isinstance(link['source'], str) else link['source']['id']
        tgt = link['target'] if isinstance(link['target'], str) else link['target']['id']
        if src not in connections:
            connections[src] = []
        if tgt not in connections:
            connections[tgt] = []
        connections[src].append(tgt)
        connections[tgt].append(src)

    node_map = {n['id']: n for n in data['nodes']}

    changed = 0
    for node in data['nodes']:
        if node.get('genre') != 'Other':
            continue

        node_id = node['id']

        # Check if connected to any EDM artist
        if node_id in connections:
            has_edm_connection = False
            for conn_id in connections[node_id]:
                if conn_id in node_map:
                    conn_genre = node_map[conn_id].get('genre', 'Other')
                    if conn_genre in edm_genres:
                        has_edm_connection = True
                        break

            if has_edm_connection:
                node['genre'] = 'Electronic'
                changed += 1

    with open(graph_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\nAssigned 'Electronic' fallback to {changed} artists with EDM connections")

    # Final count
    genres = {}
    for node in data['nodes']:
        g = node.get('genre', 'Other')
        genres[g] = genres.get(g, 0) + 1

    print("\nFinal genre distribution:")
    for g, c in sorted(genres.items(), key=lambda x: -x[1]):
        print(f"  {c:4d} - {g}")


if __name__ == "__main__":
    assign_genres("../frontend/graph_data.json")

    # Run inference multiple times to propagate
    for i in range(3):
        infer_genres_from_connections("../frontend/graph_data.json", min_connections=1)

    # Fallback for remaining connected artists
    assign_fallback_genre("../frontend/graph_data.json")
