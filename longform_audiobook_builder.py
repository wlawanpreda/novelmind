"""
ANSRE Long-form Audiobook Builder
=================================
รวบรวมไฟล์เสียงนิยายรายตอน (Chapter Audiobooks 1-5 หรือ 1-10)
มาต่อกันเป็นวิดีโอยาว 20–40 นาที สำหรับลง YouTube Long-form
พร้อมสร้าง Timestamps (สารบัญเวลา) อัตโนมัติ เพื่อดึงดูดคนฟังยาว / ฟังสมาธิ / ฟังก่อนนอน
"""

import os
import re
import glob
import subprocess
from datetime import timedelta
from typing import List, Dict, Optional

import json

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
AUDIO_DIR = os.path.join(SB, "05_Active_Projects", "Audio_Output")
COVERS_DIR = os.path.join(SB, "05_Active_Projects", "Covers")
LONGFORM_DIR = os.path.join(SB, "05_Active_Projects", "Longform_Output")


def get_readawrite_link(stem: str) -> str:
    """ค้นหาลิงก์ตรงของหน้านิยายบน ReadAWrite จากชื่อเรื่อง"""
    clean_stem = re.sub(r"[\s_:：]+", "", stem)
    ledger_p = os.path.join(SB, "05_Active_Projects", "publish_ledger.json")
    if os.path.exists(ledger_p):
        try:
            with open(ledger_p, "r", encoding="utf-8") as f:
                led = json.load(f)
                for k, v in led.get("published_stories", {}).items():
                    clean_k = re.sub(r"[\s_:：]+", "", k)
                    if clean_k in clean_stem or clean_stem in clean_k:
                        aid = v.get("article_id")
                        if aid:
                            return f"https://www.readawrite.com/a/{aid}"
        except Exception:
            pass
    raw_stats_p = os.path.join(SB, "readawrite_current_stats.json")
    if os.path.exists(raw_stats_p):
        try:
            with open(raw_stats_p, "r", encoding="utf-8") as f:
                for a in json.load(f):
                    t = re.sub(r"[\s_:：]+", "", a.get("title", ""))
                    if t and (t in clean_stem or clean_stem in t):
                        aid = a.get("aid")
                        if aid:
                            return f"https://www.readawrite.com/a/{aid}"
        except Exception:
            pass
    return ""


def get_audio_duration_sec(path: str) -> float:
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, check=True
        )
        return float(res.stdout.strip())
    except Exception:
        return 0.0

def format_timestamp(sec: float) -> str:
    td = timedelta(seconds=int(sec))
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if td.days > 0 or hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"

def find_chapters_for_story(stem: str) -> List[Dict]:
    pattern = os.path.join(AUDIO_DIR, f"{stem}_Audiobook_*.mp3")
    files = glob.glob(pattern)
    chapters = []
    for fp in files:
        m = re.search(r"Audiobook_(\d+)", fp)
        if m:
            ep = int(m.group(1))
            dur = get_audio_duration_sec(fp)
            title = f"ตอนที่ {ep}"
            ch_md = os.path.join(SB, "05_Active_Projects", "Chapters", f"{stem}_Chapter_{ep:02d}.md")
            if not os.path.exists(ch_md):
                ch_md = os.path.join(SB, "05_Active_Projects", "Chapters", f"{stem}_Chapter_{ep}.md")
            if os.path.exists(ch_md):
                try:
                    with open(ch_md, "r", encoding="utf-8") as f:
                        for line in f:
                            tm = re.search(r"ตอนที่\s*\d+\s*[:：\s]\s*([^\n\r#\(\)]+)", line)
                            if tm:
                                sub = tm.group(1).strip()
                                if sub:
                                    title = f"ตอนที่ {ep}: {sub}"
                                break
                except Exception:
                    pass
            chapters.append({"ep": ep, "path": fp, "duration": dur, "title": title})

    return sorted(chapters, key=lambda x: x["ep"])

def compile_longform_audiobook(stem: str, max_eps: int = 5) -> Optional[Dict]:
    os.makedirs(LONGFORM_DIR, exist_ok=True)
    chapters = find_chapters_for_story(stem)
    if not chapters:
        print(f"[-] No audio chapters found for '{stem}'")
        return None

    selected = chapters[:max_eps]
    first_ep = selected[0]["ep"]
    last_ep = selected[-1]["ep"]
    story_display = stem.replace("_", " ").strip()

    print(f"[*] Compiling Long-form Audiobook for '{story_display}' (EP {first_ep}–{last_ep})...")

    concat_list_path = os.path.join(LONGFORM_DIR, f"{stem}_concat.txt")
    combined_audio_path = os.path.join(LONGFORM_DIR, f"{stem}_Compilation_EP{first_ep:02d}_{last_ep:02d}.mp3")

    timestamps = []
    current_time = 0.0

    with open(concat_list_path, "w", encoding="utf-8") as f:
        for ch in selected:
            ts_str = format_timestamp(current_time)
            timestamps.append(f"{ts_str} {ch['title']}")
            f.write(f"file '{os.path.abspath(ch['path'])}'\n")
            current_time += ch["duration"]

    print(f"    Total duration: {format_timestamp(current_time)}")
    print("    Timestamps generated:")
    for ts in timestamps:
        print(f"      {ts}")

    cmd_concat = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list_path, "-c", "copy", combined_audio_path
    ]
    subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    try:
        os.remove(concat_list_path)
    except Exception:
        pass

    cover_candidates = [
        os.path.join(COVERS_DIR, f"{stem}_Cover.png"),
        os.path.join(COVERS_DIR, f"{stem}_Cover.jpg"),
        os.path.join(COVERS_DIR, f"{stem}.png"),
        os.path.join(COVERS_DIR, f"{stem}.jpg"),
    ]
    cover_path = next((c for c in cover_candidates if os.path.exists(c)), None)

    output_video_path = os.path.join(LONGFORM_DIR, f"{stem}_Longform_EP{first_ep:02d}_{last_ep:02d}.mp4")

    if cover_path:
        print(f"[*] Rendering 16:9 YouTube Long-form Video with Ambient Waves...")
        filter_complex = (
            "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
            "boxblur=20:10,eq=brightness=-0.15[bg];"
            "[0:v]scale=-1:960[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
            "[1:a]showwaves=s=1920x160:mode=line:colors=0xFFD700:rate=25,colorkey=black:0.01:0.01[wave];"
            "[base][wave]overlay=0:920[outv]"
        )

        cmd_video = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", cover_path,
            "-i", combined_audio_path,
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "1:a",
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_video_path
        ]
        try:
            subprocess.run(cmd_video, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            print(f"  ✅ Video rendered: {output_video_path}")
        except Exception as e:
            print(f"  [!] Failed to render video: {e}")
            output_video_path = None

    raw_link = get_readawrite_link(stem)
    desc = []
    if raw_link:
        desc.extend([
            f"👉 อ่านฉบับเต็มฟรีครบทุกตอนก่อนใครคลิก: {raw_link}",
            f"❤️ ฝากกดหัวใจ + เพิ่มเข้าชั้นหนังสือใน ReadAWrite ด้วยนะครับ!",
            ""
        ])
    desc.extend([
        f"🎧 นิยายเสียง: {story_display} (รวม EP {first_ep}–{last_ep} ฟังยาวต่อเนื่องก่อนนอน)",
        "",
        "⏱️ สารบัญตอน (Timestamps):",
    ])
    desc.extend(timestamps)
    desc.extend([
        "",
        f"🔗 อ่านฉบับเต็มและตอนต่อไปก่อนใครได้ที่ ReadAWrite: {raw_link}" if raw_link else "🔗 อ่านฉบับเต็มและตอนต่อไปก่อนใครได้ที่ ReadAWrite",
        "⚡ ฝากกด Like & กด Subscribe ช่อง 'Midnight Tales · มิดไนท์เทล' เพื่อติดตามตอนใหม่ทุกวันครับ!",
        "",
        "#นิยายเสียง #นิยายเสียงจบในตอน #ฟังก่อนนอน #นิยายแปล #หนังสือเสียง #นิยาย #สปีดรัน #เรื่องเล่า"
    ])

    # ชูจุดขาย winning formula ใน title
    win_title = f"นิยายเสียง: {story_display} รวมตอนที่ {first_ep}–{last_ep} (ฟังยาวต่อเนื่องก่อนนอน) [อ่านฟรี]"
    if len(win_title) > 95:
        win_title = f"นิยายเสียง: {story_display} รวมตอนที่ {first_ep}–{last_ep} (ฟังต่อเนื่องก่อนนอน)"

    result = {
        "stem": stem,
        "title": win_title,
        "description": "\n".join(desc),
        "audio_path": combined_audio_path,
        "video_path": output_video_path,
        "timestamps": timestamps,
        "duration_sec": current_time,
        "readawrite_url": raw_link
    }
    return result

if __name__ == "__main__":
    import sys
    story = sys.argv[1] if len(sys.argv) > 1 else "ดาบไร้พระเจ้า_วงจรเวลาแห่งโชคชะตา"
    res = compile_longform_audiobook(story, max_eps=5)
    if res:
        print("\n=== Compilation Summary ===")
        print(f"Title: {res['title']}")
        print(f"Audio: {res['audio_path']}")
        print(f"Video: {res['video_path']}")
