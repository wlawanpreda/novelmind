#!/usr/bin/env python3
"""
dashboard_gen.py — สร้าง SecondBrain/Live_Dashboard.md จากข้อมูลจริง (ไม่ใช่ตัวเลขเขียนมือ)
แหล่งข้อมูล: จำนวนไฟล์ผลผลิตจริง, schedule_plan_14days, mega_ledger, ypp_velocity_history, events.jsonl
    python dashboard_gen.py
orchestrator เรียกอัตโนมัติท้ายทุกรอบ (ไฟล์ AUTOMATION_DASHBOARD.md เดิมที่เขียนมือไม่ถูกแตะ)
"""
from __future__ import annotations

import os
import json
import glob
from collections import Counter, defaultdict
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
PROJ = os.path.join(SB, "05_Active_Projects")
OUT = os.path.join(SB, "Live_Dashboard.md")


def _count(subdir: str, pattern: str, recursive: bool = False) -> int:
    pat = os.path.join(PROJ, subdir, "**" if recursive else "", pattern)
    return len(glob.glob(pat, recursive=recursive))


def _json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _stage_health(hours: int = 24):
    from run_log import read_events
    since = datetime.now() - timedelta(hours=hours)
    st = defaultdict(lambda: {"runs": 0, "fail": 0, "secs": 0.0, "last_fail": None, "last_tail": ""})
    cycles = 0
    for e in read_events(since):
        if e.get("kind") == "cycle_end" and not e.get("aborted"):
            cycles += 1
        if e.get("kind") != "stage" or e.get("skipped"):
            continue
        s = st[e["stage"]]
        s["runs"] += 1
        s["secs"] += float(e.get("duration_s", 0))
        if not e.get("ok"):
            s["fail"] += 1
            s["last_fail"] = e["ts"]
            s["last_tail"] = (e.get("output_tail") or e.get("error") or "").strip().splitlines()[-1:] or [""]
            s["last_tail"] = s["last_tail"][0][:90]
    return cycles, st


def build() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    L = [f"# 🏭 ANSRE Live Dashboard", f"> สร้างอัตโนมัติ: {now} • ข้อมูลจริงจากไฟล์/ log (ไม่แก้ด้วยมือ)", ""]

    # --- คลังผลงาน
    story_names = {os.path.basename(p).rsplit("_Chapter_", 1)[0]
                   for p in glob.glob(os.path.join(PROJ, "Chapters", "*_Chapter_*.md"))}
    L += ["## 📦 คลังผลงาน", "| หมวด | จำนวน |", "|---|---:|",
          f"| เรื่อง | {len(story_names)} |",
          f"| ตอนนิยาย | {_count('Chapters', '*.md')} |",
          f"| ปก | {_count('Covers', '*.jpg') + _count('Covers', '*.png')} |",
          f"| เสียง (mp3) | {_count('Audio_Output', '*.mp3')} |",
          f"| Teaser | {_count('Teaser_Output', '*.mp4')} |",
          f"| E-Book (.epub) | {len(glob.glob(os.path.join(PROJ, 'Exports', '*.epub')))} |",
          f"| Mega Audiobook (ผลิตแล้ว) | {len(glob.glob(os.path.join(PROJ, 'Exports', 'Mega_Audiobooks', '*_Mega_Metadata.json')))} |",
          ""]

    # --- คิวปล่อย
    plan = _json(os.path.join(PROJ, "schedule_plan_14days.json"), {})
    c = Counter(i.get("status") for i in plan.get("schedule", []))
    if c:
        L += ["## 🗓️ คิวปล่อย 14 วัน", ", ".join(f"{k}: **{v}**" for k, v in sorted(c.items())), ""]
    mega = _json(os.path.join(PROJ, "mega_ledger.json"), {"items": []}).get("items", [])
    if mega:
        L += ["## 🎬 Mega ที่ตั้งเวลาโดยระบบ", "| เรื่อง | ปล่อย (UTC) | URL |", "|---|---|---|"]
        L += [f"| {m.get('story_name', '')[:40]} | {m.get('publish_at') or '-'} | {m.get('url') or '-'} |" for m in mega[-5:]]
        L.append("")

    # --- YPP
    snaps = _json(os.path.join(PROJ, "ypp_velocity_history.json"), {"snapshots": []}).get("snapshots", [])
    if snaps:
        s = snaps[-1]
        L += ["## 📈 YPP Velocity (snapshot ล่าสุด)",
              f"- วันที่ {s.get('date')}: วิวรวม **{s.get('total_views', 0):,}** ({s.get('delta_total_views', 0):+d}) "
              f"• คลิปยาว {s.get('longform_views', 0):,} วิว ({s.get('longform_count', 0)} เรื่อง) "
              f"• Shorts {s.get('shorts_views', 0):,} วิว • คิวรอปล่อย {s.get('scheduled_queue_count', 0)}", ""]

    # --- สุขภาพ pipeline
    try:
        cycles, st = _stage_health(24)
    except Exception:
        cycles, st = 0, {}
    L.append(f"## 🩺 สุขภาพ Pipeline (24 ชม. • {cycles} รอบ)")
    if st:
        L += ["| stage | รัน | ล้ม | เวลาเฉลี่ย(s) | ล้มล่าสุด |", "|---|---:|---:|---:|---|"]
        for name, s in sorted(st.items(), key=lambda kv: (-kv[1]["fail"], kv[0])):
            flag = "🔴" if s["fail"] else "🟢"
            avg = s["secs"] / s["runs"] if s["runs"] else 0
            L.append(f"| {flag} {name} | {s['runs']} | {s['fail']} | {avg:.1f} | {s['last_fail'] or '-'} {s['last_tail']} |")
    else:
        L.append("_ยังไม่มี event (จะมีหลัง orchestrator รันรอบถัดไป)_")
    L.append("")
    return "\n".join(L)


def main():
    text = build()
    os.makedirs(SB, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[dashboard] wrote {OUT}")


if __name__ == "__main__":
    main()
