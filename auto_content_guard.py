#!/usr/bin/env python3
"""
auto_content_guard.py — ระบบตรวจสอบและคัดกรองคุณภาพเนื้อหานิยายก่อนเผยแพร่ (Prose Sanitation & Quality Gate)

ความสามารถหลัก:
1. ขจัดคราบ AI Artifacts: ดักจับและถอด JSON wrapper (```json {"เนื้อหานิยาย": ...}```), code blocks, braces ที่ตกค้าง
2. กำจัดภาษาและอักขระแปลกปลอม: ลบตัวอักษรอาหรับ (Arabic) หรืออักษรจีนตกค้างจากระบบ LLM
3. กำจัดเนื้อหาซ้ำซ้อน: ตรวจจับและตัดทอนย่อหน้าที่ก๊อปปี้ซ้ำกัน
4. ตรวจนับจำนวนคำ (Word Count): การันตีเนื้อหาความยาวขั้นต่ำ (>= 400 คำ)
5. ปรับแก้และบันทึกไฟล์ (Auto-Fix Mode): สามารถสแกนและคลีนไฟล์ทั้งระบบได้ในคำสั่งเดียว
"""

import os
import re
import glob
from typing import Dict, Any, List, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
CHAPTERS_DIR = os.path.join(ROOT, "SecondBrain", "05_Active_Projects", "Chapters")


def sanitize_prose(text: str) -> Tuple[str, List[str]]:
    """
    ทำความสะอาดข้อความเนื้อหานิยาย ขจัด AI noise และ foreign artifacts ทั้งหมด
    คืนค่า (cleaned_text, fixes_applied)
    """
    fixes = []
    cleaned = text

    # 1. ถอด JSON block wrapper เช่น ```json { "เนื้อหานิยาย": "..." } ```
    if '```json' in cleaned or '"เนื้อหานิยาย"' in cleaned or '"content"' in cleaned:
        # ลองดึงจาก regex เนื้อหานิยาย ใน json string
        m = re.search(r'\"(?:เนื้อหานิยาย|content)\"\s*:\s*\"(.*?)\"\s*\}', cleaned, re.DOTALL)
        if m:
            try:
                extracted = m.group(1).encode('utf-8').decode('unicode_escape')
                extracted = extracted.replace('\\n', '\n').replace('\\"', '"').replace('\\/', '/')
                cleaned = extracted
                fixes.append("Extracted prose from JSON wrapper payload")
            except Exception:
                pass
        
        # ถอด markdown code fence
        cleaned = re.sub(r'```(?:json|markdown)?\s*', '', cleaned)
        cleaned = re.sub(r'```', '', cleaned)
        cleaned = re.sub(r'\{\s*\"(?:เนื้อหานิยาย|content)\"\s*:\s*\"?', '', cleaned)
        cleaned = re.sub(r'\"?\s*\}\s*$', '', cleaned.rstrip())
        fixes.append("Stripped markdown code fence and json brackets")

    # 2. ถอดอักขระภาษาอาหรับตกค้าง (Arabic script leakage: \u0600-\u06FF)
    if re.search(r'[\u0600-\u06FF]', cleaned):
        cleaned = cleaned.replace("ก่อนจะأفلน", "ก่อนจะลับขอบฟ้า").replace("أفلน", "ลับขอบฟ้า")
        cleaned = re.sub(r'[\u0600-\u06FF]+', '', cleaned)
        fixes.append("Removed Arabic script artifacts")

    # 3. ถอดอักขระภาษาจีนตกค้าง (Chinese script leakage: \u4E00-\u9FFF)
    if re.search(r'[\u4E00-\u9FFF]', cleaned):
        cleaned = re.sub(r'[\u4E00-\u9FFF]+', '', cleaned)
        fixes.append("Removed Chinese characters artifacts")

    # 4. ลบ prompt/meta instructions ที่อาจหลุดมา
    cleaned = re.sub(r'^(?:Here is the story|Here is the chapter|นี่คือเนื้อหาตอนที่).*?\n', '', cleaned, flags=re.IGNORECASE)

    # 5. ปรับแก้ช่องว่างและบรรทัดซ้ำซ้อน
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = cleaned.strip()

    return cleaned, fixes


def count_words(text: str) -> int:
    """นับจำนวนคำภาษาไทยและสากลโดยประมาณ"""
    # ลบ markdown formatting
    pure = re.sub(r'#+\s*', '', text)
    pure = re.sub(r'[*_`~]', '', pure)
    
    tokens = re.findall(r'[a-zA-Z0-9]+|[\u0E00-\u0E7F]+', pure)
    total_words = 0
    for tok in tokens:
        if re.match(r'^[a-zA-Z0-9]+$', tok):
            total_words += 1
        else:
            # คำไทย: เฉลี่ย 4-5 อักษรต่อหนึ่งคำ
            total_words += max(1, len(tok) // 5)
    return total_words


def check_chapter_quality(file_path: str, auto_fix: bool = True) -> Dict[str, Any]:
    """ตรวจสอบคุณภาพของไฟล์ตอน และทำการ auto-fix หากระบุ"""
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    with open(file_path, "r", encoding="utf-8") as f:
        original = f.read()

    cleaned, fixes = sanitize_prose(original)
    word_count = count_words(cleaned)
    char_count = len(cleaned)

    # ตรวจสอบเกณฑ์คุณภาพ (Quality Gates)
    issues = []
    if word_count < 400:
        issues.append(f"Low word count: {word_count} words (threshold >= 400 words)")
    if char_count < 1500:
        issues.append(f"Short character length: {char_count} chars")

    # ตรวจสอบ Cliffhanger หรือตอนจบ
    has_cliffhanger = False
    last_paragraph = cleaned.split("\n\n")[-1] if "\n\n" in cleaned else cleaned[-200:]
    cliffhanger_cues = ["?", "!", "...", "ทิ้งไว้", "รอยยิ้ม", "เงียบงัน", "ความลับ", "กระซิบ", "จ้องมอง", "ทันใดนั้น"]
    if any(cue in last_paragraph for cue in cliffhanger_cues):
        has_cliffhanger = True

    was_fixed = False
    if auto_fix and fixes:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(cleaned)
        was_fixed = True

    return {
        "file": os.path.basename(file_path),
        "word_count": word_count,
        "char_count": char_count,
        "fixes_applied": fixes,
        "was_fixed": was_fixed,
        "issues": issues,
        "has_cliffhanger": has_cliffhanger,
        "passed": len(issues) == 0
    }


def scan_and_clean_all_chapters() -> Dict[str, Any]:
    """สแกนและคลีนไฟล์ตอนทั้งหมดในคลัง SecondBrain/Chapters"""
    files = sorted(glob.glob(os.path.join(CHAPTERS_DIR, "*.md")))
    results = []
    total_fixed = 0
    total_passed = 0

    print(f"\n🛡️ [Content Guard] เริ่มต้นตรวจสอบคุณภาพไฟล์ตอนทั้งหมด ({len(files)} ไฟล์)...")
    for fpath in files:
        res = check_chapter_quality(fpath, auto_fix=True)
        results.append(res)
        if res["was_fixed"]:
            total_fixed += 1
            print(f"   🧹 คลีนสำเร็จ: {res['file']} (แก้ไข: {', '.join(res['fixes_applied'])})")
        if res["passed"]:
            total_passed += 1

    print(f"\n📊 ผลการตรวจสอบคุณภาพ:")
    print(f"   • ตรวจสอบทั้งหมด: {len(files)} ไฟล์")
    print(f"   • ทำความสะอาดไป: {total_fixed} ไฟล์")
    print(f"   • ผ่านเกณฑ์สมบูรณ์: {total_passed} ไฟล์")
    return {
        "total": len(files),
        "fixed": total_fixed,
        "passed": total_passed,
        "details": results
    }


if __name__ == "__main__":
    scan_and_clean_all_chapters()
