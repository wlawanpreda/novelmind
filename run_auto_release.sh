#!/bin/bash
set -e
DIR="/Users/pj/workflows🤖/writer"
cd "$DIR"
mkdir -p "$DIR/logs"

# 1. ปล่อยตอนนิยายบน ReadAWrite (ตามรอบ Quad Golden Hours)
"$DIR/.venv/bin/python" "$DIR/auto_release_scheduler.py" --cron-tick >> "$DIR/logs/auto_release.log" 2>&1 || true

# 2. ปล่อยคลิป YouTube Shorts ล่วงหน้าตามสต็อก 14 วัน
"$DIR/.venv/bin/python" "$DIR/scheduled_drip_publisher.py" --cron-tick >> "$DIR/logs/auto_release.log" 2>&1 || true
