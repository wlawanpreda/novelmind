#!/usr/bin/env python3
"""
generate_batch_audio_scripts.py
สร้างสคริปต์นิยายเสียง (AudioScript) สำหรับ 20 ตอนแรกของทั้ง 3 เรื่อง
ตามมาตรฐาน Audio-Cinematic Pipeline ของ ANSRE
"""
import os
import sys
import json
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from llm_provider import generate

NOVELS = {
    "01_Peerless_Alchemy_God": {
        "title": "ยอดเทพโอสถสะท้านภพ (绝世丹神)",
        "protagonist": "ฉินเฟิง (Qin Feng)",
        "summary_file": "SecondBrain/Audio_Production_Packs/01_Peerless_Alchemy_God/00_Summary_Arc_20_Chapters.md",
        "output_dir": "SecondBrain/Audio_Production_Packs/01_Peerless_Alchemy_God",
        "style": "แฟนตาซีโบราณ, ย้อนเวลาแสนปี, ปรุงยาเทพ, สุขุมเยือกเย็น, แก้เกมด้วยความรู้ระดับพระเจ้า"
    },
    "02_Transcending_Nine_Heavens": {
        "title": "ผงาดเก้าชั้นฟ้า (傲世九重天)",
        "protagonist": "ฉู่หยาง (Chu Yang)",
        "summary_file": "SecondBrain/Audio_Production_Packs/02_Transcending_Nine_Heavens/00_Summary_Arc_20_Chapters.md",
        "output_dir": "SecondBrain/Audio_Production_Packs/02_Transcending_Nine_Heavens",
        "style": "กำลังภายใน, กระบี่เก้าภัยพิบัติ, วางแผนกลยุทธ์, คารมคมคาย, มิตรภาพลูกผู้ชาย"
    },
    "03_Tales_of_Herding_Gods": {
        "title": "มหาศึกเลี้ยงเทพ (牧神记)",
        "protagonist": "ฉินมู่ (Qin Mu)",
        "summary_file": "SecondBrain/Audio_Production_Packs/03_Tales_of_Herding_Gods/00_Summary_Arc_20_Chapters.md",
        "output_dir": "SecondBrain/Audio_Production_Packs/03_Tales_of_Herding_Gods",
        "style": "แฟนตาซีโบราณแดนร้าง, ลึกลับ, ดาร์กคอเมดี้, ทรราชผู้ไร้เดียงสา, ฟ้ามืดห้ามออกจากบ้าน"
    }
}

PROMPT_TEMPLATE = """คุณคือนักเขียนบทนิยายเสียงมืออาชีพ (Audio Drama & Cinematic Scriptwriter)
ภารกิจ: เขียนบทนิยายเสียงภาษาไทยสำหรับนำไปพากย์ด้วย AI Voice (Edge-TTS) และใส่ซาวด์เอฟเฟกต์ (SFX)

เรื่อง: {title}
ตัวเอก: {protagonist}
สไตล์เรื่อง: {style}

ข้อมูลบทที่ {chapter_num}:
หัวข้อ/แก่นเรื่อง: {chapter_info}

บริบทโดยรวมของ 20 ตอนแรก:
{summary_context}

กฎเหล็กในการเขียนบทนิยายเสียง (Cinematic Format):
1. รูปแบบบรรทัด:
   - บทบรรยาย: [ผู้บรรยาย, โทน: ...] เนื้อหาบรรยายเห็นภาพ มีมิติ ไม่ยืดยาด
   - บทพูดตัวละคร: [ชื่อตัวละคร, โทน: ...] "บทพูดชัดเจน สมจริง ธรรมชาติ"
   - ซาวด์เอฟเฟกต์: [SFX: ...] เช่น [SFX: เสียงกระบี่แหวกอากาศ], [SFX: เสียงระเบิดตูม], [SFX: เสียงลมพายุหวีดหวิว]
2. ภาษาไทยต้องสละสลวย กระชับ เหมาะกับการฟัง (ห้ามแปลแข็งทื่อ)
3. มีการตัดต่อจังหวะอารมณ์ ลุ้นระทึก น่าติดตาม และจบตอนด้วยจุดกระตุ้นความสนใจ (Hook / Cliffhanger)
4. ความยาวเนื้อหาบทความ: ประมาณ 1,200 - 2,000 ตัวอักษร
5. ส่งคืนเฉพาะเนื้อหาบทสคริปต์ ไม่ต้องใส่คำเกริ่นหรือคำลงท้ายใดๆ ทั้งสิ้น"""

def parse_chapters(summary_path):
    chapters = {}
    with open(summary_path, "r", encoding="utf-8") as f:
        text = f.read()
    
    matches = re.findall(r"\*\s+\*\*ตอนที่\s+(\d+(?:\s*–\s*\d+)?)\s*\((.*?)\):\*\*\s*(.*?)(?=\n\*|\Z)", text, re.DOTALL)
    for m in matches:
        ch_range, ch_title, ch_desc = m
        if "–" in ch_range or "-" in ch_range:
            parts = [int(p.strip()) for p in re.split(r"[–-]", ch_range)]
            for num in range(parts[0], parts[1] + 1):
                chapters[num] = f"{ch_title} - {ch_desc.strip()}"
        else:
            chapters[int(ch_range.strip())] = f"{ch_title} - {ch_desc.strip()}"
    return text, chapters

def generate_script_for_chapter(novel_key, ch_num):
    info = NOVELS[novel_key]
    out_file = os.path.join(info["output_dir"], f"Chapter_{ch_num:02d}_AudioScript.md")
    
    if os.path.exists(out_file) and os.path.getsize(out_file) > 500:
        print(f"[Skip] {novel_key} ตอนที่ {ch_num:02d} มีอยู่แล้ว", flush=True)
        return True

    summary_context, ch_map = parse_chapters(info["summary_file"])
    ch_info = ch_map.get(ch_num, f"เนื้อหาดำเนินต่อจากตอนก่อนหน้า ตามโครงเรื่อง {info['title']}")
    
    prompt = PROMPT_TEMPLATE.format(
        title=info["title"],
        protagonist=info["protagonist"],
        style=info["style"],
        chapter_num=ch_num,
        chapter_info=ch_info,
        summary_context=summary_context[:2000]
    )
    
    print(f"[Generating] {info['title']} ตอนที่ {ch_num:02d}...", flush=True)
    try:
        content = generate(prompt, role="writer", temperature=0.7)
        if not content or len(content) < 300:
            print(f"[Error] ผลลัพธ์ตอนที่ {ch_num} สั้นเกินไป", flush=True)
            return False
            
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(content.strip())
        print(f"[Success] บันทึก {out_file} ({len(content)} ตัวอักษร)", flush=True)
        return True
    except Exception as e:
        print(f"[Fail] เกิดข้อผิดพลาดในตอนที่ {ch_num}: {e}", flush=True)
        return False

if __name__ == "__main__":
    target_novel = sys.argv[1] if len(sys.argv) > 1 else "all"
    start_ch = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    end_ch = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    
    novels_to_run = [target_novel] if target_novel in NOVELS else list(NOVELS.keys())
    
    for n_key in novels_to_run:
        print(f"\n==========================================", flush=True)
        print(f"🚀 เริ่มต้นสร้าง: {NOVELS[n_key]['title']}", flush=True)
        print(f"==========================================", flush=True)
        for c in range(start_ch, end_ch + 1):
            success = generate_script_for_chapter(n_key, c)
