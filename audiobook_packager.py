"""
audiobook_packager.py — Long-Form Audiobook & YouTube Compilation Engine
========================================================================

รวมไฟล์เสียงนิยายรายตอน (.mp3) ใน Audio_Output ให้กลายเป็น:
1. ไฟล์เสียงฉบับรวมตอนเต็ม (Master Audiobook MP3)
2. วิดีโอ YouTube Long-form 1080p พร้อมภาพปก (.mp4) สำหรับเปิดสร้าง Watch Time
3. สารบัญเวลา (Chapter Timestamps) สำหรับใส่ใน Description ของ YouTube

CLI:
  python audiobook_packager.py <ชื่อเรื่อง>
  python audiobook_packager.py --all
"""
from __future__ import annotations

import os
import re
import glob
import json
import subprocess
from datetime import timedelta
from typing import List, Dict, Any, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AUDIO_DIR = os.path.join(SB, "05_Active_Projects", "Audio_Output")
COVERS_DIR = os.path.join(SB, "05_Active_Projects", "Covers")
EXPORTS_DIR = os.path.join(SB, "05_Active_Projects", "Exports", "Audiobooks")

# Ensure standard binary paths are in PATH (for ffmpeg / ffprobe)
for _p in ["/opt/homebrew/bin", "/usr/local/bin"]:
    if os.path.exists(_p) and _p not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")

os.makedirs(EXPORTS_DIR, exist_ok=True)


def get_audio_duration(file_path: str) -> float:
    """หาความยาวของไฟล์เสียงเป็นวินาทีด้วย ffprobe"""
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
    """แปลงวินาทีเป็นฟอร์แมต 00:00 หรือ 00:00:00 สำหรับ YouTube Chapter"""
    td = timedelta(seconds=int(seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def find_audio_chapters(title: str) -> List[Dict[str, Any]]:
    """ค้นหาไฟล์เสียงทั้งหมดของเรื่อง เรียงตามลำดับตอน"""
    patterns = [
        os.path.join(AUDIO_DIR, f"{title}_Audiobook_*.mp3"),
        os.path.join(AUDIO_DIR, f"{title}_Chapter_*.mp3"),
    ]
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat))
    files = list(set(files))

    chapters = []
    for fp in files:
        fname = os.path.basename(fp)
        m = re.search(r"_(?:Audiobook|Chapter)_(\d+)\.mp3$", fname)
        ch_num = int(m.group(1)) if m else 1
        chapters.append({
            "num": ch_num,
            "filepath": fp,
            "filename": fname
        })

    chapters.sort(key=lambda x: x["num"])
    return chapters


def find_cover_image(title: str) -> Optional[str]:
    """หาภาพปกต้นฉบับคุณภาพดีที่สุดสำหรับสร้างสื่อ 16:9 (เลี่ยงปก 9:16 ที่เบิร์นซับไว้)"""
    candidates = [
        f"{title}_Cover.jpg",
        f"{title}_Cover.png",
        f"{title}_Cover_3x4.jpg",
        f"{title}.jpg",
        f"{title}.png",
        f"{title}_Cover_captioned.jpg"
    ]
    for fn in candidates:
        fp = os.path.join(COVERS_DIR, fn)
        if os.path.exists(fp) and os.path.getsize(fp) > 1000:
            return fp
    matches = glob.glob(os.path.join(COVERS_DIR, f"*{title}*Cover*.*"))
    # ให้ความสำคัญกับไฟล์ปกคลีนที่ไม่ติด captioned ก่อน
    clean_matches = [m for m in matches if "_captioned" not in m]
    if clean_matches:
        return sorted(clean_matches)[0]
    if matches:
        return sorted(matches)[0]
    # Fuzzy match by key terms or sliding substrings
    if os.path.exists(COVERS_DIR):
        all_covers = [f for f in os.listdir(COVERS_DIR) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        # หาปกคลีนก่อน
        for i in range(max(1, len(title) - 3)):
            chunk = title[i:i+4]
            for cf in all_covers:
                if chunk in cf and "Cover" in cf and "_captioned" not in cf:
                    return os.path.join(COVERS_DIR, cf)
        for i in range(max(1, len(title) - 3)):
            chunk = title[i:i+4]
            for cf in all_covers:
                if chunk in cf and "Cover" in cf:
                    return os.path.join(COVERS_DIR, cf)
    return None


def generate_high_ctr_16x9_cover(title: str, cover_fp: str) -> str:
    """สร้างภาพปก High-CTR 16:9 อัตโนมัติ (1920x1080) สำหรับเรนเดอร์ลงวิดีโอและใช้เป็น Custom Thumbnail"""
    safe_title = re.sub(r'[^\w\-_\s฀-๿]', '', title).strip().replace(' ', '_')
    out_16x9 = os.path.join(EXPORTS_DIR, f"{safe_title}_Thumbnail_16x9.jpg")
    if os.path.exists(out_16x9) and os.path.getsize(out_16x9) > 10000:
        return out_16x9
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        orig = Image.open(cover_fp).convert("RGBA")
        width, height = 1920, 1080
        bg = orig.resize((width, height)).filter(ImageFilter.GaussianBlur(32))
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 190))
        bg = Image.alpha_composite(bg, overlay)

        orig_ratio = orig.width / orig.height
        card_h = 900
        card_w = int(card_h * orig_ratio)
        cover_resized = orig.resize((card_w, card_h), Image.Resampling.LANCZOS)
        card_bg = Image.new("RGBA", (card_w + 16, card_h + 16), (255, 255, 255, 220))
        card_bg.paste(cover_resized, (8, 8))
        bg.paste(card_bg, (90, 90), card_bg)

        draw = ImageDraw.Draw(bg)
        font_path = "/System/Library/Fonts/Supplemental/SukhumvitSet.ttc"
        if not os.path.exists(font_path):
            font_path = "/System/Library/Fonts/Helvetica.ttc"

        t_len = len(title)
        t_size = 80 if t_len <= 14 else (66 if t_len <= 22 else 54)
        title_font = ImageFont.truetype(font_path, t_size, index=4) if os.path.exists(font_path) else ImageFont.load_default()
        badge_font = ImageFont.truetype(font_path, 36, index=4) if os.path.exists(font_path) else ImageFont.load_default()
        sub_font = ImageFont.truetype(font_path, 44, index=4) if os.path.exists(font_path) else ImageFont.load_default()
        tag_font = ImageFont.truetype(font_path, 32, index=1) if os.path.exists(font_path) else ImageFont.load_default()
        pill_font = ImageFont.truetype(font_path, 32, index=4) if os.path.exists(font_path) else ImageFont.load_default()

        text_x = 90 + card_w + 65
        # Badges
        draw.rounded_rectangle([(text_x, 130), (text_x + 420, 205)], radius=14, fill=(245, 158, 11, 245))
        draw.text((text_x + 28, 145), "FULL AUDIOBOOK", fill=(0, 0, 0), font=badge_font)

        draw.rounded_rectangle([(text_x + 445, 130), (text_x + 740, 205)], radius=14, fill=(14, 165, 233, 240))
        draw.text((text_x + 475, 145), "รวมครบจบภาค", fill=(255, 255, 255), font=badge_font)

        # Title
        draw.text((text_x, 260), title[:24], fill=(255, 255, 255), font=title_font)
        # Subtitle
        draw.text((text_x, 385), "ฟังยาวต่อเนื่องก่อนนอน (รวมครบทุกตอน)", fill=(56, 189, 248), font=sub_font)
        # Tagline
        draw.text((text_x, 480), "นิยายเสียงคุณภาพ บรรยายลื่นไหล สนุก ตื่นเต้น", fill=(226, 232, 240), font=tag_font)

        # Bottom pill badge
        draw.rounded_rectangle([(text_x, 780), (text_x + 680, 875)], radius=16, fill=(30, 41, 59, 240), outline=(56, 189, 248), width=3)
        draw.text((text_x + 45, 805), "รวมครบทุกตอน · ฟังยาวต่อเนื่องก่อนนอน", fill=(241, 245, 249), font=pill_font)

        bg.convert("RGB").save(out_16x9, quality=95)
        return out_16x9
    except Exception as e:
        print(f"   [!] generate_high_ctr_16x9_cover error: {e}")
        return cover_fp


def package_story_audiobook(title: str, make_video: bool = True, force: bool = False) -> Optional[Dict[str, Any]]:
    """รวมตอนเสียง สร้าง Master MP3 และ YouTube Long-Form Video (Idempotent)"""
    chapters = find_audio_chapters(title)
    if not chapters:
        print(f"[!] ไม่พบไฟล์เสียงของเรื่อง '{title}'")
        return None

    safe_title = re.sub(r'[^\w\-_\s฀-๿]', '', title).strip().replace(' ', '_')
    output_mp3 = os.path.join(EXPORTS_DIR, f"{safe_title}_Full_Audiobook.mp3")
    output_desc = os.path.join(EXPORTS_DIR, f"{safe_title}_YouTube_Description.txt")
    output_mp4 = os.path.join(EXPORTS_DIR, f"{safe_title}_Audiobook_Video.mp4")

    # Idempotency check: หากไฟล์ MP3 และ MP4 มีอยู่แล้วและใหม่กว่าไฟล์เสียงรายตอนทุกไฟล์ ให้ข้ามการเรนเดอร์ซ้ำ
    latest_ch_mtime = max(os.path.getmtime(c["filepath"]) for c in chapters)
    mp3_up_to_date = os.path.exists(output_mp3) and os.path.getsize(output_mp3) > 10000 and os.path.getmtime(output_mp3) >= latest_ch_mtime
    mp4_up_to_date = (not make_video) or (os.path.exists(output_mp4) and os.path.getsize(output_mp4) > 10000 and os.path.getmtime(output_mp4) >= latest_ch_mtime)

    if not force and mp3_up_to_date and mp4_up_to_date and os.path.exists(output_desc):
        dur = get_audio_duration(output_mp3)
        return {
            "title": title,
            "chapters_count": len(chapters),
            "total_duration": format_timestamp(dur),
            "mp3_path": output_mp3,
            "video_path": output_mp4 if make_video else None,
            "desc_path": output_desc,
            "cached": True
        }

    print(f"\n🎧 กำลังประมวลผล Audiobook: {title} (พบ {len(chapters)} ตอน)")

    # จำกัดจำนวนตอนในคลิปฟรีบน YouTube (Funnel Strategy: ปล่อยฟังฟรี 5 ตอนแรกเพื่อดึงคนไปอ่านต่อบน ReadAWrite / ซื้อ E-Book)
    max_free_chapters = int(os.environ.get("ANSRE_AUDIOBOOK_FREE_CHAPTERS", "5"))
    total_available_chapters = len(chapters)
    if max_free_chapters > 0 and len(chapters) > max_free_chapters:
        print(f"   🎯 [Funnel Mode] จำกัดคลิป YouTube ที่ {max_free_chapters}/{total_available_chapters} ตอนแรก เพื่อดึงคนอ่านเข้า ReadAWrite!")
        chapters = chapters[:max_free_chapters]

    # 1. คำนวณ Timestamps (ข้ามไฟล์เสียงที่เสีย/ความยาว 0 วินาที)
    current_time = 0.0
    timestamps = []
    valid_chapters = []
    filelist_path = os.path.join(EXPORTS_DIR, f"_temp_{safe_title}_list.txt")

    with open(filelist_path, "w", encoding="utf-8") as f_list:
        for ch in chapters:
            dur = get_audio_duration(ch["filepath"])
            if dur <= 0.5:
                print(f"   ⚠️ ข้ามไฟล์เสียงที่เสียหาย/ว่างเปล่า: {ch['filename']}")
                continue
            valid_chapters.append(ch)
            ts_str = format_timestamp(current_time)
            timestamps.append(f"{ts_str} ตอนที่ {ch['num']}")
            f_list.write(f"file '{os.path.abspath(ch['filepath'])}'\n")
            current_time += dur

    if len(valid_chapters) < 2:
        if os.path.exists(filelist_path):
            os.remove(filelist_path)
        print(f"   [!] ไฟล์เสียงที่ใช้งานได้มีน้อยเกินไป ({len(valid_chapters)} ตอน) — ข้ามเรื่อง '{title}'")
        return None

    total_duration_str = format_timestamp(current_time)
    timestamps_text = "\n".join(timestamps)
    print(f"   ⏱️ ความยาวรวมทั้งสิ้น: {total_duration_str}")

    # 2. Concat MP3 ด้วย ffmpeg
    if not mp3_up_to_date or force:
        print("   🔨 กำลังรวมไฟล์เสียง Master MP3...")
        cmd_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", filelist_path,
            "-c", "copy",
            output_mp3
        ]
        try:
            subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError as e:
            print(f"   [!] Concat error: {e.stderr.decode('utf-8', errors='ignore')}")
            if os.path.exists(filelist_path):
                os.remove(filelist_path)
            return None

    if os.path.exists(filelist_path):
        os.remove(filelist_path)

    # ดึงลิงก์ ReadAWrite อัตโนมัติจาก publish_ledger.json และ known_links
    raw_novel_link = ""
    ledger_fp = os.path.join(SB, "05_Active_Projects", "publish_ledger.json")
    if os.path.exists(ledger_fp):
        try:
            with open(ledger_fp, "r", encoding="utf-8") as lf:
                ldata = json.load(lf)
                for st_title, st_info in ldata.get("published_stories", {}).items():
                    clean_st = re.sub(r'[:\s_-]+', '', st_title)
                    clean_tt = re.sub(r'[:\s_-]+', '', title)
                    if clean_st and (clean_st in clean_tt or clean_tt in clean_st):
                        aid = st_info.get("article_id")
                        if aid:
                            raw_novel_link = f"https://www.readawrite.com/a/{aid}"
                            break
        except Exception:
            pass

    if not raw_novel_link:
        known_links = {
            "กระจกเงาคนตาย": "https://www.readawrite.com/a/e90bfef727e4730819e92444783d6850",
            "ร้านค้าเหนือโลก": "https://www.readawrite.com/a/e90bfef727e4730819e92444783d6850",
            "ยอดนักสืบสปีดรัน": "https://www.readawrite.com/a/084947f5c23530e03094cc84bb1364b5",
            "สมาคมประกันภัยลี้ลับ": "https://www.readawrite.com/a/f3624f7b4e09cde8fc524dff4f2fc4bd",
            "โลกแฟนตาซีอันเหนือจริง": "https://www.readawrite.com/a/d7b6b42256a73ff2c99dee9291b23c2e",
        }
        for kn_name, kn_url in known_links.items():
            if kn_name in title:
                raw_novel_link = kn_url
                break

    raw_link_section = f"\n🔥 อ่านต่อตอนที่ {len(valid_chapters) + 1}–{max(total_available_chapters, len(valid_chapters) + 5)} ก่อนใครได้ที่ ReadAWrite (คลิกเลย!):\n👉 {raw_novel_link}\n" if raw_novel_link else f"\n🔥 อ่านต่อรายตอนบน ReadAWrite / Dek-D: ค้นหาชื่อ \"{title}\" (นามปากกา: เงาพันจันทร์)\n"

    desc_content = f"""🎧 {title} — รวมตอนที่ 1–{len(valid_chapters)} (Highlight Audiobook ฟังต่อเนื่อง)
ฟังนิยายเสียงคุณภาพ บรรยายลื่นไหล สนุก ตื่นเต้น เหมาะสำหรับฟังตอนทำงาน ฟังก่อนนอน หรือเดินทาง
{raw_link_section}
⏱️ สารบัญเลือกตอน (Chapters):
{timestamps_text}

---
📖 ช่องทางติดตามอ่านฉบับเต็ม & สนับสนุน E-Book (นามปากกา: เงาพันจันทร์):
{raw_link_section}
📚 ดาวน์โหลด E-Book เล่มเต็ม (อ่านรวดเดียวจบ + ตอนพิเศษ) บน Meb Market:
👉 ค้นหาชื่อเรื่อง "{title}" หรือนามปากกา "เงาพันจันทร์"

✨ ผลิตและสร้างสรรค์โดย: ANSRE Studio & NovelMind (เงาพันจันทร์)
กดติดตาม (Subscribe) และกดกระดิ่งแจ้งเตือน เพื่อไม่พลาดตอนใหม่และนิยายเรื่องใหม่ทุกวัน!

#นิยายเสียง #หนังสือนิยาย #นิยายเสียงก่อนนอน #{title.replace(' ', '')} #Audiobook #นิยายแฟนตาซี #เงาพันจันทร์
"""
    with open(output_desc, "w", encoding="utf-8") as df:
        df.write(desc_content)

    # 4. สร้างวิดีโอ YouTube Long-Form (สร้างภาพปก High-CTR 16:9 อัตโนมัติ)
    cover_fp = find_cover_image(title)
    thumb_16x9 = generate_high_ctr_16x9_cover(title, cover_fp) if cover_fp else None
    video_created = os.path.exists(output_mp4) and os.path.getsize(output_mp4) > 10000
    video_input_img = thumb_16x9 or cover_fp
    if make_video and video_input_img and os.path.exists(video_input_img) and (not mp4_up_to_date or force):
        print(f"   🎬 กำลังเรนเดอร์ YouTube Long-Form Video 1080p (High-CTR ปก 16:9: {os.path.basename(video_input_img)})...")
        cmd_video = [
            "ffmpeg", "-y",
            "-framerate", "1", "-loop", "1", "-i", video_input_img,
            "-i", output_mp3,
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
            "-r", "1",
            "-c:a", "copy",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
            "-shortest",
            output_mp4
        ]
        try:
            subprocess.run(cmd_video, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
            video_created = True
            print(f"   ✅ สร้างวิดีโอสำเร็จ: {output_mp4}")
        except subprocess.CalledProcessError as e:
            print(f"   [!] Render video error: {e.stderr.decode('utf-8', errors='ignore')}")

    print(f"   ✅ รวมเสียงสำเร็จ: {output_mp3}")
    print(f"   📝 บันทึกคำบรรยาย YouTube: {output_desc}")

    return {
        "title": title,
        "chapters_count": len(valid_chapters),
        "total_duration": total_duration_str,
        "mp3_path": output_mp3,
        "video_path": output_mp4 if video_created else None,
        "desc_path": output_desc,
        "thumbnail_path": thumb_16x9
    }


def package_all_audiobooks():
    """รวบรวมและสร้าง Audiobook สำหรับทุกเรื่องที่มีไฟล์เสียงอย่างน้อย 3 ตอน"""
    files = glob.glob(os.path.join(AUDIO_DIR, "*.mp3"))
    titles = set()
    for fp in files:
        fn = os.path.basename(fp)
        m = re.match(r"^(.*?)_(?:Audiobook|Chapter)_\d+\.mp3$", fn)
        if m:
            titles.add(m.group(1))

    completed = []
    print(f"[*] พบ {len(titles)} เรื่องที่มีไฟล์เสียง — กำลังประมวลผล...")
    for t in sorted(titles):
        chs = find_audio_chapters(t)
        if len(chs) >= 3:
            res = package_story_audiobook(t, make_video=True)
            if res:
                completed.append(res)

    summary_file = os.path.join(EXPORTS_DIR, "audiobooks_catalog.json")
    with open(summary_file, "w", encoding="utf-8") as sf:
        json.dump(completed, sf, ensure_ascii=False, indent=2)

    print(f"\n🎉 ประมวลผล Audiobook เสร็จสิ้น {len(completed)} เรื่อง! สรุปไว้ที่ {summary_file}")


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if "--all" in args:
        package_all_audiobooks()
    elif args:
        package_story_audiobook(args[0], make_video=True)
    else:
        print("Usage: python audiobook_packager.py <ชื่อเรื่อง> หรือ --all")
