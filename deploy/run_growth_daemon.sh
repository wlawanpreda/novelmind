#!/bin/bash
# run_growth_daemon.sh — Background Continuous Growth Engine for ANSRE
# รันงานต่อเนื่อง: ปล่อยนิยายตาม Golden Hours และสร้าง/ตรวจเช็คสื่อ

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "[$(date)] 🚀 Starting ANSRE Growth Daemon..."
exec .venv/bin/python auto_release_scheduler.py --daemon >> SecondBrain/scheduler.log 2>&1
