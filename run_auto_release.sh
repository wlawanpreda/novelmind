#!/bin/bash
set -e
DIR="/Users/pj/workflows🤖/writer"
cd "$DIR"
"$DIR/.venv/bin/python" "$DIR/auto_release_scheduler.py" >> "$DIR/logs/auto_release.log" 2>&1
