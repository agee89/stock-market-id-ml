#!/bin/bash
# Wrapper script to run DeepSeek Analyst inside Docker container
if [ -z "$1" ]; then
    echo "Usage: ./analyze.sh [SYMBOL]"
    echo "Example: ./analyze.sh BBRI.JK"
    exit 1
fi

echo "🚀 Launching DeepSeek Analyst for $1..."
docker compose exec -T api python -m src.analyze $1
