"""
ANSRE Ideation Engine — คลังไอเดีย + เครื่องคิด/ให้คะแนน/promote ก่อนเขียนบทแรก
==============================================================================
วางไว้หน้าสุดของ pipeline: [Idea Vault] -> promote -> [Write -> ... -> Publish]

วงจร: Captured -> Scored -> Approved/Promoted  (หรือ Parked ถ้าคะแนนต่ำ)
แหล่งไอเดีย: manual / brainstorm(AI) / trend(จาก analyzer) / fusion(ผสม)

เก็บเป็น markdown ใน SecondBrain/00_Idea_Vault/idea_*.md
LLM ผ่าน llm_provider (role "ideation"/"brainstorm" -> local ฟรีในโหมด hybrid)

CLI:
  python ideation.py add "ไอเดียดิบ..."        เพิ่มไอเดีย manual
  python ideation.py brainstorm [n]            ให้ AI คิด n ไอเดียใหม่
  python ideation.py trends                    ดูดไอเดียจากนิยายที่ analyze แล้ว
  python ideation.py fuse                       ผสม 2 ไอเดียเด่นเป็นไอเดียใหม่
  python ideation.py score                      ขยาย+ให้คะแนนไอเดีย Captured ทั้งหมด
  python ideation.py promote <id>               เปลี่ยนไอเดียเป็นโปรเจกต์ (เข้าคิวเขียน)
  python ideation.py list                       แสดงคลังไอเดียเรียงตามคะแนน
  python ideation.py auto                       รันครบวงจรอัตโนมัติ (สำหรับ orchestrator)
"""
from __future__ import annotations

import os
import re
import sys
import glob
import json
from datetime import datetime

from llm_provider import generate, generate_json

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
VAULT = os.path.join(SB, "00_Idea_Vault")
POOL = os.path.join(SB, "01_Scouting_Pool")

# ---- load .env ----
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def _cfg_int(n, d):
    try:
        return int(os.environ.get(n, d))
    except ValueError:
        return d


def _cfg_float(n, d):
    try:
        return float(os.environ.get(n, d))
    except ValueError:
        return d


MIN_VAULT = _cfg_int("ANSRE_IDEA_MIN_VAULT", 8)            # คงไอเดียในคลังอย่างน้อยกี่ตัว
BRAINSTORM_BATCH = _cfg_int("ANSRE_IDEA_BRAINSTORM_BATCH", 3)
PROMOTE_SCORE = _cfg_float("ANSRE_IDEA_PROMOTE_SCORE", 8.0)  # คะแนนขั้นต่ำที่จะ auto-promote
PROMOTE_DAILY = _cfg_int("ANSRE_IDEA_PROMOTE_DAILY", 1)      # auto-promote ได้กี่เรื่อง/วัน
PARK_SCORE = _cfg_float("ANSRE_IDEA_PARK_SCORE", 5.0)        # ต่ำกว่านี้ park ทิ้ง


# ---------------------------------------------------------------------------
# markdown helpers
# ---------------------------------------------------------------------------
def _ensure_dirs():
    os.makedirs(VAULT, exist_ok=True)
    os.makedirs(POOL, exist_ok=True)


def parse_md(fp):
    with open(fp, "r", encoding="utf-8") as f:
        content = f.read()
    fm, body = {}, content
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", content, re.DOTALL)
    if m:
        body = m.group(2)
        cur_list = None
        for line in m.group(1).splitlines():
            if re.match(r"^\s+-\s", line) and cur_list:
                fm[cur_list].append(line.strip()[2:].strip().strip('"'))
            elif ":" in line:
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if v == "":
                    fm[k] = []
                    cur_list = k
                else:
                    fm[k] = v
                    cur_list = None
    return fm, body


def write_md(fp, fm, body):
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for it in v:
                lines.append(f'  - "{it}"')
        else:
            lines.append(f'{k}: "{v}"')
    lines.append("---\n")
    with open(fp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + body)


def _all_ideas():
    return sorted(glob.glob(os.path.join(VAULT, "idea_*.md")))


def _next_id():
    n = len(_all_ideas()) + 1
    return f"idea_{datetime.now().strftime('%Y%m%d')}_{n:03d}"


def _slug(s):
    return re.sub(r"[^\w฀-๿]+", "_", s)[:40].strip("_") or "idea"


def load_ideas(*statuses):
    out = []
    for fp in _all_ideas():
        fm, body = parse_md(fp)
        if not statuses or fm.get("status") in statuses:
            out.append((fp, fm, body))
    return out


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------
def capture(text, source="manual", title=None):
    _ensure_dirs()
    iid = _next_id()
    title = title or text.strip().split("\n")[0][:60]
    fp = os.path.join(VAULT, f"{iid}_{_slug(title)}.md")
    fm = {"id": iid, "status": "Captured", "source": source, "title": title,
          "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    write_md(fp, fm, f"\n# ไอเดียดิบ\n{text}\n")
    print(f"[+] เก็บไอเดีย: {title}  ({source})")
    return fp


# ---------------------------------------------------------------------------
# brainstorm (AI คิดใหม่)
# ---------------------------------------------------------------------------
def brainstorm(n=BRAINSTORM_BATCH):
    existing = [fm.get("title", "") for _, fm, _ in load_ideas()]
    avoid = "\n".join(f"- {t}" for t in existing[-25:]) or "(ยังไม่มี)"
    # ดึงเทรนด์ล่าสุดมาชี้นำ (ถ้ามี) — ปิดด้วย ANSRE_IDEA_USE_TRENDS=0
    trend_ctx = ""
    if os.environ.get("ANSRE_IDEA_USE_TRENDS", "1").lower() in ("1", "true", "yes"):
        try:
            import trends
            brief = trends.read_brief()
            if brief:
                trend_ctx = f"\n\n📈 เทรนด์ตลาดล่าสุด (ใช้ชี้นำให้ไอเดียตรงกระแสแต่ยังสดใหม่):\n{brief[:1000]}\n"
        except Exception:
            pass
    prompt = f"""คุณคือนักคิดพล็อตนิยายไทยที่สร้างสรรค์และไม่ซ้ำใคร
คิดไอเดียนิยาย {n} เรื่องที่สดใหม่ น่าสนใจ มีจุดขายชัด เหมาะกับคนอ่านไทยและไวรัลบนโซเชียล
หลากหลายแนว (ลึกลับ/แฟนตาซี/ระบบ/ย้อนเวลา/สืบสวน/โรแมนซ์-คอเมดี){trend_ctx}

ห้ามซ้ำกับไอเดียที่มีอยู่แล้วเหล่านี้:
{avoid}

ตอบเป็น JSON เท่านั้น:
{{"ideas": [{{"title": "ชื่อเรื่องสั้นๆ", "pitch": "ไอเดีย/จุดขาย 2-3 ประโยค"}}]}}"""
    data = generate_json(prompt, role="brainstorm", temperature=1.0)
    created = []
    for it in data.get("ideas", [])[:n]:
        t = (it.get("title") or "").strip()
        p = (it.get("pitch") or "").strip()
        if t and p:
            created.append(capture(p, source="brainstorm", title=t))
    print(f"[brainstorm] สร้าง {len(created)} ไอเดียใหม่")
    return created


# ---------------------------------------------------------------------------
# trends (ดูดจากนิยายที่ analyze แล้ว)
# ---------------------------------------------------------------------------
def from_trends():
    seen = {fm.get("title", "") for _, fm, _ in load_ideas()}
    created = []
    for fp in glob.glob(os.path.join(POOL, "*.md")):
        fm, body = parse_md(fp)
        if fm.get("status") not in ("Analyzed", "Processed"):
            continue
        title = fm.get("thai_working_title") or fm.get("title", "")
        if not title or title in seen:
            continue
        m = re.search(r"แนวทางการสร้างเรื่องใหม่.*?\n(.+?)(?:\n#|\Z)", body, re.DOTALL)
        concept = (m.group(1).strip()[:600] if m else fm.get("title", ""))
        created.append(capture(concept, source="trend", title=title))
        seen.add(title)
    print(f"[trends] ดูด {len(created)} ไอเดียจาก trend")
    return created


# ---------------------------------------------------------------------------
# fusion (ผสม 2 ไอเดียเด่น)
# ---------------------------------------------------------------------------
def fuse():
    scored = sorted(load_ideas("Scored"),
                    key=lambda x: float(x[1].get("score_total", 0) or 0), reverse=True)
    if len(scored) < 2:
        print("[fuse] ต้องมีไอเดีย Scored อย่างน้อย 2 ตัว")
        return None
    a, b = scored[0][1], scored[1][1]
    prompt = f"""ผสมแก่นของ 2 ไอเดียนิยายนี้ให้เป็นไอเดียลูกผสม "ใหม่" ที่ลงตัวและน่าสนใจกว่าเดิม
ไอเดีย A: {a.get('title')} — {a.get('logline','')}
ไอเดีย B: {b.get('title')} — {b.get('logline','')}
ตอบ JSON: {{"title": "...", "pitch": "จุดขายของลูกผสม 2-3 ประโยค"}}"""
    d = generate_json(prompt, role="ideation", temperature=0.9)
    if d.get("title") and d.get("pitch"):
        return capture(d["pitch"], source="fusion", title=d["title"])
    return None


# ---------------------------------------------------------------------------
# จัดการไอเดีย (merge / delete / archive / group / edit)
# ---------------------------------------------------------------------------
def _find_idea(idea_id):
    for fp, fm, body in load_ideas():
        if fm.get("id") == idea_id or (idea_id and idea_id in fp):
            return fp, fm, body
    return None


def merge_ideas(ids):
    """ผสมไอเดียที่เลือก (2+ ตัว) เป็นไอเดียใหม่ 1 ตัว"""
    items = [x for x in (_find_idea(i) for i in ids) if x]
    if len(items) < 2:
        print("[merge] ต้องเลือกอย่างน้อย 2 ไอเดีย")
        return None
    descs = "\n".join(f"- {fm.get('title')}: {fm.get('logline') or body.strip()[:200]}"
                      for _, fm, body in items)
    prompt = f"""ผสมไอเดียนิยายเหล่านี้ให้เป็นไอเดีย "ใหม่" 1 เรื่องที่ลงตัว ดึงจุดเด่นของแต่ละอันมารวมกันอย่างสร้างสรรค์:
{descs}
ตอบ JSON: {{"title": "ชื่อเรื่องลูกผสม", "pitch": "จุดขาย 2-3 ประโยค"}}"""
    d = generate_json(prompt, role="ideation", temperature=0.9)
    if d.get("title") and d.get("pitch"):
        fp = capture(d["pitch"], source="merge", title=d["title"])
        # บันทึกว่ามาจากการผสมอันไหน
        _, fm, body = _find_idea(d["title"]) or (None, None, None)
        print(f"[merge] รวม {len(items)} ไอเดีย → '{d['title']}'")
        return fp
    return None


def delete_idea(idea_id):
    hit = _find_idea(idea_id)
    if hit:
        os.remove(hit[0])
        print(f"[delete] ลบ {hit[1].get('title')}")
        return True
    return False


def archive_idea(idea_id):
    hit = _find_idea(idea_id)
    if hit:
        fp, fm, body = hit
        fm["status"] = "Archived"
        write_md(fp, fm, body)
        return True
    return False


def set_group(idea_id, group):
    hit = _find_idea(idea_id)
    if hit:
        fp, fm, body = hit
        fm["group"] = group
        write_md(fp, fm, body)
        return True
    return False


def edit_idea(idea_id, text):
    hit = _find_idea(idea_id)
    if hit and text.strip():
        fp, fm, body = hit
        fm["status"] = "Captured"   # แก้แล้วต้องให้คะแนนใหม่
        for k in ("score_total", "logline"):
            fm.pop(k, None)
        write_md(fp, fm, f"\n# ไอเดียดิบ\n{text.strip()}\n")
        return True
    return False


# ---------------------------------------------------------------------------
# expand + score
# ---------------------------------------------------------------------------
def score_one(fp, fm, body):
    raw = body.strip()
    prompt = f"""คุณคือบรรณาธิการ+นักวางกลยุทธ์เนื้อหานิยายไทย วิเคราะห์ไอเดียนี้:
ชื่อ: {fm.get('title')}
ไอเดีย: {raw}

ขยายความและให้คะแนนตามเกณฑ์ ตอบ JSON เท่านั้น:
{{
  "logline": "ประโยคเดียวที่ขายเรื่องได้",
  "premise": "แก่นเรื่อง 3-4 ประโยค",
  "genre": "แนวเรื่อง",
  "tropes": ["trope เด่น 1","2","3"],
  "hooks": ["ประโยคเปิดที่หยุดสายตา 1","2","3"],
  "why_now": "ทำไมเหมาะกับตลาด/เทรนด์ตอนนี้",
  "audience": "กลุ่มเป้าหมาย",
  "score_originality": 8,
  "score_market": 8,
  "score_virality": 8,
  "score_feasibility": 8,
  "score_saturation": 7,
  "reasoning": "เหตุผลคะแนนสั้นๆ"
}}
(คะแนน 1-10; score_saturation สูง = ตลาดยังไม่เกลื่อน ดี)"""
    try:
        d = generate_json(prompt, role="ideation")
    except Exception as e:
        print(f"[score] {fm.get('id')} ล้มเหลว: {e}")
        return None
    parts = [d.get(f"score_{k}", 0) for k in ("originality", "market", "virality", "feasibility", "saturation")]
    try:
        total = round(sum(float(x) for x in parts) / len(parts), 2)
    except Exception:
        total = 0
    fm.update({
        "status": "Scored", "genre": d.get("genre", ""),
        "logline": d.get("logline", ""), "audience": d.get("audience", ""),
        "score_total": total, "score_originality": d.get("score_originality", ""),
        "score_market": d.get("score_market", ""), "score_virality": d.get("score_virality", ""),
        "score_feasibility": d.get("score_feasibility", ""), "score_saturation": d.get("score_saturation", ""),
        "tropes": d.get("tropes", []),
    })
    new_body = f"""
# {fm.get('title')}

**Logline:** {d.get('logline','')}

## แก่นเรื่อง (Premise)
{d.get('premise','')}

## Hooks
{chr(10).join('- ' + h for h in d.get('hooks', []))}

## ทำไมต้องตอนนี้
{d.get('why_now','')}

## เหตุผลคะแนน
{d.get('reasoning','')} (รวม {total}/10)

## ไอเดียดิบเดิม
{raw}
"""
    write_md(fp, fm, new_body)
    print(f"[score] {fm.get('title')} → {total}/10")
    return total


def score_all():
    todo = load_ideas("Captured")
    print(f"[score] มีไอเดีย Captured {len(todo)} ตัว")
    for fp, fm, body in todo:
        score_one(fp, fm, body)


# ---------------------------------------------------------------------------
# promote -> เข้าคิวเขียน (สร้าง record แบบ Analyzed ใน scouting pool)
# ---------------------------------------------------------------------------
def _promoted_today():
    today = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for _, fm, _ in load_ideas("Promoted")
               if str(fm.get("promoted_at", "")).startswith(today))


def promote(idea_id):
    match = [(fp, fm, b) for fp, fm, b in load_ideas() if fm.get("id") == idea_id or idea_id in fp]
    if not match:
        print(f"[promote] ไม่พบไอเดีย {idea_id}")
        return None
    fp, fm, body = match[0]
    title = fm.get("title", "Untitled")
    tropes = fm.get("tropes", [])
    if isinstance(tropes, str):
        tropes = [tropes]

    # สร้างไฟล์ใน scouting pool สถานะ Analyzed -> agent_writer จะหยิบไปเขียนต่อเอง
    _ensure_dirs()
    pool_fp = os.path.join(POOL, f"idea_{_slug(title)}.md")
    pfm = {
        "id": fm.get("id"), "source": "Original Idea", "title": title,
        "author": "ANSRE", "genre": fm.get("genre", ""), "status": "Analyzed",
        "thai_working_title": title, "market_fit_score": fm.get("score_total", ""),
        "scouted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tags": tropes,
    }
    pbody = f"""
# {title}

## 🇹🇭 บทวิเคราะห์ (จากคลังไอเดีย Original IP)

### เรื่องย่อ (Localized Synopsis)
{_section(body, 'แก่นเรื่อง') or fm.get('logline','')}

### แกนพล็อตเด่น (Core Tropes)
{chr(10).join('- ' + t for t in tropes)}

### แนวทางสร้างเรื่อง (Inspired Concept)
{fm.get('logline','')}
{_section(body, 'ทำไมต้องตอนนี้')}
"""
    write_md(pool_fp, pfm, pbody)

    fm["status"] = "Promoted"
    fm["promoted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fm["project_file"] = os.path.basename(pool_fp)
    write_md(fp, fm, body)
    print(f"[promote] ✅ '{title}' เข้าคิวเขียนแล้ว → {os.path.basename(pool_fp)}")
    return pool_fp


def _section(body, header):
    m = re.search(rf"##\s*{re.escape(header)}.*?\n(.+?)(?:\n##|\Z)", body, re.DOTALL)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# auto cycle (สำหรับ orchestrator)
# ---------------------------------------------------------------------------
def auto():
    _ensure_dirs()
    print("===== IDEATION AUTO CYCLE =====")
    # 1) ดูดไอเดียจาก trend ที่ analyze แล้ว
    from_trends()
    # 2) เติมคลังถ้าน้อย (Captured+Scored)
    live = len(load_ideas("Captured", "Scored"))
    if live < MIN_VAULT:
        brainstorm(min(BRAINSTORM_BATCH, MIN_VAULT - live))
    # 3) ขยาย+ให้คะแนน Captured ทั้งหมด
    score_all()
    # 4) park ไอเดียคะแนนต่ำ
    for fp, fm, body in load_ideas("Scored"):
        if float(fm.get("score_total", 0) or 0) < PARK_SCORE:
            fm["status"] = "Parked"
            write_md(fp, fm, body)
    # 5) auto-promote ตัวท็อป (มี guardrail: คะแนนขั้นต่ำ + เพดาน/วัน)
    budget = PROMOTE_DAILY - _promoted_today()
    if budget > 0:
        cands = sorted(load_ideas("Scored"),
                       key=lambda x: float(x[1].get("score_total", 0) or 0), reverse=True)
        for fp, fm, body in cands[:budget]:
            if float(fm.get("score_total", 0) or 0) >= PROMOTE_SCORE:
                promote(fm.get("id"))
    else:
        print(f"[auto] ครบเพดาน promote วันนี้แล้ว ({PROMOTE_DAILY}/วัน)")
    print("===== IDEATION DONE =====")


def list_ideas():
    rows = sorted(load_ideas(), key=lambda x: float(x[1].get("score_total", 0) or 0), reverse=True)
    if not rows:
        print("(คลังไอเดียว่าง — ลอง: python ideation.py brainstorm)")
        return
    print(f"{'SCORE':>6}  {'STATUS':<10} {'SRC':<10} TITLE")
    for _, fm, _ in rows:
        sc = fm.get("score_total", "-")
        print(f"{str(sc):>6}  {fm.get('status',''):<10} {fm.get('source',''):<10} {fm.get('title','')}")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "list"
    if cmd == "add" and len(a) > 1:
        capture(" ".join(a[1:]), source="manual")
    elif cmd == "brainstorm":
        brainstorm(int(a[1]) if len(a) > 1 else BRAINSTORM_BATCH)
    elif cmd == "trends":
        from_trends()
    elif cmd == "fuse":
        fuse()
    elif cmd == "score":
        score_all()
    elif cmd == "promote" and len(a) > 1:
        promote(a[1])
    elif cmd == "merge" and len(a) > 1:
        merge_ideas(a[1:])
    elif cmd == "delete" and len(a) > 1:
        delete_idea(a[1])
    elif cmd == "archive" and len(a) > 1:
        archive_idea(a[1])
    elif cmd == "group" and len(a) > 2:
        set_group(a[1], a[2])
    elif cmd == "edit" and len(a) > 2:
        edit_idea(a[1], " ".join(a[2:]))
    elif cmd == "auto":
        auto()
    elif cmd == "list":
        list_ideas()
    else:
        print(__doc__)
