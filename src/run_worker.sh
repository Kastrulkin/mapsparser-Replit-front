#!/bin/bash
# Script to run worker with correct environment
# Usage: ./src/run_worker.sh

# Ensure we are in the project root
cd "$(dirname "$0")/.." 

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found at venv/"
    exit 1
fi

# Install dependencies if missing (just in case)
pip install -r requirements.txt > /dev/null 2>&1
playwright install chromium > /dev/null 2>&1

# Run worker
echo "Starting worker..."
python -u src/worker.py
