#!/bin/bash
# Session Prediction CLI Wrapper
# Usage: session-predict "implement feature X"

cd ~/researchgravity || exit 1

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python3 predict_session.py "$@"
