"""
episode_video_builder.py — High-Retention 3-5 Minute YouTube Audiobook Video Generator
======================================================================================
ผลิตวิดีโอนิยายเสียงสำหรับ YouTube ความยาว 3-5 นาที (หรือ Shorts 2:30-2:55 นาที):
1. Layout สวยงาม: ภาพปกคมชัด + พื้นหลังเบลอเรืองแสง + ตราสัญลักษณ์ช่อง "เงาพันจันทร์"
2. Audio Waveform แบบเคลื่อนไหวเรียลไทม์ (FFmpeg showwaves) สีฟ้า/ทองเรืองแสง
3. ป้ายชื่อตอนและ Hook สะดุดตา ดึงดูดสายตาคนฟัง
4. รองรับทั้งสัดส่วน 16:9 แนวนอน (Full Episode สะสม Watch Time) และ 9:16 แนวตั้ง (Shorts Viral Reach)
"""

import os
import sys
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

_THAI_FONT = "/System/Library/Fonts/Supplemental/Thonburi.ttc"
if not os.path.exists(_THAI_FONT):
    _THAI_FONT = "/System/Library/Fonts/ThonburiUI.ttc"
if not os.path.exists(_THAI_FONT):
    _THAI_FONT = "Arial"

def get_thai_font(size: int):
    try:
        return ImageFont.truetype(_THAI_FONT, size, index=0)
    except Exception:
        return ImageFont.load_default()

def create_landscape_frame(cover_path: str, story_title: str, episode_title: str, out_img_path: str):
    """สร้างภาพพื้นหลังสำหรับวิดีโอ 16:9 (1920x1080) พร้อมปกคมชัดและป้ายชื่อเรื่อง"""
    W, H = 1920, 1080
    src = Image.open(cover_path).convert("RGB")
    
    # 1. พื้นหลัง: ขยายเต็มจอแล้วเบลอ 32px + มืด 50%
    sw, sh = src.size
    scale_bg = max(W / sw, H / sh)
    bg = src.resize((int(sw * scale_bg) + 1, int(sh * scale_bg) + 1))
    bx, by = (bg.width - W) // 2, (bg.height - H) // 2
    bg = bg.crop((bx, by, bx + W, by + H)).filter(ImageFilter.GaussianBlur(32))
    dark = Image.new("RGB", (W, H), (10, 12, 18))
    canvas = Image.blend(bg, dark, 0.55)

    # 2. ปกคมชัด: วางฝั่งซ้าย (สัดส่วน 3:4 ขนาดความสูง 840px)
    cover_h = 840
    cover_w = int(cover_h * (sw / sh))
    fg = src.resize((cover_w, cover_h), Image.Resampling.LANCZOS)
    
    # เงาหลังปก
    shadow = Image.new("RGBA", (cover_w + 40, cover_h + 40), (0, 0, 0, 180))
    canvas.paste(shadow, (100, (H - cover_h) // 2 - 10), mask=shadow)
    canvas.paste(fg, (120, (H - cover_h) // 2))

    # 3. ข้อมูลและ Typography ฝั่งขวา
    draw = ImageDraw.Draw(canvas, "RGBA")
    text_x = 120 + cover_w + 80
    
    # Badge ช่อง
    badge_f = get_thai_font(30)
    draw.rounded_rectangle([text_x, 180, text_x + 360, 235], radius=10, fill=(255, 51, 102, 230))
    draw.text((text_x + 20, 190), "นิยายเสียงโดย เงาพันจันทร์", font=badge_f, fill="#FFFFFF")

    # ชื่อเรื่องหลัก
    title_f = get_thai_font(58)
    draw.text((text_x, 265), story_title, font=title_f, fill="#FFFFFF")

    # ชื่อตอน
    ep_f = get_thai_font(44)
    draw.text((text_x, 350), episode_title, font=ep_f, fill="#FFD700")

    # แท็กฟังสบาย / สะสมเวลา
    tag_f = get_thai_font(28)
    draw.text((text_x, 445), "• ฟังเพลินต่อเนื่อง 3-5 นาที  • บรรยายไทยเต็มอารมณ์", font=tag_f, fill="#E0E0E0")
    draw.text((text_x, 490), "• อ่านฟรีจนจบเรื่องบน ReadAWrite", font=tag_f, fill="#AAAAAA")

    # บล็อกบอกคลื่นเสียงด้านล่าง
    draw.rounded_rectangle([text_x, 680, text_x + 600, 725], radius=8, fill=(30, 35, 50, 200), outline=(0, 229, 255, 180), width=2)
    draw.text((text_x + 20, 688), "Audio Visualizer Sync", font=tag_f, fill="#00E5FF")

    canvas.save(out_img_path, quality=95)
    print(f"  Generated landscape frame with crisp Thai text: {out_img_path}")

def render_episode_video(frame_img_path: str, audio_path: str, output_mp4: str, duration_sec: float = None):
    """ประกอบวิดีโอ 16:9 พร้อมคลื่นเสียง Waveform เคลื่อนไหวด้วย FFmpeg"""
    print(f"  Rendering MP4 video with animated waveform: {output_mp4}...")
    
    filter_complex = (
        "[1:a]showwaves=s=880x140:mode=cline:colors=0x00E5FF:rate=25,colorkey=black:0.01:0.01[wave];"
        "[0:v][wave]overlay=820:740[outv]"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", frame_img_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_mp4
    ]
    if duration_sec:
        cmd.extend(["-t", str(duration_sec)])
        
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"  FFmpeg Error: {res.stderr[-300:]}")
        return False
    print(f"  Successfully rendered: {output_mp4} ({os.path.getsize(output_mp4)} bytes)")
    return True

if __name__ == "__main__":
    cover = "SecondBrain/05_Active_Projects/Covers/เหล่ามือกระบี่ไร้แม่เหล็ก_Cover_3x4.jpg"
    audio = "SecondBrain/05_Active_Projects/Audio_Output/เหล่ามือกระบี่ไร้แม่เหล็ก_Audiobook_02.mp3"
    frame = "/Users/pj/.gemini/antigravity-cli/brain/70a1be55-3256-4d06-8736-bde9d8afa44d/youtube_episode_layout.jpg"
    
    create_landscape_frame(cover, "เหล่ามือกระบี่ไร้แม่เหล็ก", "ตอนที่ 2: ป่าโบราณ", frame)

def create_vertical_shorts_frame(cover_path: str, story_title: str, hook_text: str, out_img_path: str):
    """สร้างภาพพื้นหลังสำหรับ TikTok / YouTube Shorts 9:16 (1080x1920)"""
    W, H = 1080, 1920
    src = Image.open(cover_path).convert("RGB")
    
    # 1. พื้นหลังเบลอ
    sw, sh = src.size
    scale_bg = max(W / sw, H / sh)
    bg = src.resize((int(sw * scale_bg) + 1, int(sh * scale_bg) + 1))
    bx, by = (bg.width - W) // 2, (bg.height - H) // 2
    bg = bg.crop((bx, by, bx + W, by + H)).filter(ImageFilter.GaussianBlur(36))
    dark = Image.new("RGB", (W, H), (10, 12, 18))
    canvas = Image.blend(bg, dark, 0.50)

    # 2. ปกวางกลางเด่นชัด
    cover_w = 900
    cover_h = int(cover_w * (sh / sw))
    fg = src.resize((cover_w, cover_h), Image.Resampling.LANCZOS)
    fy = 420
    canvas.paste(fg, ((W - cover_w) // 2, fy))

    # 3. Typography หัวและท้าย
    draw = ImageDraw.Draw(canvas, "RGBA")
    
    # Badge หัวคลิป
    badge_f = get_thai_font(34)
    draw.rounded_rectangle([80, 160, W - 80, 240], radius=16, fill=(255, 45, 85, 240))
    draw.text((120, 175), "⚡ นิยายเสียงหักมุม 60 วินาที", font=badge_f, fill="#FFFFFF")

    # ชื่อเรื่อง
    title_f = get_thai_font(52)
    draw.text((80, 270), story_title, font=title_f, fill="#FFFFFF")

    # กล่อง Hook ท้ายคลิป
    draw.rounded_rectangle([80, 1500, W - 80, 1640], radius=16, fill=(20, 24, 35, 230), outline=(255, 215, 0, 200), width=3)
    hook_f = get_thai_font(32)
    draw.text((110, 1520), f"🔥 {hook_text}", font=hook_f, fill="#FFD700")
    draw.text((110, 1580), "👉 อ่านฟรีจนจบเรื่องที่ ReadAWrite: เงาพันจันทร์", font=get_thai_font(26), fill="#CCCCCC")

    canvas.save(out_img_path, quality=95)
    print(f"  Generated vertical shorts frame: {out_img_path}")

def render_vertical_shorts_video(frame_img_path: str, audio_path: str, output_mp4: str, duration_sec: float = None):
    """เรนเดอร์คลิปแนวตั้ง 9:16 พร้อมคลื่นเสียง Waveform สำหรับ TikTok / Shorts"""
    print(f"  Rendering Vertical Shorts MP4: {output_mp4}...")
    filter_complex = (
        "[1:a]showwaves=s=920x160:mode=cline:colors=0xFFD700:rate=25,colorkey=black:0.01:0.01[wave];"
        "[0:v][wave]overlay=80:1680[outv]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", frame_img_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_mp4
    ]
    if duration_sec:
        cmd.extend(["-t", str(duration_sec)])
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0:
        print(f"  Successfully rendered Shorts: {output_mp4}")
        return True
    return False
