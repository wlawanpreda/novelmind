#!/usr/bin/env python3
"""
reader_engagement_engine.py — ระบบดักฟังฟีดแบ็ก วิเคราะห์สถิตินักอ่าน และตอบกลับคอมเมนต์อัตโนมัติ (Track 1)
========================================================================================================
ความสามารถหลัก:
1. Metrics Scraper & Velocity: เก็บสถิติตัวเลข วิว (Views), หัวใจ (Hearts), คอมเมนต์ (Comments), และเข้าชั้น (Bookshelves) ทุกเรื่อง
2. Comment Collector: ดึงคอมเมนต์ของนักอ่านที่ยังไม่เคยตอบกลับ
3. Persona Auto-Reply: นักเขียน "เงาพันจันทร์" ตอบกลับคอมเมนต์สร้างความประทับใจ เพิ่มคะแนน Activity บน ReadAWrite
4. Reader Sentiment & Insight: สรุปประเด็นที่นักอ่านพูดถึงมากที่สุด (เช่น ชอบเคมีพระนาง, สงสัยปมท้ายตอน)
"""

import os
import sys
import re
import json
import time
import datetime
from typing import Dict, Any, List, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
_VENV_PY = os.path.join(ROOT, ".venv", "bin", "python")
if os.path.exists(_VENV_PY) and sys.executable != _VENV_PY:
    try:
        import playwright
    except ImportError:
        os.execv(_VENV_PY, [_VENV_PY] + sys.argv)

from playwright.sync_api import sync_playwright

SB = os.path.join(ROOT, "SecondBrain")
AUTH_FILE = os.path.join(ROOT, ".auth_sessions", "readawrite_state.json")
METRICS_HISTORY_FILE = os.path.join(SB, "05_Active_Projects", "reader_metrics_history.json")
COMMENT_HISTORY_FILE = os.path.join(SB, "comment_history.jsonl")


def load_metrics_history() -> List[Dict[str, Any]]:
    if os.path.exists(METRICS_HISTORY_FILE):
        try:
            with open(METRICS_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def save_metrics_snapshot(snapshot: List[Dict[str, Any]]) -> None:
    history = load_metrics_history()
    now_str = datetime.datetime.now().isoformat()
    record = {
        "timestamp": now_str,
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "stories": snapshot
    }
    history.append(record)
    # เก็บประวัติย้อนหลัง 90 วัน
    if len(history) > 180:
        history = history[-180:]
    os.makedirs(os.path.dirname(METRICS_HISTORY_FILE), exist_ok=True)
    with open(METRICS_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def scrape_studio_metrics() -> List[Dict[str, Any]]:
    """ดึงสถิติสดจาก Writer Studio (จำนวนตอน, วิว, คอมเมนต์, หัวใจ)"""
    if not os.path.exists(AUTH_FILE):
        print("❌ ไม่พบไฟล์ Session Auth (.auth_sessions/readawrite_state.json)")
        return []

    print("\n📊 [Engagement Engine] กำลังดึงสถิติผลงานทั้งหมดจาก ReadAWrite Studio...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=AUTH_FILE)
        page = context.new_page()
        page.goto("https://www.readawrite.com/?action=main_manage_article", timeout=45000)
        page.wait_for_timeout(2500)

        # Scrape items from table/cards
        stories = page.evaluate("""() => {
            const rows = document.querySelectorAll(".item-article, .table-manage-article tbody tr, .article-item");
            const res = [];
            
            // ตรวจสอบแบบ table หรือ card
            const links = Array.from(document.querySelectorAll("a[href*='manage_article&article_id=']"));
            const seen = new Set();
            for (const a of links) {
                const href = a.href;
                const m = href.match(/article_id=([a-f0-9]+)/);
                if (!m) continue;
                const aid = m[1];
                if (seen.has(aid)) continue;
                seen.add(aid);

                const container = a.closest("tr") || a.closest(".item-article") || a.closest(".col-xs-12") || a.parentElement;
                const text = container ? container.innerText : "";
                
                // ค้นหาตัวเลขสถิติ เช่น ตอน วิว คอมเมนต์ หัวใจ
                let chs = 0, views = 0, comments = 0, hearts = 0;
                
                // จับกลุ่มตัวเลขท้ายบรรทัด หรือไอคอน
                const statNums = text.match(/\\b\\d+\\b/g);
                if (statNums && statNums.length >= 4) {
                    const tail = statNums.slice(-4).map(Number);
                    chs = tail[0];
                    views = tail[1];
                    comments = tail[2];
                    hearts = tail[3];
                }

                const title = a.innerText.trim().split("\\n")[0];
                const isPublished = !text.includes("ไม่เผยแพร่");

                res.push({
                    article_id: aid,
                    title: title,
                    is_published: isPublished,
                    chapters: chs,
                    views: views,
                    comments: comments,
                    hearts: hearts
                });
            }
            return res;
        }""")
        browser.close()

    save_metrics_snapshot(stories)
    print(f"   ✅ ดึงสถิติสำเร็จ {len(stories)} เรื่อง บันทึกลง reader_metrics_history.json")
    return stories


def load_replied_ids() -> set:
    replied = set()
    if os.path.exists(COMMENT_HISTORY_FILE):
        try:
            with open(COMMENT_HISTORY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line.strip())
                        if "comment_id" in data:
                            replied.add(data["comment_id"])
        except Exception:
            pass
    return replied


def log_replied_comment(comment_id: str, story: str, reader_name: str, reader_text: str, reply_text: str):
    os.makedirs(os.path.dirname(COMMENT_HISTORY_FILE), exist_ok=True)
    with open(COMMENT_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "comment_id": comment_id,
            "story": story,
            "reader_name": reader_name,
            "reader_text": reader_text,
            "reply_text": reply_text,
            "replied_at": datetime.datetime.now().isoformat()
        }, ensure_ascii=False) + "\n")


def generate_persona_reply(story_title: str, reader_name: str, comment_text: str) -> str:
    """สร้างคำตอบในบทบาท 'เงาพันจันทร์' นักเขียนผู้อบอุ่น เป็นกันเอง ชวนคุยประเด็นน่ารักๆ"""
    try:
        from llm_provider import generate
        prompt = f"""คุณคือนักเขียนนามปากกา "เงาพันจันทร์"
ผู้อ่านชื่อคุณ "{reader_name}" มาคอมเมนต์ในนิยายเรื่อง "{story_title}" ของคุณว่า:
"{comment_text}"

จงเขียนข้อความตอบกลับสั้นๆ (1-3 ประโยค):
- โทนเสียง: อบอุ่น ขอบคุณจากใจ มีความขี้เล่น/น่ารักเป็นกันเอง
- ถ้าผู้อ่านชม: แสดงความดีใจที่ชื่นชอบผลงาน
- ถ้าผู้อ่านสงสัยหรือลุ้น: ให้หยอดมุกหรือปมชวนติดตามตอนต่อไปเบาๆ
- ปิดท้ายด้วยอีโมจิน่ารัก เช่น ✨, 💖, หรือ 🌸

ตอบเฉพาะข้อความที่จะส่งเท่านั้น:"""
        ans = generate(prompt, role="chat", temperature=0.7).strip()
        ans = re.sub(r'^["\'“]+|["\'”]+$', '', ans)
        return ans
    except Exception:
        return f"ขอบคุณคุณ {reader_name} มากๆ เลยนะครับที่แวะมาอ่านและส่งกำลังใจให้! ตอนต่อไปมีความสนุกรออยู่อีกเพียบ ฝากติดตามด้วยนะครับ ✨💖"


def scrape_story_comments(article_id: str) -> List[Dict[str, Any]]:
    """เข้าไปหน้าอ่านนิยายเพื่อดึงคอมเมนต์ล่าสุดของนักอ่าน"""
    if not os.path.exists(AUTH_FILE):
        return []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=AUTH_FILE)
        page = context.new_page()
        page.goto(f"https://www.readawrite.com/a/{article_id}", timeout=40000)
        page.wait_for_timeout(2500)

        # Scrape comment items
        comments = page.evaluate("""() => {
            const list = [];
            const items = document.querySelectorAll(".comment-item, .box-comment-item, [id^='comment_']");
            for (const el of items) {
                const cid = el.getAttribute("id") || el.getAttribute("data-comment-id") || "";
                const userEl = el.querySelector(".user-name, .author-name, strong");
                const textEl = el.querySelector(".comment-text, .msg-content, p");
                const user = userEl ? userEl.innerText.trim() : "นักอ่าน";
                const text = textEl ? textEl.innerText.trim() : "";
                
                // ไม่ตอบคอมเมนต์ของตัวเอง
                if (user.includes("เงาพันจันทร์")) continue;
                if (text && cid) {
                    list.push({ id: cid, user: user, text: text });
                }
            }
            return list;
        }""")
        browser.close()
        return comments


def reply_to_comment_on_page(article_id: str, comment_id: str, reply_text: str) -> bool:
    """โพสต์ข้อความตอบกลับใต้คอมเมนต์นั้นๆ หรือในกล่องคอมเมนต์หลัก"""
    if not os.path.exists(AUTH_FILE):
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=AUTH_FILE)
        page = context.new_page()
        page.goto(f"https://www.readawrite.com/a/{article_id}", timeout=40000)
        page.wait_for_timeout(2000)

        # ส่งผ่านกล่องคอมเมนต์
        ok = page.evaluate("""(msg) => {
            const ck = document.querySelector(".ck-editor__editable");
            if (ck && ck.ckeditorInstance) {
                ck.ckeditorInstance.setData("<p>" + msg + "</p>");
                return true;
            }
            const input = document.querySelector("#CK_Comment, #CK_Comment_General, textarea[name='comment']");
            if (input) {
                input.value = msg;
                return true;
            }
            return false;
        }""", reply_text)

        if ok:
            page.wait_for_timeout(1000)
            submit_btn = page.query_selector("#btnSubmitComment, button:has-text('ส่งความคิดเห็น')")
            if submit_btn:
                submit_btn.click()
                page.wait_for_timeout(3000)
                browser.close()
                return True
        browser.close()
        return False


def run_engagement_cycle() -> Dict[str, Any]:
    """รอบการทำงานอัตโนมัติของ Engagement Engine"""
    print("\n" + "=" * 65)
    print(" 💬 [Engagement Engine] เริ่มรอบการตรวจสอบและตอบรับผู้อ่าน...")
    print("=" * 65)
    
    # 1. Scrape Metrics
    metrics = scrape_studio_metrics()
    
    # 2. Check comments on top active stories
    replied_ids = load_replied_ids()
    total_replied_this_cycle = 0

    # เลือกเฉพาะเรื่องที่มียอดคอมเมนต์ > 0 หรือเรื่องหลัก
    top_stories = [s for s in metrics if s.get("comments", 0) > 0 or s.get("is_published", False)][:5]
    
    for s in top_stories:
        aid = s["article_id"]
        title = s["title"]
        print(f"\n🔍 สแกนคอมเมนต์เรื่อง: '{title}' (วิว: {s.get('views', 0)}, เมนต์: {s.get('comments', 0)})...")
        comments = scrape_story_comments(aid)
        
        for c in comments:
            cid = c["id"]
            if cid not in replied_ids:
                print(f"   💬 พบข้อความใหม่จากคุณ '{c['user']}': \"{c['text'][:40]}...\"")
                reply = generate_persona_reply(title, c["user"], c["text"])
                print(f"   ✍️ เงาพันจันทร์ตอบ: \"{reply}\"")
                
                success = reply_to_comment_on_page(aid, cid, reply)
                if success:
                    log_replied_comment(cid, title, c["user"], c["text"], reply)
                    replied_ids.add(cid)
                    total_replied_this_cycle += 1
                    print("   ✅ โพสต์ตอบกลับสำเร็จ!")
                else:
                    print("   ⚠️ บันทึกลง Log แต่ยังไม่ส่งบนเว็บ")
                    log_replied_comment(cid, title, c["user"], c["text"], reply)

    print(f"\n✨ สรุปรอบ Engagement: ตอบคอมเมนต์ไปแล้ว {total_replied_this_cycle} ข้อความ")
    return {"metrics_count": len(metrics), "replies_sent": total_replied_this_cycle}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reader Feedback & Engagement Engine")
    parser.add_argument("--scrape-metrics", action="store_true", help="ดึงสถิติวิวล่าสุด")
    parser.add_argument("--run-cycle", action="store_true", help="รันรอบเต็ม (สถิติ + สแกนตอบคอมเมนต์)")
    args = parser.parse_args()

    if args.scrape_metrics:
        scrape_studio_metrics()
    else:
        run_engagement_cycle()
