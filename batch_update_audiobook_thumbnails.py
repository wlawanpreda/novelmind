import os
import sys
import time
import glob
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from googleapiclient.http import MediaFileUpload

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import youtube_stats

COVERS_DIR = os.path.join(ROOT, 'SecondBrain', '05_Active_Projects', 'Covers')
OUTPUT_DIR = os.path.join(ROOT, 'scratch', 'thumbnails')
os.makedirs(OUTPUT_DIR, exist_ok=True)

TARGET_AUDIOBOOKS = [
    {
        "vid": "Bh6YtuWNZcE",
        "title": "วีรบุรุษสุดขี้เกียจ",
        "subtitle": "รวมทุกตอนจบภาค 1 (ฟังยาวต่อเนื่อง)",
        "tagline": "พลังหลับใหลไร้เทียมทาน สู่ตำนานผู้กอบกู้",
        "cover_pattern": "*วีรบุรุษสุดขี้เกียจ*Cover.jpg"
    },
    {
        "vid": "AwrE4AMQS4k",
        "title": "จากน้องสาวสู่พี่ใหญ่",
        "subtitle": "รวม 8 ตอนจบภาคแรก (อ่านฟรีจนจบ)",
        "tagline": "สายใยแห่งความรัก ก้าวข้ามความเจ็บปวดสู่ครอบครัวอบอุ่น",
        "cover_pattern": "*จากน้องสาวสู่พี่ใหญ่*Cover.jpg"
    },
    {
        "vid": "10iL6jE8htw",
        "title": "คุณแม่ลูกแฝดยุค 70",
        "subtitle": "พร้อมซูเปอร์มาร์เก็ตลับ (รวมทุกตอนจบภาค)",
        "tagline": "ทะลุมิติสู่ยุค 70 สู้ชีวิตเลี้ยงลูกแฝดพร้อมมิติช้อปปิ้งไม่อั้น",
        "cover_pattern": "*คุณแม่ลูกแฝดยุค*Cover_3x4.jpg"
    },
    {
        "vid": "3BPqQLhCgaE",
        "title": "ตื่นตามฝันนางพยากรณ์",
        "subtitle": "รวมทุกตอนจบภาค (ฟังยาวก่อนนอน)",
        "tagline": "นิมิตคำทำนายพลิกชะตา ก้าวสู่เส้นทางแห่งความจริง",
        "cover_pattern": "*ตื่นตามฝัน*Cover.jpg"
    },
    {
        "vid": "lqpU5OFLscg",
        "title": "ยอดนักสืบสปีดรัน",
        "subtitle": "รวมทุกตอนจบภาค (ครบ 10 ตอน)",
        "tagline": "ไขคดีเร็วกว่าแสง ข้ามบทสนทนาไร้สาระ สปีดรันทุกหลักฐาน",
        "cover_pattern": "*ยอดนักสืบสปีดรัน*Cover*.jpg"
    },
    {
        "vid": "-E5IgijqfSc",
        "title": "กระจกเงาคนตาย",
        "subtitle": "รวมทุกตอนจบภาค (Full Audiobook)",
        "tagline": "ย้อนดูความทรงจำ 30 นาทีก่อนตาย สัมผัสวัตถุโบราณเยาวราช",
        "cover_pattern": "*กระจกเงาคนตาย*Cover.jpg"
    },
    {
        "vid": "pB74ZaKV4tU",
        "title": "ดาบไร้พระเจ้า",
        "subtitle": "วงจรเวลาแห่งโชคชะตา (รวมทุกตอนจบ)",
        "tagline": "เกมเมอร์หนุ่มทะลุมิติ สู้ชะตากรรมวนลูปในโลกโบราณ",
        "cover_pattern": "*ดาบไร้พระเจ้า*Cover.jpg"
    },
    {
        "vid": "Emd4CPU3ePQ",
        "title": "ดวงจันทร์แห่งเวทมนตร์",
        "subtitle": "รวมทุกตอนจบภาค (อ่านฟรีบน ReadAWrite)",
        "tagline": "สืบสวนคดีปริศนาโลกวิญญาณ และเด็กสาวผู้เต้นระบำใต้แสงจันทร์",
        "cover_pattern": "*ดวงจันทร์แห่งเวทมนตร์*Cover.jpg"
    },
    {
        "vid": "1P583lKnKWw",
        "title": "กอธาม ทหารรับจ้าง",
        "subtitle": "ชะตาเปลี่ยน (รวมทุกตอนจบภาค)",
        "tagline": "ดาบและเวทมนตร์เพื่ออิสรภาพ สู่สมรภูมิที่ไม่มีวันลืม",
        "cover_pattern": "*กอธาม*Cover.jpg"
    },
    {
        "vid": "nLrsjUcp_fU",
        "title": "ตื่นขึ้นมาด้วยรอยยิ้ม",
        "subtitle": "รวมทุกตอนจบภาค (ฟังต่อเนื่องก่อนนอน)",
        "tagline": "การเดินทางเยียวยาหัวใจ สู่รอยยิ้มที่งดงามที่สุด",
        "cover_pattern": "*ตื่นขึ้นมาด้วยรอยยิ้ม*Cover.jpg"
    }
]

def find_cover(pattern: str) -> str:
    matches = glob.glob(os.path.join(COVERS_DIR, pattern))
    if matches:
        return matches[0]
    # Fallback to any matching cover
    clean_p = pattern.replace("*", "")
    for f in os.listdir(COVERS_DIR):
        if any(w in f for w in clean_p.split("_") if len(w) > 3):
            return os.path.join(COVERS_DIR, f)
    raise FileNotFoundError(f"Cover not found for pattern: {pattern}")

def generate_thumbnail(item: dict) -> str:
    width, height = 1280, 720
    cover_path = find_cover(item['cover_pattern'])
    orig = Image.open(cover_path).convert('RGBA')

    # 1. Background (blurred + darkened)
    bg = orig.resize((width, height)).filter(ImageFilter.GaussianBlur(26))
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 185))
    bg = Image.alpha_composite(bg, overlay)

    # 2. Cover card on left
    orig_ratio = orig.width / orig.height
    card_h = 600
    card_w = int(card_h * orig_ratio)
    cover_resized = orig.resize((card_w, card_h), Image.Resampling.LANCZOS)

    card_bg = Image.new('RGBA', (card_w + 12, card_h + 12), (255, 255, 255, 220))
    card_bg.paste(cover_resized, (6, 6))
    bg.paste(card_bg, (60, 60), card_bg)

    # 3. Typography on right
    draw = ImageDraw.Draw(bg)
    font_path = '/System/Library/Fonts/Supplemental/SukhumvitSet.ttc'
    
    t_len = len(item['title'])
    t_size = 64 if t_len <= 16 else (52 if t_len <= 24 else 44)
    title_font = ImageFont.truetype(font_path, t_size, index=4)
    badge_font = ImageFont.truetype(font_path, 28, index=4)
    sub_font = ImageFont.truetype(font_path, 36, index=4)
    tag_font = ImageFont.truetype(font_path, 26, index=1)

    text_x = 60 + card_w + 45

    # Badge 1: Amber pill (FULL AUDIOBOOK)
    draw.rounded_rectangle([(text_x, 85), (text_x + 290, 138)], radius=10, fill=(245, 158, 11, 245))
    draw.text((text_x + 20, 95), 'FULL AUDIOBOOK', fill=(0, 0, 0), font=badge_font)

    # Badge 2: Cyan badge (จบภาคแรก / อ่านฟรี)
    draw.rounded_rectangle([(text_x + 305, 85), (text_x + 520, 138)], radius=10, fill=(14, 165, 233, 240))
    draw.text((text_x + 325, 95), 'อ่านฟรีจนจบ', fill=(255, 255, 255), font=badge_font)

    # Title (White)
    draw.text((text_x, 165), item['title'], fill=(255, 255, 255), font=title_font)

    # Subtitle (Cyan gold)
    draw.text((text_x, 260), item['subtitle'], fill=(56, 189, 248), font=sub_font)
    
    # Tagline (Light slate)
    draw.text((text_x, 330), item['tagline'], fill=(226, 232, 240), font=tag_font)

    # Bottom badge
    draw.rounded_rectangle([(text_x, 520), (text_x + 460, 595)], radius=12, fill=(30, 41, 59, 240), outline=(56, 189, 248), width=2)
    draw.text((text_x + 32, 542), 'ฟังยาวต่อเนื่องก่อนนอน · รวมครบทุกตอน', fill=(241, 245, 249), font=tag_font)

    out_file = os.path.join(OUTPUT_DIR, f"{item['vid']}_highctr.jpg")
    bg.convert('RGB').save(out_file, quality=95)
    return out_file

def main():
    print("=== HIGH-CTR AUDIOBOOK THUMBNAIL UPGRADER ===")
    yt = youtube_stats._yt()
    success_count = 0

    for idx, item in enumerate(TARGET_AUDIOBOOKS):
        vid = item['vid']
        title = item['title']
        print(f"\n[{idx+1:02d}/{len(TARGET_AUDIOBOOKS)}] Processing: {title} ({vid})")
        try:
            thumb_path = generate_thumbnail(item)
            print(f"  🎨 Rendered: {os.path.basename(thumb_path)}")

            media = MediaFileUpload(thumb_path, mimetype='image/jpeg')
            yt.thumbnails().set(videoId=vid, media_body=media).execute()
            print(f"  🚀 Live on YouTube thumbnail successfully!")
            success_count += 1
            time.sleep(1.0)
        except Exception as e:
            print(f"  ❌ Failed on {title}: {e}")

    print(f"\n🎉 Finished! Successfully updated {success_count}/{len(TARGET_AUDIOBOOKS)} high-CTR thumbnails live!")

if __name__ == "__main__":
    main()
