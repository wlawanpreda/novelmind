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
import json
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


def wrap_thai_text(text: str, max_chars: int = 34) -> List[str]:
    lines = []
    for paragraph in text.split("\n"):
        p = paragraph.strip()
        if not p:
            continue
        while len(p) > max_chars:
            idx = p[:max_chars].rfind(" ")
            if idx == -1 or idx < max_chars // 2:
                idx = max_chars
            lines.append(p[:idx].strip())
            p = p[idx:].strip()
        if p:
            lines.append(p)
    return lines


AID_MAP = {
    "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70": "627d9707279484797acafaba010fcf69",
    "จากน้องสาวสู่พี่ใหญ่": "c9ba3d70c41e7b9e05e4d1110ec5b94e",
    "ผู้สาปแช่ง Chimera": "454f3980e21e630dc4891fa752796d58",
    "ฟาร์มสาวปีศาจรัก": "ac04dda030fae1380e3aa7ac52f66762",
    "ดวงจันทร์แห่งเวทมนตร์": "9e8c07991925a7993519a4d261fd6f2a",
    "วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์": "f5d5ec2e430ab0bbade7b02be1beb149",
    "ยอดนักสืบสปีดรัน": "084947f5c23530e03094cc84bb1364b5",
    "สมาคมประกันภัยลี้ลับ": "f3624f7b4e09cde8fc524dff4f2fc4bd",
    "สาวอภินิหารหัวใจเหล็ก": "2ac4e08e36403cb46241714ff5758789",
    "กระจกเงาคนตาย": "e90bfef727e4730819e92444783d6850",
}


def find_aid_for_query(query: str) -> str:
    clean_q = re.sub(r"[\s_:：]+", "", query)
    for k, aid in AID_MAP.items():
        clean_k = re.sub(r"[\s_:：]+", "", k)
        if clean_k in clean_q or clean_q in clean_k:
            return aid
    return ""


def create_vertical_promo_frame(
    cover_path: str,
    story_title: str,
    hook_tag: str,
    out_frame_path: str,
    quote_text: str = ""
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
    
    # ซ้อน Gradient มืดด้านบนและล่าง เพื่อให้อ่านข้อความชัดเจน
    dark = Image.new("RGB", (W, H), (12, 10, 18))
    canvas = Image.blend(bg, dark, 0.65)

    draw = ImageDraw.Draw(canvas, "RGBA")

    # 3. Top Banner: ป้ายเตือนความสนใจ (Viral Hook Badge)
    banner_y = 120
    draw.rounded_rectangle([60, banner_y, W - 60, banner_y + 85], radius=20, fill=(255, 45, 85, 240))
    badge_font = get_thai_font(36, bold=True)
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

    # 5. ป้ายชื่อเรื่องใต้ภาพปก (ลบ _ ออกทั้งหมด)
    title_font = get_thai_font(40, bold=True)
    clean_title = story_title.replace("_", " ")
    if len(clean_title) > 30:
        clean_title = clean_title[:30] + "..."
    draw.text((W // 2, cover_y + cover_h + 45), clean_title, font=title_font, fill="#FFD700", anchor="mm")

    # 6. กรอบพื้นที่คลื่นเสียง (Waveform Area)
    wave_box_y = cover_y + cover_h + 90
    draw.rounded_rectangle([80, wave_box_y, W - 80, wave_box_y + 100], radius=15, fill=(20, 24, 38, 220), outline=(0, 229, 255, 180), width=2)
    wave_font = get_thai_font(26)
    draw.text((W // 2, wave_box_y + 25), "🎙️ สปอยล์เนื้อเรื่องสุดเข้มข้น • สวมหูฟังเพื่ออรรถรส", font=wave_font, fill="#00E5FF", anchor="mm")

    # 7. Subtitle / Teaser Quote Area Box
    sub_box_y = wave_box_y + 130
    draw.rounded_rectangle([60, sub_box_y, W - 60, sub_box_y + 240], radius=20, fill=(0, 0, 0, 195), outline=(255, 255, 255, 70), width=2)

    if quote_text:
        q_lines = wrap_thai_text(quote_text, max_chars=34)
        q_font = get_thai_font(28, bold=True)
        line_h = 42
        total_h = len(q_lines) * line_h
        start_y = sub_box_y + (240 - total_h) // 2 + 10
        for i, line in enumerate(q_lines):
            draw.text((W // 2, start_y + i * line_h), line, font=q_font, fill="#FFF9C4", anchor="mm")
    else:
        q_font = get_thai_font(30, bold=True)
        draw.text((W // 2, sub_box_y + 120), "🎧 กดเปิดเสียงเพื่อฟังไฮไลท์เด็ด", font=q_font, fill="#FFF9C4", anchor="mm")

    # 8. Bottom CTA Banner (ดึงคนเข้า ReadAWrite & Dek-D)
    cta_y = H - 150
    draw.rounded_rectangle([60, cta_y, W - 60, cta_y + 90], radius=25, fill=(16, 185, 129, 245))
    cta_font = get_thai_font(34, bold=True)
    draw.text((W // 2, cta_y + 45), "📖 อ่านฟรีจนจบเรื่องบน ReadAWrite & Dek-D", font=cta_font, fill="#FFFFFF", anchor="mm")

    canvas.save(out_frame_path, quality=95)
    print(f"  ✅ สร้าง Vertical Frame 9:16 สำเร็จ: {out_frame_path}")
    return out_frame_path


def render_dynamic_promo_video(
    story_query: str,
    duration_sec: float = 40.0,
    hook_tag: str = "นิยายยอดฮิตติดชาร์ตอันดับ 1!",
    quote_text: str = ""
) -> Optional[str]:
    """เรนเดอร์คลิปวิดีโอโปรโมท TikTok/Shorts (9:16) พร้อมเสียง Waveform และซับไตเติล"""
    # 1. ค้นหาภาพปก
    cover_candidates = glob.glob(os.path.join(COVERS_DIR, f"*{story_query}*.jpg")) + \
                       glob.glob(os.path.join(COVERS_DIR, f"*{story_query.replace(' ', '_')}*.jpg"))
    cover_path = cover_candidates[0] if cover_candidates else ""

    # 2. ค้นหาไฟล์เสียง Audiobook
    clean_q = story_query.replace(" ", "_")
    audio_cands = (
        glob.glob(os.path.join(AUDIO_DIR, f"*{clean_q}*Audiobook_01.mp3")) +
        glob.glob(os.path.join(AUDIO_DIR, f"*{story_query}*Audiobook_01.mp3")) +
        glob.glob(os.path.join(AUDIO_DIR, f"*{clean_q}*.mp3")) +
        glob.glob(os.path.join(AUDIO_DIR, f"*{story_query}*.mp3"))
    )
    # ตัด raw ออก
    audio_cands = [a for a in audio_cands if "_raw" not in a]
    
    if not audio_cands:
        print(f"❌ ไม่พบไฟล์เสียงสำหรับ '{story_query}' ใน {AUDIO_DIR}")
        return None

    audio_path = audio_cands[0]
    raw_name = os.path.basename(audio_path).replace("_Audiobook_01.mp3", "").replace(".mp3", "")
    clean_display_title = raw_name.replace("_", " ")

    out_frame_img = os.path.join(PROMO_OUTPUT_DIR, f"{raw_name}_vertical_frame.png")
    out_video_mp4 = os.path.join(PROMO_OUTPUT_DIR, f"{raw_name}_PROMO_SHORTS.mp4")
    out_meta_json = os.path.join(PROMO_OUTPUT_DIR, f"{raw_name}_metadata.json")

    print(f"\n🎬 กำลังสร้างวิดีโอโปรโมทสั้น (Vertical Shorts 9:16): '{clean_display_title}'")
    print(f"   • ไฟล์เสียง: {os.path.basename(audio_path)}")
    print(f"   • ความยาว Teaser: {duration_sec} วินาที")

    # สร้าง Frame ภาพนิ่งพร้อมกล่อง Quote
    create_vertical_promo_frame(cover_path, clean_display_title, hook_tag, out_frame_img, quote_text=quote_text)

    # 3. Filter Complex สำหรับ Waveform Animation
    filter_complex = (
        f"[1:a]atrim=0:{duration_sec},showwaves=s=860x65:mode=cline:colors=0x00E5FF:rate=25,colorkey=black:0.01:0.01[wave];"
        f"[0:v][wave]overlay=110:1360[outv]"
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
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"\n🎉 ผลิตวิดีโอโปรโมทสำเร็จ (Ready for TikTok/Shorts/Reels):")
        print(f"   📹 {out_video_mp4} ({os.path.getsize(out_video_mp4) / (1024*1024):.1f} MB)")

        # 4. สร้างไฟล์ Metadata สำหรับอัปโหลดทันที (Line 1 Direct ReadAWrite Link, NO underscores)
        aid = find_aid_for_query(clean_display_title)
        raw_link = f"https://www.readawrite.com/a/{aid}" if aid else "https://www.readawrite.com"
        
        meta = {
            "title": f"{clean_display_title} ตอนที่ 1 #Shorts #นิยายเสียง",
            "description": (
                f"👉 อ่านฟรีครบทุกตอนก่อนใครคลิก: {raw_link}\n"
                f"❤️ ฝากกดหัวใจ + เพิ่มเข้าชั้นหนังสือใน ReadAWrite ด้วยนะครับ!\n\n"
                f"{clean_display_title} — สปอยล์และไฮไลท์ความสนุกฉบับสั้น ฟังต่อเนื่องก่อนนอน\n\n"
                f"#นิยาย #นิยายเสียง #ReadAWrite #DekD #Shorts #นิยายออนไลน์"
            ),
            "readawrite_link": raw_link,
            "story_title": clean_display_title,
            "tags": ["Shorts", "นิยายเสียง", "ReadAWrite", "DekD", "นิยายแปลกใหม่", "ฟังยาวก่อนนอน"],
            "video_path": out_video_mp4,
            "duration_sec": duration_sec
        }
        with open(out_meta_json, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"   📄 บันทึก Metadata พร้อมลิงก์ ReadAWrite: {out_meta_json}")

        return out_video_mp4

    except Exception as e:
        print(f"❌ เรนเดอร์วิดีโอล้มเหลว: {e}")
        return None


def produce_flagship_shorts():
    """สร้าง 3 วิดีโอ Shorts ตัวท็อปสำหรับแคมเปญกระตุ้นยอดวิว"""
    flagships = [
        {
            "query": "ทะลุมิติไปเป็นคุณแม่ลูกแฝด",
            "duration": 40.0,
            "hook": "ลืมตาขึ้นมาก็กลายเป็นคุณแม่ลูกแฝดยุค 70!",
            "quote": "สามีไม่อยู่ บ้านยากจน แต่โชคดีที่ฉันมี 'ซูเปอร์มาร์เก็ตลับ' จากมิติวิเศษ... ลูกแฝดของแม่ วันนี้จะได้กินเนื้อหมูชิ้นโต!"
        },
        {
            "query": "จากน้องสาวสู่พี่ใหญ่",
            "duration": 40.0,
            "hook": "จากน้องสาวตัวเล็ก สู่การปกป้องครอบครัว",
            "quote": "ในวันที่โลกไม่เคยปรานี... พี่ชายปกป้องฉันมาทั้งชีวิต คราวนี้ถึงตาที่ฉันจะยืนหยัดเพื่อเขา แม้ต้องแลกด้วยทุกสิ่ง!"
        },
        {
            "query": "ผู้สาปแช่ง Chimera",
            "duration": 40.0,
            "hook": "กำเนิดใหม่ในร่างอสูร คิเมร่าไร้พ่าย!",
            "quote": "พวกเขาเรียกฉันว่าตัวประหลาดและสาปแช่งฉัน... แต่พวกเขาไม่รู้หรอกว่า พลังแห่งคิเมร่ากำลังจะกลืนกินเวทมนตร์ทั้งพิภพ!"
        }
    ]

    results = []
    for item in flagships:
        res = render_dynamic_promo_video(
            story_query=item["query"],
            duration_sec=item["duration"],
            hook_tag=item["hook"],
            quote_text=item["quote"]
        )
        if res:
            results.append(res)
    return results


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        produce_flagship_shorts()
    elif len(sys.argv) > 1:
        render_dynamic_promo_video(sys.argv[1])
    else:
        produce_flagship_shorts()

