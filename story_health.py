"""
ANSRE Story Health — สแกนหาปัญหาในเรื่องที่ผลิตแล้ว ก่อนปล่อยจริง
==================================================================
ตรวจปัญหาที่เจอจริงจากการรีวิว: error ดิบหลุดในบท, ตัวอักษรจีน/CJK หลุด,
AI meta-talk, บทสั้นผิดปกติ, สินทรัพย์ขาด

ใช้:
  from story_health import scan_story, scan_all
  scan_all("./SecondBrain")        # คืน list ทุกเรื่องพร้อมสถานะ
CLI:
  python story_health.py [./SecondBrain]   # พิมพ์รายงาน
"""
import os
import re
import glob

# (regex, label, severity)  severity: "red"=พัง/ห้ามปล่อย · "yellow"=ควรแก้
_PATTERNS = [
    (re.compile(r"Error:\s*HTTPConnectionPool|Max retries exceeded|NameResolutionError|Failed to resolve"),
     "บทมี error การเชื่อมต่อหลุด (pipeline ถูกตัดกลางคัน)", "red"),
    (re.compile(r"Traceback \(most recent call last\)"),
     "มี Python traceback หลุดในเนื้อหา", "red"),
    (re.compile(r"ในฐานะ(?:โมเดล|ปัญญาประดิษฐ์)?\s*AI|as an AI(?: language model)?|"
                r"I'?m sorry,? (?:but )?I (?:can'?t|cannot)|I cannot (?:assist|help|fulfill|create)|"
                r"在转换|假设背景|作为(?:一个)?AI"),
     "มี AI meta-talk หลุด (AI พูดกับตัวเอง)", "red"),
    (re.compile(r"[一-鿿]{4,}"),
     "มีตัวอักษรจีน/CJK หลุดในเนื้อหาไทย", "red"),
]

_MIN_CHAPTER = 1500   # ตัวอักษร


def _read(fp):
    try:
        return open(fp, "r", encoding="utf-8").read()
    except Exception:
        return ""


def _scan_text(txt, where, skip_cjk=False):
    out = []
    for rx, label, sev in _PATTERNS:
        if skip_cjk and "CJK" in label:
            continue
        if rx.search(txt):
            out.append({"label": label, "where": where, "sev": sev})
    return out


def _slug(t):
    return re.sub(r"[^\w\-_\s฀-๿]", "", t or "").strip().replace(" ", "_")


def scan_story(sb, base, title=None):
    """สแกนเรื่องเดียว (base = slug ของ recreation) → {status, issues, assets}"""
    issues = []
    ap = os.path.join(sb, "05_Active_Projects")

    # บท
    chapters = sorted(glob.glob(os.path.join(ap, "Chapters", f"{base}_Chapter_*.md")))
    for cf in chapters:
        txt = _read(cf)
        n = os.path.basename(cf).replace(".md", "").split("_Chapter_")[-1]
        issues += _scan_text(txt, f"ตอน {n}")
        if 0 < len(txt) < _MIN_CHAPTER:
            issues.append({"label": f"บทสั้นผิดปกติ ({len(txt)} ตัวอักษร) อาจเขียนไม่จบ",
                           "where": f"ตอน {n}", "sev": "yellow"})

    # ไฟล์ตัวละคร / โครงเรื่อง (outline ข้าม CJK เพราะมีบรรทัด "Inspired by: <ชื่อต้นฉบับ ญี่ปุ่น/จีน>")
    for folder, suffix, lbl, skip_cjk in [
            ("04_Character_Database", "_Characters.md", "ไฟล์ตัวละคร", False),
            ("02_Concept_Extraction", "_Outline.md", "ไฟล์โครงเรื่อง", True)]:
        fp = os.path.join(sb, folder, f"{base}{suffix}")
        if os.path.exists(fp):
            issues += _scan_text(_read(fp), lbl, skip_cjk=skip_cjk)

    # สินทรัพย์
    g = lambda *p: glob.glob(os.path.join(ap, *p))
    assets = {
        "chapters": len(chapters),
        "cover": bool(g("Covers", f"{base}_Cover*")),
        "audio": len(g("Audio_Output", f"{base}_Audiobook_*.mp3")),
        "teaser": len(g("Teasers", f"{base}_Teaser*")) + len(g("Teaser_Output", f"{base}*.mp4")),
    }
    if chapters and not assets["cover"]:
        issues.append({"label": "ยังไม่มีปก", "where": "asset", "sev": "yellow"})
    if chapters and not assets["audio"]:
        issues.append({"label": "ยังไม่มีหนังสือเสียง", "where": "asset", "sev": "yellow"})
    if chapters and not assets["teaser"]:
        issues.append({"label": "ยังไม่มี teaser", "where": "asset", "sev": "yellow"})

    reds = [i for i in issues if i["sev"] == "red"]
    yellows = [i for i in issues if i["sev"] == "yellow"]
    status = "red" if reds else ("yellow" if yellows else "green")
    return {"base": base, "title": title or base, "status": status,
            "issues": issues, "red": len(reds), "yellow": len(yellows), "assets": assets}


def scan_all(sb):
    """สแกนทุกเรื่องที่ status=Processed ใน pool → list (เรียง พังก่อน)"""
    import json
    rows = []
    for fp in glob.glob(os.path.join(sb, "01_Scouting_Pool", "*.md")):
        head = _read(fp)
        fm = {}
        m = re.match(r"^---\s*\n(.*?)\n---", head, re.DOTALL)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line and not line.startswith(" "):
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip().strip('"').strip("'")
        if fm.get("status") != "Processed":
            continue
        title = fm.get("recreation_title") or fm.get("thai_working_title") or fm.get("title")
        base = _slug(title)
        rows.append(scan_story(sb, base, title))
    order = {"red": 0, "yellow": 1, "green": 2}
    rows.sort(key=lambda r: (order.get(r["status"], 3), -r["red"], -r["yellow"]))
    return rows


if __name__ == "__main__":
    import sys
    sb = sys.argv[1] if len(sys.argv) > 1 else "./SecondBrain"
    rows = scan_all(sb)
    icon = {"red": "🔴", "yellow": "🟡", "green": "🟢"}
    n_red = sum(1 for r in rows if r["status"] == "red")
    n_yel = sum(1 for r in rows if r["status"] == "yellow")
    n_grn = sum(1 for r in rows if r["status"] == "green")
    print(f"=== Story Health: {len(rows)} เรื่อง · 🟢{n_grn} พร้อม · 🟡{n_yel} ควรแก้ · 🔴{n_red} พัง ===\n")
    for r in rows:
        print(f"{icon[r['status']]} {r['title'][:45]}  (🔴{r['red']} 🟡{r['yellow']})")
        for i in r["issues"][:6]:
            mk = "🔴" if i["sev"] == "red" else "🟡"
            print(f"      {mk} [{i['where']}] {i['label']}")
