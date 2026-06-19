#!/bin/bash

echo "Starting NovAtel AI Assistant Streamlit App..."
echo ""

# Activate virtual environment
source .venv/bin/activate

# Check if .env file exists
if [ ! -f .env ]; then
    echo "WARNING: .env file not found!"
    echo "Please create a .env file with your AWS configuration."
    echo "See STREAMLIT_SETUP.md for details."
    echo ""
    exit 1
fi

# Start Streamlit
echo "Starting Streamlit server..."
echo "The app will open in your browser at http://localhost:8501"
echo "Press Ctrl+C to stop the server"
echo ""

python -m streamlit run streamlit_app.py
