#!/bin/bash
set -e
DIR="/Users/pj/workflows🤖/writer"
cd "$DIR"
"$DIR/.venv/bin/python" "$DIR/daily_digest_reporter.py" >> "$DIR/logs/daily_digest.log" 2>&1
