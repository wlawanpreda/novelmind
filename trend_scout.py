"""
ANSRE Trend Scout — จัดอันดับเรื่องที่ "ควรลงมือทำต่อ" ตามโอกาสตลาด
==================================================================
รวมสัญญาณหลายอย่างเป็น opportunity score:
  • popularity_score (ความนิยมต้นทาง 0-100)
  • rating (คะแนนรีวิว)
  • market_fit_score (คะแนนที่ AI ให้ตอน analyze 0-10)
  • genre heat — หมวดที่กำลังมาแรง (จาก Trend_Report)
  • freshness — อัปเดตล่าสุดใหม่แค่ไหน
  • สถานะ — ยังไม่ได้ดัดแปลง = โอกาสใหม่ (boost)

ใช้:  python trend_scout.py [./SecondBrain]
"""
import os
import re
import sys
import glob
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))

W = {"pop": 0.30, "rating": 0.15, "fit": 0.25, "heat": 0.20, "fresh": 0.10}


def _frontmatter(fp):
    fm = {}
    try:
        with open(fp, "r", encoding="utf-8") as f:
            txt = f.read()
    except Exception:
        return fm
    if not txt.startswith("---"):
        return fm
    block = txt.split("---", 2)[1]
    for line in block.splitlines():
        if ":" in line and not line.startswith("  "):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def _genre_heat(sb):
    """หมวด → ความแรง (นับจาก 'หมวดยอดนิยม' ใน Trend_Report)"""
    fp = os.path.join(sb, "Trend_Report.md")
    heat = {}
    if not os.path.exists(fp):
        return heat
    with open(fp, "r", encoding="utf-8") as f:
        txt = f.read()
    m = re.search(r"##\s*หมวดยอดนิยม(.*?)(\n##|\n---|\Z)", txt, re.S)
    if not m:
        return heat
    for line in m.group(1).splitlines():
        mm = re.match(r"\s*-\s*(.+?)\s*\(×(\d+)\)", line)
        if mm:
            heat[mm.group(1).strip().lower()] = int(mm.group(2))
    return heat


def _fresh_score(val):
    """0-1 จากความสดของ last_updated (ภายใน 30 วัน = 1, เกิน 180 วัน = 0)"""
    if not val:
        return 0.3
    try:
        s = re.sub(r"[TZ].*$", "", str(val))[:10]
        d = datetime.strptime(s, "%Y-%m-%d")
        days = (datetime.now() - d).days
        if days <= 30:
            return 1.0
        if days >= 180:
            return 0.0
        return 1 - (days - 30) / 150
    except Exception:
        return 0.3


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def scout(sb):
    heat = _genre_heat(sb)
    max_heat = max(heat.values()) if heat else 1
    rows = []
    for fp in glob.glob(os.path.join(sb, "01_Scouting_Pool", "*.md")):
        fm = _frontmatter(fp)
        genre = (fm.get("genre") or "").lower()
        # genre heat: จับคู่บางส่วน (หมวดต้นทางอาจเป็นภาษาญี่ปุ่น/อังกฤษ)
        gh = 0
        for k, v in heat.items():
            if genre and (genre in k or k in genre or any(t in k for t in genre.split() if len(t) > 2)):
                gh = max(gh, v)
        s_pop = min(_f(fm.get("popularity_score")) / 100, 1)
        s_rating = min(_f(fm.get("rating")) / 5, 1)
        s_fit = min(_f(fm.get("market_fit_score")) / 10, 1)
        s_heat = gh / max_heat if max_heat else 0
        s_fresh = _fresh_score(fm.get("last_updated"))
        score = (W["pop"] * s_pop + W["rating"] * s_rating + W["fit"] * s_fit +
                 W["heat"] * s_heat + W["fresh"] * s_fresh)
        recreated = bool(fm.get("recreation_title"))
        # ยังไม่ดัดแปลง = โอกาสใหม่ → boost; ดัดแปลงแล้ว → ลดความสำคัญลงนิด
        score *= 1.0 if not recreated else 0.85
        reasons = []
        if s_pop > 0.7:
            reasons.append(f"ฮิตต้นทาง {int(s_pop*100)}%")
        if s_fit > 0.7:
            reasons.append(f"AI ให้ fit {fm.get('market_fit_score')}/10")
        if s_heat > 0:
            reasons.append("หมวดกำลังมาแรง")
        if s_fresh > 0.8:
            reasons.append("อัปเดตสด")
        if not recreated:
            reasons.append("ยังไม่ได้ดัดแปลง")
        rows.append({
            "title": fm.get("thai_working_title") or fm.get("recreation_title") or fm.get("title") or os.path.basename(fp),
            "original": fm.get("title", ""),
            "source": fm.get("source", ""),
            "genre": fm.get("genre", ""),
            "score": round(score * 100, 1),
            "recreated": recreated,
            "popularity": int(_f(fm.get("popularity_score"))),
            "rating": fm.get("rating", ""),
            "fit": fm.get("market_fit_score", ""),
            "reasons": reasons,
            "breakdown": {"pop": round(s_pop, 2), "rating": round(s_rating, 2),
                          "fit": round(s_fit, 2), "heat": round(s_heat, 2), "fresh": round(s_fresh, 2)},
        })
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows


if __name__ == "__main__":
    sb = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "SecondBrain")
    rows = scout(sb)
    print(f"จัดอันดับ {len(rows)} เรื่องตามโอกาสตลาด:\n")
    for i, r in enumerate(rows[:12], 1):
        tag = "🆕" if not r["recreated"] else "✓"
        print(f"{i:2d}. [{r['score']:5.1f}] {tag} {r['title'][:40]}  · {', '.join(r['reasons'][:3])}")
