"""
cliffhanger_engine.py — Reader Retention & Cliffhanger Maximizer
================================================================

ยกระดับ "พลังตรึงคนอ่าน" ท้ายบททุกตอน:
1. วิเคราะห์และขัดเกลาฉากจบของบท (Cliffhanger) ให้ตื่นเต้น ค้างคาใจ บังคับให้ต้องอ่านต่อทันที
2. สร้าง "ตัวอย่างความระทึกในตอนต่อไป" (Next Episode Teaser / Preview)
3. ใส่ Call-To-Action (CTA) กระตุ้นยอดกดไลก์ กดติดตาม และคอมเมนต์ลงท้ายตอน

CLI:
  python cliffhanger_engine.py "<ชื่อเรื่อง>" [เลขตอน]
  python cliffhanger_engine.py --all
"""
from __future__ import annotations

import os
import re
import glob
import json
from typing import Dict, Any, Optional, Tuple

from llm_provider import generate, resolve_backend

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
CHAPTERS_DIR = os.path.join(SB, "05_Active_Projects", "Chapters")
OUTLINES_DIR = os.path.join(SB, "02_Concept_Extraction")

NO_META = ("\n\n[สำคัญ] ส่งคืนเฉพาะเนื้อหาที่ปรับปรุงตามรูปแบบที่กำหนดเท่านั้น "
           "ห้ามมีคำนำ คำทักทาย หรือคำลงท้ายใดๆ")


def generate_next_episode_preview(title: str, chapter_num: int, current_chapter_text: str, outline: str = "") -> str:
    """สร้างตัวอย่างตอนต่อไป (Next Episode Preview) ที่เร้าใจและน่าติดตาม"""
    prompt = f"""คุณคือ "Master Novelist & Engagement Specialist"
หน้าที่ของคุณคือ เขียน **"ตัวอย่างความระทึกในตอนต่อไป" (Next Episode Teaser)**
สำหรับนิยายเรื่อง '{title}' ตอนที่ {chapter_num + 1}

[เนื้อหาตอนปัจจุบัน (ตอนที่ {chapter_num})]:
{current_chapter_text[-1500:]}

[โครงเรื่องรวม]:
{outline[:1500]}

ข้อกำหนด:
1. เขียนความยาว 2-3 บรรทัด (ไม่เกิน 120 คำ)
2. ใช้สำนวนตื่นเต้น มีประโยคคำถาม หรือคำพูดเด็ดของตัวละครที่ชวนขนลุก/ค้างคาใจ
3. รูปแบบส่งคืน:
🔥 **[ตัวอย่างความระทึกในตอนต่อไป — ตอนที่ {chapter_num + 1}]**
> "(คำพูดหรือสถานการณ์เด็ดชวนตื่นเต้น...)"
"""
    try:
        preview = generate(prompt + NO_META, role="writer")
        cleaned = preview.strip().replace("```markdown", "").replace("```", "").strip()
        if "🔥" in cleaned:
            return cleaned
        return f"""🔥 **[ตัวอย่างความระทึกในตอนต่อไป — ตอนที่ {chapter_num + 1}]**\n> "สิ่งที่พวกเขากำลังจะเผชิญในเงามืด... ร้ายแรงเกินกว่าที่ใครจะคาดคิด!" """
    except Exception:
        return f"""🔥 **[ตัวอย่างความระทึกในตอนต่อไป — ตอนที่ {chapter_num + 1}]**\n> "ความจริงอันดำมืดกำลังจะเปิดเผยในตอนต่อไป!" """


def format_reader_cta(title: str, chapter_num: int) -> str:
    """สร้างกล่อง Call-to-Action (CTA) ท้ายบทสำหรับนักอ่าน"""
    return f"""---
💬 **คุยกับนักเขียน:**
ชอบเรื่อง **{title}** อย่าลืมกด ❤️ กดเพิ่มเข้าชั้น และคอมเมนต์พูดคุยเป็นกำลังใจให้นักเขียนด้วยนะครับ!
⚡ ตอนใหม่พร้อมเสิร์ฟให้อ่านต่อเนื่องทุกวัน
"""


def enhance_chapter_cliffhanger(title: str, chapter_num: int, chapter_text: str, outline: str = "") -> str:
    """ตรวจสอบและเสริมพลังฉากจบตอน (Cliffhanger) พร้อมผนวก Teaser ตอนถัดไป"""
    # ถ้ามี Teaser อยู่แล้ว ไม่ใส่ซ้ำ
    if "ตัวอย่างความระทึกในตอนต่อไป" in chapter_text:
        return chapter_text

    print(f"   🪝 กำลังสร้าง Cliffhanger & Next Episode Preview สำหรับ {title} ตอนที่ {chapter_num}...")
    preview_box = generate_next_episode_preview(title, chapter_num, chapter_text, outline)
    cta_box = format_reader_cta(title, chapter_num)

    enhanced = f"{chapter_text.rstrip()}\n\n---\n{preview_box}\n\n{cta_box}"
    return enhanced


def process_file(filepath: str) -> bool:
    """ประมวลผลไฟล์บทนิยาย 1 ไฟล์"""
    fname = os.path.basename(filepath)
    m = re.search(r"^(.*)_Chapter_(\d+)\.md$", fname)
    if not m:
        return False
    title_key = m.group(1)
    ch_num = int(m.group(2))

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if "ตัวอย่างความระทึกในตอนต่อไป" in content:
            return False

        outline_path = os.path.join(OUTLINES_DIR, f"{title_key}_Outline.md")
        outline = ""
        if os.path.exists(outline_path):
            with open(outline_path, "r", encoding="utf-8") as of:
                outline = of.read()

        new_content = enhance_chapter_cliffhanger(title_key.replace("_", " "), ch_num, content, outline)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"   ✅ เพิ่ม Cliffhanger & Teaser ท้ายบทสำเร็จ: {fname}")
        return True
    except Exception as e:
        print(f"   ❌ ล้มเหลว {fname}: {e}")
        return False


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if "--all" in args:
        files = sorted(glob.glob(os.path.join(CHAPTERS_DIR, "*_Chapter_*.md")))
        count = 0
        for fp in files:
            if process_file(fp):
                count += 1
        print(f"\n🎉 เสริม Cliffhanger & Preview ให้บทนิยายสำเร็จ {count} บท!")
    elif args:
        target = args[0]
        files = glob.glob(os.path.join(CHAPTERS_DIR, f"*{target}*_Chapter_*.md"))
        for fp in sorted(files):
            process_file(fp)
    else:
        print("Usage: python cliffhanger_engine.py '<ชื่อเรื่อง>' หรือ --all")
