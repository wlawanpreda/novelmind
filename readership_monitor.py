"""
readership_monitor.py — Autonomous Readership Drop-Off & Chapter Retention Monitor
================================================================================
ดึงสถิติยอดอ่านจริงแบบรายตอนจาก ReadAWrite และคำนวณ:
1. Chapter-to-Chapter Retention (% คนที่อ่านตอนก่อนหน้าแล้วกดอ่านตอนถัดไป)
2. Drop-Off Alert: ถ้าอัตราหลุดจาก Ch 1 -> Ch 2 เกิน 40% ให้แจ้งเตือนจุดปรับ Hook / Cliffhanger
3. Bookshelf & Reader Conversion: วิเคราะห์ว่าเรื่องไหนมีฐานแฟนคลับพร้อมต่อยอด
"""

import os
import sys
import json
from playwright.sync_api import sync_playwright

auth_file = '.auth_sessions/readawrite_state.json'
output_dir = "SecondBrain/Analytics"
os.makedirs(output_dir, exist_ok=True)

TRACKED_STORIES = [
    {"aid": "5738758aa9e2c5f89bcf6552d3a79187", "name": "รักกับเจ้าหญิงเพลย์บอย"},
    {"aid": "f3624f7b4e09cde8fc524dff4f2fc4bd", "name": "สมาคมประกันภัยลี้ลับ"},
    {"aid": "33e483f95428f693527c5d4843c7fef4", "name": "เมื่อนางร้ายหมดรัก ท่านประธานก็เริ่มคลั่ง"},
    {"aid": "627d9707279484797acafaba010fcf69", "name": "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70 พร้อมซูเปอร์มาร์เก็ตลับ"},
    {"aid": "e90bfef727e4730819e92444783d6850", "name": "ร้านค้าเหนือโลก: กระจกเงาคนตาย"},
    {"aid": "084947f5c23530e03094cc84bb1364b5", "name": "ยอดนักสืบสปีดรัน"},
    {"aid": "41b125951707f59f407094e795dc9c11", "name": "แสงแห่งฤดูใบไม้ผลิในเมืองเทา"},
    {"aid": "df9588a13de2636f3a23ea0ce9286e4a", "name": "เหล่ามือกระบี่ไร้แม่เหล็ก"},
    {"aid": "655b42cb45491b18752e86e6553c9fdc", "name": "เส้นทางแห่งชัยชนะในดินแดนเซ็กซ์"}
]

def analyze_story_retention(page, aid: str, name: str) -> dict:
    url = f"https://www.readawrite.com/?action=manage_article&article_id={aid}&tab=mainManageChapter"
    print(f"\nAnalyzing retention for '{name}' ({aid})...", flush=True)
    page.goto(url, timeout=35000)
    page.wait_for_timeout(3000)

    # Scrape chapter stats from table
    data = page.evaluate('''() => {
        let rows = [];
        document.querySelectorAll('tr').forEach(tr => {
            let chk = tr.querySelector('input[name=chk_chapter_guid]');
            if (chk) {
                let title = chk.getAttribute('title_name') || '';
                // Read views and comments
                let text = tr.innerText;
                let views = 0;
                let comments = 0;
                let eyeIcon = tr.querySelector('.fa-eye, i[class*="eye"]');
                if (eyeIcon && eyeIcon.parentElement) {
                    let vt = eyeIcon.parentElement.innerText.trim();
                    views = parseInt(vt.replace(/[^0-9]/g, '')) || 0;
                }
                let commentIcon = tr.querySelector('.fa-comment, i[class*="comment"]');
                if (commentIcon && commentIcon.parentElement) {
                    let ct = commentIcon.parentElement.innerText.trim();
                    comments = parseInt(ct.replace(/[^0-9]/g, '')) || 0;
                }
                rows.push({
                    guid: chk.value,
                    title: title,
                    views: views,
                    comments: comments
                });
            }
        });
        return rows;
    }''')

    # ReadAWrite lists newest first, so reverse to chronological 1 -> N
    chapters = list(reversed(data))
    
    # Calculate retention rates
    retention_rates = []
    total_views = sum(c['views'] for c in chapters)
    
    for i in range(len(chapters)):
        curr_v = chapters[i]['views']
        if i == 0:
            retention_rates.append({"chapter": chapters[i]['title'], "views": curr_v, "retention_from_prev": 100.0})
        else:
            prev_v = chapters[i-1]['views']
            pct = (curr_v / prev_v * 100.0) if prev_v > 0 else (100.0 if curr_v == 0 else 100.0)
            retention_rates.append({"chapter": chapters[i]['title'], "views": curr_v, "retention_from_prev": round(pct, 1)})

    # Health evaluation
    alerts = []
    if len(retention_rates) >= 2:
        ch1_v = retention_rates[0]['views']
        ch2_v = retention_rates[1]['views']
        if ch1_v > 5 and ch2_v / ch1_v < 0.6:
            alerts.append(f"⚠️ จุดหลุดสูง: Ch1->Ch2 ร่วงเกิน 40% แนะนำให้เร่งเครื่อง Hook และ Cliffhanger ท้ายตอน 1")

    return {
        "story_id": aid,
        "story_name": name,
        "total_chapters": len(chapters),
        "total_views": total_views,
        "chapter_analytics": retention_rates,
        "alerts": alerts if alerts else ["✅ อัตราการอ่านอยู่ในเกณฑ์ปกติ"]
    }

def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(storage_state=auth_file, viewport={'width': 1440, 'height': 1200}).new_page()

        for story in TRACKED_STORIES:
            res = analyze_story_retention(page, story["aid"], story["name"])
            results.append(res)
            print(f"  Total Views: {res['total_views']}, Chapters: {res['total_chapters']}")
            print(f"  Alerts: {res['alerts']}")

        browser.close()

    out_file = os.path.join(output_dir, "readership_analytics.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n📊 Saved readership report to: {out_file}")

if __name__ == "__main__":
    main()
