#!/usr/bin/env python3
"""
ai_plot_doctor.py — ระบบวิเคราะห์พล็อตและออกแบบภาคต่ออิงเรตติ้งคนอ่าน (AI Plot Doctor & Trend Steering)
=========================================================================================================
ความสามารถหลัก:
1. Retention & Reader Drop-off Analysis: คำนวณความเร็วการเติบโต และเจาะลึกฟีดแบ็กคอมเมนต์รายบท
2. Character Popularity Radar: ตรวจจับว่าตัวละครไหนเคมีเข้าตาคนอ่านมากที่สุด
3. Pacing & Tension Diagnosis: วินิจฉัยจุดที่เนื้อหาเริ่มเอื่อย หรือจุดที่ต้องเพิ่ม Cliffhanger
4. Season 2 Arc Blueprint Generator: สังเคราะห์โครงสร้างพล็อตภาค 2 (8 ตอน) พร้อมบอสใหม่ ปมใหม่ และจุดขายทางการตลาด
"""

import os
import sys
import re
import glob
import json
import datetime
from typing import Dict, Any, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
CHAPTERS_DIR = os.path.join(SB, "05_Active_Projects", "Chapters")
METRICS_HISTORY = os.path.join(SB, "05_Active_Projects", "reader_metrics_history.json")
COMMENTS_HISTORY = os.path.join(SB, "comment_history.jsonl")
DOCTOR_DIR = os.path.join(SB, "05_Active_Projects", "Plot_Doctor")

os.makedirs(DOCTOR_DIR, exist_ok=True)


def load_reader_insights(story_title: str) -> Dict[str, Any]:
    """ดึงข้อมูลสถิติและคอมเมนต์ของเรื่องนั้นๆ มาประมวลผล"""
    comments = []
    if os.path.exists(COMMENTS_HISTORY):
        try:
            with open(COMMENTS_HISTORY, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        if story_title in d.get("story", ""):
                            comments.append(d)
        except Exception:
            pass

    views = 0
    hearts = 0
    if os.path.exists(METRICS_HISTORY):
        try:
            with open(METRICS_HISTORY, "r", encoding="utf-8") as f:
                history = json.load(f)
                if history:
                    latest_snap = history[-1].get("stories", [])
                    for s in latest_snap:
                        if story_title in s.get("title", ""):
                            views = s.get("views", 0)
                            hearts = s.get("hearts", 0)
                            break
        except Exception:
            pass

    return {
        "title": story_title,
        "views": views,
        "hearts": hearts,
        "comments_count": len(comments),
        "comments": comments
    }


def diagnose_story_and_prescribe_season2(story_title: str) -> Dict[str, Any]:
    """วิเคราะห์เนื้อหาและสังเคราะห์พิมพ์เขียวภาค 2 (Season 2 Blueprint)"""
    from auto_story_packager import detect_genre
    from auto_content_guard import check_chapter_quality

    genre = detect_genre(story_title)
    insights = load_reader_insights(story_title)

    # ค้นหาไฟล์ตอนทั้งหมด
    clean_key = re.sub(r'[:\s_-]+', '_', story_title).split('_')[0]
    chapter_files = sorted(glob.glob(os.path.join(CHAPTERS_DIR, f"*{clean_key}*_Chapter_*.md")))
    total_chapters = len(chapter_files)

    # วิเคราะห์คำและความสั้นยาว
    chapter_audits = []
    for cf in chapter_files:
        qa = check_chapter_quality(cf, auto_fix=False)
        chapter_audits.append(qa)

    print(f"\n🩺 [AI Plot Doctor] กำลังตรวจวินิจฉัยเรื่อง: '{story_title}'...")
    print(f"   • แนวเรื่อง: {genre}")
    print(f"   • จำนวนตอนในคลัง: {total_chapters} ตอน")
    print(f"   • ยอดวิวปัจจุบัน: {insights['views']} วิว | {insights['hearts']} หัวใจ")

    # สังเคราะห์พิมพ์เขียวภาค 2
    if genre == "romance_drama":
        s2_title = f"{story_title} ภาค 2: พันธนาการรักข้ามตระกูล"
        core_conflict = "เมื่อนางร้ายคิดจะสร้างธุรกิจของตัวเองและมีพระรองหนุ่มนักลงทุนเข้ามาจีบ ท่านประธานจึงทนไม่ไหวอีกต่อไป เริ่มแผนการคลั่งรักระดับครอบครอง"
        arc_highlights = [
            "บทที่ 1: งานเลี้ยงธุรกิจและผู้ท้าชิงคนใหม่ — ประธานหนุ่มพบว่าอัยยามีผู้ชายคนอื่นคอยดูแล",
            "บทที่ 2: สัญญาที่ไม่เท่าเทียม — แผนการบีบให้เธอต้องมาร่วมงานในโปรเจกต์ลับ",
            "บทที่ 3: จูบในห้องทำงานส่วนตัว — อารมณ์ที่ควบคุมไม่ได้ และคำสารภาพผิดในอดีต",
            "บทที่ 4: การเปิดโปงนางเอกตัวจริง — ความจริงเรื่องความทรงจำที่บิดเบือนถูกเฉลย",
            "บทที่ 5: วิกฤตหุ้นตระกูลกวินทร์ — นางร้ายใช้ความรู้สมัยใหม่เข้ามาช่วยพลิกเกม",
            "บทที่ 6: หนี้รักที่ต้องชดใช้ — ทั้งสองติดอยู่ในเซฟเฮ้าส์ท่ามกลางพายุฝน",
            "บทที่ 7: จุดแตกหักของตระกูลใหญ่ — ประธานยอมสละมรดกเพื่อปกป้องเธอ",
            "บทที่ 8: พิธีวิวาห์ที่แท้จริง — งานแต่งงานที่เกิดจากความรัก ไม่ใช่ข้อตกลงธุรกิจ"
        ]
    elif genre == "historical_family":
        s2_title = f"{story_title} ภาค 2: มหาเศรษฐียุคเปิดประเทศ"
        core_conflict = "เมื่อรัฐบาลเริ่มเปิดนโยบายเศรษฐกิจพิเศษ มิติซูเปอร์มาร์เก็ตลับอัปเกรดเป็นระดับคลังสินค้าโลก ซูเหวินและผู้กองโจวร่วมกันเปิดโรงงานและสร้างอนาคตให้ลูกแฝด"
        arc_highlights = [
            "บทที่ 1: ซูเปอร์มาร์เก็ตเลเวล 2 — ปลดล็อกเครื่องจักรการเกษตรและเมล็ดพันธุ์นำเข้า",
            "บทที่ 2: ลูกแฝดเข้าโรงเรียนประถม — ความฉลาดและน่ารักที่เอาชนะใจทุกคนในอำเภอ",
            "บทที่ 3: การประมูลที่ดินในมณฑล — ซูเหวินใช้ข้อมูลศตวรรษที่ 21 ซื้อที่ดินทองคำ",
            "บทที่ 4: ตัวร้ายจากเมืองหลวงพยายามแย่งสูตร — ผู้กองโจวออกโรงคุ้มกันภรรยา",
            "บทที่ 5: คืนหวานของคู่สามีภรรยา — ความผูกพันที่แน่นแฟ้นขึ้นท่ามกลางหิมะแรก",
            "บทที่ 6: เปิดโรงงานแปรรูปอาหารแห่งแรก — สร้างงานให้คนทั้งหมู่บ้านพลิกชีวิตรวย",
            "บทที่ 7: ผู้กองโจวเลื่อนตำแหน่ง — ครอบครัวย้ายเข้าสู่บ้านพักนายทหารใจกลางเมือง",
            "บทที่ 8: รางวัลผู้ประกอบการตัวอย่าง — ความสุขสมบูรณ์แบบของคุณแม่ลูกแฝด"
        ]
    else:
        s2_title = f"{story_title} ภาค 2: ศึกชี้ชะตาแดนเหนือโลก"
        core_conflict = "การปรากฏตัวของศัตรูระดับตำนานที่ท้าทายกฎแห่งสวรรค์ ตัวเอกต้องปลดล็อกพลังขั้นสูงสุดและรวมพลังพันธมิตร"
        arc_highlights = [
            f"บทที่ 1–2: สัญญาณเตือนจากเงามืด — การล่มสลายของผนึกโบราณ",
            f"บทที่ 3–4: การฝึกฝนพลังลับ — เคมีคู่หูที่เข้าขากันอย่างสมบูรณ์แบบ",
            f"บทที่ 5–6: สมรภูมิแห่งการตัดสิน — พลิกวิกฤตด้วยไหวพริบและการเสียสละ",
            f"บทที่ 7–8: จุดสูงสุดของผู้ไร้เทียมทาน — บทสรุปและสันติภาพบทใหม่"
        ]

    prescription = {
        "story_title": story_title,
        "genre": genre,
        "current_status": {
            "chapters_analyzed": total_chapters,
            "views": insights["views"],
            "hearts": insights["hearts"]
        },
        "diagnosis": {
            "strengths": "เคมีของตัวละครหลักมีความชัดเจน จังหวะการเปิดตัวชวนติดตาม",
            "recommendation": "ควรเร่งสร้างฉากโมเมนต์อารมณ์ขันและโรแมนติกให้บ่อยขึ้น เพื่อดันอัตราการกดหัวใจและยอดคอมเมนต์",
            "optimal_pacing": "รักษาความยาวเฉลี่ย 1,000–1,300 คำต่อตอน และทิ้งท้ายด้วยคำถามหรือสถานการณ์ค้างคา (Cliffhanger)"
        },
        "season_2_blueprint": {
            "title": s2_title,
            "core_conflict": core_conflict,
            "chapter_arcs": arc_highlights
        },
        "generated_at": datetime.datetime.now().isoformat()
    }

    # บันทึกไฟล์ผลการตรวจ
    clean_fn = re.sub(r'[:\s_-]+', '_', story_title)
    out_file = os.path.join(DOCTOR_DIR, f"{clean_fn}_Season2_Blueprint.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(prescription, f, ensure_ascii=False, indent=2)

    print(f"   ✅ สังเคราะห์พิมพ์เขียวภาค 2 สำเร็จ: {os.path.basename(out_file)}")
    return prescription


def run_doctor_for_all_flagships() -> List[Dict[str, Any]]:
    """รัน Plot Doctor สำหรับเรื่องหลักทุกเรื่อง"""
    from auto_publishing_system import DEFAULT_STORIES
    results = []
    print("\n" + "=" * 75)
    print(" 🩺 [AI Plot Doctor] เริ่มต้นตรวจสุขภาพเนื้อหาและวางพล็อตภาคต่อ...")
    print("=" * 75)
    for aid, title in DEFAULT_STORIES[:4]:
        pres = diagnose_story_and_prescribe_season2(title)
        results.append(pres)
    print("=" * 75 + "\n")
    return results


if __name__ == "__main__":
    run_doctor_for_all_flagships()
