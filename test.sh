#!/bin/bash
# A single command to run the SNANA Pipeline Assistant tests.
# Usage: ./test.sh [ANTHROPIC_API_KEY]

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Extract API key if provided as parameter (overrides .env)
if [ ! -z "$1" ]; then
    export ANTHROPIC_API_KEY="$1"
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY is not set. Please set it in .env or run as:"
    echo "  ./test.sh your-api-key"
    exit 1
fi

echo "Running SNANA Pipeline Assistant evaluation suite..."
echo "Using Anthropic API Key: ${ANTHROPIC_API_KEY:0:12}..."

# Run the test runner within the virtualenv, stripping PYTHONPATH to avoid NERSC environment conflicts
env -u PYTHONPATH .venv/bin/python eval/run_eval.py --provider anthropic
