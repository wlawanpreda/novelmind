#!/usr/bin/env python3
"""batch_repair_audioscripts.py — Auto-repair empty or broken AudioScripts from Chapters.

Scans all AudioScripts in SecondBrain/05_Active_Projects/Audio_Scripts.
If an AudioScript is empty or says "[ไม่สามารถสร้างบทเสียงได้]", it automatically
recovers the rich prose from the corresponding Chapter file in Chapters/,
formats it into clean audiobook script tags, and saves it.

Usage:
  venv/bin/python batch_repair_audioscripts.py
"""
from __future__ import annotations

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
AS_DIR = os.path.join(ROOT, "SecondBrain", "05_Active_Projects", "Audio_Scripts")
CH_DIR = os.path.join(ROOT, "SecondBrain", "05_Active_Projects", "Chapters")


def convert_chapter_to_audioscript(chapter_text: str) -> str:
    """แปลงเนื้อหาตอนนิยายดิบเป็น AudioScript พร้อมคิวผู้บรรยายและบทสนทนา"""
    lines = chapter_text.strip().split("\n")
    script_blocks = []

    for line in lines:
        l = line.strip()
        if not l or l.startswith("#"):
            continue

        # ตรวจสอบว่าเป็นบทสนทนาในเครื่องหมายคำพูดหรือไม่
        m_dialogue = re.match(r'^["“](.*?)[”"]\s*(.*?)$', l)
        if m_dialogue:
            dialogue_text = m_dialogue.group(1).strip()
            action_text = m_dialogue.group(2).strip()
            block = f"[ตัวละคร] {dialogue_text}"
            if action_text:
                block += f"\n[ผู้บรรยาย] {action_text}"
            script_blocks.append(block)
        else:
            # ตรวจสอบกรณีชื่อตัวละครนำหน้า เช่น ณิชา: "..."
            m_speaker = re.match(r"^([^:：]+)[:：]\s*[\"“]?(.*?)[\"”]?$", l)
            if m_speaker and len(m_speaker.group(1)) <= 15:
                speaker = m_speaker.group(1).strip()
                speech = m_speaker.group(2).strip()
                script_blocks.append(f"[{speaker}] {speech}")
            else:
                # คำบรรยายทั่วไป
                script_blocks.append(f"[ผู้บรรยาย] {l}")

    return "\n\n".join(script_blocks)


def main() -> int:
    files = glob.glob(os.path.join(AS_DIR, "*.md"))
    print(f"🔍 เริ่มสแกน AudioScripts ทั้งหมด {len(files)} ไฟล์...")

    broken_files = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                txt = f.read()
        except Exception:
            continue

        clean = re.sub(r"\[SFX:[^\]]*\]", "", txt)
        clean = re.sub(r"\[[^\]]*\]", "", clean).strip()
        thai_chars = len(re.findall(r"[\u0E00-\u0E7F]", clean))

        if thai_chars < 100 or "[ไม่สามารถสร้างบทเสียงได้]" in txt:
            broken_files.append((fp, os.path.basename(fp)))

    print(f"⚠️ พบไฟล์ที่บทพากย์พังหรือว่างเปล่า: {len(broken_files)} ไฟล์")
    if not broken_files:
        print("✅ ไฟล์ AudioScript ทั้งหมดสมบูรณ์ดี")
        return 0

    repaired_count = 0
    for fp, fname in broken_files:
        # Match story stem and episode number
        # e.g. สมาคมประกันภัยลี้ลับ_AudioScript_04.md -> สมาคมประกันภัยลี้ลับ_Chapter_04.md
        m = re.match(r"^(.*?)_AudioScript_(\d+)\.md$", fname)
        if not m:
            continue

        story_stem = m.group(1)
        ep_num = int(m.group(2))

        ch_candidates = [
            os.path.join(CH_DIR, f"{story_stem}_Chapter_{ep_num:02d}.md"),
            os.path.join(CH_DIR, f"{story_stem}_Chapter_{ep_num}.md")
        ]
        ch_path = next((p for p in ch_candidates if os.path.exists(p)), None)

        if not ch_path:
            # Fuzzy match
            matches = glob.glob(os.path.join(CH_DIR, f"*{story_stem}*Chapter*{ep_num}*.md"))
            if matches:
                ch_path = matches[0]

        if not ch_path or not os.path.exists(ch_path):
            continue

        with open(ch_path, "r", encoding="utf-8") as cf:
            ch_text = cf.read()

        if len(re.findall(r"[\u0E00-\u0E7F]", ch_text)) < 100:
            continue

        new_script = convert_chapter_to_audioscript(ch_text)
        if new_script:
            with open(fp, "w", encoding="utf-8") as out_f:
                out_f.write(new_script)
            repaired_count += 1
            print(f"  ✨ กู้คืนสำเร็จ: {fname} (จาก {os.path.basename(ch_path)})")

    print(f"\n🎉 กู้คืนบทพากย์สำเร็จ {repaired_count}/{len(broken_files)} ไฟล์!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
