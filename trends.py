"""
ANSRE Trend Intelligence — สรุปเทรนด์จากนิยายที่ scout/analyze มา
================================================================
รวมข้อมูลนิยายยอดนิยมทั้ง pool → หา "อะไรกำลังมาแรง + จุดเด่นร่วม"
→ ออกคำแนะนำสำหรับนิยายเรื่องต่อไปของเรา (ป้อนเข้า ideation อัตโนมัติ)

ผลลัพธ์:
  SecondBrain/Trend_Report.md   — รายงานเต็ม (คน/แดชบอร์ดอ่าน)
  SecondBrain/.trend_brief.txt  — สรุปสั้น (ideation ดึงไปใช้คิดไอเดีย)

CLI:  python trends.py            สร้างรายงาน
      python trends.py brief      พิมพ์สรุปสั้น
"""
from __future__ import annotations

import os
import re
import sys
import glob
from collections import Counter

from llm_provider import generate

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
POOL = os.path.join(SB, "01_Scouting_Pool")
REPORT = os.path.join(SB, "Trend_Report.md")
BRIEF = os.path.join(SB, ".trend_brief.txt")

_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def _parse(fp):
    txt = open(fp, "r", encoding="utf-8").read()
    fm, body = {}, txt
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", txt, re.DOTALL)
    if m:
        body = m.group(2)
        cur = None
        for line in m.group(1).splitlines():
            if re.match(r"^\s+-\s", line) and cur == "tags":
                fm.setdefault("tags", []).append(line.strip()[2:].strip().strip('"'))
            elif ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                fm[k] = [] if (k == "tags" and v == "") else v
                cur = k
    return fm, body


def gather():
    """นิยายที่ analyze แล้ว เรียงตามความนิยม"""
    rows = []
    for fp in glob.glob(os.path.join(POOL, "*.md")):
        fm, body = _parse(fp)
        if fm.get("status") in ("Analyzed", "Processed"):
            rows.append((fm, body))
    rows.sort(key=lambda x: int(x[0].get("popularity_score", 0) or 0), reverse=True)
    return rows


def _section(body, header):
    m = re.search(rf"###[^\n]*{re.escape(header)}.*?\n(.+?)(?:\n###|\n##|\Z)", body, re.DOTALL)
    return m.group(1).strip() if m else ""


def build_report():
    rows = gather()
    if not rows:
        print("[trends] ยังไม่มีนิยายที่ analyze แล้ว — รัน scout + analyze ก่อน")
        return None

    # ----- รวมสถิติ -----
    tag_counter = Counter()
    genre_counter = Counter()
    for fm, _ in rows:
        for t in fm.get("tags", []) or []:
            if t:
                tag_counter[t] += 1
        g = fm.get("genre", "")
        if g:
            genre_counter[g.split("(")[0].strip()] += 1
    top_tags = tag_counter.most_common(15)
    top_genres = genre_counter.most_common(8)

    # ----- สรุปจุดเด่นของ Top 8 ป้อนให้ AI -----
    digest = []
    for fm, body in rows[:8]:
        standout = _section(body, "จุดเด่น") or _section(body, "Standout")
        digest.append(f"- {fm.get('thai_working_title') or fm.get('title')} "
                      f"(score {fm.get('popularity_score','?')}, {fm.get('genre','')}): "
                      f"{standout[:400]}")
    digest_txt = "\n".join(digest)
    tags_txt = ", ".join(f"{t}×{c}" for t, c in top_tags)

    prompt = f"""คุณคือนักวิเคราะห์เทรนด์ตลาดนิยายออนไลน์ ดูข้อมูลนิยายยอดนิยมล่าสุด {len(rows)} เรื่องนี้
แล้วสรุป "เทรนด์ที่กำลังมาแรง" และ "วิธีเอามาปรับใช้กับนิยายไทยเรื่องต่อไปของเรา"

แท็ก/ธีมที่พบบ่อย: {tags_txt}
หมวดยอดนิยม: {", ".join(g for g,_ in top_genres)}

จุดเด่นของเรื่องท็อป:
{digest_txt}

เขียนรายงานภาษาไทยกระชับ มีหัวข้อ:
1. 🔥 เทรนด์/ธีมที่กำลังมาแรง (3-5 ข้อ พร้อมเหตุผลจากข้อมูล)
2. 🧩 สูตรสำเร็จร่วม (pattern ที่เรื่องดังมักมี)
3. 🎯 คำแนะนำสำหรับนิยายเรื่องต่อไปของเรา (5 ข้อ เป็นรูปธรรม สั่งทำได้เลย)
4. 💡 ไอเดียพล็อตที่ควรลอง (3 ไอเดียสั้นๆ ที่ตรงเทรนด์แต่เป็น Original)"""
    print(f"[trends] สังเคราะห์จาก {len(rows)} เรื่อง...")
    report = generate(prompt, role="researcher")

    header = (f"# 📈 Trend Report — ANSRE Market Intelligence\n\n"
              f"*วิเคราะห์จาก {len(rows)} เรื่องยอดนิยม*\n\n"
              f"## แท็ก/ธีมที่พบบ่อย\n" + "\n".join(f"- {t} (×{c})" for t, c in top_tags) + "\n\n"
              f"## หมวดยอดนิยม\n" + "\n".join(f"- {g} (×{c})" for g, c in top_genres) + "\n\n---\n\n")
    full = header + report
    os.makedirs(SB, exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(full)
    # สรุปสั้นสำหรับ ideation
    with open(BRIEF, "w", encoding="utf-8") as f:
        f.write(f"เทรนด์ล่าสุด (แท็กบ่อย: {tags_txt}):\n{report[:1200]}")
    print(f"[trends] ✅ บันทึก {REPORT}")
    return full


def read_brief():
    """สรุปเทรนด์สั้นๆ (ให้ ideation ดึงไปใช้)"""
    if os.path.exists(BRIEF):
        return open(BRIEF, "r", encoding="utf-8").read()
    return ""


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "brief":
        print(read_brief() or "(ยังไม่มี trend brief — รัน: python trends.py)")
    else:
        out = build_report()
        if out:
            print("\n" + "=" * 50)
            print(out[:1500])
