"""
run_log.py — โครงสร้าง log สำหรับวิเคราะห์/พัฒนาระบบต่อ
=======================================================
เขียน event แบบ JSONL (1 บรรทัด = 1 event) ที่ SecondBrain/logs/events.jsonl
และหมุนไฟล์ orchestrator.log อัตโนมัติไม่ให้โตไม่จำกัด

Event ที่บันทึก:
  cycle_start / cycle_end   — ขอบเขตของแต่ละรอบ (cycle_id เดียวกันทุก event ในรอบ)
  stage                     — ผลแต่ละ stage: ok, rc, duration_s, output_tail (เมื่อล้ม), skipped
  (อื่นๆ)                   — เรียก log_event(kind, **fields) ได้จากสคริปต์ใดก็ได้

ใช้วิเคราะห์ด้วย:  python log_report.py [--days 7]
"""
from __future__ import annotations

import os
import json
import gzip
import shutil
import threading
from datetime import datetime
from typing import Any, Dict, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(ROOT, "SecondBrain", "logs")
EVENTS_FILE = os.path.join(LOG_DIR, "events.jsonl")

MAX_EVENTS_BYTES = int(os.environ.get("ANSRE_EVENTS_MAX_MB", "20")) * 1024 * 1024
MAX_TEXT_LOG_BYTES = int(os.environ.get("ANSRE_LOG_MAX_MB", "10")) * 1024 * 1024
KEEP_ARCHIVES = int(os.environ.get("ANSRE_LOG_KEEP", "5"))

_lock = threading.Lock()


def rotate_if_large(path: str, max_bytes: int = MAX_TEXT_LOG_BYTES, keep: int = KEEP_ARCHIVES) -> bool:
    """ถ้าไฟล์ใหญ่เกิน max_bytes → บีบเป็น path.<timestamp>.gz แล้วเริ่มไฟล์ใหม่; เก็บ archive แค่ `keep` ชุดล่าสุด"""
    try:
        if not os.path.exists(path) or os.path.getsize(path) < max_bytes:
            return False
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive = f"{path}.{stamp}.gz"
        with open(path, "rb") as src, gzip.open(archive, "wb") as dst:
            shutil.copyfileobj(src, dst)
        open(path, "w").close()
        base = os.path.basename(path)
        d = os.path.dirname(path)
        olds = sorted(f for f in os.listdir(d) if f.startswith(base + ".") and f.endswith(".gz"))
        for f in olds[:-keep]:
            os.remove(os.path.join(d, f))
        return True
    except Exception:
        return False


def log_event(kind: str, **fields: Any) -> None:
    """บันทึก 1 event ลง events.jsonl (ไม่ throw — log พังต้องไม่ทำให้ pipeline พัง)"""
    rec: Dict[str, Any] = {"ts": datetime.now().isoformat(timespec="seconds"), "kind": kind}
    rec.update(fields)
    try:
        with _lock:
            os.makedirs(LOG_DIR, exist_ok=True)
            rotate_if_large(EVENTS_FILE, MAX_EVENTS_BYTES)
            with open(EVENTS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def read_events(since: Optional[datetime] = None):
    """อ่าน event ทั้งหมด (ข้ามบรรทัดเสีย) — กรองด้วยเวลาได้"""
    if not os.path.exists(EVENTS_FILE):
        return
    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if since:
                try:
                    if datetime.fromisoformat(rec["ts"]) < since:
                        continue
                except Exception:
                    continue
            yield rec
