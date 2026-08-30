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
    """หาภาพปกที่มีคุณภาพดีที่สุด"""
    candidates = [
        f"{title}_Cover_captioned.jpg",
        f"{title}_Cover.jpg",
        f"{title}_Cover.png",
        f"{title}.jpg"
    ]
    for fn in candidates:
        fp = os.path.join(COVERS_DIR, fn)
        if os.path.exists(fp) and os.path.getsize(fp) > 1000:
            return fp
    matches = glob.glob(os.path.join(COVERS_DIR, f"*{title}*Cover*.*"))
    if matches:
        return sorted(matches)[0]
    # Fuzzy match by key terms or sliding substrings
    if os.path.exists(COVERS_DIR):
        all_covers = [f for f in os.listdir(COVERS_DIR) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        # Check 4-character chunks from title
        for i in range(max(1, len(title) - 3)):
            chunk = title[i:i+4]
            for cf in all_covers:
                if chunk in cf and "Cover" in cf:
                    return os.path.join(COVERS_DIR, cf)
    return None


def package_story_audiobook(title: str, make_video: bool = True) -> Optional[Dict[str, Any]]:
    """รวมตอนเสียง สร้าง Master MP3 และ YouTube Long-Form Video"""
    chapters = find_audio_chapters(title)
    if not chapters:
        print(f"[!] ไม่พบไฟล์เสียงของเรื่อง '{title}'")
        return None

    safe_title = re.sub(r'[^\w\-_\s฀-๿]', '', title).strip().replace(' ', '_')
    output_mp3 = os.path.join(EXPORTS_DIR, f"{safe_title}_Full_Audiobook.mp3")
    output_desc = os.path.join(EXPORTS_DIR, f"{safe_title}_YouTube_Description.txt")
    output_mp4 = os.path.join(EXPORTS_DIR, f"{safe_title}_Audiobook_Video.mp4")

    print(f"\n🎧 กำลังประมวลผล Audiobook: {title} (พบ {len(chapters)} ตอน)")

    # 1. คำนวณ Timestamps
    current_time = 0.0
    timestamps = []
    filelist_path = os.path.join(EXPORTS_DIR, f"_temp_{safe_title}_list.txt")

    with open(filelist_path, "w", encoding="utf-8") as f_list:
        for ch in chapters:
            dur = get_audio_duration(ch["filepath"])
            ts_str = format_timestamp(current_time)
            timestamps.append(f"{ts_str} ตอนที่ {ch['num']}")
            # เขียนสำหรับ ffmpeg concat
            f_list.write(f"file '{os.path.abspath(ch['filepath'])}'\n")
            current_time += dur

    total_duration_str = format_timestamp(current_time)
    print(f"   ⏱️ ความยาวรวมทั้งสิ้น: {total_duration_str}")

    # 2. Concat MP3 ด้วย ffmpeg
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

    # 3. สร้าง YouTube Description พร้อม Timestamps
    timestamps_text = "\n".join(timestamps)
    desc_content = f"""🎧 {title} — รวมทุกตอนจบภาค (Full Audiobook)
ฟังนิยายเสียงคุณภาพ บรรยายลื่นไหล สนุก ตื่นเต้น เหมาะสำหรับฟังตอนทำงาน ฟังก่อนนอน หรือเดินทาง

⏱️ สารบัญเลือกตอน (Chapters):
{timestamps_text}

---
📖 สำหรับท่านที่ต้องการอ่านบทความฉบับเต็ม หรือสนับสนุนผลงาน E-Book:
• E-Book เล่มเต็มบน Meb Market: ค้นหาชื่อ "{title}"
• อ่านรายตอนบน ReadAWrite / Dek-D: ค้นหาชื่อ "{title}"

✨ ผลิตและสร้างสรรค์โดย: ANSRE Studio & NovelMind
กดติดตาม (Subscribe) และกดกระดิ่งแจ้งเตือน เพื่อไม่พลาดตอนใหม่และนิยายเรื่องใหม่ๆ!

#นิยายเสียง #หนังสือนิยาย #นิยายเสียงก่อนนอน #{title.replace(' ', '')} #Audiobook #นิยายแฟนตาซี
"""
    with open(output_desc, "w", encoding="utf-8") as df:
        df.write(desc_content)

    # 4. สร้างวิดีโอ YouTube Long-Form (ถ้ามีภาพปก)
    cover_fp = find_cover_image(title)
    video_created = False
    if make_video and cover_fp and os.path.exists(cover_fp):
        print(f"   🎬 กำลังเรนเดอร์ YouTube Long-Form Video 1080p (ภาพปก: {os.path.basename(cover_fp)})...")
        cmd_video = [
            "ffmpeg", "-y",
            "-framerate", "1", "-loop", "1", "-i", cover_fp,
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
        "chapters_count": len(chapters),
        "total_duration": total_duration_str,
        "mp3_path": output_mp3,
        "video_path": output_mp4 if video_created else None,
        "desc_path": output_desc
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
