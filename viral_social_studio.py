#!/usr/bin/env python3
"""
viral_social_studio.py — Transmedia Social Asset Producer
=========================================================
ผลิตคอนเทนต์กราฟิกสำหรับดึงดูดนักอ่านบน Facebook Page, X (Twitter), และ Lemon8:
1. 4-Panel Comic Strip (Webtoon Gag 4 ช่อง): นำโมเมนต์สนุกมาเล่าใน 4 ช่อง
2. Character Chat Mockup (ภาพจำลองแชทโทรศัพท์): บทสนทนาแสบๆ ฟินๆ ระหว่างตัวละคร
3. Golden Quote Card: การ์ดประโยคเด็ดทัชใจ คมเข้ม สไตล์ Dark Luxury
"""

from __future__ import annotations

import os
import sys
import glob
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
SECOND_BRAIN = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
SOCIAL_OUTPUT_DIR = os.path.join(SECOND_BRAIN, "05_Active_Projects", "Social_Assets")
COVERS_DIR = os.path.join(SECOND_BRAIN, "05_Active_Projects", "Covers")
os.makedirs(SOCIAL_OUTPUT_DIR, exist_ok=True)

_THAI_FONT = "/System/Library/Fonts/Supplemental/Thonburi.ttc"
if not os.path.exists(_THAI_FONT):
    _THAI_FONT = "/System/Library/Fonts/ThonburiUI.ttc"
if not os.path.exists(_THAI_FONT):
    _THAI_FONT = "Arial"


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    try:
        idx = 1 if bold else 0
        return ImageFont.truetype(_THAI_FONT, size, index=idx)
    except Exception:
        try:
            return ImageFont.truetype(_THAI_FONT, size, index=0)
        except Exception:
            return ImageFont.load_default()


# ============================================================================
# 1. 4-PANEL COMIC STRIP (Webtoon Gag 4 ช่อง)
# ============================================================================

def generate_4panel_comic(
    story_title: str,
    panels_data: Optional[List[Dict[str, str]]] = None,
    out_path: Optional[str] = None
) -> str:
    """สร้างภาพการ์ตูน 4 ช่อง (1080x1920) สำหรับโพสต์โซเชียล"""
    W, H = 1080, 1920
    canvas = Image.new("RGB", (W, H), (248, 249, 252))
    draw = ImageDraw.Draw(canvas, "RGBA")

    clean_title = story_title.replace("_", " ")
    if not out_path:
        out_path = os.path.join(SOCIAL_OUTPUT_DIR, f"{story_title}_4PANEL_COMIC.png")

    if not panels_data:
        # Default panels data for flagship
        panels_data = [
            {"panel": "1. จุดเริ่มต้น", "speaker": "แม่เฒ่าลู่", "dialogue": "ไสหัวไปให้พ้นบ้านข้า! หญิงหม้ายไร้ประโยชน์กับลูกแฝดกาลกิณี!"},
            {"panel": "2. การเจรจา", "speaker": "หลินม่าน", "dialogue": "ได้... ฉันจะไป แต่ต้องเซ็นหนังสือตัดขาด แลกกับกระท่อมร้างท้ายเขา!"},
            {"panel": "3. จุดพลิกผัน", "speaker": "บรรยาย", "dialogue": "วูบ! ประตูมิติเปิดออก... ซูเปอร์มาร์เก็ตหรูศตวรรษที่ 21 ของกินไม่อั้น!"},
            {"panel": "4. บทสรุป", "speaker": "สองแฝด", "dialogue": "แม่จ๋า ซาลาเปาหมูสับกับนมอุ่นๆ หอมจังเลย... พวกเราไม่อดตายแล้ว!"}
        ]

    # Header Title Banner
    draw.rectangle([0, 0, W, 140], fill=(30, 41, 59))
    header_f = get_font(42, bold=True)
    draw.text((W // 2, 50), f"มินิเว็บตูน 4 ช่อง: {clean_title[:24]}", font=header_f, fill="#FFFFFF", anchor="mm")
    sub_f = get_font(24)
    draw.text((W // 2, 95), "ดัดแปลงจากฉากสำคัญ • นามปากกา: เงาพันจันทร์", font=sub_f, fill="#94A3B8", anchor="mm")

    # Draw 4 Panels
    panel_h = 390
    gap = 25
    start_y = 165

    panel_colors = [
        (254, 242, 242),  # Light red
        (254, 249, 195),  # Light yellow
        (238, 242, 255),  # Light indigo
        (236, 253, 245)   # Light emerald
    ]

    for i, p in enumerate(panels_data[:4]):
        py = start_y + i * (panel_h + gap)
        # Panel frame
        draw.rounded_rectangle([50, py, W - 50, py + panel_h], radius=18, fill=panel_colors[i], outline=(203, 213, 225), width=3)
        
        # Panel Badge
        draw.rounded_rectangle([75, py + 25, 260, py + 65], radius=10, fill=(30, 41, 59))
        p_f = get_font(22, bold=True)
        draw.text((167, py + 45), p["panel"], font=p_f, fill="#FFFFFF", anchor="mm")

        # Speaker Tag
        spk_f = get_font(28, bold=True)
        draw.text((75, py + 95), f"🗣️ {p['speaker']}:", font=spk_f, fill="#0F172A")

        # Speech Box
        draw.rounded_rectangle([75, py + 140, W - 75, py + panel_h - 30], radius=14, fill=(255, 255, 255, 230), outline=(226, 232, 240), width=2)
        dlg_f = get_font(30)
        
        # Word wrap dialogue
        words = p["dialogue"]
        lines = []
        cur = ""
        for char in words:
            cur += char
            if len(cur) >= 32:
                lines.append(cur)
                cur = ""
        if cur:
            lines.append(cur)

        line_y = py + 180
        for l in lines[:3]:
            draw.text((105, line_y), l, font=dlg_f, fill="#1E293B")
            line_y += 45

    # Footer CTA
    footer_y = H - 90
    draw.rectangle([0, footer_y, W, H], fill=(16, 185, 129))
    cta_f = get_font(30, bold=True)
    draw.text((W // 2, footer_y + 45), "📖 อ่านเรื่องเต็มฉบับนิยายฟรีได้ที่ ReadAWrite & Dek-D", font=cta_f, fill="#FFFFFF", anchor="mm")

    canvas.save(out_path, quality=95)
    print(f"  🎨 สร้าง Webtoon 4 ช่องสำเร็จ: {out_path}")
    return out_path


# ============================================================================
# 2. CHARACTER CHAT MOCKUP (ภาพแชทตัวละครไวรัล)
# ============================================================================

def generate_character_chat_mockup(
    story_title: str,
    character_name: str = "ท่านประธานกู้",
    chats: Optional[List[Dict[str, str]]] = None,
    out_path: Optional[str] = None
) -> str:
    """สร้างภาพแชทเสมือนจริงระหว่างตัวละคร (Smartphone Chat UI 1080x1920)"""
    W, H = 1080, 1920
    canvas = Image.new("RGB", (W, H), (238, 242, 246))
    draw = ImageDraw.Draw(canvas, "RGBA")

    clean_title = story_title.replace("_", " ")
    if not out_path:
        out_path = os.path.join(SOCIAL_OUTPUT_DIR, f"{story_title}_CHAT_MOCKUP.png")

    if not chats:
        chats = [
            {"from": "other", "text": "คุณคิดว่าการขอหย่าจะทำให้ผมสนใจคุณงั้นเหรอ?"},
            {"from": "me", "text": "ท่านประธานเข้าใจผิดแล้วค่ะ... ฉันไม่ได้เรียกร้องความสนใจ"},
            {"from": "me", "text": "ฉันแค่ 'หมดรัก' และเหนื่อยที่จะต้องวิ่งตามคนใจร้ายแบบคุณแล้วจริงๆ"},
            {"from": "other", "text": "โกหก! คุณรักผมมาตั้งห้าปี จะเลิกรักง่ายๆ ได้ยังไง?!"},
            {"from": "me", "text": "ห้าปีที่ผ่านมาถือว่าฉันทำบุญค่ะ ลาก่อนนะคะ :) [บล็อกการติดต่อ]"},
            {"from": "other", "text": "เดี๋ยวสิ! รินดา! กลับมาคุยกันให้รู้เรื่องเดี๋ยวนี้นะ!!"}
        ]

    # Status Bar
    draw.rectangle([0, 0, W, 70], fill=(255, 255, 255))
    bar_f = get_font(24, bold=True)
    draw.text((60, 35), "09:41", font=bar_f, fill="#000000", anchor="lm")
    draw.text((W - 60, 35), "5G 100% 🔋", font=bar_f, fill="#000000", anchor="rm")

    # Header Bar
    draw.rectangle([0, 70, W, 210], fill=(255, 255, 255))
    draw.line([(0, 210), (W, 210)], fill=(226, 232, 240), width=2)
    
    # Back button & Avatar
    draw.text((40, 140), "‹", font=get_font(60), fill="#3B82F6", anchor="lm")
    draw.ellipse([95, 105, 175, 185], fill=(244, 63, 94))
    draw.text((135, 145), character_name[0], font=get_font(38, bold=True), fill="#FFFFFF", anchor="mm")

    # Name & Status
    draw.text((200, 125), character_name, font=get_font(36, bold=True), fill="#0F172A")
    draw.text((200, 168), "ออนไลน์เมื่อ 1 นาทีที่แล้ว", font=get_font(22), fill="#10B981")

    # Chat Bubbles
    cur_y = 260
    for c in chats:
        is_me = (c["from"] == "me")
        txt = c["text"]
        
        # Word wrap text
        lines = []
        tmp = ""
        for char in txt:
            tmp += char
            if len(tmp) >= 28:
                lines.append(tmp)
                tmp = ""
        if tmp:
            lines.append(tmp)

        bubble_w = min(W - 240, max(280, max(len(l) for l in lines) * 26 + 60))
        bubble_h = len(lines) * 44 + 40

        if is_me:
            bx = W - 60 - bubble_w
            draw.rounded_rectangle([bx, cur_y, bx + bubble_w, cur_y + bubble_h], radius=22, fill=(59, 130, 246))
            for i, l in enumerate(lines):
                draw.text((bx + 25, cur_y + 20 + i * 44), l, font=get_font(28), fill="#FFFFFF")
            # Read receipt
            draw.text((bx - 85, cur_y + bubble_h - 15), "อ่านแล้ว", font=get_font(18), fill="#94A3B8")
        else:
            bx = 60
            draw.rounded_rectangle([bx, cur_y, bx + bubble_w, cur_y + bubble_h], radius=22, fill=(255, 255, 255))
            for i, l in enumerate(lines):
                draw.text((bx + 25, cur_y + 20 + i * 44), l, font=get_font(28), fill="#1E293B")

        cur_y += bubble_h + 30

    # Novel Teaser Footer Card
    card_y = H - 240
    draw.rounded_rectangle([50, card_y, W - 50, card_y + 180], radius=20, fill=(15, 23, 42))
    draw.text((W // 2, card_y + 45), f"🔥 ฉากเด็ดจากเรื่อง: {clean_title[:26]}", font=get_font(32, bold=True), fill="#F59E0B", anchor="mm")
    draw.text((W // 2, card_y + 95), "เมื่อนางร้ายหมดรัก ท่านประธานก็เริ่มคลั่งรักจนเสียอาการ!", font=get_font(24), fill="#E2E8F0", anchor="mm")
    draw.text((W // 2, card_y + 140), "👉 ค้นหาชื่อเรื่องบน ReadAWrite & Dek-D ได้เลย!", font=get_font(26, bold=True), fill="#10B981", anchor="mm")

    canvas.save(out_path, quality=95)
    print(f"  💬 สร้างภาพแชทตัวละครสำเร็จ: {out_path}")
    return out_path


# ============================================================================
# 3. GOLDEN QUOTE CARD (การ์ดคำคมทัชใจ สไตล์ Dark Luxury)
# ============================================================================

def generate_golden_quote_card(
    story_title: str,
    quote_text: str,
    out_path: Optional[str] = None
) -> str:
    """สร้างการ์ดคำคมขนาด 1:1 (1080x1080) สำหรับแชร์ลง Twitter / Instagram"""
    S = 1080
    canvas = Image.new("RGB", (S, S), (15, 17, 26))
    draw = ImageDraw.Draw(canvas, "RGBA")

    clean_title = story_title.replace("_", " ")
    if not out_path:
        out_path = os.path.join(SOCIAL_OUTPUT_DIR, f"{story_title}_QUOTE_CARD.png")

    # กรอบเส้นสีทองคู่
    draw.rectangle([40, 40, S - 40, S - 40], outline=(212, 175, 55, 180), width=3)
    draw.rectangle([55, 55, S - 55, S - 55], outline=(212, 175, 55, 100), width=1)

    # สัญลักษณ์คำพูดใหญ่ “ ”
    mark_f = get_font(120, bold=True)
    draw.text((S // 2, 220), "“", font=mark_f, fill="#D4AF37", anchor="mm")

    # ตัดข้อความคำคม
    lines = []
    tmp = ""
    for char in quote_text:
        tmp += char
        if len(tmp) >= 22:
            lines.append(tmp)
            tmp = ""
    if tmp:
        lines.append(tmp)

    quote_f = get_font(42, bold=True)
    start_y = 380
    for l in lines[:5]:
        draw.text((S // 2, start_y), l, font=quote_f, fill="#F8FAFC", anchor="mm")
        start_y += 65

    # ลายเซ็นผู้แต่งและเรื่อง
    sig_f = get_font(28)
    draw.text((S // 2, S - 200), f"— เงาพันจันทร์", font=sig_f, fill="#D4AF37", anchor="mm")
    title_f = get_font(24)
    draw.text((S // 2, S - 150), f"จากนิยายเรื่อง: {clean_title}", font=title_f, fill="#94A3B8", anchor="mm")

    canvas.save(out_path, quality=95)
    print(f"  ✨ สร้างการ์ดคำคมทองสำเร็จ: {out_path}")
    return out_path


def generate_all_social_assets_for_story(story_name: str) -> Dict[str, str]:
    """ผลิตชุดคอนเทนต์โซเชียลครบเซ็ต 3 อย่างสำหรับเรื่องที่ระบุ"""
    print(f"\n🎨 [Viral Social Studio] เริ่มต้นผลิตสื่อกราฟิกโปรโมทสำหรับ: '{story_name}'...")
    
    # 1. 4-Panel Comic
    comic_path = generate_4panel_comic(story_name)

    # 2. Character Chat Mockup
    chat_path = generate_character_chat_mockup(story_name)

    # 3. Golden Quote Card
    quote = "ในวันที่คุณเพิ่งเริ่มเห็นค่าของฉัน... ฉันอาจจะกลายเป็นคนที่คุณไม่มีวันเอื้อมถึงอีกต่อไปแล้ว"
    quote_path = generate_golden_quote_card(story_name, quote)

    return {
        "comic": comic_path,
        "chat": chat_path,
        "quote": quote_path
    }


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "เมื่อนางร้ายหมดรัก_ท่านประธานก็เริ่มคลั่ง"
    generate_all_social_assets_for_story(target)
