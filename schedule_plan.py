"""
ANSRE Content Calendar — แผนปล่อยคอนเทนต์ (เรื่อง/ตอน/วันที่/แพลตฟอร์ม)
=====================================================================
เก็บแผนเป็น JSON ใน SecondBrain/schedule_plan.json — ใช้วางแผนปล่อยทั้งเดือน
ดูวันว่าง · รายการที่ถึงกำหนด/เลยกำหนด

API:
  list_plan(sb)         -> [entry, ...]
  add_entry(sb, e)      -> entry (เติม id ให้)
  remove_entry(sb, id)  -> bool
  upcoming(sb, days=14) -> {due, overcoming, ...}
"""
import os
import json
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))


def _path(sb):
    return os.path.join(sb, "schedule_plan.json")


def list_plan(sb):
    fp = _path(sb)
    if not os.path.exists(fp):
        return []
    try:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(sb, plan):
    with open(_path(sb), "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


def _next_id(plan):
    return (max([e.get("id", 0) for e in plan], default=0)) + 1


def add_entry(sb, e):
    """e = {title, date(YYYY-MM-DD), platform, ch?, note?}"""
    plan = list_plan(sb)
    entry = {
        "id": _next_id(plan),
        "title": (e.get("title") or "").strip(),
        "date": (e.get("date") or "").strip(),
        "platform": (e.get("platform") or "youtube").strip(),
        "ch": e.get("ch"),
        "note": (e.get("note") or "").strip(),
        "status": "planned",
    }
    if not entry["title"] or not entry["date"]:
        return None
    plan.append(entry)
    plan.sort(key=lambda x: x.get("date", ""))
    _save(sb, plan)
    return entry


def remove_entry(sb, eid):
    plan = list_plan(sb)
    new = [e for e in plan if e.get("id") != int(eid)]
    if len(new) == len(plan):
        return False
    _save(sb, new)
    return True


def set_status(sb, eid, status):
    plan = list_plan(sb)
    hit = False
    for e in plan:
        if e.get("id") == int(eid):
            e["status"] = status
            hit = True
    if hit:
        _save(sb, plan)
    return hit


def upcoming(sb, days=14, today=None):
    today = today or datetime.now().strftime("%Y-%m-%d")
    plan = list_plan(sb)
    horizon = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
    due = [e for e in plan if e.get("status") != "done" and e.get("date", "") < today]
    soon = [e for e in plan if e.get("status") != "done" and today <= e.get("date", "") <= horizon]
    return {"today": today, "overdue": due, "soon": soon, "total": len(plan)}


if __name__ == "__main__":
    import sys
    sb = os.path.join(ROOT, "SecondBrain")
    print(json.dumps(upcoming(sb), ensure_ascii=False, indent=2))
