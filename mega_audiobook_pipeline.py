#!/usr/bin/env python3
"""
mega_audiobook_pipeline.py — Unified Mega Audiobook Production & Publishing Engine
==================================================================================
ระบบรวมเล่มนิยายเสียงแบบครบวงจรอัตโนมัติ (Mega Audiobook 1-2+ ชั่วโมง)
สำหรับสะสมยอดเวลารับชม 4,000 ชั่วโมงตามเกณฑ์ YouTube Partner Program (YPP)

ฟังก์ชันหลัก:
1. 🔍 Auto-Discovery: สแกนพบคลังนิยายที่มีไฟล์เสียงครบ (20 ตอน หรือ 8 ตอน) ใน Audio_Output
2. 🔨 Lossless Audio Concatenation: รวมไฟล์เสียงระดับสตูดิโอ พร้อมคำนวณ Timestamps ละเอียดทุกบท
3. 🎨 High-CTR 16:9 Card Thumbnail: สร้างภาพปก 1920x1080 สไตล์ YouTube Premium Card Layout
4. 🎬 Ultra-Fast 1080p Video Rendering: เรนเดอร์วิดีโอ 1080p พร้อมภาพนิ่ง 16:9 ไม่เสียคุณภาพ
5. 🚀 YouTube Scheduled Uploader: อัปโหลดและตั้งเวลาปล่อย พร้อมคำอธิบายและสารบัญ Chapters แบบอัตโนมัติ
"""

import os
import sys
import re
import glob
import json
import argparse
import subprocess
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import youtube_stats
from googleapiclient.http import MediaFileUpload

SB = os.path.join(ROOT, "SecondBrain")
AUDIO_DIR = os.path.join(SB, "05_Active_Projects", "Audio_Output")
COVERS_DIR = os.path.join(SB, "05_Active_Projects", "Covers")
EXPORTS_DIR = os.path.join(SB, "05_Active_Projects", "Exports", "Mega_Audiobooks")
os.makedirs(EXPORTS_DIR, exist_ok=True)

FONT_PATH = "/System/Library/Fonts/Supplemental/SukhumvitSet.ttc"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "/System/Library/Fonts/Thonburi.ttc"

DISPLAY_TITLE_OVERRIDES = {
    "รหสลบใตเงา_บทเพลงแหงกาลเวลา": "รหัสลับใต้เงา บทเพลงแห่งกาลเวลา",
    "รานคาเหนอโลก_สตรมดนเจยนลาเทพ": "ร้านค้าเหนือโลก สตรีมดันเจียนล่าเทพ",
    "สถานตรวจกาววญญาณ": "สถานีตำรวจกาววิญญาณ",
}


def get_display_title(story_name: str) -> str:
    return DISPLAY_TITLE_OVERRIDES.get(story_name, story_name.replace("_", " "))




def get_audio_duration(file_path: str) -> float:
    """วัดความยาวไฟล์เสียงด้วย ffprobe"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def format_timestamp(seconds: float) -> str:
    """แปลงวินาทีเป็นรูปแบบ HH:MM:SS หรือ MM:SS สำหรับ YouTube Chapters"""
    td = timedelta(seconds=int(seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def scan_available_series() -> Dict[str, List[str]]:
    """สแกนค้นหานิยายทั้งหมดในคลัง Audio_Output ที่มีไฟล์เสียงพร้อมรวม"""
    files = glob.glob(os.path.join(AUDIO_DIR, "*.mp3"))
    series = {}
    for f in files:
        base = os.path.basename(f)
        if "_Audiobook_" in base:
            story_name, ep_part = base.rsplit("_Audiobook_", 1)
            series.setdefault(story_name, []).append(f)

    # จัดเรียงตอนตามลำดับตัวเลข
    def sort_key(path):
        m = re.search(r'_Audiobook_(\d+)\.mp3$', path)
        return int(m.group(1)) if m else 0

    for s in series:
        series[s].sort(key=sort_key)
    return series


def create_mega_thumbnail(
    out_path: str,
    story_title: str,
    cover_path: Optional[str] = None,
    badge_text: str = "รวมครบจบในตอน",
    sub_title: str = "นิยายเสียงฟังสบายก่อนนอน (จบภาค)",
    duration_str: str = "ฟังยาวต่อเนื่อง"
) -> str:
    """สร้าง Thumbnail 16:9 (1920x1080) ดีไซน์ Card Layout ดึงดูดสายตา CTR สูง"""
    width, height = 1920, 1080

    # ค้นหาภาพปกต้นฉบับถ้าไม่ได้ระบุ
    if not cover_path or not os.path.exists(cover_path):
        candidates = [
            os.path.join(COVERS_DIR, f"{story_title}_Cover.jpg"),
            os.path.join(COVERS_DIR, f"{story_title}_Cover_captioned.jpg"),
        ]
        for c in candidates:
            if os.path.exists(c):
                cover_path = c
                break

    if cover_path and os.path.exists(cover_path):
        orig = Image.open(cover_path).convert("RGBA")
    else:
        orig = Image.new("RGBA", (800, 1200), (30, 41, 59, 255))

    # 1. พื้นหลัง Gaussian Blur หรูหรา
    bg = orig.resize((width, height)).filter(ImageFilter.GaussianBlur(36))
    dark_overlay = Image.new("RGBA", (width, height), (15, 23, 42, 205))
    bg = Image.alpha_composite(bg, dark_overlay)

    # 2. จัดวางปกหนังสือแนวตั้งเป็น Card โค้งมนพร้อมกรอบเรืองแสง
    card_h = 920
    orig_ratio = orig.width / orig.height
    card_w = int(card_h * orig_ratio)
    cover_resized = orig.resize((card_w, card_h), Image.Resampling.LANCZOS)
    card_bg = Image.new("RGBA", (card_w + 16, card_h + 16), (255, 255, 255, 220))
    card_bg.paste(cover_resized, (8, 8))
    bg.paste(card_bg, (90, 80), card_bg)

    # 3. Typography & Badges
    draw = ImageDraw.Draw(bg)
    title_font = ImageFont.truetype(FONT_PATH, 74, index=4 if "Sukhumvit" in FONT_PATH else 0)
    badge_font = ImageFont.truetype(FONT_PATH, 34, index=4 if "Sukhumvit" in FONT_PATH else 0)
    sub_font = ImageFont.truetype(FONT_PATH, 42, index=4 if "Sukhumvit" in FONT_PATH else 0)
    pill_font = ImageFont.truetype(FONT_PATH, 32, index=4 if "Sukhumvit" in FONT_PATH else 0)

    text_x = 90 + card_w + 65

    # Badge 1: Mega Audiobook
    draw.rounded_rectangle([(text_x, 120), (text_x + 480, 195)], radius=14, fill=(245, 158, 11, 250))
    draw.text((text_x + 25, 136), "FULL AUDIOBOOK", fill=(0, 0, 0), font=badge_font)

    # Badge 2: รวมครบจบในตอน
    draw.rounded_rectangle([(text_x + 500, 120), (text_x + 850, 195)], radius=14, fill=(14, 165, 233, 245))
    draw.text((text_x + 525, 136), badge_text[:16], fill=(255, 255, 255), font=badge_font)

    # Story Title (ตัดขึ้นบรรทัดใหม่หากยาวเกินไป)
    clean_title = get_display_title(story_title)
    if len(clean_title) > 22:
        title_line1 = clean_title[:20]
        title_line2 = clean_title[20:45]
        draw.text((text_x, 245), title_line1, fill=(255, 255, 255), font=title_font)
        draw.text((text_x, 340), title_line2, fill=(255, 255, 255), font=title_font)
        sub_y = 445
    else:
        draw.text((text_x, 260), clean_title, fill=(255, 255, 255), font=title_font)
        sub_y = 380

    # Subtitle
    draw.text((text_x, sub_y), sub_title, fill=(56, 189, 248), font=sub_font)

    # Duration Pill
    draw.rounded_rectangle([(text_x, 780), (text_x + 720, 875)], radius=16, fill=(30, 41, 59, 240), outline=(56, 189, 248), width=3)
    draw.text((text_x + 40, 805), f"● {duration_str} · ฟังเพลิน ไม่มีสะดุด", fill=(241, 245, 249), font=pill_font)

    bg.convert("RGB").save(out_path, quality=95)
    return out_path


def build_mega_audiobook(
    story_name: str,
    custom_badge: Optional[str] = None,
    custom_sub: Optional[str] = None,
    schedule_utc: Optional[str] = None
) -> Dict[str, Any]:
    """สร้าง Master MP3, Timestamps, Video 1080p, Thumbnail และ Metadata สำหรับเรื่องที่กำหนด"""
    series_map = scan_available_series()
    if story_name not in series_map:
        raise ValueError(f"ไม่พบนิยายชื่อ '{story_name}' ในคลัง Audio_Output")

    chapter_files = series_map[story_name]
    num_chapters = len(chapter_files)
    clean_title = get_display_title(story_name)

    print("\n" + "=" * 70)
    print(f"🎬 กำลังสร้าง MEGA AUDIOBOOK: {clean_title}")
    print(f"📚 จำนวนตอนทั้งหมด: {num_chapters} ตอน")
    print("=" * 70)

    # ตั้งชื่อไฟล์ส่งออก
    safe_name = re.sub(r'[\s/\\:]+', '_', clean_title)
    master_mp3 = os.path.join(EXPORTS_DIR, f"{safe_name}_Mega_Master.mp3")
    master_mp4 = os.path.join(EXPORTS_DIR, f"{safe_name}_Mega_1080p.mp4")
    thumb_path = os.path.join(EXPORTS_DIR, f"{safe_name}_Mega_Thumbnail_16x9.jpg")
    desc_path = os.path.join(EXPORTS_DIR, f"{safe_name}_Mega_Description.txt")
    meta_json = os.path.join(EXPORTS_DIR, f"{safe_name}_Mega_Metadata.json")

    # 1. คำนวณความยาวและสร้างสารบัญ Timestamps
    print("⏱️ กำลังคำนวณสารบัญบท (Chapters Timestamps)...")
    concat_list_file = os.path.join(EXPORTS_DIR, f"_temp_{safe_name}_concat.txt")
    timestamps = []
    current_sec = 0.0

    with open(concat_list_file, "w", encoding="utf-8") as f_list:
        for idx, fp in enumerate(chapter_files, 1):
            dur = get_audio_duration(fp)
            ts_str = format_timestamp(current_sec)
            timestamps.append(f"{ts_str} ตอนที่ {idx}")
            f_list.write(f"file '{os.path.abspath(fp)}'\n")
            current_sec += dur

    total_time_str = format_timestamp(current_sec)
    print(f"⏱️ ความยาวรวมทั้งสิ้น: {total_time_str} ({current_sec:.1f} วินาที)")

    # 2. รวมไฟล์เสียง Master MP3 (Normalize Sample Rate 44.1kHz ป้องกันปัญหาคลื่นความถี่ต่างกันระหว่างตอน)
    print("🔨 กำลังรวมและ Normalize ไฟล์เสียง Master MP3 (44.1kHz)...")
    cmd_concat = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_file,
        "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k",
        master_mp3
    ]
    subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    if os.path.exists(concat_list_file):
        os.remove(concat_list_file)

    # 3. สร้าง Thumbnail 16:9
    badge = custom_badge or f"รวมครบ {num_chapters} ตอนจบ"
    sub = custom_sub or "นิยายเสียงฟังสบายก่อนนอน (จบภาค)"
    dur_label = f"ฟังยาว {total_time_str}"
    create_mega_thumbnail(thumb_path, story_name, badge_text=badge, sub_title=sub, duration_str=dur_label)
    print(f"🎨 สร้างปก High-CTR 16:9 สำเร็จ: {os.path.basename(thumb_path)}")

    # 4. ประกอบคำบรรยาย Description แบบ High-Retention & SEO
    desc_text = f"""💬 ชวนคุยก่อนนอน: คืนนี้เพื่อนๆ ฟังเรื่อง '{clean_title}' ถึงตอนไหนกันบ้างครับ? ชอบตัวละครไหนเป็นพิเศษ มาร่วมแชร์และพูดคุยกันด้านล่างได้เลยนะครับ 👇✨

🎧 [รวมครบ {num_chapters} ตอนจบ] {clean_title} (Full Mega Audiobook)
ความยาวกว่า {total_time_str} ฟังยาวต่อเนื่อง ไม่มีสะดุด หลับสบายตลอดทั้งคืน

⏱️ สารบัญเลือกตอน (Chapters):
{chr(10).join(timestamps)}

---
📖 สำหรับท่านที่ต้องการอ่านบทความฉบับเต็ม หรือติดตามผลงาน (นามปากกา: เงาพันจันทร์):
🔗 ติดตามผลงานฉบับเต็มได้ที่ ReadAWrite นามปากกา 'เงาพันจันทร์'
📚 ดาวน์โหลด E-Book ฉบับเต็มบน Meb Market

✨ ช่อง Midnight Tales · มิดไนต์เทล
กดติดตาม (Subscribe) และกดกระดิ่งแจ้งเตือน เพื่อไม่พลาดนิยายเรื่องใหม่ทุกสัปดาห์!

#นิยายเสียง #นิยายเสียงก่อนนอน #{clean_title.replace(' ', '')} #FullAudiobook #Audiobook #หนังสือนิยาย #จบในตอน
"""
    with open(desc_path, "w", encoding="utf-8") as df:
        df.write(desc_text)

    # 5. เรนเดอร์วิดีโอ 1080p แบบ Ultrafast Still-Image
    print("🎬 กำลังเรนเดอร์วิดีโอ 1080p 16:9 (ภาพคมชัด ไร้ขอบดำ)...")
    cmd_video = [
        "ffmpeg", "-y",
        "-framerate", "1", "-loop", "1", "-i", thumb_path,
        "-i", master_mp3,
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
        "-r", "1",
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        "-shortest",
        master_mp4
    ]
    subprocess.run(cmd_video, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    video_size_mb = os.path.getsize(master_mp4) / 1024 / 1024
    print(f"✅ เรนเดอร์วิดีโอสำเร็จ: {os.path.basename(master_mp4)} ({video_size_mb:.2f} MB)")

    # 6. บันทึก Metadata
    yt_title = f"[จบในตอน {total_time_str}] {clean_title} รวมครบ {num_chapters} ตอนจบ | นิยายเสียงก่อนนอน"
    if len(yt_title) > 95:
        yt_title = yt_title[:95]

    meta_info = {
        "story_name": story_name,
        "clean_title": clean_title,
        "chapters_count": num_chapters,
        "duration_str": total_time_str,
        "duration_seconds": current_sec,
        "youtube_title": yt_title,
        "description_path": desc_path,
        "video_path": master_mp4,
        "thumbnail_path": thumb_path,
        "created_at": datetime.now().isoformat()
    }
    with open(meta_json, "w", encoding="utf-8") as mf:
        json.dump(meta_info, mf, ensure_ascii=False, indent=2)

    # 7. อัปโหลด/ตั้งเวลาบน YouTube หากมีการระบุ schedule_utc
    if schedule_utc:
        print(f"\n🚀 กำลังตั้งเวลาเผยแพร่บน YouTube @ {schedule_utc}...")
        yt_res = upload_and_schedule_mega(meta_info, schedule_utc)
        meta_info["youtube_result"] = yt_res

    print("\n🎉 MEGA AUDIOBOOK ผลิตเสร็จสมบูรณ์ พร้อมขับเคลื่อน 4,000 ชั่วโมงแล้ว!")
    return meta_info


def upload_and_schedule_mega(meta: Dict[str, Any], publish_at_utc: str) -> Dict[str, Any]:
    """อัปโหลดวิดีโอยาวขึ้น YouTube ในสถานะ Private + publishAt และอัปเดต Thumbnail"""
    yt = youtube_stats._yt()
    video_path = meta["video_path"]
    thumb_path = meta["thumbnail_path"]

    with open(meta["description_path"], "r", encoding="utf-8") as df:
        desc = df.read()

    body = {
        "snippet": {
            "title": meta["youtube_title"],
            "description": desc,
            "tags": ["นิยายเสียง", "Full Audiobook", "นิยายเสียงก่อนนอน", "จบในตอน", meta["clean_title"]],
            "categoryId": "24"
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at_utc,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"   ⏳ กำลังส่งข้อมูลวิดีโอ: {int(status.progress() * 100)}%")

    vid = resp.get("id")
    yt_url = f"https://youtu.be/{vid}"
    print(f"   ✅ อัปโหลดวิดีโอสำเร็จ! YouTube ID: {vid}")
    print(f"   🔗 URL: {yt_url}")

    # อัปเดต Thumbnail
    if os.path.exists(thumb_path):
        try:
            print("   🎨 กำลังอัปเดต Custom Thumbnail...")
            thumb_media = MediaFileUpload(thumb_path, mimetype="image/jpeg")
            yt.thumbnails().set(videoId=vid, media_body=thumb_media).execute()
            print("   ✅ อัปเดต Custom Thumbnail เรียบร้อย")
        except Exception as e:
            print(f"   ⚠️ ไม่สามารถตั้ง Thumbnail ได้: {e}")

    return {"youtube_id": vid, "url": yt_url, "publish_at": publish_at_utc}


def main():
    parser = argparse.ArgumentParser(description="Unified Mega Audiobook Production & Publishing Pipeline")
    parser.add_argument("--list", action="store_true", help="แสดงรายชื่อนิยายทั้งหมดที่มีคลังเสียงพร้อมรวม")
    parser.add_argument("--story", type=str, help="ชื่อเรื่องนิยายที่ต้องการรวมเล่ม Mega Audiobook")
    parser.add_argument("--badge", type=str, default=None, help="ข้อความบน Badge (เช่น 'รวมครบ 20 ตอนจบ')")
    parser.add_argument("--sub", type=str, default=None, help="คำบรรยายย่อยใต้ชื่อเรื่อง")
    parser.add_argument("--schedule", type=str, default=None, help="วันเวลาเผยแพร่ในรูปแบบ UTC ISO (เช่น 2026-11-15T13:00:00Z)")

    args = parser.parse_args()

    if args.list:
        series = scan_available_series()
        print("\n" + "=" * 65)
        print(" 📚 รายชื่อนิยายที่มีคลังไฟล์เสียงพร้อมผลิต Mega Audiobook:")
        print("=" * 65)
        for s, files in sorted(series.items(), key=lambda x: len(x[1]), reverse=True):
            status = "🔥 เหมาะสร้าง Mega (1-2 ชม.)" if len(files) >= 15 else ("⭐ รวมเล่มสั้น (30-40 นาที)" if len(files) >= 8 else "⏳ ตอนยังน้อย")
            print(f"  • {s}: {len(files)} ตอน ({status})")
        print("=" * 65)
        return

    if args.story:
        build_mega_audiobook(args.story, custom_badge=args.badge, custom_sub=args.sub, schedule_utc=args.schedule)
    else:
        print("กรุณาระบุ --story <ชื่อเรื่อง> หรือใช้ --list เพื่อดูรายการนิยายที่มีในคลัง")


if __name__ == "__main__":
    main()
