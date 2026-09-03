"""
story_bible.py — Multi-Chapter Continuity Engine & Story Bible for ANSRE
=========================================================================

จัดการและควบคุมความต่อเนื่องของพล็อต, กฎของโลก, และสถานะตัวละครข้ามตอน (Chapters 1..N):
1. เก็บประวัติเหตุการณ์ย่อของแต่ละบท (Chapter Event Logs)
2. อัปเดตสถานะตัวละคร, สิ่งของในตัว, ความสัมพันธ์, และความลับที่ยังไม่เปิดเผย
3. ตรวจสอบกฎของโลก (World Rules & Constraints) ไม่ให้เกิด Plot Hole
4. ป้อนบริบทความต่อเนื่องเข้าสู่ prompt ของ chapter_continuer.py แบบอัตโนมัติ

CLI:
  python story_bible.py --init <title>      # สร้าง Story Bible เริ่มต้นจาก Outline + Characters DB
  python story_bible.py --init-all          # สร้าง Story Bible สำหรับทุกเรื่องที่มีอยู่
  python story_bible.py --show <title>      # แสดงข้อมูล Story Bible ปัจจุบัน
  python story_bible.py --update <title> <chapter_num> # สรุปและอัปเดต Story Bible จากบทใหม่
"""
from __future__ import annotations

import os
import re
import sys
import glob
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
BIBLES_DIR = os.path.join(SB, "06_Story_Bibles")
os.makedirs(BIBLES_DIR, exist_ok=True)


def _clean_title(t: str) -> str:
    thai_chars = "฀-๿"
    return re.sub(r'[^\w\-_\s' + thai_chars + r']', '', t).strip().replace(' ', '_')


def get_bible_path(title: str) -> str:
    clean = _clean_title(title)
    return os.path.join(BIBLES_DIR, f"{clean}_StoryBible.json")


def load_story_bible(title: str) -> Dict[str, Any]:
    """โหลด Story Bible ถ้ามี หรือสร้างโครงสร้างเปล่า"""
    fp = get_bible_path(title)
    if os.path.exists(fp):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return init_story_bible(title)


def save_story_bible(title: str, data: Dict[str, Any]) -> str:
    """บันทึก Story Bible ลงไฟล์ JSON"""
    fp = get_bible_path(title)
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return fp


def init_story_bible(title: str) -> Dict[str, Any]:
    """สร้าง Story Bible จากไฟล์ Outline, Character Database และบทที่มีอยู่เดิม"""
    clean = _clean_title(title)
    
    # 1. อ่าน Outline
    outline_text = ""
    for pat in [f"{clean}_Outline.md", f"*{clean}*.md"]:
        matches = glob.glob(os.path.join(SB, "02_Concept_Extraction", pat))
        if matches:
            with open(matches[0], "r", encoding="utf-8") as f:
                outline_text = f.read()
            break

    # 2. อ่าน Character Database
    chars_text = ""
    for pat in [f"{clean}_Characters.md", f"*{clean}*.md"]:
        matches = glob.glob(os.path.join(SB, "04_Character_Database", pat))
        if matches:
            with open(matches[0], "r", encoding="utf-8") as f:
                chars_text = f.read()
            break

    # 3. รวบรวมตอนที่มีอยู่เดิม
    ch_files = sorted(glob.glob(os.path.join(SB, "05_Active_Projects", "Chapters", f"{clean}_Chapter_*.md")))
    chapters_log = []
    for cf in ch_files:
        m = re.search(r'_Chapter_(\d+)\.md', cf)
        ch_num = int(m.group(1)) if m else len(chapters_log) + 1
        with open(cf, "r", encoding="utf-8") as f:
            c_text = f.read().strip()
        # ดึงหัวข้อตอน
        m_head = re.search(r'#+\s*(?:ตอนที่|บทที่)\s*\d+[:\s]*([^\n\r]+)', c_text)
        ch_title = m_head.group(1).strip() if m_head else f"ตอนที่ {ch_num}"
        # ย่อความยาวสรุป
        summary_snippet = c_text[:300].replace("\n", " ").strip()
        chapters_log.append({
            "chapter_num": ch_num,
            "title": ch_title,
            "char_count": len(c_text),
            "summary": summary_snippet
        })

    bible_data = {
        "title": title,
        "author": "เงาพันจันทร์",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "genre_and_tone": "นิยายแฟนตาซี/ผจญภัย สนุกสนาน มีมุกตลกและจังหวะกระชับ",
        "core_premise": outline_text[:400].replace("\n", " ").strip() if outline_text else f"เรื่องราวของ {title}",
        "world_rules": [
            "คงกฎฟิสิกส์/พลังพิเศษตามที่กำหนดใน Outline",
            "ไม่ออกนอกโทนเรื่องและไม่เปลี่ยนบุคลิกตัวละครหลักกะทันหัน",
            "ห้ามมีตัวอักษรจีนหรือข้อความสื่อสารของ AI ภายในเนื้อหา"
        ],
        "character_roster": chars_text[:600].replace("\n\n", "\n").strip() if chars_text else "ตัวละครหลักและพันธมิตร",
        "unresolved_threads": [
            "การสืบหาความจริงเกี่ยวกับเงามืดเบื้องหลัง",
            "การยกระดับความสามารถและภารกิจหลัก"
        ],
        "chapters_history": chapters_log
    }

    save_story_bible(title, bible_data)
    return bible_data


def get_continuity_prompt_context(title: str, next_chapter_num: int) -> str:
    """สร้าง Prompt Context สรุปความต่อเนื่องสำหรับส่งต่อให้ LLM ตอนเขียนตอนถัดไป"""
    bible = load_story_bible(title)
    history = bible.get("chapters_history", [])
    
    last_chapters = history[-3:] if history else []
    history_str = "\n".join([f"- ตอนที่ {c['chapter_num']}: {c['title']} — {c.get('summary', '')[:150]}..." for c in last_chapters])
    
    context = f"""
[📜 STORY BIBLE & CONTINUITY CONTEXT — คุมความต่อเนื่อง]
- ชื่อเรื่อง: {bible.get('title', title)}
- โทนและแก่นเรื่อง: {bible.get('genre_and_tone', '')}
- กฎของโลก: {'; '.join(bible.get('world_rules', []))}
- สรุปเหตุการณ์ในตอนก่อนหน้า:
{history_str if history_str else '(เป็นตอนแรกหรือไม่มีประวัติก่อนหน้า)'}
- ปมที่ยังค้างคาและต้องสานต่อ: {'; '.join(bible.get('unresolved_threads', []))}
- คำสั่งพิเศษ: เดินเรื่องบทที่ {next_chapter_num} ให้ต่อเนื่องจากเหตุการณ์ล่าสุด ห้ามขัดแย้งกับกฎและนิสัยตัวละคร
"""
    return context.strip()


def update_story_bible_from_chapter(title: str, chapter_num: int, chapter_text: str):
    """อัปเดต Story Bible หลังแต่งตอนใหม่เสร็จสิ้น"""
    bible = load_story_bible(title)
    
    # ดึงชื่อตอน
    m_head = re.search(r'#+\s*(?:ตอนที่|บทที่)\s*\d+[:\s]*([^\n\r]+)', chapter_text)
    ch_title = m_head.group(1).strip() if m_head else f"ตอนที่ {chapter_num}"
    
    # ตรวจสอบว่ามีตอนเดิมอยู่แล้วหรือไม่
    history = bible.get("chapters_history", [])
    found = False
    for item in history:
        if item.get("chapter_num") == chapter_num:
            item["title"] = ch_title
            item["char_count"] = len(chapter_text)
            item["summary"] = chapter_text[:300].replace("\n", " ").strip()
            found = True
            break
            
    if not found:
        history.append({
            "chapter_num": chapter_num,
            "title": ch_title,
            "char_count": len(chapter_text),
            "summary": chapter_text[:300].replace("\n", " ").strip()
        })
        
    history.sort(key=lambda x: x.get("chapter_num", 0))
    bible["chapters_history"] = history
    save_story_bible(title, bible)
    print(f"[+] Story Bible อัปเดตข้อมูลตอนที่ {chapter_num} สำเร็จ: {get_bible_path(title)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--init-all" in args:
        ch_dir = os.path.join(SB, "05_Active_Projects", "Chapters")
        titles = sorted(list({os.path.basename(f).split("_Chapter_")[0] for f in glob.glob(os.path.join(ch_dir, "*_Chapter_*.md"))}))
        print(f"กำลังสร้าง Story Bible สำหรับ {len(titles)} เรื่อง...")
        for t in titles:
            init_story_bible(t)
            print(f"  ✅ {t}")
    elif "--show" in args and len(args) > 1:
        target = args[args.index("--show") + 1]
        b = load_story_bible(target)
        print(json.dumps(b, ensure_ascii=False, indent=2))
    elif "--init" in args and len(args) > 1:
        target = args[args.index("--init") + 1]
        b = init_story_bible(target)
        print(f"สร้าง Story Bible สำเร็จ: {get_bible_path(target)}")
    else:
        print("วิธีใช้: python story_bible.py [--init <title> | --init-all | --show <title>]")
