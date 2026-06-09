"""
ANSRE Feedback Loop — Phase 5: ระบบเรียนรู้จากผลงานจริง
========================================================
ปิดวงจร: ผลิต → วัดผล → เรียนรู้ → ลำเอียงการผลิตรอบถัดไปเข้าหา "สูตรที่ปัง"

แนวคิด: บันทึกตัวเลข engagement จริงของแต่ละเรื่อง (views/likes/comments/shares)
แล้ว join กับ metadata ที่ analyze ไว้ (genre/tags/hooks) → คำนวณว่า genre/tag ไหน
ทำผลงานเฉลี่ยดีสุด → เขียน "winning-patterns brief" ป้อนกลับเข้า ideation/analyze/scout

ผลลัพธ์:
  SecondBrain/feedback.jsonl       — ledger ผลงานดิบ (1 บรรทัด/การบันทึก)
  SecondBrain/.feedback_brief.txt  — สรุปสูตรที่ปัง (ตัวอื่นดึงไปใช้ via read_brief())
  SecondBrain/Feedback_Report.md   — รายงานเต็มสำหรับคน/แดชบอร์ด

CLI:
  python feedback.py record "ชื่อเรื่อง" --views 12000 --likes 850 --comments 120 --shares 60 --platform tiktok
  python feedback.py learn            สังเคราะห์ brief จาก ledger
  python feedback.py list             ดูผลงานที่บันทึกไว้
  python feedback.py brief            พิมพ์สรุปที่ป้อนเข้า ideation
"""
from __future__ import annotations

import os
import re
import sys
import json
import glob
import argparse
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
POOL = os.path.join(SB, "01_Scouting_Pool")
LEDGER = os.path.join(SB, "feedback.jsonl")
BRIEF = os.path.join(SB, ".feedback_brief.txt")
REPORT = os.path.join(SB, "Feedback_Report.md")

# โหลด .env (เผื่อใช้ AI สังเคราะห์)
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# น้ำหนัก engagement — ยิ่ง interaction ลึก ยิ่งมีค่า (like<comment<share)
W_VIEW, W_LIKE, W_COMMENT, W_SHARE = 1, 5, 12, 25


def _now():
    """เวลาปัจจุบัน (import ในฟังก์ชันกัน Date.now ตอน import-time)"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------- อ่าน metadata จาก pool ----------
def _parse(fp):
    txt = open(fp, "r", encoding="utf-8").read()
    fm = {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", txt, re.DOTALL)
    body = txt
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


def _index_pool():
    """map: ชื่อเรื่อง (title/thai/recreation, lower) -> metadata"""
    idx = {}
    for fp in glob.glob(os.path.join(POOL, "*.md")):
        try:
            fm, body = _parse(fp)
        except Exception:
            continue
        for key in ("recreation_title", "thai_working_title", "title"):
            v = fm.get(key)
            if v:
                idx[v.strip().lower()] = (fm, body)
    return idx


def _match_meta(story: str, idx: dict):
    s = (story or "").strip().lower()
    if s in idx:
        return idx[s]
    # จับคู่หลวมๆ (substring)
    for k, val in idx.items():
        if s and (s in k or k in s):
            return val
    return None, None


def engagement_score(rec: dict) -> float:
    return (W_VIEW * rec.get("views", 0) + W_LIKE * rec.get("likes", 0)
            + W_COMMENT * rec.get("comments", 0) + W_SHARE * rec.get("shares", 0))


def engagement_rate(rec: dict) -> float:
    v = max(rec.get("views", 0), 1)
    return (rec.get("likes", 0) + rec.get("comments", 0) + rec.get("shares", 0)) / v


# ---------- บันทึกผลงาน ----------
def record(story, views=0, likes=0, comments=0, shares=0, platform="", url=""):
    rec = {
        "story": story, "platform": platform, "url": url,
        "views": int(views), "likes": int(likes),
        "comments": int(comments), "shares": int(shares),
        "recorded_at": _now(),
    }
    rec["engagement_score"] = round(engagement_score(rec), 1)
    rec["engagement_rate"] = round(engagement_rate(rec), 4)
    os.makedirs(SB, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[feedback] ✅ บันทึก '{story}' ({platform}): "
          f"score {rec['engagement_score']:.0f} · rate {rec['engagement_rate']:.2%}")
    return rec


def load_ledger():
    if not os.path.exists(LEDGER):
        return []
    out = []
    for line in open(LEDGER, "r", encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


# ---------- เรียนรู้ ----------
def learn(use_ai=False):
    rows = load_ledger()
    if not rows:
        print("[feedback] ยังไม่มีข้อมูล performance — บันทึกก่อนด้วย:")
        print('   python feedback.py record "ชื่อเรื่อง" --views 12000 --likes 850 --platform tiktok')
        return None

    idx = _index_pool()

    # join performance กับ metadata → สะสมคะแนนต่อ genre / tag
    by_genre = defaultdict(lambda: {"n": 0, "score": 0.0, "rate": 0.0})
    by_tag = defaultdict(lambda: {"n": 0, "score": 0.0, "rate": 0.0})
    per_story = defaultdict(lambda: {"n": 0, "score": 0.0, "rate": 0.0, "genre": "", "tags": []})
    matched = 0

    for r in rows:
        sc, rate = r.get("engagement_score", 0.0), r.get("engagement_rate", 0.0)
        fm, _ = _match_meta(r.get("story"), idx)
        ps = per_story[r.get("story")]
        ps["n"] += 1
        ps["score"] += sc
        ps["rate"] += rate
        if fm:
            matched += 1
            genre = (fm.get("genre") or "").split("(")[0].strip()
            if genre:
                ps["genre"] = genre
                g = by_genre[genre]
                g["n"] += 1
                g["score"] += sc
                g["rate"] += rate
            for t in (fm.get("tags") or []):
                if t:
                    ps["tags"].append(t)
                    tg = by_tag[t]
                    tg["n"] += 1
                    tg["score"] += sc
                    tg["rate"] += rate

    def _rank(d, n=10):
        out = []
        for k, v in d.items():
            if v["n"]:
                out.append((k, v["n"], v["score"] / v["n"], v["rate"] / v["n"]))
        out.sort(key=lambda x: x[2], reverse=True)
        return out[:n]

    top_genres = _rank(by_genre, 6)
    top_tags = _rank(by_tag, 12)
    top_stories = sorted(
        [(s, v["score"] / v["n"], v["rate"] / v["n"], v["genre"]) for s, v in per_story.items() if v["n"]],
        key=lambda x: x[1], reverse=True)[:8]

    # ----- เขียน brief (pure-python ก่อน — ฟรี) -----
    lines = ["สูตรที่ทำผลงานดี (จากผลงานจริง — ใช้ลำเอียงการเลือก/ปรับเรื่องต่อไป):"]
    if top_genres:
        lines.append("• หมวดที่ engagement เฉลี่ยสูงสุด: "
                     + ", ".join(f"{g}(avg {s:,.0f})" for g, _, s, _ in top_genres))
    if top_tags:
        lines.append("• แท็ก/ธีมที่ปังสุด: "
                     + ", ".join(f"{t}" for t, _, _, _ in top_tags[:8]))
    if top_stories:
        lines.append("• เรื่องที่ทำผลงานดีสุด (ถอดสูตรไปใช้ซ้ำ): "
                     + ", ".join(f"{s}" for s, _, _, _ in top_stories[:5]))
    lines.append(f"(สรุปจาก {len(rows)} การบันทึก, จับคู่ metadata ได้ {matched})")
    brief = "\n".join(lines)

    # ----- (option) ให้ AI สังเคราะห์คำแนะนำเชิงรุก -----
    ai_advice = ""
    if use_ai:
        try:
            from llm_provider import generate
            prompt = f"""คุณคือนักวิเคราะห์ data-driven ของโรงงานผลิตนิยาย
ข้อมูลผลงานจริง (engagement) ของเรื่องที่ปล่อยไปแล้ว:

หมวดที่เฉลี่ยดีสุด: {', '.join(f'{g} (avg score {s:,.0f}, rate {rt:.1%}, n={n})' for g,n,s,rt in top_genres)}
แท็กที่ดีสุด: {', '.join(f'{t}(avg {s:,.0f})' for t,n,s,rt in top_tags)}
เรื่องท็อป: {', '.join(f'{s} (avg {sc:,.0f})' for s,sc,rt,g in top_stories)}

สรุปสั้นๆ (ภาษาไทย) 4-5 ข้อ "ควรทำอะไรซ้ำ / ควรเลิกทำอะไร" สำหรับเรื่องต่อไป — สั่งทำได้จริง"""
            ai_advice = generate(prompt, role="researcher")
        except Exception as e:
            ai_advice = f"(ข้าม AI synthesis: {e})"

    os.makedirs(SB, exist_ok=True)
    with open(BRIEF, "w", encoding="utf-8") as f:
        f.write(brief + (("\n\nคำแนะนำ:\n" + ai_advice) if ai_advice else ""))

    # ----- รายงานเต็ม -----
    rep = ["# 📊 Feedback Report — ANSRE Performance Intelligence\n",
           f"*จาก {len(rows)} การบันทึก · จับคู่ metadata ได้ {matched}*\n",
           "## 🏆 หมวดที่ทำผลงานดีสุด (avg engagement)",
           *[f"- **{g}** — avg score {s:,.0f} · rate {rt:.1%} (n={n})" for g, n, s, rt in top_genres],
           "\n## 🔖 แท็ก/ธีมที่ปัง",
           *[f"- {t} — avg score {s:,.0f} (n={n})" for t, n, s, rt in top_tags],
           "\n## 📚 เรื่องที่ทำผลงานดีสุด",
           *[f"- **{s}** — avg score {sc:,.0f} · rate {rt:.1%} · {g}" for s, sc, rt, g in top_stories]]
    if ai_advice:
        rep += ["\n---\n## 🎯 คำแนะนำเชิงรุก (AI)\n", ai_advice]
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(rep))

    print(f"[feedback] ✅ เรียนรู้จาก {len(rows)} การบันทึก → {BRIEF}")
    print("\n" + brief)
    return brief


def _est_cost_per_story():
    """ประมาณต้นทุน LLM เฉลี่ยต่อเรื่อง = ต้นทุนรวม / จำนวนเรื่องที่เขียนแล้ว"""
    log = os.path.join(SB, "llm_usage.jsonl")
    total = 0.0
    if os.path.exists(log):
        for line in open(log, encoding="utf-8"):
            try:
                total += json.loads(line).get("est_usd", 0) or 0
            except Exception:
                pass
    n = len(glob.glob(os.path.join(POOL, "*.md"))) or 1
    processed = sum(1 for fp in glob.glob(os.path.join(POOL, "*.md"))
                    if 'status: "Processed"' in (open(fp, encoding="utf-8").read(1500)))
    return round(total / max(processed, 1), 3), round(total, 2), processed


def roi():
    """ROI ต่อเรื่อง: engagement จริง (feedback) เทียบต้นทุนประมาณการ"""
    rows = load_ledger()
    est, total_cost, n_processed = _est_cost_per_story()
    if not rows:
        print(f"[ROI] ยังไม่มีข้อมูล engagement — บันทึกด้วย: python feedback.py record \"เรื่อง\" --views N")
        print(f"      (ต้นทุนรวม ${total_cost} · {n_processed} เรื่อง · เฉลี่ย ~${est}/เรื่อง)")
        return None
    from collections import defaultdict
    per = defaultdict(lambda: {"score": 0.0, "views": 0, "n": 0})
    for r in rows:
        p = per[r.get("story")]
        p["score"] += r.get("engagement_score", 0)
        p["views"] += r.get("views", 0)
        p["n"] += 1
    out = []
    for story, v in per.items():
        roi_val = v["score"] / est if est else 0
        out.append((story, v["score"], v["views"], roi_val))
    out.sort(key=lambda x: x[3], reverse=True)
    print(f"=== ROI ต่อเรื่อง (ต้นทุนเฉลี่ย ~${est}/เรื่อง · รวม ${total_cost}) ===")
    print(f"{'ROI':>8} {'engagement':>11} {'views':>9}  เรื่อง")
    for story, sc, vw, rv in out:
        print(f"{rv:>8.0f} {sc:>11,.0f} {vw:>9,}  {story[:40]}")
    return out


def read_brief():
    """สรุปสูตรที่ปัง (ให้ ideation/analyze ดึงไปใช้ลำเอียงการผลิต)"""
    if os.path.exists(BRIEF):
        return open(BRIEF, "r", encoding="utf-8").read()
    return ""


def _list():
    rows = load_ledger()
    if not rows:
        print("(ยังไม่มีผลงานบันทึก)")
        return
    print(f"=== ผลงานที่บันทึก ({len(rows)}) ===")
    for r in sorted(rows, key=lambda x: x.get("engagement_score", 0), reverse=True):
        print(f"  score {r.get('engagement_score',0):>9,.0f} · rate {r.get('engagement_rate',0):>6.1%} · "
              f"{r.get('platform','?'):<8} · {r.get('story')}")


def main():
    ap = argparse.ArgumentParser(description="ANSRE feedback loop (Phase 5)")
    sub = ap.add_subparsers(dest="cmd")

    rec = sub.add_parser("record", help="บันทึกผลงานจริงของเรื่อง")
    rec.add_argument("story")
    rec.add_argument("--views", type=int, default=0)
    rec.add_argument("--likes", type=int, default=0)
    rec.add_argument("--comments", type=int, default=0)
    rec.add_argument("--shares", type=int, default=0)
    rec.add_argument("--platform", default="")
    rec.add_argument("--url", default="")

    lrn = sub.add_parser("learn", help="สังเคราะห์ brief จาก ledger")
    lrn.add_argument("--ai", action="store_true", help="ให้ AI ช่วยสรุปคำแนะนำ (มีค่า token)")

    sub.add_parser("list", help="ดูผลงานที่บันทึก")
    sub.add_parser("brief", help="พิมพ์ brief ที่ป้อนเข้า ideation")
    sub.add_parser("roi", help="ROI ต่อเรื่อง (engagement เทียบต้นทุน)")

    a = ap.parse_args()
    if a.cmd == "record":
        record(a.story, a.views, a.likes, a.comments, a.shares, a.platform, a.url)
    elif a.cmd == "learn":
        learn(use_ai=a.ai)
    elif a.cmd == "list":
        _list()
    elif a.cmd == "brief":
        print(read_brief() or "(ยังไม่มี feedback brief — รัน: python feedback.py learn)")
    elif a.cmd == "roi":
        roi()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
