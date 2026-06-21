#!/bin/bash

set -e

if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found."
    echo "Run: cp .env.example .env  then add your ANTHROPIC_API_KEY"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Installing dependencies..."
venv/bin/pip install -r requirements.txt -q

echo "Starting SafeHealth on http://localhost:5001 ..."
venv/bin/python app.py
