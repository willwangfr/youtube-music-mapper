#!/usr/bin/env python3
"""
Interactive setup script for YouTube Music authentication.
Run this first to authenticate with your YouTube Music account.
"""

import json
import sys
from pathlib import Path

def manual_auth_setup():
    """Guide user through manual authentication header extraction."""
    print("\n" + "="*60)
    print("  YouTube Music Authentication Setup")
    print("="*60)
    print("""
To authenticate with YouTube Music, you need to extract your browser cookies.

STEPS:
1. Open YouTube Music (music.youtube.com) in your browser
2. Make sure you're logged in
3. Open Developer Tools:
   - Chrome/Edge: Press F12 or Ctrl+Shift+I (Cmd+Option+I on Mac)
   - Firefox: Press F12 or Ctrl+Shift+I
4. Go to the 'Network' tab
5. Filter requests by typing 'browse' in the filter box
6. Click on any song or navigate to trigger a request
7. Click on any request that starts with 'browse'
8. Look in the 'Request Headers' section

You'll need to copy these headers:
- Cookie
- Authorization (if present)
- X-Goog-AuthUser (usually 0)
""")

    print("\nNow, paste your headers below. Type 'done' when finished.\n")

    headers = {}

    # Get Cookie
    print("Paste your 'Cookie' header value (this will be long):")
    cookie_lines = []
    while True:
        line = input()
        if line.lower() == 'done':
            break
        cookie_lines.append(line)
    headers['Cookie'] = ' '.join(cookie_lines)

    if not headers['Cookie']:
        print("Error: Cookie is required!")
        sys.exit(1)

    # Ask for optional headers
    print("\nPaste 'Authorization' header (or press Enter to skip):")
    auth = input().strip()
    if auth:
        headers['Authorization'] = auth

    print("\nPaste 'X-Goog-AuthUser' (usually 0, press Enter for default):")
    auth_user = input().strip()
    headers['X-Goog-AuthUser'] = auth_user if auth_user else '0'

    # Save to browser.json
    auth_file = Path(__file__).parent / 'browser.json'

    # Format for ytmusicapi
    ytmusic_headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "cookie": headers['Cookie'],
        "x-goog-authuser": headers.get('X-Goog-AuthUser', '0'),
        "x-origin": "https://music.youtube.com",
    }

    if 'Authorization' in headers:
        ytmusic_headers['authorization'] = headers['Authorization']

    with open(auth_file, 'w') as f:
        json.dump(ytmusic_headers, f, indent=2)

    print(f"\n✓ Authentication saved to {auth_file}")
    print("\nYou can now run: python server.py")


def ytmusicapi_setup():
    """Use ytmusicapi's built-in setup."""
    try:
        from ytmusicapi import YTMusic

        print("\n" + "="*60)
        print("  YouTube Music Authentication Setup (ytmusicapi)")
        print("="*60)
        print("""
This will guide you through the ytmusicapi authentication process.

You'll need to:
1. Open YouTube Music in your browser
2. Open Developer Tools (F12)
3. Go to Network tab and filter by 'browse'
4. Copy the full request headers when prompted
""")

        auth_file = Path(__file__).parent / 'browser.json'
        YTMusic.setup(filepath=str(auth_file))

        print(f"\n✓ Authentication saved to {auth_file}")
        print("\nYou can now run: python server.py")

    except ImportError:
        print("ytmusicapi not installed. Run: pip install ytmusicapi")
        print("Falling back to manual setup...")
        manual_auth_setup()


if __name__ == "__main__":
    print("\nChoose setup method:")
    print("1. Use ytmusicapi setup (recommended)")
    print("2. Manual header extraction")
    print()

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "2":
        manual_auth_setup()
    else:
        ytmusicapi_setup()
