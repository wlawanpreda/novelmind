#!/usr/bin/env python3
"""
comment_responder.py — ระบบ AI ตอบกลับคอมเมนต์นักอ่านสร้าง Engagement (Author Persona: เงาพันจันทร์)
================================================================================================
หน้าที่:
1. สแกนความคิดเห็นของนักอ่านจาก ReadAWrite และ YouTube
2. ส่งเนื้อหาคอมเมนต์ให้นักเขียน AI ในบทบาท "เงาพันจันทร์" (อบอุ่น, ถ่อมตน, ตอบคำถามน่ารัก, ขอบคุณนักอ่าน)
3. ตรวจสอบประวัติเพื่อป้องกันการตอบซ้ำ (Dedup via comment_history.jsonl)
4. โพสต์ตอบกลับอัตโนมัติหรือบันทึกเป็น Draft ให้ตรวจสอบ
"""

from __future__ import annotations

import os
import re
import sys
import json
import time
from typing import Dict, Any, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AUTH_FILE = os.path.join(ROOT, ".auth_sessions", "readawrite_state.json")
HISTORY_FILE = os.path.join(SB, "comment_history.jsonl")


def load_replied_ids() -> set:
    replied = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line.strip())
                    if "comment_id" in data:
                        replied.add(data["comment_id"])
        except Exception:
            pass
    return replied


def save_reply_log(comment_id: str, platform: str, story: str, reader_text: str, reply_text: str):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "comment_id": comment_id,
            "platform": platform,
            "story": story,
            "reader_text": reader_text,
            "reply_text": reply_text,
            "replied_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        }, ensure_ascii=False) + "\n")


def generate_author_reply(story_title: str, reader_name: str, comment_text: str) -> str:
    """ใช้ AI ในบทบาท 'เงาพันจันทร์' สรรค์สร้างข้อความตอบกลับที่อบอุ่นและสร้างความประทับใจ"""
    from llm_provider import generate

    prompt = f"""คุณคือนักเขียนนิยายชื่อ "เงาพันจันทร์"
มีนักอ่านชื่อคุณ "{reader_name}" มาคอมเมนต์ในนิยายเรื่อง "{story_title}" ของคุณว่า:
"{comment_text}"

จงเขียนข้อความตอบกลับนักอ่านสั้นๆ 1-3 ประโยคในฐานะนักเขียน:
- โทนเสียง: อบอุ่น สุภาพ เป็นกันเอง ขอบคุณที่เข้ามาอ่านและให้กำลังใจ
- ถ้าคอมเมนต์ถามคำถามหรือสงสัยในเนื้อเรื่อง: ให้ตอบแบบหยอดปมชวนลุ้นตอนต่อไปเบาๆ
- ห้ามใช้คำหยาบ ห้ามสปอยล์จนหมดสนุก ตอบด้วยความจริงใจ

ตอบเฉพาะข้อความที่จะส่งให้นักอ่านเท่านั้น:"""

    try:
        reply = generate(prompt, role="chat", temperature=0.7).strip()
        # ตัดเครื่องหมายคำพูดรอบข้อความถ้ามี
        reply = re.sub(r'^["\'“]+|["\'”]+$', '', reply)
        return reply
    except Exception as e:
        return f"ขอบคุณคุณ {reader_name} มากๆ เลยนะครับที่แวะมาอ่านและให้กำลังใจ ฝากติดตามตอนต่อไปด้วยนะครับ! ✨"


def post_author_pinned_note(article_id: str, note_text: str, dry_run: bool = False) -> bool:
    """โพสต์ข้อความพูดคุย/ขอบคุณจากนักเขียนใต้เรื่องบน ReadAWrite"""
    if dry_run:
        print(f"[dry-run] Would post author note on {article_id}: {note_text}")
        return True

    if not os.path.exists(AUTH_FILE):
        return False

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=AUTH_FILE)
        page = context.new_page()
        page.goto(f"https://www.readawrite.com/a/{article_id}", timeout=35000)
        page.wait_for_timeout(2000)

        # ใส่ข้อความในกล่องคอมเมนต์ของนักเขียน
        set_ok = page.evaluate("""(text) => {
            const ck = document.querySelector(".ck-editor__editable");
            if (ck && ck.ckeditorInstance) {
                ck.ckeditorInstance.setData("<p>" + text + "</p>");
                return true;
            }
            const txt = document.querySelector("#CK_Comment, #CK_Comment_General");
            if (txt) {
                txt.value = text;
                return true;
            }
            return false;
        }""", note_text)

        if not set_ok:
            browser.close()
            return False

        page.wait_for_timeout(1000)
        # กดส่งความคิดเห็น
        page.click("#btnSubmitComment", force=True)
        page.wait_for_timeout(3000)
        browser.close()
        return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Author Persona Comment Responder")
    parser.add_argument("--test", action="store_true", help="ทดสอบจำลองตอบคอมเมนต์")
    args = parser.parse_args()

    if args.test:
        test_comment = "เรื่องนี้น่าติดตามมากเลยครับ พระเอกเก่งแบบมีเหตุผล ไม่ได้เทพเกินไป ลุ้นมากว่าตอนต่อไปจะรอดไหม!"
        reply = generate_author_reply("ร้านค้าเหนือโลก: กระจกเงาคนตาย", "นักอ่านเงาหมายเลข 9", test_comment)
        print(f"📖 ข้อความนักอ่าน: {test_comment}")
        print(f"✍️ คำตอบจาก 'เงาพันจันทร์':\n{reply}")
    else:
        print("Comment Responder Engine ready.")
