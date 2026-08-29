"""
story_bible.py — Story Bible & State Consistency Tracker for Multi-Chapter Novels
===================================================================================

ติดตามและควบคุมความต่อเนื่องของเนื้อเรื่องหลายตอน (Continuity & State Tracking):
  - สถานะตัวละคร (เลเวล, สกิล, ไอเทม, ความสัมพันธ์, พลัง)
  - เส้นเวลาและเหตุการณ์สำคัญ (Timeline of events)
  - กฎของโลกและปมปริศนา (World lore & Active mysteries)

บันทึกเป็น JSON ใน SecondBrain/05_Active_Projects/Story_Bible/<ชื่อเรื่อง>_Bible.json
"""
from __future__ import annotations

import os
import re
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
BIBLE_DIR = os.path.join(SB, "05_Active_Projects", "Story_Bible")
os.makedirs(BIBLE_DIR, exist_ok=True)


def _bible_path(title: str) -> str:
    safe = re.sub(r'[^\w\-_\s฀-๿]', '', title).strip().replace(' ', '_')
    return os.path.join(BIBLE_DIR, f"{safe}_Bible.json")


def load_story_bible(title: str) -> Dict[str, Any]:
    """โหลด Story Bible ของเรื่อง ถ้ายังไม่มีจะสร้าง template เริ่มต้นให้"""
    fp = _bible_path(title)
    if os.path.exists(fp):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "title": title,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_chapter": 1,
        "world_rules": [],
        "characters": {},
        "timeline_events": [],
        "active_mysteries": [],
        "resolved_mysteries": []
    }


def save_story_bible(title: str, bible_data: Dict[str, Any]) -> str:
    """บันทึก Story Bible ลงไฟล์"""
    fp = _bible_path(title)
    bible_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(bible_data, f, ensure_ascii=False, indent=2)
    return fp


def update_bible_from_chapter(title: str, chapter_num: int, chapter_text: str):
    """วิเคราะห์และอัปเดต Story Bible หลังจบตอนใหม่"""
    try:
        from llm_provider import generate_json
    except ImportError:
        generate_json = None

    bible = load_story_bible(title)
    bible["current_chapter"] = max(bible.get("current_chapter", 1), chapter_num)

    if not generate_json:
        save_story_bible(title, bible)
        return bible

    prompt = f"""คุณคือ "Continuity Editor & Story Bible Master"
หน้าที่ของคุณคือ สกัดสถานะตัวละครและเหตุการณ์สำคัญจากบทที่ {chapter_num} ของเรื่อง "{title}"
เพื่อนำมาอัปเดตลง Story Bible ป้องกันข้อมูลขัดแย้งในตอนถัดไป

[เนื้อหาบทที่ {chapter_num}]:
{chapter_text[:3500]}

จงสกัดข้อมูลในรูปแบบ JSON:
{{
  "new_events": ["เหตุการณ์สำคัญ 1", "เหตุการณ์สำคัญ 2"],
  "character_updates": {{
    "ชื่อตัวละคร": "สถานะปัจจุบัน, สกิล/ไอเทมใหม่, หรือการเปลี่ยนแปลงอารมณ์"
  }},
  "new_mysteries": ["ปมปริศนาที่เพิ่งเปิดขึ้นมาใหม่"],
  "resolved_mysteries": ["ปมปริศนาที่คลี่คลายแล้วในบทนี้"]
}}
"""
    try:
        data = generate_json(prompt, role="analyzer")
        if isinstance(data, dict):
            for ev in data.get("new_events", []):
                bible["timeline_events"].append(f"[ตอนที่ {chapter_num}] {ev}")
            for ch_name, status in data.get("character_updates", {}).items():
                bible["characters"][ch_name] = status
            for m in data.get("new_mysteries", []):
                if m not in bible["active_mysteries"]:
                    bible["active_mysteries"].append(m)
            for rm in data.get("resolved_mysteries", []):
                if rm in bible["active_mysteries"]:
                    bible["active_mysteries"].remove(rm)
                bible["resolved_mysteries"].append(rm)
    except Exception as e:
        print(f"[!] Bible update error: {e}")

    save_story_bible(title, bible)
    return bible


def get_bible_context_prompt(title: str) -> str:
    """สร้าง Context ย่อสำหรับส่งให้ Writer Agent อ่านก่อนเริ่มเขียนตอนใหม่"""
    bible = load_story_bible(title)
    if not bible.get("timeline_events") and not bible.get("characters"):
        return ""

    lines = [f"\n[📖 Story Bible & ข้อมูลความต่อเนื่องของเรื่อง '{title}']"]
    if bible.get("characters"):
        lines.append("- **สถานะตัวละครล่าสุด:**")
        for c, st in bible["characters"].items():
            lines.append(f"  • {c}: {st}")
    if bible.get("timeline_events"):
        lines.append("- **ลำดับเหตุการณ์สำคัญที่ผ่านมา:**")
        for ev in bible["timeline_events"][-5:]:
            lines.append(f"  • {ev}")
    if bible.get("active_mysteries"):
        lines.append("- **ปมปริศนาที่ยังค้างคา (ห้ามลืม):**")
        for m in bible["active_mysteries"]:
            lines.append(f"  • {m}")
    return "\n".join(lines) + "\n"
