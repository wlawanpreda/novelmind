"""
monetization_auditor.py — Monetization Readiness & Audience Threshold Gate
==========================================================================
ระบบตรวจวัดความพร้อมในการเปิดสร้างรายได้ (Monetization Gatekeeper):
ยึดหลักเกณฑ์: "ยังไม่ติดเหรียญถ้ายังไม่มีคนอ่านมากพอ เน้นสร้างนิยายดีและสะสมคนอ่านก่อน"

เกณฑ์ผ่านเข้าสู่เฟสเปิดสร้างรายได้ (Monetization Ready Thresholds):
1. ยอดวิวรวมต่อเรื่อง (Total Views) >= 3,000 วิว
2. ยอดเพิ่มเข้าชั้น (Bookshelf Adds) >= 200 คน
3. อัตราอ่านจบตอน (Completion Rate) >= 50%
4. มีนิยายเสียงรองรับบน YouTube อย่างน้อย 3 ตอน เพื่อสร้างกระแส Cross-Platform
"""

import os
import sys
import json

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
ANALYTICS_FILE = os.path.join(SB, "Analytics", "readership_analytics.json")
REPORT_FILE = os.path.join(SB, "Analytics", "Monetization_Readiness_Report.md")

THRESHOLDS = {
    "min_views": 3000,
    "min_chapters": 5,
    "min_retention_pct": 50.0
}

def audit_monetization():
    if not os.path.exists(ANALYTICS_FILE):
        print(f"Analytics file not found: {ANALYTICS_FILE}. Run readership_monitor.py first.")
        return

    with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    report_lines = [
        "# 📊 รายงานประเมินความพร้อมในการเปิดสร้างรายได้ (Monetization Readiness Gate)",
        "> **นโยบาย:** มุ่งเน้นสร้างฐานแฟนคลับและส่งต่อคนอ่านไปสู่ YouTube แบบฟรี 100% จนกว่าจะผ่านเกณฑ์ความนิยม\n",
        "| ชื่อเรื่อง | จำนวนตอน | ยอดวิวรวม | สถานะปัจจุบัน | แผนปฏิบัติการที่แนะนำ |",
        "| :--- | :---: | :---: | :---: | :--- |"
    ]

    for item in data:
        name = item.get("story_name", "")
        chaps = item.get("total_chapters", 0)
        views = item.get("total_views", 0)

        # Evaluate readiness
        is_ready = views >= THRESHOLDS["min_views"] and chaps >= THRESHOLDS["min_chapters"]
        
        if is_ready:
            status = "🟢 พร้อมเปิดสร้างรายได้ (Monetization Ready)"
            action = "เปิดขาย E-Book เล่มเต็มบน Meb + ติดเหรียญอ่านล่วงหน้าตอนที่ 6 เป็นต้นไป"
        else:
            pct = min(100, int((views / THRESHOLDS["min_views"]) * 100))
            status = f"🟡 กำลังสะสมฐานแฟนคลับ ({pct}% สู่เกณฑ์)"
            action = "เปิดให้อ่านฟรี 100% + ฝัง CTA ส่งคนไปเพิ่ม Watch Time ช่อง YouTube"

        report_lines.append(f"| **{name}** | {chaps} ตอน | {views:,} วิว | {status} | {action} |")

    report_lines.extend([
        "\n---",
        "## 💡 สรุปยุทธศาสตร์เพื่อผลักดันรายได้ (Strategic Roadmap)",
        "1. **ขั้นที่ 1 (ปัจจุบัน):** ปล่อยอ่านฟรีทุกเรื่อง ดันยอดวิวและยอดคนเข้าชั้นใน ReadAWrite ให้ทะลุ 3,000 วิว พร้อมส่งทราฟฟิกไปช่อง YouTube 'เงาพันจันทร์' เพื่อสะสมชั่วโมง Watch Time สู่ 4,000 ชั่วโมง",
        "2. **ขั้นที่ 2 (เมื่อถึงเกณฑ์):** เปิดระบบ **'เหรียญอ่านล่วงหน้า (Early Bird Coins)'** 2-3 เหรียญ สำหรับบทใหม่ และทำเป็น **E-Book วางขายบน Meb**",
        "3. **ขั้นที่ 3 (YouTube Partner Program):** เมื่อผ่านเกณฑ์ 1,000 ซับและ 4,000 ชม. เปิดรับรายได้โฆษณา YouTube AdSense ควบคู่กัน"
    ])

    report_md = "\n".join(report_lines)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(report_md)
    print(f"\n✅ Saved readiness report to: {REPORT_FILE}")

if __name__ == "__main__":
    audit_monetization()
