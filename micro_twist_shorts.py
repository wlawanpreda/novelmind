"""
micro_twist_shorts.py — Viral Short Story & Comedy Engine for YouTube Shorts / TikTok
======================================================================================
ออกแบบเฉพาะสำหรับพฤติกรรมผู้ชม Shorts & TikTok:
1. เรื่องสั้นจบใน 60 วินาที หรือมุกตลกกาวๆ (Micro Twist / Comedy Meme)
2. Hook โดนใจใน 3 วินาทีแรก (คำถามชวนสงสัย หรือสถานการณ์ปั่นๆ)
3. พากย์ไทยด้วย Edge-TTS พร้อมตัวหนังสือขนาดใหญ่สะกดสายตากลางจอ (Safe Zone)
4. ทิ้ง Call-To-Action ให้คนดูเมนต์เดาตอนจบ หรือตามไปอ่านนิยายยาวเต็มๆ บน ReadAWrite

การใช้งาน:
  python micro_twist_shorts.py --batch 3
"""
from __future__ import annotations

import os
import re
import sys
import glob
import json
import subprocess
from typing import Dict, Any, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AP = os.path.join(SB, "05_Active_Projects")
SHORTS_DIR = os.path.join(AP, "Shorts")
os.makedirs(SHORTS_DIR, exist_ok=True)

# ตัวอย่างเทมเพลตเรื่องตลกกวนๆ และเรื่องสั้นหักมุม (Viral Templates)
VIRAL_TEMPLATES = [
    {
        "id": "speedrun_01",
        "title": "สืบคดีตายใน 15 วินาที",
        "type": "comedy",
        "hook": "อย่าให้ยอดนักสืบคนนี้ได้กลิ่นคดีเด็ดขาด!",
        "story": (
            "ผู้กองบอกว่านี่คือคดีฆาตกรรมห้องปิดตายที่ยากที่สุดในรอบสิบปี "
            "แต่ยอดนักสืบสปีดรันเดินเข้ามาในห้อง มองหน้าต่างหนึ่งที มองแก้วกาแฟหนึ่งที "
            "แล้วชี้หน้าผู้กองทันทีว่า คนร้ายก็คือผู้กองนั่นแหละ! "
            "ผู้กองเหงื่อแตกพลั่ก รู้ได้ยังไงวะ! "
            "นักสืบตอบเรียบๆ ผมเดา... แต่หน้าผู้กองมีพิรุธเองนะ "
            "สรุปปิดคดีได้ในสิบห้าวินาที ปรบมือสิครับรออะไร!"
        ),
        "cta": "ถ้าอยากเห็นคดีกาวๆ อีก ตามไปอ่าน ยอดนักสืบสปีดรัน ใน ReadAWrite นะครับ!"
    },
    {
        "id": "convenience_store_01",
        "title": "มิติลับยุค 70 กับซูเปอร์มาร์เก็ต",
        "type": "comedy",
        "hook": "ทะลุมิติไปยุค 70 ทั้งที ดันได้ของสิ่งนี้มา!",
        "story": (
            "คนอื่นทะลุมิติไปยุค 70 ได้พลังเวท ได้พลังมังกรสวรรค์ "
            "แต่ฉันดันได้มิติลับที่เป็นซูเปอร์มาร์เก็ต 24 ชั่วโมงพร้อมแอร์เย็นฉ่ำ! "
            "แม่สามีใจร้ายบอกว่า วันนี้ไม่มีข้าวกินนะนังตัวดี "
            "ฉันเลยแอบแวบเข้ามิติ นั่งกินแซลมอนซาชิมิราดน้ำจิ้มซีฟู้ดจนพุงกาง "
            "ก่อนจะเอาบะหมี่กึ่งสำเร็จรูปถ้วยละห้าบาท ออกไปขายให้หัวหน้าหมู่บ้านในราคาทองคำ!"
        ),
        "cta": "กดหัวใจแล้วตามไปอ่าน คุณแม่ลูกแฝดยุค 70 ใน ReadAWrite ได้เลย!"
    },
    {
        "id": "ghost_mirror_01",
        "title": "กระจกเงาคนตาย",
        "type": "twist",
        "hook": "ถ้านาฬิกาปลุกดังตอนตีสาม อย่าเพิ่งลืมตาเด็ดขาด!",
        "story": (
            "มีกฎข้อเดียวของการซื้อกระจกโบราณบานนี้มาไว้ในห้องนอน "
            "คือถ้าคุณตื่นมาตอนตีสาม แล้วเห็นเงาตัวเองในกระจกยังนอนหลับอยู่... "
            "ห้ามขยับตัวเด็ดขาด เพราะร่างที่นอนอยู่ตรงนั้นไม่ใช่คุณ "
            "แต่มันคือตัวคุณในกระจก ที่กำลังรอให้คุณลืมตาขึ้นมา... เพื่อสลับที่กันตลอดกาล!"
        ),
        "cta": "ใครกล้าส่องกระจกดึกๆ เมนต์บอกหน่อย! ตามอ่านเต็มๆ ได้ที่ ReadAWrite"
    }
]


def synthesize_speech(text: str, out_path: str, voice: str = "th-TH-NiwatNeural") -> bool:
    """แปลงข้อความเป็นเสียงพากย์ฉะฉานด้วย Edge-TTS"""
    import asyncio
    import edge_tts

    async def _run():
        comm = edge_tts.Communicate(text, voice=voice, rate="+15%")
        await comm.save(out_path)

    try:
        asyncio.run(_run())
        return os.path.exists(out_path) and os.path.getsize(out_path) > 1000
    except Exception as e:
        print(f"[!] Speech synthesis error: {e}")
        return False


def build_micro_short(item: Dict[str, Any], output_path: str) -> bool:
    """รวมเสียง พากย์ และภาพ เข้าด้วยกันเป็นวิดีโอ 9:16 Viral Short"""
    import teaser_generator as tg

    title = item.get("title", "เรื่องสั้นสุดพีก")
    hook = item.get("hook", "")
    full_script = f"{hook} {item.get('story', '')} {item.get('cta', '')}"

    # 1. สร้างเสียงพากย์
    temp_audio = os.path.join(SHORTS_DIR, f"temp_{item['id']}.mp3")
    voice = "th-TH-NiwatNeural" if item.get("type") == "comedy" else "th-TH-PremwadeeNeural"
    ok_voice = synthesize_speech(full_script, temp_audio, voice=voice)
    if not ok_voice:
        print("   ❌ สร้างเสียงไม่สำเร็จ")
        return False

    # 2. ค้นหาภาพปกที่เข้ากัน
    covers = glob.glob(os.path.join(AP, "Covers", "*.jpg")) + glob.glob(os.path.join(AP, "Covers", "*.png"))
    bg_cover = covers[0] if covers else os.path.join(ROOT, "author_banner.jpg")

    # 3. เบิร์น Headline และ Hook สะดุดตา
    capped_img = tg.caption_cover(bg_cover, title, hook, tiktok_safe=True)

    # 4. ประกอบวิดีโอด้วย FFmpeg
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fade=t=in:st=0:d=0.3"
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", capped_img,
        "-i", temp_audio,
        "-vf", vf,
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-pix_fmt", "yuv420p",
        "-shortest", output_path
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(temp_audio):
        os.remove(temp_audio)

    if res.returncode == 0 and os.path.exists(output_path):
        mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"   ✅ สร้าง Micro-Short สำเร็จ: {output_path} ({mb:.2f} MB)")
        return True
    else:
        print(f"   ❌ FFmpeg error: {res.stderr[-200:]}")
        return False


def run_batch(count: int = 3):
    """สร้าง Micro Twist / Comedy Shorts ตามโควตา"""
    print(f"\n🎬 เริ่มต้นการสร้าง Viral Shorts จำนวน {count} ชิ้น...")
    success = 0
    for idx, item in enumerate(VIRAL_TEMPLATES[:count], 1):
        print(f"\n[{idx}/{count}] กำลังเรนเดอร์: {item['title']} ({item['type']})")
        out_file = os.path.join(SHORTS_DIR, f"Short_Viral_{item['id']}.mp4")
        if build_micro_short(item, out_file):
            success += 1

    print(f"\n🎉 สำเร็จแล้ว {success}/{count} คลิปในโฟลเดอร์ {SHORTS_DIR}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=3, help="จำนวน Shorts ที่ต้องการสร้าง")
    args = parser.parse_args()
    run_batch(args.batch)
