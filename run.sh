#!/bin/bash

# YouTube Music Mapper - Quick Start Script

echo "=================================="
echo "  YouTube Music Mapper"
echo "=================================="
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed."
    exit 1
fi

cd "$(dirname "$0")/backend"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Check if auth exists
if [ ! -f "browser.json" ]; then
    echo
    echo "No authentication found."
    echo "Running setup..."
    echo
    python setup_auth.py
fi

# Start server
echo
echo "Starting server..."
echo "Open http://localhost:5000 in your browser"
echo
python server.py
