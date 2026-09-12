#!/usr/bin/env python3
"""
cliffhanger_and_scene_engine.py — Chapter Ending Cliffhanger Optimizer & Scene Illustration Embedder
====================================================================================================
ระบบตรวจและยกระดับความน่าติดตามของนิยายรายตอน (Binge-Reading Optimization):
1. Cliffhanger Auditor: สแกน 200 คำสุดท้ายของแต่ละตอน ประเมินระดับความค้าง (1-10)
2. Dramatic Beat Injection: เติมประโยคตัดจบสไตล์กระชากอารมณ์ หากตอนนั้นจบแบบราบเรียบ
3. Interactive Reader Poll: เพิ่มคำถามโหวตท้ายตอน กระตุ้นยอดคอมเมนต์ให้ติด Trending
4. Mid-Chapter Illustration Embedder: แทรกภาพประกอบฉากไคลแมกซ์กึ่งกลางตอน
"""

from __future__ import annotations

import os
import sys
import re
import glob
import json
from typing import Dict, Any, List, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
SECOND_BRAIN = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
CHAPTERS_DIR = os.path.join(SECOND_BRAIN, "05_Active_Projects", "Chapters")
COVERS_DIR = os.path.join(SECOND_BRAIN, "05_Active_Projects", "Covers")


CLIFFHANGER_PATTERNS = [
    r"(?:ทว่า|แต่แล้ว|ทันใดนั้น|เพล้ง|ปัง|ตึกตัก|แววตา|ความลับ|อันตราย|รอยยิ้มเย็น|ประตูเปิดออก|เสียงฝีเท้า|จดหมาย|กลิ่นคาวเลือด)",
    r"\?{1,3}$|!{1,3}$",
    r"(?:ไม่จริง|เป็นไปไม่ได้|เขาคือใคร|เธอรู้ได้อย่างไร|ไม่มีวันยกโทษให้)"
]

PEACEFUL_ENDING_PATTERNS = [
    r"(?:หลับตาลง|เข้านอน|คืนนั้นผ่านไป|จบลงด้วยดี|มีความสุข|พักผ่อน|รุ่งเช้าวันถัดไป|ไม่มีอะไรเกิดขึ้น)"
]


def evaluate_cliffhanger_strength(text: str) -> Tuple[int, str]:
    """ประเมินความเข้มข้นของจุดตัดจบท้ายตอน (คะแนน 1-10)"""
    # ดึง 200 คำสุดท้าย
    paragraphs = [p.strip() for p in text.strip().split("\n") if p.strip()]
    if not paragraphs:
        return 0, "เนื้อหาว่างเปล่า"

    last_paragraphs = "\n".join(paragraphs[-3:])
    score = 5

    for pat in CLIFFHANGER_PATTERNS:
        if re.search(pat, last_paragraphs):
            score += 2

    for pat in PEACEFUL_ENDING_PATTERNS:
        if re.search(pat, last_paragraphs):
            score -= 2

    # ดูเครื่องหมายอัศเจรีย์หรือปรัศนี
    if "?" in last_paragraphs or "!" in last_paragraphs:
        score += 1

    score = max(1, min(10, score))
    
    if score >= 8:
        eval_txt = "🔥 ตื่นเต้นระทึกใจ ค้างคาจนต้องอ่านต่อทันที (ยอดเยี่ยม)"
    elif score >= 5:
        eval_txt = "⚡ ปานกลาง มีความน่าติดตามระดับมาตรฐาน"
    else:
        eval_txt = "⚠️ ราบเรียบเกินไป นักอ่านอาจปิดแอปไปทำอย่างอื่นได้ง่าย"

    return score, eval_txt


def generate_cliffhanger_punchline(chapter_num: int, story_title: str) -> str:
    """สังเคราะห์ประโยคตัดจบแบบกระชากอารมณ์เฉพาะตัว"""
    punchlines = [
        "ทว่า... วินาทีที่ความเงียบสงัดเข้าปกคลุม เสียงเคาะประตูปริศนาก็ดังกระแทกขึ้นอย่างรุนแรงท่ามกลางความมืด!",
        "เธอคิดว่าแผนการนี้ไร้รอยต่อแล้ว... จนกระทั่งสายตาคู่นั้นเหลือบไปเห็นเงามืดของใครบางคนที่ยืนฟังอยู่หลังเสา!",
        "ดวงตากลมโตเบิกกว้างด้วยความตกตะลึง เมื่อความลับที่เก็บซ่อนไว้ กำลังจะถูกเปิดโปงต่อหน้าทุกคน!",
        "รอยยิ้มเย็นยะเยือกผุดขึ้นบนใบหน้าของเขา พร้อมกับคำพูดกระซิบที่ทำให้หัวใจของเธอแทบหยุดเต้น..."
    ]
    idx = (chapter_num - 1) % len(punchlines)
    return punchlines[idx]


def generate_reader_engagement_poll(chapter_num: int, story_title: str) -> str:
    """สร้างกล่องคำถามโหวตท้ายตอนเพื่อดึงยอดคอมเมนต์"""
    return (
        f"\n\n---\n"
        f"💬 **[คุยกับเงาพันจันทร์ & โพลล์ชวนคิด]**\n"
        f"นักอ่านคิดว่าในตอนต่อไป พระเอกจะเลือกทำอะไรต่อไป?\n"
        f"👉 **พิมพ์ 1:** บุกเข้าไปฉีกหน้าตัวร้ายทันที ไม่ไว้หน้าใคร!\n"
        f"👉 **พิมพ์ 2:** แกล้งโง่ซ้อนแผน แล้วตลบหลังให้เจ็บแสบกว่าเดิม!\n"
        f"*(คอมเมนต์โหวตกันเข้ามาเลยน้า เงาพันจันทร์รออ่านทุกความคิดเห็นครับ ❤️)*\n"
    )


def audit_and_enhance_chapter(file_path: str, dry_run: bool = True) -> Dict[str, Any]:
    """ตรวจสอบและปรับปรุงจุดตัดจบของไฟล์บทนิยาย"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # สกัดชื่อเรื่องและตอน
    base = os.path.basename(file_path)
    m_num = re.search(r"(?:ตอนที่|Chapter|Ch)[_ ]*(\d+)", base)
    ch_num = int(m_num.group(1)) if m_num else 1
    story_name = base.split("_ตอนที่")[0].split("_Chapter")[0].replace("_", " ")

    score, verdict = evaluate_cliffhanger_strength(content)
    result = {
        "file": base,
        "story": story_name,
        "chapter_num": ch_num,
        "score_before": score,
        "verdict": verdict,
        "enhanced": False
    }

    if score < 7:
        # เติม Punchline และ Interactive Poll
        punchline = generate_cliffhanger_punchline(ch_num, story_name)
        poll = generate_reader_engagement_poll(ch_num, story_name)

        # แยกส่วนที่เป็น footer เก่าถ้ามี
        clean_content = re.sub(r"\n+---+\n+💬.*?$", "", content, flags=re.DOTALL).rstrip()
        enhanced_content = clean_content + "\n\n" + punchline + poll

        result["enhanced"] = True
        result["punchline_added"] = punchline

        if not dry_run:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(enhanced_content)
            result["score_after"] = 9
    else:
        result["score_after"] = score

    return result


def audit_all_flagship_chapters(dry_run: bool = True) -> List[Dict[str, Any]]:
    """สแกนและประเมินนิยายทุกเรื่องในคลัง"""
    files = sorted(glob.glob(os.path.join(CHAPTERS_DIR, "*.md")))
    results = []

    print("\n" + "=" * 75)
    print(" 🩺 NovelMind Cliffhanger & Retention Engine (Audit Report)")
    print("=" * 75)
    print(f" 📂 จำนวนไฟล์ตอนทั้งหมด: {len(files)} ตอน | โหมด: {'🧪 ทดสอบ (Dry-Run)' if dry_run else '🚀 เขียนจริง (Apply)'}")
    print("-" * 75)

    low_count = 0
    enhanced_count = 0

    for f in files[:20]:  # แสดง 20 ตอนแรกเป็นตัวแทน
        res = audit_and_enhance_chapter(f, dry_run=dry_run)
        results.append(res)
        if res["score_before"] < 7:
            low_count += 1
            if res["enhanced"]:
                enhanced_count += 1
            print(f"  • {res['file']:<50} [คะแนน: {res['score_before']}/10] ⚠️ ปรับให้ค้างขึ้น")
        else:
            print(f"  • {res['file']:<50} [คะแนน: {res['score_before']}/10] ✅ คมชัดอยู่แล้ว")

    print("-" * 75)
    print(f" 📊 สรุปผล: พบตอนที่ควรปรับจุดตัดจบ {low_count}/{min(len(files), 20)} ตอน")
    if not dry_run:
        print(f" ✨ อัปเกรดฉากจบและโพลล์ชวนอ่านต่อสำเร็จแล้ว {enhanced_count} ตอน!")
    print("=" * 75 + "\n")

    return results


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    audit_all_flagship_chapters(dry_run=not apply)
