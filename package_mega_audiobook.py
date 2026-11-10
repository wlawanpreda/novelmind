#!/usr/bin/env python3
"""
package_mega_audiobook.py
=========================
สร้าง Mega Audiobook ความยาวเกือบ 1 ชั่วโมง (58 นาที) รวม 20 ตอนจบภาค 1
เรื่อง: ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70 พร้อมซูเปอร์มาร์เก็ตลับ
- รวมไฟล์เสียงทั้ง 20 ตอนเป็น Master MP3
- คำนวณ Timestamps ละเอียดครบ 20 ตอน
- สร้าง High-CTR Thumbnail 16:9 สำหรับ Mega Audiobook
- เรนเดอร์วิดีโอ 1080p 16:9 สวยงาม คมชัด ไม่มีขอบดำ
- ออกแบบ YouTube Description จัดเต็มพร้อม Chapter Search
"""

import os
import re
import glob
import subprocess
from datetime import timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
AUDIO_DIR = os.path.join(SB, "05_Active_Projects", "Audio_Output")
COVERS_DIR = os.path.join(SB, "05_Active_Projects", "Covers")
EXPORTS_DIR = os.path.join(SB, "05_Active_Projects", "Exports", "Audiobooks")
os.makedirs(EXPORTS_DIR, exist_ok=True)


def get_audio_duration(file_path: str) -> float:
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
    td = timedelta(seconds=int(seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def create_mega_thumbnail(out_path: str, cover_path: str) -> str:
    width, height = 1920, 1080
    orig = Image.open(cover_path).convert("RGBA")

    # 1. Background
    bg = orig.resize((width, height)).filter(ImageFilter.GaussianBlur(32))
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 190))
    bg = Image.alpha_composite(bg, overlay)

    # 2. Card
    orig_ratio = orig.width / orig.height
    card_h = 920
    card_w = int(card_h * orig_ratio)
    cover_resized = orig.resize((card_w, card_h), Image.Resampling.LANCZOS)
    card_bg = Image.new("RGBA", (card_w + 16, card_h + 16), (255, 255, 255, 220))
    card_bg.paste(cover_resized, (8, 8))
    bg.paste(card_bg, (90, 80), card_bg)

    # 3. Typography
    draw = ImageDraw.Draw(bg)
    font_path = "/System/Library/Fonts/Supplemental/SukhumvitSet.ttc"
    title_font = ImageFont.truetype(font_path, 74, index=4)
    badge_font = ImageFont.truetype(font_path, 34, index=4)
    sub_font = ImageFont.truetype(font_path, 42, index=4)
    tag_font = ImageFont.truetype(font_path, 30, index=1)
    pill_font = ImageFont.truetype(font_path, 32, index=4)

    text_x = 90 + card_w + 65

    # Badges
    draw.rounded_rectangle([(text_x, 120), (text_x + 470, 195)], radius=14, fill=(245, 158, 11, 245))
    draw.text((text_x + 24, 135), "MEGA AUDIOBOOK 1 ชม.", fill=(0, 0, 0), font=badge_font)

    draw.rounded_rectangle([(text_x + 490, 120), (text_x + 820, 195)], radius=14, fill=(14, 165, 233, 240))
    draw.text((text_x + 515, 135), "รวมครบ 20 ตอนจบ", fill=(255, 255, 255), font=badge_font)

    # Titles
    draw.text((text_x, 245), "คุณแม่ลูกแฝดยุค 70", fill=(255, 255, 255), font=title_font)
    draw.text((text_x, 365), "พร้อมซูเปอร์มาร์เก็ตลับ (จบภาค 1)", fill=(56, 189, 248), font=sub_font)
    draw.text((text_x, 455), "ทะลุมิติสู่ยุค 70 สู้ชีวิตเลี้ยงลูกแฝดพร้อมมิติช้อปปิ้งไม่อั้น", fill=(226, 232, 240), font=tag_font)

    # Pill badge
    draw.rounded_rectangle([(text_x, 770), (text_x + 720, 865)], radius=16, fill=(30, 41, 59, 240), outline=(56, 189, 248), width=3)
    draw.text((text_x + 40, 795), "ฟังยาวต่อเนื่อง 1 ชั่วโมงเต็ม · จบภาคแรก", fill=(241, 245, 249), font=pill_font)

    bg.convert("RGB").save(out_path, quality=95)
    return out_path


def main():
    print("=" * 65)
    print("🎧 กำลังสร้าง MEGA AUDIOBOOK: คุณแม่ลูกแฝดยุค 70 (รวม 20 ตอนจบภาค 1)")
    print("=" * 65)

    cover_file = os.path.join(COVERS_DIR, "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค_70_พร้อมซูเปอร์มาร์เก็ตลับ_Cover_3x4.jpg")
    if not os.path.exists(cover_file):
        cover_file = os.path.join(COVERS_DIR, "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค_70_พร้อมซูเปอร์มาร์เก็ตลับ_Cover.jpg")

    thumb_16x9 = os.path.join(EXPORTS_DIR, "คุณแม่ลูกแฝดยุค70_Mega_Thumbnail_16x9.jpg")
    create_mega_thumbnail(thumb_16x9, cover_file)
    print(f"🎨 เจนเนอเรตหน้าปก 16:9 Mega เรียบร้อย: {os.path.basename(thumb_16x9)}")

    # ค้นหาและเรียงลำดับไฟล์เสียงทั้ง 20 ตอน
    chapters = []
    for ep in range(1, 21):
        fp = os.path.join(AUDIO_DIR, f"ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค_70_พร้อมซูเปอร์มาร์เก็ตลับ_Audiobook_{ep:02d}.mp3")
        if os.path.exists(fp):
            chapters.append((ep, fp))

    print(f"📁 พบไฟล์เสียงครบ {len(chapters)} ตอน")

    output_mp3 = os.path.join(EXPORTS_DIR, "คุณแม่ลูกแฝดยุค70_Mega_Audiobook_20ตอนจบ.mp3")
    output_mp4 = os.path.join(EXPORTS_DIR, "คุณแม่ลูกแฝดยุค70_Mega_Audiobook_20ตอนจบ.mp4")
    output_desc = os.path.join(EXPORTS_DIR, "คุณแม่ลูกแฝดยุค70_Mega_Audiobook_Description.txt")

    # รวมไฟล์เสียง Concat
    list_txt = os.path.join(EXPORTS_DIR, "_temp_concat_list.txt")
    current_sec = 0.0
    timestamps = []

    with open(list_txt, "w", encoding="utf-8") as f_list:
        for ep, fp in chapters:
            dur = get_audio_duration(fp)
            ts = format_timestamp(current_sec)
            timestamps.append(f"{ts} ตอนที่ {ep}")
            f_list.write(f"file '{os.path.abspath(fp)}'\n")
            current_sec += dur

    total_time_str = format_timestamp(current_sec)
    print(f"⏱️ ความยาวรวมทั้งสิ้น: {total_time_str} ({current_sec:.1f} วินาที)")

    print("🔨 กำลังรวม Master MP3...")
    cmd_concat = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_txt, "-c", "copy", output_mp3]
    subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    if os.path.exists(list_txt):
        os.remove(list_txt)

    # สร้าง Description
    desc_text = f"""💬 ชวนคุยก่อนนอน: ถ้าย้อนเวลาไปยุค 70 พร้อม "ซูเปอร์มาร์เก็ตลับ" สิ่งแรกที่คุณอยากหยิบออกมาใช้คืออะไร? ร่วมแชร์ความคิดเห็นกันด้านล่างได้เลยนะครับ 👇✨

🎧 [รวม 20 ตอนจบภาค 1] คุณแม่ลูกแฝดยุค 70 พร้อมซูเปอร์มาร์เก็ตลับ (Full Mega Audiobook)
ความยาวเกือบ 1 ชั่วโมงเต็ม ({total_time_str}) ฟังยาวต่อเนื่อง ไม่มีสะดุด เหมาะสำหรับเปิดฟังตอนทำงาน ฟังก่อนนอน หรือเดินทาง

⏱️ สารบัญเลือกตอน (Chapters):
{chr(10).join(timestamps)}

---
📖 สำหรับท่านที่ต้องการอ่านบทความฉบับเต็ม หรือสนับสนุนผลงาน (นามปากกา: เงาพันจันทร์):
🔗 อ่านฉบับเต็มและตอนต่อไปก่อนใครได้ที่ ReadAWrite:
👉 https://www.readawrite.com/a/627d9707279484797acafaba010fcf69

📚 ดาวน์โหลด E-Book เล่มเต็มบน Meb Market:
👉 ค้นหาชื่อ "คุณแม่ลูกแฝดยุค 70" หรือนามปากกา "เงาพันจันทร์"

✨ ช่อง Midnight Tales · มิดไนต์เทล
กดติดตาม (Subscribe) และกดกระดิ่งแจ้งเตือน เพื่อไม่พลาดนิยายเรื่องใหม่ทุกวัน!

#นิยายเสียง #หนังสือนิยาย #นิยายเสียงก่อนนอน #คุณแม่ลูกแฝดยุค70 #Audiobook #นิยายแฟนตาซี #สู้ชีวิต #ทะลุมิติ
"""
    with open(output_desc, "w", encoding="utf-8") as df:
        df.write(desc_text)

    # เรนเดอร์วิดีโอ 1080p
    print("🎬 กำลังเรนเดอร์ YouTube Long-Form Video 1080p (ภาพ 16:9 ไร้ขอบดำ)...")
    cmd_video = [
        "ffmpeg", "-y",
        "-framerate", "1", "-loop", "1", "-i", thumb_16x9,
        "-i", output_mp3,
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
        "-r", "1",
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_mp4
    ]
    subprocess.run(cmd_video, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    print(f"✅ เรนเดอร์วิดีโอสำเร็จ: {output_mp4} ({os.path.getsize(output_mp4)/1024/1024:.2f} MB)")
    print(f"📝 บันทึกคำบรรยาย: {output_desc}")
    print("\n🎉 MEGA AUDIOBOOK พร้อมเผยแพร่เรียบร้อยแล้ว!")


if __name__ == "__main__":
    main()
