#!/usr/bin/env python3
"""
dynamic_promo_video_engine.py — Viral Short-Form Video Producer (TikTok / Reels / YouTube Shorts)
=================================================================================================
ระบบผลิตวิดีโอโปรโมทแนวตั้ง (9:16 - 1080x1920) ความยาว 30-50 วินาที
โดดเด่นด้วย:
1. Top Viral Hook Banner: ป้ายพาดหัวสีสดกระตุ้นความสนใจใน 3 วินาทีแรก (Thumb-Stop Rate)
2. Kinetic Subtitles: ตัวหนังสือภาษาไทยขนาดใหญ่ อ่านง่าย พร้อมกรอบเรืองแสง
3. Animated Audio Waveform: คลื่นเสียงแบบเรียลไทม์ผ่าน FFmpeg
4. Actionable CTA Outro: ป้ายปิดท้ายดึงคนตามไปอ่านเต็มเรื่องบน ReadAWrite / Dek-D
"""

from __future__ import annotations

import os
import sys
import re
import glob
import subprocess
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
SECOND_BRAIN = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AUDIO_DIR = os.path.join(SECOND_BRAIN, "05_Active_Projects", "Audio_Output")
COVERS_DIR = os.path.join(SECOND_BRAIN, "05_Active_Projects", "Covers")
PROMO_OUTPUT_DIR = os.path.join(SECOND_BRAIN, "05_Active_Projects", "Promo_Shorts")
os.makedirs(PROMO_OUTPUT_DIR, exist_ok=True)

# ตรวจสอบฟอนต์ภาษาไทย
_THAI_FONT = "/System/Library/Fonts/Supplemental/Thonburi.ttc"
if not os.path.exists(_THAI_FONT):
    _THAI_FONT = "/System/Library/Fonts/ThonburiUI.ttc"
if not os.path.exists(_THAI_FONT):
    _THAI_FONT = "Arial"


def get_thai_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    try:
        idx = 1 if bold else 0
        return ImageFont.truetype(_THAI_FONT, size, index=idx)
    except Exception:
        try:
            return ImageFont.truetype(_THAI_FONT, size, index=0)
        except Exception:
            return ImageFont.load_default()


def parse_srt_subtitles(srt_path: str, max_duration_sec: float = 45.0) -> List[Dict[str, Any]]:
    """อ่านไฟล์ .srt และตัดเฉพาะช่วง Hook 30-45 วินาทีแรก"""
    if not os.path.exists(srt_path):
        return []

    with open(srt_path, "r", encoding="utf-8") as f:
        text = f.read()

    blocks = text.strip().split("\n\n")
    subs = []
    for b in blocks:
        lines = b.strip().split("\n")
        if len(lines) >= 3:
            time_match = re.search(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", lines[1])
            if time_match:
                sh, sm, ss, sms = map(int, time_match.groups()[:4])
                eh, em, es, ems = map(int, time_match.groups()[4:])
                start_sec = sh * 3600 + sm * 60 + ss + sms / 1000.0
                end_sec = eh * 3600 + em * 60 + es + ems / 1000.0
                content = " ".join(lines[2:]).strip()

                if start_sec < max_duration_sec:
                    subs.append({
                        "start": start_sec,
                        "end": min(end_sec, max_duration_sec),
                        "text": content
                    })
    return subs


def create_vertical_promo_frame(
    cover_path: str,
    story_title: str,
    hook_tag: str,
    out_frame_path: str
) -> str:
    """สร้างภาพเฟรมแนวตั้ง 9:16 (1080x1920) สไตล์ TikTok/Reels Viral Promo"""
    W, H = 1080, 1920
    
    # 1. โหลดภาพปก
    if cover_path and os.path.exists(cover_path):
        src = Image.open(cover_path).convert("RGB")
    else:
        src = Image.new("RGB", (600, 800), (30, 20, 45))

    sw, sh = src.size

    # 2. พื้นหลังเบลอเต็มจอ (Full Canvas Gaussian Blur)
    scale_bg = max(W / sw, H / sh)
    bg = src.resize((int(sw * scale_bg) + 2, int(sh * scale_bg) + 2))
    bx, by = (bg.width - W) // 2, (bg.height - H) // 2
    bg = bg.crop((bx, by, bx + W, by + H)).filter(ImageFilter.GaussianBlur(38))
    
    # ซ้อน Gradient มืดด้านบนและล่าง เพื่อให้อ่านซับไตเติลชัดเจน
    dark = Image.new("RGB", (W, H), (12, 10, 18))
    canvas = Image.blend(bg, dark, 0.65)

    draw = ImageDraw.Draw(canvas, "RGBA")

    # 3. Top Banner: ป้ายเตือนความสนใจ (Viral Hook Badge)
    banner_y = 120
    draw.rounded_rectangle([60, banner_y, W - 60, banner_y + 85], radius=20, fill=(255, 45, 85, 240))
    badge_font = get_thai_font(38, bold=True)
    draw.text((W // 2, banner_y + 42), f"🚨 {hook_tag}", font=badge_font, fill="#FFFFFF", anchor="mm")

    # 4. Center: ภาพปกแบบ 3:4 ลอยเด่นพร้อมเงาขอบนีออน
    cover_h = 760
    cover_w = int(cover_h * (sw / sh))
    if cover_w > 640:
        cover_w = 640
    cover_x = (W - cover_w) // 2
    cover_y = banner_y + 130

    fg = src.resize((cover_w, cover_h), Image.Resampling.LANCZOS)
    
    # เงาเรืองแสงสีทอง/ชมพูรอบปก
    glow_box = Image.new("RGBA", (cover_w + 30, cover_h + 30), (255, 215, 0, 80))
    canvas.paste(glow_box, (cover_x - 15, cover_y - 15), mask=glow_box)
    canvas.paste(fg, (cover_x, cover_y))

    # กรอบเส้นบางหรูหรา
    draw.rectangle([cover_x, cover_y, cover_x + cover_w, cover_y + cover_h], outline=(255, 215, 0, 200), width=3)

    # 5. ป้ายชื่อเรื่องใต้ภาพปก
    title_font = get_thai_font(42, bold=True)
    clean_title = story_title.replace("_", " ")
    if len(clean_title) > 28:
        clean_title = clean_title[:28] + "..."
    draw.text((W // 2, cover_y + cover_h + 45), clean_title, font=title_font, fill="#FFD700", anchor="mm")

    # 6. กรอบพื้นที่คลื่นเสียง (Waveform Area)
    wave_box_y = cover_y + cover_h + 90
    draw.rounded_rectangle([80, wave_box_y, W - 80, wave_box_y + 100], radius=15, fill=(20, 24, 38, 220), outline=(0, 229, 255, 180), width=2)
    wave_font = get_thai_font(26)
    draw.text((W // 2, wave_box_y + 25), "🎙️ สปอยล์เนื้อเรื่องสุดเข้มข้น • สวมหูฟังเพื่ออรรถรส", font=wave_font, fill="#00E5FF", anchor="mm")

    # 7. Subtitle Area Box (พื้นที่รองรับซับไตเติลเด้ง)
    sub_box_y = wave_box_y + 130
    draw.rounded_rectangle([60, sub_box_y, W - 60, sub_box_y + 240], radius=20, fill=(0, 0, 0, 180), outline=(255, 255, 255, 60), width=2)

    # 8. Bottom CTA Banner (ดึงคนเข้า ReadAWrite / Dek-D)
    cta_y = H - 150
    draw.rounded_rectangle([60, cta_y, W - 60, cta_y + 90], radius=25, fill=(16, 185, 129, 245))
    cta_font = get_thai_font(34, bold=True)
    draw.text((W // 2, cta_y + 45), "📖 อ่านฟรีจนจบเรื่องบน ReadAWrite & Dek-D", font=cta_font, fill="#FFFFFF", anchor="mm")

    canvas.save(out_frame_path, quality=95)
    print(f"  ✅ สร้าง Vertical Frame 9:16 สำเร็จ: {out_frame_path}")
    return out_frame_path


def render_dynamic_promo_video(
    story_query: str,
    duration_sec: float = 35.0,
    hook_tag: str = "นิยายยอดฮิตติดชาร์ตอันดับ 1!"
) -> Optional[str]:
    """เรนเดอร์คลิปวิดีโอโปรโมท TikTok/Shorts (9:16) พร้อมเสียง Waveform และซับไตเติล"""
    # 1. ค้นหาภาพปก
    cover_candidates = glob.glob(os.path.join(COVERS_DIR, f"*{story_query}*.jpg")) + \
                       glob.glob(os.path.join(COVERS_DIR, f"*{story_query.replace(' ', '_')}*.jpg"))
    cover_path = cover_candidates[0] if cover_candidates else ""

    # 2. ค้นหาไฟล์เสียง Audiobook และซับไตเติล
    audio_cands = glob.glob(os.path.join(AUDIO_DIR, f"*{story_query}*Audiobook_01.mp3")) + \
                  glob.glob(os.path.join(AUDIO_DIR, f"*{story_query.replace(' ', '_')}*Audiobook_01.mp3"))
    if not audio_cands:
        # fallback ค้นหาไฟล์แรกที่มี
        audio_cands = glob.glob(os.path.join(AUDIO_DIR, f"*{story_query}*.mp3"))
    
    if not audio_cands:
        print(f"❌ ไม่พบไฟล์เสียงสำหรับ '{story_query}' ใน {AUDIO_DIR}")
        return None

    audio_path = audio_cands[0]
    srt_candidates = glob.glob(audio_path.replace(".mp3", ".srt"))
    srt_path = srt_candidates[0] if srt_candidates else ""

    clean_name = os.path.basename(audio_path).replace("_Audiobook_01.mp3", "").replace(".mp3", "")
    out_frame_img = os.path.join(PROMO_OUTPUT_DIR, f"{clean_name}_vertical_frame.png")
    out_video_mp4 = os.path.join(PROMO_OUTPUT_DIR, f"{clean_name}_PROMO_SHORTS.mp4")

    print(f"\n🎬 กำลังสร้างวิดีโอโปรโมทสั้น (Vertical Shorts 9:16): '{clean_name}'")
    print(f"   • ไฟล์เสียง: {os.path.basename(audio_path)}")
    print(f"   • ความยาว Teaser: {duration_sec} วินาที")

    # สร้าง Frame ภาพนิ่ง
    create_vertical_promo_frame(cover_path, clean_name, hook_tag, out_frame_img)

    # 3. สร้าง Filter Complex สำหรับ FFmpeg (เรนเดอร์ Waveform ตรงตำแหน่งกล่อง)
    # กล่องคลื่นเสียงอยู่ที่ y=1340, ความกว้าง 840, สูง 70
    filter_complex = (
        f"[1:a]atrim=0:{duration_sec},showwaves=s=860x65:mode=cline:colors=0x00E5FF:rate=25,colorkey=black:0.01:0.01[wave];"
        f"[0:v][wave]overlay=110:1360[outv]"
    )

    # ถ้ามีไฟล์ซับไตเติล ให้เพิ่ม drawtext หรือ subtitles filter
    if srt_path and os.path.exists(srt_path):
        # ใช้วิธีแปลงเป็น subtitles filter
        filter_complex = (
            f"[1:a]atrim=0:{duration_sec},showwaves=s=860x65:mode=cline:colors=0x00E5FF:rate=25,colorkey=black:0.01:0.01[wave];"
            f"[0:v][wave]overlay=110:1360[v1];"
            f"[v1]subtitles='{srt_path}':force_style='FontName=Thonburi,FontSize=28,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Alignment=2,MarginV=360'[outv]"
        )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", out_frame_img,
        "-i", audio_path,
        "-t", str(duration_sec),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        out_video_mp4
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"⚠️ FFmpeg subtitle filter fallback, rendering standard wave...")
            # Fallback ไม่ใส่ซับไตเติลถ้า fontconfig มีปัญหา
            fallback_filter = (
                f"[1:a]atrim=0:{duration_sec},showwaves=s=860x65:mode=cline:colors=0x00E5FF:rate=25,colorkey=black:0.01:0.01[wave];"
                f"[0:v][wave]overlay=110:1360[outv]"
            )
            cmd[cmd.index("-filter_complex") + 1] = fallback_filter
            subprocess.run(cmd, check=True)

        print(f"\n🎉 ผลิตวิดีโอโปรโมทสำเร็จ (Ready for TikTok/Shorts/Reels):")
        print(f"   📹 {out_video_mp4} ({os.path.getsize(out_video_mp4) / (1024*1024):.1f} MB)")
        return out_video_mp4

    except Exception as e:
        print(f"❌ เรนเดอร์วิดีโอล้มเหลว: {e}")
        return None


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "คุณแม่ลูกแฝด"
    render_dynamic_promo_video(q)
