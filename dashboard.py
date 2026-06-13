"""
ANSRE Web Dashboard — หน้าควบคุมระบบทั้งหมดในที่เดียว (สวย + ใช้ง่าย)
====================================================================
ไม่ต้องลง dependency เพิ่ม — ใช้ http.server ของ Python ล้วน

รัน:   ./ansre web        (หรือ  .venv/bin/python dashboard.py)
เปิด:  http://localhost:8765

API:
  GET  /api/status     สรุปสถานะ pipeline + ผลผลิต + ค่าใช้จ่าย
  GET  /api/doctor     health check (โครงสร้างข้อมูล)
  GET  /api/usage      ค่า token รายวัน + ประวัติ
  GET  /api/novels     รายการนิยายใน scouting pool
  GET  /api/config     LLM backend + routing
  GET  /api/outputs    รายการปก/เสียง/teaser
  POST /api/run        สั่งเดิน pipeline 1 รอบ (background) -> task id
  POST /api/stage      สั่งรัน stage เดียว {stage: "scout"|...}
  POST /api/worker     {action: "start"|"stop"}
  GET  /api/task/<id>  สถานะ + log ของ task
  GET  /media/<cat>/<file>  เสิร์ฟไฟล์สื่อ
"""
from __future__ import annotations

import os
import re
import io
import sys
import json
import glob
import time
import threading
import subprocess
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, unquote, quote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
WEB = os.path.join(ROOT, "web")
TASK_DIR = os.path.join(SB, ".tasks")
PORT = int(os.environ.get("PORT") or os.environ.get("ANSRE_WEB_PORT") or "8765")

# --- Hot-reload (dev) ---
RELOAD = (os.environ.get("ANSRE_RELOAD") == "1") or ("--reload" in sys.argv)


def _watched_files():
    fs = []
    for ext in ("*.html", "*.js", "*.css"):
        fs += glob.glob(os.path.join(WEB, ext))
    fs += glob.glob(os.path.join(ROOT, "*.py"))
    return fs


def _reload_token():
    try:
        return str(round(max((os.path.getmtime(f) for f in _watched_files()), default=0), 2))
    except Exception:
        return "0"


def _free_port(port):
    """kill process ที่ค้างพอร์ตอยู่ (กัน OSError: Address already in use)"""
    try:
        out = subprocess.run(["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True).stdout.split()
        mypid = str(os.getpid())
        killed = [p for p in out if p and p != mypid]
        for p in killed:
            subprocess.run(["kill", p], capture_output=True)
        if killed:
            print(f"[web] ปิด instance เดิมที่ค้างพอร์ต {port} (pid {','.join(killed)})", flush=True)
            time.sleep(1)
    except Exception:
        pass


def _reload_watcher():
    """เฝ้า *.py — เปลี่ยนแล้ว restart server อัตโนมัติ (web files ไม่ต้อง restart, client reload เอง)"""
    seen = {f: os.path.getmtime(f) for f in glob.glob(os.path.join(ROOT, "*.py"))}
    while True:
        time.sleep(1)
        for f in glob.glob(os.path.join(ROOT, "*.py")):
            try:
                m = os.path.getmtime(f)
            except OSError:
                continue
            if seen.get(f) and m > seen[f]:
                print(f"[reload] {os.path.basename(f)} เปลี่ยน → restart dashboard", flush=True)
                time.sleep(0.3)  # กันอ่านไฟล์ตอนเขียนยังไม่จบ
                os.execv(sys.executable, [sys.executable] + sys.argv)
            seen[f] = m

LAUNCH_LABEL = "com.ansre.worker"
LAUNCH_PLIST = os.path.expanduser(f"~/Library/LaunchAgents/{LAUNCH_LABEL}.plist")

# ---- load .env ----
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def venv_py():
    c = os.path.join(ROOT, ".venv", "bin", "python")
    return c if os.path.exists(c) else sys.executable


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def _read_head(fp, n=2000):
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return f.read(n)
    except Exception:
        return ""


def count_status(*statuses):
    n = 0
    for fp in glob.glob(os.path.join(SB, "01_Scouting_Pool", "*.md")):
        h = _read_head(fp, 1500)
        if any(f'status: "{s}"' in h or f"status: {s}" in h for s in statuses):
            n += 1
    return n


def count_files(*parts):
    return len(glob.glob(os.path.join(SB, *parts)))


def _frontmatter(fp):
    fm = {}
    txt = _read_head(fp, 2500)
    m = re.match(r"^---\s*\n(.*?)\n---", txt, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith("  "):
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def api_status():
    return {
        "pool": {
            "scouted": count_status("Scouted"),
            "analyzed": count_status("Analyzed"),
            "processed": count_status("Processed"),
        },
        "outputs": {
            "chapters": count_files("05_Active_Projects", "Chapters", "*.md"),
            "covers": count_files("05_Active_Projects", "Covers", "*"),
            "audio": count_files("05_Active_Projects", "Audio_Output", "*.mp3"),
            "teasers": count_files("05_Active_Projects", "Teaser_Output", "*.mp4"),
            "publish_queue": count_files("05_Active_Projects", "Publish_Queue", "*"),
        },
        "spend_today": round(today_spend(), 4),
        "worker_running": _worker_running(),
        "time": datetime.now().strftime("%H:%M:%S"),
    }


def today_spend():
    log = os.path.join(SB, "llm_usage.jsonl")
    if not os.path.exists(log):
        return 0.0
    today = datetime.now().strftime("%Y-%m-%d")
    t = 0.0
    with open(log, "r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
                if e.get("date") == today:
                    t += e.get("est_usd", 0.0)
            except Exception:
                pass
    return t


def api_usage():
    log = os.path.join(SB, "llm_usage.jsonl")
    by_date = {}
    by_backend, by_role, by_model = {}, {}, {}

    def _agg():
        return {"calls": 0, "usd": 0.0, "in": 0, "out": 0}

    def _add(dic, key, usd, it, ot):
        a = dic.setdefault(key or "?", _agg())
        a["calls"] += 1
        a["usd"] = round(a["usd"] + usd, 6)
        a["in"] += it
        a["out"] += ot

    totals, today_agg = _agg(), _agg()
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(log):
        with open(log, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                d = e.get("date", "?")
                usd = e.get("est_usd", 0) or 0
                it = int(e.get("in_tokens", 0) or 0)
                ot = int(e.get("out_tokens", 0) or 0)
                by_date[d] = round(by_date.get(d, 0) + usd, 6)
                _add(by_backend, e.get("backend"), usd, it, ot)
                _add(by_role, e.get("role"), usd, it, ot)
                _add(by_model, e.get("model"), usd, it, ot)
                _add({"_": totals}, "_", usd, it, ot)
                if d == today:
                    _add({"_": today_agg}, "_", usd, it, ot)

    def _tolist(dic):
        return sorted(([{"name": k, **v} for k, v in dic.items()]),
                      key=lambda x: x["usd"], reverse=True)

    series = sorted(by_date.items())[-14:]
    return {"by_date": series,
            "by_backend": _tolist(by_backend),
            "by_role": _tolist(by_role),
            "by_model": _tolist(by_model),
            "totals": totals, "today_agg": today_agg,
            "today": round(today_spend(), 6)}


def api_publish_status():
    """สถานะเผยแพร่: แพลตฟอร์มที่เปิด · teaser พร้อม · เผยแพร่แล้วกี่ชิ้น"""
    ap = os.path.join(SB, "05_Active_Projects")
    teasers = set(glob.glob(os.path.join(ap, "Teasers", "*.mp4")) +
                  glob.glob(os.path.join(ap, "Teaser_Output", "*.mp4")))
    plat = {p: os.environ.get(p, "0").lower() in ("1", "true", "yes", "on")
            for p in ("PUBLISH_YOUTUBE", "PUBLISH_TIKTOK", "PUBLISH_NOVEL")}
    published, links = 0, []
    try:
        import publisher
        led = publisher.load_ledger(SB)
        for k, e in led.items():
            vals = e.values() if isinstance(e, dict) else []
            if any(str(v).startswith("http") or str(v) in ("queued", "ok", "uploaded") for v in vals):
                published += 1
            if isinstance(e, dict):
                for pf, v in e.items():
                    if str(v).startswith("http"):
                        links.append({"title": k, "platform": pf, "url": v})
    except Exception:
        pass

    # ตรวจความพร้อม credential ต่อแพลตฟอร์ม → ready / needs_token / disabled
    yt_token = os.environ.get("YOUTUBE_TOKEN_FILE", os.path.join(ROOT, "youtube_token.json"))
    creds = {
        "PUBLISH_YOUTUBE": {"enabled": plat["PUBLISH_YOUTUBE"], "has_cred": os.path.exists(yt_token),
                            "cred_hint": "วางไฟล์ OAuth ที่ YOUTUBE_TOKEN_FILE (มี refresh_token)"},
        "PUBLISH_TIKTOK": {"enabled": plat["PUBLISH_TIKTOK"], "has_cred": bool(os.environ.get("TIKTOK_ACCESS_TOKEN")),
                           "cred_hint": "ตั้ง TIKTOK_ACCESS_TOKEN ใน .env"},
        "PUBLISH_NOVEL": {"enabled": plat["PUBLISH_NOVEL"], "has_cred": True,
                          "cred_hint": "บันทึกไฟล์พร้อมลงเว็บนิยาย (ไม่ต้องใช้ token)"},
    }
    for c in creds.values():
        c["state"] = "ready" if (c["enabled"] and c["has_cred"]) else \
                     "needs_token" if c["enabled"] else "disabled"
    ready = any(c["state"] == "ready" for c in creds.values())
    return {"ok": True, "teasers": len(teasers), "platforms": plat,
            "any_enabled": any(plat.values()), "published": published,
            "creds": creds, "ready": ready, "links": links[:20]}


def publish_run(payload):
    dry = not any(os.environ.get(p, "0").lower() in ("1", "true", "yes", "on")
                  for p in ("PUBLISH_YOUTUBE", "PUBLISH_TIKTOK", "PUBLISH_NOVEL"))
    argv = ["publisher.py", SB] + (["--dry-run"] if (dry or payload.get("dry")) else [])
    return {"task": start_argv("publish" + ("(dry)" if dry else ""), argv), "dry": dry}


def api_cost_advice():
    """วิเคราะห์ usage → คำแนะนำลดต้นทุน (ย้าย role แพงไป local + ปรับ pacing)"""
    u = api_usage()
    advice = []
    # role ที่ route ไป gemini ตอนนี้ (เพื่อแนะนำย้าย local)
    try:
        sys.path.insert(0, ROOT)
        import llm_provider
        def _be(r): return llm_provider.resolve_backend(r)
    except Exception:
        def _be(r): return os.environ.get("LLM_BACKEND", "gemini")

    tot = (u.get("totals") or {}).get("usd", 0) or 1e-6
    for r in u.get("by_role", []):
        name, usd, calls = r["name"], r["usd"], r["calls"]
        if usd < 0.2:  # ข้าม role ที่ถูกอยู่แล้ว
            continue
        be = _be(name)
        if be == "gemini":
            advice.append({
                "type": "move_local", "role": name, "usd": round(usd, 3),
                "pct": round(usd / tot * 100),
                "label": f"ย้าย “{name}” ไป Mac mini local (ฟรี)",
                "detail": f"ตอนนี้ {calls} ครั้ง = ${usd:.2f} ({round(usd/tot*100)}% ของต้นทุน) → ประหยัดได้เกือบทั้งหมด",
                "env_key": f"LLM_ROLE_{name.upper()}", "env_val": "local",
                "save": round(usd, 3),
            })
    # โหมดเขียน pro→flash
    if os.environ.get("WRITING_MODE", "premium") in ("master", "premium"):
        pro = next((m for m in u.get("by_model", []) if "pro" in m["name"]), None)
        if pro and pro["usd"] > 1:
            advice.append({
                "type": "writing_mode", "label": "เปลี่ยนโหมดเขียนเป็น draft (flash ทุก stage)",
                "detail": f"ตอนนี้ pro = ${pro['usd']:.2f} — draft จะถูกลง ~5-8 เท่า (คุณภาพลดบ้าง)",
                "env_key": "WRITING_MODE", "env_val": "draft", "save": round(pro["usd"] * 0.7, 3),
            })
    advice.sort(key=lambda x: x.get("save", 0), reverse=True)
    total_save = round(sum(a.get("save", 0) for a in advice if a["type"] == "move_local"), 2)
    budget = None
    try:
        import llm_provider
        budget = llm_provider.budget_status()
    except Exception:
        pass
    return {"ok": True, "advice": advice, "total_save_est": total_save,
            "today": u["today"], "total14": round(sum(v for _, v in u["by_date"]), 3),
            "budget": budget}


def api_analytics(days=30):
    """แนวโน้มตามเวลา: ต้นทุน/วัน + ผลผลิต/วัน (นับจากเวลาแก้ไขไฟล์ผลงาน)"""
    ap = os.path.join(SB, "05_Active_Projects")
    # ผลผลิตแต่ละชนิด → โฟลเดอร์ + pattern
    prod_dirs = {
        "บท": [("Chapters", "*_Chapter_*.md")],
        "ปก": [("Covers", "*.png"), ("Covers", "*.jpg")],
        "เสียง": [("Audio_Output", "*.mp3")],
        "teaser": [("Teasers", "*.mp4"), ("Teaser_Output", "*.mp4")],
    }
    # สร้างชุดวันที่ย้อนหลัง (เติม 0 วันว่าง)
    start = datetime.now().date() - timedelta(days=days - 1)
    dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    didx = {d: i for i, d in enumerate(dates)}

    prod = {k: [0] * days for k in prod_dirs}
    prod_total = {k: 0 for k in prod_dirs}
    for kind, specs in prod_dirs.items():
        seen = set()
        for folder, pat in specs:
            for fp in glob.glob(os.path.join(ap, folder, pat)):
                if fp in seen:
                    continue
                seen.add(fp)
                d = datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d")
                prod_total[kind] += 1
                if d in didx:
                    prod[kind][didx[d]] += 1

    # ต้นทุน/วัน จาก usage log
    cost = [0.0] * days
    log = os.path.join(SB, "llm_usage.jsonl")
    if os.path.exists(log):
        with open(log, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                d = e.get("date", "?")
                if d in didx:
                    cost[didx[d]] = round(cost[didx[d]] + (e.get("est_usd", 0) or 0), 6)

    active = [i for i in range(days) if cost[i] > 0 or any(prod[k][i] for k in prod)]
    span = (max(active) - min(active) + 1) if active else 0
    chapters_total = prod_total.get("บท", 0)
    return {"ok": True, "days": days, "dates": dates,
            "cost": cost, "production": prod, "prod_total": prod_total,
            "cost_total": round(sum(cost), 3),
            "velocity": round(chapters_total / span, 2) if span else 0,
            "active_days": len(active)}


def api_doctor():
    checks = []

    def add(ok, label, detail="", level="ok"):
        checks.append({"ok": ok, "label": label, "detail": detail,
                       "level": "ok" if ok else level})

    have_venv = os.path.exists(os.path.join(ROOT, ".venv", "bin", "python"))
    add(have_venv, "Virtual environment", ".venv" if have_venv else "ยังไม่ติดตั้ง — ./ansre setup",
        level="bad")
    if have_venv:
        r = subprocess.run([venv_py(), "-c", "import streamlit,google.genai,edge_tts,pydub,requests,googleapiclient"],
                           capture_output=True, text=True)
        add(r.returncode == 0, "Dependencies", "ครบ" if r.returncode == 0 else "ขาดบางตัว", level="bad")
    add(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0,
        "ffmpeg", "พร้อม", level="bad")

    backend = os.environ.get("LLM_BACKEND", "gemini")
    gem = bool(os.environ.get("GEMINI_API_KEY"))
    add(gem or backend == "local", "GEMINI_API_KEY",
        "set" if gem else ("ไม่จำเป็น (local)" if backend == "local" else "ขาด"),
        level="bad" if backend in ("gemini", "hybrid") else "warn")
    add(bool(os.environ.get("NOTION_TOKEN")), "NOTION_TOKEN",
        "set" if os.environ.get("NOTION_TOKEN") else "ขาด (sync Notion)", level="warn")

    import socket

    def probe(env_url, default, label, fallback_note):
        u = urlparse(os.environ.get(env_url, default))
        host, port = u.hostname or "localhost", u.port or (u.scheme == "https" and 443 or 80)
        try:
            with socket.create_connection((host, port), timeout=2):
                add(True, label, f"{host}:{port} ต่อได้")
        except Exception:
            add(False, label, f"{host}:{port} ต่อไม่ได้ ({fallback_note})", level="warn")

    if backend in ("local", "hybrid"):
        probe("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1", "Local LLM (Mac mini)", "fallback Gemini")
    # Image backend (ComfyUI)
    img_backend = os.environ.get("IMAGE_BACKEND", "gemini")
    if img_backend in ("local", "hybrid"):
        probe("LOCAL_IMAGE_BASE_URL", "http://localhost:8188", "Image gen (ComfyUI)", "fallback Imagen")
    # Gateway (ถ้าตั้ง)
    if os.environ.get("ANSRE_GATEWAY_URL"):
        probe("ANSRE_GATEWAY_URL", "", "ANSRE Gateway", "ใช้ตรงแทน")
    # ffmpeg + libass (สำหรับ teaser)
    has_ff = subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0
    libass = has_ff and b"subtitles" in subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                                                        capture_output=True).stdout
    add(has_ff, "ffmpeg (teaser)", "พร้อม" + (" + libass" if libass else " (ไม่มี libass — caption ผ่าน PIL)"),
        level="bad")

    add(_worker_running(), "Auto worker", "กำลังทำงาน" if _worker_running() else "หยุดอยู่", level="warn")
    return {"backend": backend, "checks": checks,
            "all_ok": all(c["ok"] or c["level"] == "warn" for c in checks)}


def api_novels():
    items = []
    for fp in glob.glob(os.path.join(SB, "01_Scouting_Pool", "*.md")):
        fm = _frontmatter(fp)
        items.append({
            "title": fm.get("thai_working_title") or fm.get("title") or os.path.basename(fp),
            "original": fm.get("title", ""),
            "source": fm.get("source", ""),
            "status": fm.get("status", "?"),
            "score": fm.get("market_fit_score", ""),
            "genre": fm.get("genre", ""),
            "popularity": int(fm.get("popularity_score", 0) or 0),
            "rank": int(fm.get("rank", 0) or 0),
            "rating": fm.get("rating", ""),
            "views": int(fm.get("views", 0) or 0),
        })
    items.sort(key=lambda x: x["popularity"], reverse=True)
    return {"novels": items}


def api_trends():
    fp = os.path.join(SB, "Trend_Report.md")
    return {"content": _read_head(fp, 30000) if os.path.exists(fp) else ""}


def api_config():
    backend = os.environ.get("LLM_BACKEND", "gemini")
    roles = ["analyzer", "outline", "characters", "planner", "writer", "enhancer",
             "audio", "researcher", "editor", "brainstorm"]
    routing = []
    try:
        sys.path.insert(0, ROOT)
        import llm_provider  # noqa
        for r in roles:
            routing.append({"role": r, "backend": llm_provider.resolve_backend(r)})
    except Exception:
        for r in roles:
            routing.append({"role": r, "backend": backend})
    return {"backend": backend,
            "local_url": os.environ.get("LOCAL_LLM_BASE_URL", ""),
            "local_model": os.environ.get("LOCAL_LLM_MODEL", ""),
            "writing_mode": os.environ.get("WRITING_MODE", "premium"),
            "daily_cap": os.environ.get("ANSRE_DAILY_USD_CAP", "0"),
            "hard_cap": os.environ.get("ANSRE_DAILY_HARD_CAP", "0"),
            "target_chapters": os.environ.get("ANSRE_TARGET_CHAPTERS", "8"),
            "image_backend": os.environ.get("IMAGE_BACKEND", "gemini"),
            "image_url": os.environ.get("LOCAL_IMAGE_BASE_URL", ""),
            "image_model": os.environ.get("LOCAL_IMAGE_MODEL", ""),
            "tts_engine": os.environ.get("TTS_ENGINE", "edge-tts"),
            "call_gap": os.environ.get("ANSRE_CALL_GAP", "0"),
            "routing": routing}


def api_ideas():
    try:
        import ideation
        rows = sorted(ideation.load_ideas(),
                      key=lambda x: float(x[1].get("score_total", 0) or 0), reverse=True)
        return {"ideas": [{
            "id": fm.get("id", ""), "title": fm.get("title", ""), "status": fm.get("status", ""),
            "source": fm.get("source", ""), "score": fm.get("score_total", ""),
            "logline": fm.get("logline", ""), "genre": fm.get("genre", ""),
            "group": fm.get("group", ""),
        } for _, fm, _ in rows]}
    except Exception as e:  # noqa: BLE001
        return {"ideas": [], "error": str(e)}


def idea_add(text):
    import ideation
    if not text.strip():
        return {"ok": False, "error": "empty"}
    ideation.capture(text.strip(), source="manual")
    return {"ok": True}


def idea_promote(idea_id):
    import ideation
    fp = ideation.promote(idea_id)
    return {"ok": bool(fp)}


def idea_action(payload):
    """จัดการไอเดีย: delete / archive / group / edit (เร็ว, ไม่เรียก LLM)"""
    import ideation
    act = payload.get("action", "")
    iid = payload.get("id", "")
    if act == "delete":
        return {"ok": ideation.delete_idea(iid)}
    if act == "archive":
        return {"ok": ideation.archive_idea(iid)}
    if act == "group":
        return {"ok": ideation.set_group(iid, payload.get("group", ""))}
    if act == "edit":
        return {"ok": ideation.edit_idea(iid, payload.get("text", ""))}
    if act == "set_body":
        return {"ok": ideation.set_body(iid, payload.get("body", ""))}
    return {"ok": False, "error": "bad action"}


def idea_devwrite(idea_id):
    """พัฒนา→promote→เขียน ในคลิกเดียว (background, ยาว)"""
    if not idea_id:
        return {"error": "no id"}
    return {"task": start_argv("dev-promote-write", ["studio.py", "devwrite", idea_id])}


def idea_character(payload):
    """เพิ่มตัวละครจากฟอร์ม (template + AI) — background"""
    iid = payload.get("id", "")
    if not iid:
        return {"error": "no id"}
    argv = ["ideation.py", "character", iid, payload.get("name", "ตัวละคร"),
            payload.get("age", ""), payload.get("role", ""), payload.get("plot", "")]
    return {"task": start_argv("add-character", argv)}


def idea_merge(ids):
    """ผสมไอเดียที่เลือก (LLM) — รันเป็น background task"""
    if not ids or len(ids) < 2:
        return {"error": "ต้องเลือกอย่างน้อย 2 ไอเดีย"}
    return {"task": start_argv("idea-merge", ["ideation.py", "merge"] + list(ids))}


def idea_detail(idea_id):
    """เนื้อหาเต็มของไอเดีย (โชว์ในแผงกาง)"""
    import ideation
    hit = ideation._find_idea(idea_id)
    if not hit:
        return {"ok": False, "body": ""}
    return {"ok": True, "body": hit[2]}


def idea_develop(payload):
    """แตกเนื้อหาไอเดีย (concept/characters/names/plot/all) — background LLM"""
    iid, kind = payload.get("id", ""), payload.get("kind", "all")
    if not iid:
        return {"error": "no id"}
    return {"task": start_argv(f"idea-develop-{kind}", ["ideation.py", "develop", iid, kind])}


# ---- Studio (visual/video/loops) ----
_STUDIO_OUT = {
    "visual": ("Visual_Prompts", "_Visual.md"),
    "video": ("Video_Prompts", "_Video.md"),
    "bible": ("Story_Bible", "_Bible.md"),
    "audio": ("Audio_Scripts", "_AudioScript_01.md"),
    "caption": ("Captions", "_Caption.md"),
    "abtest": ("AB_Tests", "_AB.md"),
}


def api_projects():
    try:
        import studio
        return {"projects": studio.list_projects()}
    except Exception as e:  # noqa: BLE001
        return {"projects": [], "error": str(e)}


def api_studio_output(kind, title):
    try:
        import studio
        base = studio._match_base(title) or studio._slug(title)
        folder, suffix = _STUDIO_OUT.get(kind, (None, None))
        if not folder:
            return {"ok": False, "error": "bad kind"}
        fp = os.path.join(SB, "05_Active_Projects", folder, f"{base}{suffix}")
        if os.path.exists(fp):
            return {"ok": True, "content": _read_head(fp, 60000), "file": os.path.basename(fp)}
        return {"ok": True, "content": "", "file": ""}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def api_studio_status(title):
    """เช็คว่าเรื่องนี้มี studio output อะไรแล้วบ้าง (visual/video/audio/bible)"""
    try:
        import studio
        base = studio._match_base(title) or studio._slug(title)
        st = {}
        for kind, (folder, suffix) in _STUDIO_OUT.items():
            st[kind] = os.path.exists(os.path.join(SB, "05_Active_Projects", folder, f"{base}{suffix}"))
        # นับบทด้วย
        ch = len(glob.glob(os.path.join(SB, "05_Active_Projects", "Chapters", f"{base}_Chapter_*.md")))
        return {"ok": True, "status": st, "chapters": ch}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def _find_novel(title):
    """หาไฟล์นิยายใน pool จากชื่อ — normalize ตัวคั่น (_ : ช่องว่าง) เพื่อให้ slug กับชื่อจริงแมตช์กัน"""
    files = glob.glob(os.path.join(SB, "01_Scouting_Pool", "*.md"))
    _norm = lambda s: re.sub(r"[\s_:：]+", "", s or "")
    tn = _norm(title)
    if not tn:
        return None, {}
    keys = ("thai_working_title", "recreation_title", "title")
    for fp in files:  # exact (normalized)
        fm = _frontmatter(fp)
        if any(_norm(fm.get(k)) == tn for k in keys):
            return fp, fm
    for fp in files:  # substring (normalized)
        fm = _frontmatter(fp)
        if any(fm.get(k) and (tn in _norm(fm.get(k)) or _norm(fm.get(k)) in tn) for k in keys):
            return fp, fm
    return None, {}


def _assets_for(base):
    """สถานะสินทรัพย์ของเรื่อง (จาก slug base): ตอน/ปก/เสียง/teaser"""
    if not base:
        return {"chapters": 0, "cover": False, "audio": 0, "teaser": 0}
    g = lambda *p: glob.glob(os.path.join(SB, "05_Active_Projects", *p))
    return {
        "chapters": len(g("Chapters", f"{base}_Chapter_*.md")),
        "cover": bool(g("Covers", f"{base}_Cover*")),
        "audio": len(g("Audio_Output", f"{base}_Audiobook_*.mp3")),
        "teaser": len(g("Teasers", f"{base}_Teaser*")) + len(g("Teaser_Output", f"{base}*.mp4")),
    }


def _base_for(fm, title=""):
    try:
        import studio
        return studio._match_base(fm.get("recreation_title") or fm.get("thai_working_title")
                                  or title) or studio._slug(title)
    except Exception:
        return ""


def api_novel_detail(title):
    """เนื้อหาเต็ม + บทวิเคราะห์ AI + สถานะสินทรัพย์ ของนิยายหนึ่งเรื่อง"""
    fp, fm = _find_novel(title)
    if not fp:
        return {"ok": False, "error": "ไม่พบเรื่อง"}
    txt = _read_head(fp, 80000)
    body = txt.split("\n---", 1)[-1].split("---\n", 1)[-1] if txt.startswith("---") else txt
    base = _base_for(fm, title)
    health = None
    try:
        import story_health
        health = story_health.scan_story(SB, base, title)
    except Exception:
        pass
    return {"ok": True, "fm": fm, "body": body, "assets": _assets_for(base), "health": health}


def api_chapter(title, ch):
    """เนื้อหาบท (prose) สำหรับอ่านในแอป"""
    _, fm = _find_novel(title)
    base = _base_for(fm, title)
    try:
        n = int(ch)
    except (TypeError, ValueError):
        n = 1
    cf = os.path.join(SB, "05_Active_Projects", "Chapters", f"{base}_Chapter_{n:02d}.md")
    if not base or not os.path.exists(cf):
        return {"ok": False, "error": "ไม่พบบท"}
    chs = sorted(glob.glob(os.path.join(SB, "05_Active_Projects", "Chapters", f"{base}_Chapter_*.md")))
    total = len(chs)
    txt = _read_head(cf, 120000)
    return {"ok": True, "content": txt, "ch": n, "total": total,
            "title": fm.get("recreation_title") or fm.get("thai_working_title") or title,
            "chars": len(txt)}


def api_audiobook_status(title):
    """สถานะหนังสือเสียงรวมเล่ม: มีกี่ตอน · รวมแล้วหรือยัง · ลิงก์ + markers"""
    import audiobook
    base = audiobook._base_from(SB, title)
    if not base:
        return {"ok": False, "error": "ไม่พบไฟล์เสียงของเรื่องนี้"}
    adir = os.path.join(SB, "05_Active_Projects", "Audio_Output")
    n = len(glob.glob(os.path.join(adir, f"{base}_Audiobook_*.mp3")))
    full = os.path.join(SB, "05_Active_Projects", "Audiobooks", f"{base}_FULL.mp3")
    mk = os.path.join(SB, "05_Active_Projects", "Audiobooks", f"{base}_chapters.txt")
    exists = os.path.exists(full)
    return {"ok": True, "base": base, "parts": n, "exists": exists,
            "url": "/media/audiobooks/" + quote(f"{base}_FULL.mp3") if exists else "",
            "size_mb": round(os.path.getsize(full) / 1e6, 1) if exists else 0,
            "markers": _read_head(mk, 4000) if os.path.exists(mk) else ""}


def audiobook_run(payload):
    title = payload.get("title", "")
    return {"task": start_argv("Audiobook", ["audiobook.py", title])}


def continue_run(payload):
    """เขียนตอนต่อไปของเรื่อง (background) — เพิ่ม count ตอน"""
    title = payload.get("title", "")
    count = int(payload.get("count", 1) or 1)
    _, fm = _find_novel(title)
    base = _base_for(fm, title) or title
    return {"task": start_argv(f"เขียนต่อ:{base[:20]}",
            ["chapter_continuer.py", SB, str(count), "--title", base])}


def podcast_run(payload):
    """เรนเดอร์ + อัป podcast episodes (background). dry=true → ไม่อัปจริง"""
    title = payload.get("title", "")
    flag = "--publish-dry" if payload.get("dry") else "--publish"
    return {"task": start_argv(f"Podcast:{title[:18]}", ["podcast.py", title, flag])}


def shorts_run(payload):
    """สร้าง Shorts 9:16 ต่อตอน (background) — TikTok-safe สำหรับ YouTube Shorts + TikTok"""
    title = payload.get("title", "")
    if not title:
        return {"ok": False, "error": "ต้องระบุชื่อเรื่อง"}
    dur = str(int(payload.get("dur", 50) or 50))
    return {"task": start_argv(f"Shorts:{title[:18]}", ["shorts_generator.py", title, dur])}


def export_pack_run(payload):
    try:
        import export_pack
        r = export_pack.build_pack(SB, payload.get("title", ""))
        if r.get("ok"):
            r["url"] = "/media/exports/" + quote(os.path.basename(r["file"]))
        return r
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def api_feedback():
    """ผลตอบรับจริง: ledger + winning-patterns report + brief"""
    try:
        import feedback
        ledger = sorted(feedback.load_ledger(), key=lambda r: r.get("recorded_at", ""), reverse=True)
        report = _read_head(feedback.REPORT, 8000) if os.path.exists(feedback.REPORT) else ""
        brief = _read_head(feedback.BRIEF, 2000) if os.path.exists(feedback.BRIEF) else ""
        return {"ok": True, "ledger": ledger[:50], "count": len(ledger),
                "report": report, "brief": brief}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def feedback_record(payload):
    """บันทึก engagement ของเรื่อง แล้วสังเคราะห์ brief ใหม่ทันที"""
    try:
        import feedback
        story = (payload.get("story") or "").strip()
        if not story:
            return {"ok": False, "error": "ต้องระบุชื่อเรื่อง"}
        rec = feedback.record(story,
                              views=payload.get("views", 0) or 0,
                              likes=payload.get("likes", 0) or 0,
                              comments=payload.get("comments", 0) or 0,
                              shares=payload.get("shares", 0) or 0,
                              platform=payload.get("platform", "") or "",
                              url=payload.get("url", "") or "")
        feedback.learn(use_ai=False)  # อัปเดต brief/report (ฟรี ไม่ใช้ AI)
        return {"ok": True, "rec": rec}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def api_scout():
    try:
        import trend_scout
        rows = trend_scout.scout(SB)
        return {"ok": True, "rows": rows[:20], "total": len(rows)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def api_calendar():
    import schedule_plan
    return {"ok": True, "plan": schedule_plan.list_plan(SB),
            "upcoming": schedule_plan.upcoming(SB)}


def calendar_add(payload):
    import schedule_plan
    e = schedule_plan.add_entry(SB, payload)
    return {"ok": bool(e), "entry": e} if e else {"ok": False, "error": "ต้องมีชื่อเรื่อง + วันที่"}


def calendar_remove(payload):
    import schedule_plan
    return {"ok": schedule_plan.remove_entry(SB, payload.get("id"))}


def calendar_status(payload):
    import schedule_plan
    return {"ok": schedule_plan.set_status(SB, payload.get("id"), payload.get("status", "done"))}


def _heuristic_schedule(cands, today, per_week):
    """ตารางปล่อยแบบกฎ: เริ่มพรุ่งนี้ เว้นจังหวะตาม per_week · podcast→YouTube, teaser→TikTok สลับ"""
    gap = max(1, round(7 / max(per_week, 1)))
    d0 = datetime.strptime(today, "%Y-%m-%d")
    out = []
    for i, c in enumerate(cands):
        a = c.get("assets", {})
        plat = "tiktok" if (a.get("teaser") and i % 3 == 2) else "youtube"
        out.append({"title": c["title"],
                    "date": (d0 + timedelta(days=1 + i * gap)).strftime("%Y-%m-%d"),
                    "platform": plat,
                    "note": f"AI: fit {c.get('fit', '?')}"})
    return out


def _ai_schedule(cands, today, per_week):
    """ให้ AI จัดตารางปล่อย — คืน list entry หรือ None ถ้าพลาด"""
    try:
        import llm_provider
        lines = "\n".join(
            f"- {c['title']} (fit {c.get('fit', '?')}/10, สื่อ: "
            f"{'ปก' if c.get('assets', {}).get('cover') else ''}"
            f"{'+เสียง' if c.get('assets', {}).get('audio') else ''}"
            f"{'+teaser' if c.get('assets', {}).get('teaser') else ''})"
            for c in cands)
        prompt = f"""คุณคือผู้จัดการคอนเทนต์ของช่องนิยายเสียง วางแผนตารางปล่อยให้เหมาะสม
วันนี้คือ {today}. เรื่องที่พร้อมปล่อย (ยังไม่ได้วางแผน):
{lines}

จัดตารางปล่อย ~{per_week} เรื่อง/สัปดาห์ เริ่มจากพรุ่งนี้ เว้นจังหวะสม่ำเสมอ
เรียงเรื่องคะแนน fit สูงให้ปล่อยก่อน · เลือกแพลตฟอร์มให้เหมาะ (youtube=คลิปยาว/หนังสือเสียง, tiktok=สั้น)
ตอบ JSON เท่านั้น:
{{"plan":[{{"title":"ชื่อเรื่องตรงตามรายการ","date":"YYYY-MM-DD","platform":"youtube|tiktok","note":"เหตุผลสั้นๆ ว่าทำไมปล่อยวันนี้/แพลตฟอร์มนี้"}}]}}"""
        data = llm_provider.generate_json(prompt, role="researcher")
        plan = data.get("plan", []) if isinstance(data, dict) else []
        valid = [e for e in plan if e.get("title") and re.match(r"\d{4}-\d{2}-\d{2}", str(e.get("date", "")))]
        return valid or None
    except Exception:
        return None


def calendar_autoplan(payload):
    """🤖 AI วางแผนปล่อยอัตโนมัติจากเรื่องที่พร้อม (ยังไม่ได้วางแผน)"""
    import schedule_plan
    per_week = int(payload.get("per_week", 3) or 3)
    kb = api_kanban()
    cols = kb.get("columns", {})
    cands = []
    for col in ("ready", "assets"):
        for c in cols.get(col, []):
            cands.append({"title": c["title"], "fit": c.get("fit", ""), "assets": c.get("assets", {})})
    planned = {e.get("title") for e in schedule_plan.list_plan(SB)}
    cands = [c for c in cands if c["title"] not in planned]
    if not cands:
        return {"ok": False, "error": "ไม่มีเรื่องพร้อมปล่อยที่ยังไม่ได้วางแผน (ผลิตสื่อให้ครบก่อน)"}

    today = datetime.now().strftime("%Y-%m-%d")
    plan = _ai_schedule(cands, today, per_week)
    used_ai = bool(plan)
    if not plan:
        plan = _heuristic_schedule(cands, today, per_week)
    # จับคู่ชื่อกับ candidate จริง (กัน AI พิมพ์ชื่อเพี้ยน) + กรองวันที่อดีต
    titles = {c["title"] for c in cands}
    added = []
    for e in plan:
        t = e.get("title", "")
        if t not in titles:  # match ยืดหยุ่น
            t = next((x for x in titles if x in e.get("title", "") or e.get("title", "") in x), t)
        if t not in titles or e.get("date", "") < today:
            continue
        r = schedule_plan.add_entry(SB, {"title": t, "date": e["date"],
                                         "platform": e.get("platform", "youtube"), "note": e.get("note", "")})
        if r:
            added.append(r)
    return {"ok": bool(added), "added": len(added), "used_ai": used_ai,
            "entries": added, "candidates": len(cands)}


def _chapter_path(title, ch):
    _, fm = _find_novel(title)
    base = _base_for(fm, title)
    try:
        n = int(ch)
    except (TypeError, ValueError):
        n = 1
    if not base:
        return None
    return os.path.join(SB, "05_Active_Projects", "Chapters", f"{base}_Chapter_{n:02d}.md")


def api_versions(title, ch):
    fp = _chapter_path(title, ch)
    if not fp:
        return {"ok": False, "error": "ไม่พบเรื่อง"}
    import versions
    return {"ok": True, "versions": versions.list_versions(fp), "ch": int(ch)}


def api_version_read(title, ch, vname):
    fp = _chapter_path(title, ch)
    if not fp:
        return {"ok": False, "error": "ไม่พบเรื่อง"}
    import versions
    c = versions.read_version(fp, vname)
    if c is None:
        return {"ok": False, "error": "ไม่พบเวอร์ชัน"}
    return {"ok": True, "content": c, "chars": len(c), "name": vname}


def version_restore(payload):
    fp = _chapter_path(payload.get("title", ""), payload.get("ch", 1))
    if not fp or not os.path.exists(fp):
        return {"ok": False, "error": "ไม่พบบทปัจจุบัน"}
    import versions
    return versions.restore(fp, payload.get("v", ""))


def api_kanban():
    """จัดกลุ่มทุกเรื่องตามขั้นผลิต: รอเขียน → เขียนแล้ว → มีสื่อ → พร้อมปล่อย → เผยแพร่แล้ว"""
    cols = {"todo": [], "written": [], "assets": [], "ready": [], "published": []}
    pub_bases = set()
    try:
        import publisher
        for k, e in publisher.load_ledger(SB).items():
            if isinstance(e, dict) and any(str(v).startswith("http") for v in e.values()):
                pub_bases.add(re.sub(r"_Teaser.*$", "", k))
    except Exception:
        pass
    try:
        import story_health
    except Exception:
        story_health = None
    for fp in glob.glob(os.path.join(SB, "01_Scouting_Pool", "*.md")):
        fm = _frontmatter(fp)
        st = fm.get("status", "")
        title = fm.get("thai_working_title") or fm.get("title") or "?"
        card = {"title": title, "fit": fm.get("market_fit_score", ""), "status": st}
        if st in ("Scouted", "Analyzed"):
            card["sub"] = "วิเคราะห์แล้ว" if st == "Analyzed" else "รอวิเคราะห์"
            cols["todo"].append(card)
        elif st == "Processed":
            base = _base_for(fm, title)
            a = _assets_for(base)
            complete = a["cover"] and a["audio"] and a["teaser"]
            h = story_health.scan_story(SB, base, title) if story_health else {"status": "green"}
            card["health"] = h["status"]
            card["assets"] = a
            if base in pub_bases:
                cols["published"].append(card)
            elif complete and h["status"] == "green":
                cols["ready"].append(card)
            elif complete:
                cols["assets"].append(card)
            else:
                card["sub"] = f"{'✅' if a['cover'] else '⚪'}ปก {'✅' if a['audio'] else '⚪'}เสียง {'✅' if a['teaser'] else '⚪'}teaser"
                cols["written"].append(card)
    for c in cols.values():
        c.sort(key=lambda x: float(x.get("fit") or 0), reverse=True)
    return {"ok": True, "columns": cols,
            "counts": {k: len(v) for k, v in cols.items()}}


def api_health_stories():
    """สแกนสุขภาพทุกเรื่อง → summary + map(title→status) สำหรับ badge หน้านิยาย"""
    try:
        import story_health
        rows = story_health.scan_all(SB)
        summary = {"green": 0, "yellow": 0, "red": 0}
        m = {}
        for r in rows:
            summary[r["status"]] = summary.get(r["status"], 0) + 1
            m[r["title"]] = {"status": r["status"], "red": r["red"], "yellow": r["yellow"]}
        return {"ok": True, "summary": summary, "map": m}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def api_studio_detail(title):
    """รายละเอียดเรื่องสำหรับหน้า Studio: คอนเซ็ป/ตัวละคร/รายการตอน/สินทรัพย์/เมตา"""
    fp, fm = _find_novel(title)
    base = _base_for(fm, title)
    rd = lambda folder, name, n=40000: (_read_head(os.path.join(SB, folder, name), n)
                                        if os.path.exists(os.path.join(SB, folder, name)) else "")
    outline = rd("02_Concept_Extraction", f"{base}_Outline.md") if base else ""
    chars = rd("04_Character_Database", f"{base}_Characters.md", 25000) if base else ""
    chapters = [{"name": os.path.basename(c), "kb": os.path.getsize(c) // 1024}
                for c in sorted(glob.glob(os.path.join(SB, "05_Active_Projects", "Chapters",
                                                        f"{base}_Chapter_*.md")))] if base else []
    studio_st = {}
    for kind, (folder, suffix) in _STUDIO_OUT.items():
        studio_st[kind] = bool(base) and os.path.exists(
            os.path.join(SB, "05_Active_Projects", folder, f"{base}{suffix}"))
    return {"ok": True, "base": base, "outline": outline, "characters": chars,
            "chapters": chapters, "studio": studio_st, "assets": _assets_for(base),
            "target_chapters": int(os.environ.get("ANSRE_TARGET_CHAPTERS", "8") or 8),
            "meta": {"market_fit": fm.get("market_fit_score", ""), "popularity": fm.get("popularity_score", ""),
                     "genre": fm.get("genre", ""), "source": fm.get("source", ""),
                     "original": fm.get("title", ""), "status": fm.get("status", "")}}


def api_backups():
    try:
        import backup
        return {"ok": True, "backups": backup.list_backups()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def backup_run():
    try:
        import backup
        return backup.make_backup(SB)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def notify_test():
    try:
        import notify
        if not notify.enabled():
            return {"ok": False, "error": "ยังไม่ตั้ง ANSRE_DISCORD_WEBHOOK ใน .env"}
        ok = notify.notify("🔔 ทดสอบจาก dashboard — ระบบแจ้งเตือนใช้งานได้!", "ANSRE ทดสอบแจ้งเตือน", "good")
        return {"ok": ok, "error": "" if ok else "ส่งไม่สำเร็จ (เช็ค webhook)"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def api_translate(payload):
    """แปลข้อความ (ภาษาต่างชาติ เช่น ญี่ปุ่น/อังกฤษ) เป็นไทย"""
    text = (payload.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "no text"}
    try:
        from llm_provider import generate
        out = generate(
            "แปลข้อความต่อไปนี้เป็นภาษาไทยให้เป็นธรรมชาติ ลื่นไหล "
            "(ส่วนที่เป็นไทยอยู่แล้วคงไว้) ตอบเฉพาะคำแปล ไม่ต้องอธิบายหรือใส่หมายเหตุ:\n\n"
            + text[:3000], role="analyzer")
        return {"ok": True, "text": (out or "").strip()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def api_refine_modes():
    try:
        import studio
        return {"modes": studio.list_refine_modes()}
    except Exception as e:  # noqa: BLE001
        return {"modes": [], "error": str(e)}


def novel_write(payload):
    """เขียนนิยายเรื่องที่เจาะจง (ข้าม quality gate เพราะผู้ใช้เลือกเอง)"""
    title = (payload.get("title") or "").strip()
    if not title:
        return {"error": "no title"}
    return {"task": start_argv(f"write:{title[:18]}", ["agent_writer.py", SB, "--only", title])}


def novel_autofix(payload):
    """ซ่อมเรื่องอัตโนมัติ (บท error→regenerate, ตัวละคร CJK→เขียนใหม่) — เรื่องเดียวหรือทุก red"""
    title = (payload.get("title") or "").strip()
    argv = ["autofix.py", SB] + (["--only", title] if title else [])
    return {"task": start_argv("autofix:" + (title[:14] if title else "red"), argv)}


def novel_finish(payload):
    """เติมสินทรัพย์ที่ขาด (ปก/teaser/[+audio]) — เรื่องเดียวหรือทุกเรื่อง"""
    title = (payload.get("title") or "").strip()
    argv = ["finish.py", SB]
    if title:
        argv += ["--only", title]
    if payload.get("audio"):
        argv += ["--audio"]
    return {"task": start_argv("finish:" + (title[:14] if title else "all"), argv)}


def studio_launch(payload):
    action = payload.get("action", "")
    title = payload.get("title", "")
    rounds = str(payload.get("rounds", 2))
    argv_map = {
        "visual": ["studio.py", "visual", title],
        "video": ["studio.py", "video", title],
        "bible": ["studio.py", "bible", title],
        "audio": ["studio.py", "audio-script", title],
        "auto-qa": ["studio.py", "auto-qa", title, str(payload.get("chapter", 1) or 1)],
        "continuity": ["studio.py", "continuity", title],
        "caption": ["studio.py", "caption", title],
        "abtest": ["studio.py", "abtest", title],
        "idea-loop": ["studio.py", "idea-loop", payload.get("id", ""), rounds],
        "chapter-loop": ["studio.py", "chapter-loop", title,
                         str(payload.get("chapter", 1) or 1), rounds,
                         payload.get("mode", "critique") or "critique",
                         payload.get("note", "") or ""],
    }
    argv = argv_map.get(action)
    if not argv:
        return {"error": "bad action"}
    return {"task": start_argv(f"studio-{action}", argv)}


def api_outputs():
    """จัดกลุ่มสื่อตามเรื่อง (ปก+เสียง+teaser ของเรื่องเดียวกันอยู่ด้วยกัน)"""
    ap = os.path.join(SB, "05_Active_Projects")
    stories = {}

    def story(base):
        return stories.setdefault(base, {"base": base, "title": base.replace("_", " "),
                                         "cover": "", "audio": [], "teasers": []})
    # ปก (ใช้ตัวที่มี caption ก่อน)
    for fp in sorted(glob.glob(os.path.join(ap, "Covers", "*.jpg"))):
        n = os.path.basename(fp)
        if n.endswith("_Cover_captioned.jpg"):
            s = story(n[:-len("_Cover_captioned.jpg")])
            s["cover"] = f"/media/covers/{n}"
        elif n.endswith("_Cover.jpg"):
            s = story(n[:-len("_Cover.jpg")])
            s.setdefault("_raw", f"/media/covers/{n}")
    for s in stories.values():
        if not s["cover"] and s.get("_raw"):
            s["cover"] = s["_raw"]
    # เสียง
    for fp in sorted(glob.glob(os.path.join(ap, "Audio_Output", "*.mp3"))):
        n = os.path.basename(fp)
        b = re.sub(r"_Audiobook_\d+\.mp3$", "", n)
        story(b)["audio"].append({"name": n, "url": f"/media/audio/{n}"})
    # teaser
    for fp in sorted(glob.glob(os.path.join(ap, "Teaser_Output", "*.mp4"))):
        n = os.path.basename(fp)
        b = re.sub(r"_Teaser_\d+\.mp4$", "", n)
        story(b)["teasers"].append({"name": n, "url": f"/media/teasers/{n}"})
    # เรียง: เรื่องที่มี teaser ก่อน
    rows = sorted(stories.values(), key=lambda s: (-len(s["teasers"]), -len(s["audio"]), s["base"]))
    for s in rows:
        s.pop("_raw", None)
    return {"stories": rows}


# ---------------------------------------------------------------------------
# Worker (launchd)
# ---------------------------------------------------------------------------
def _worker_running():
    if not os.path.exists(LAUNCH_PLIST):
        return False
    return subprocess.run(["launchctl", "list", LAUNCH_LABEL], capture_output=True).returncode == 0


EDITABLE_ENV = {"LLM_BACKEND", "WRITING_MODE", "ANSRE_DAILY_USD_CAP", "ANSRE_DAILY_HARD_CAP", "ANSRE_TARGET_CHAPTERS", "ANSRE_CALL_GAP",
                "LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL", "TTS_ENGINE",
                "PUBLISH_YOUTUBE", "PUBLISH_TIKTOK", "PUBLISH_NOVEL"} | {
                f"LLM_ROLE_{r.upper()}" for r in
                ("writer", "enhancer", "outline", "characters", "planner",
                 "analyzer", "audio", "reviewer", "researcher", "editor", "brainstorm")}


def update_env(updates: dict):
    """แก้ค่าใน .env แบบปลอดภัย (เฉพาะคีย์ใน whitelist) + อัปเดต process env ทันที"""
    path = os.path.join(ROOT, ".env")
    lines = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    keys = {k: str(v) for k, v in updates.items() if k in EDITABLE_ENV}
    seen = set()
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.split("=", 1)[0].strip()
            if k in keys:
                lines[i] = f"{k}={keys[k]}\n"
                seen.add(k)
    # กันไฟล์เดิมที่บรรทัดสุดท้ายไม่มี newline (ไม่งั้น append จะต่อท้ายบรรทัดเดิม -> ค่าพัง)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    for k, v in keys.items():
        if k not in seen:
            lines.append(f"{k}={v}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    for k, v in keys.items():
        os.environ[k] = v  # ให้มีผลทันทีกับ process นี้
    return {"ok": True, "updated": list(keys.keys())}


def worker_action(action):
    if action == "start":
        src = os.path.join(ROOT, "deploy", "com.ansre.worker.plist")
        content = _read_head(src, 10000).replace("<REPO_PATH>", ROOT).replace("&lt;REPO_PATH&gt;", ROOT)
        os.makedirs(os.path.dirname(LAUNCH_PLIST), exist_ok=True)
        with open(LAUNCH_PLIST, "w", encoding="utf-8") as f:
            f.write(content)
        subprocess.run(["launchctl", "unload", LAUNCH_PLIST], capture_output=True)
        subprocess.run(["launchctl", "load", "-w", LAUNCH_PLIST], capture_output=True)
        return {"ok": True, "running": True}
    else:
        if os.path.exists(LAUNCH_PLIST):
            subprocess.run(["launchctl", "unload", LAUNCH_PLIST], capture_output=True)
        return {"ok": True, "running": False}


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------
TASKS = {}
_task_lock = threading.Lock()

STAGE_CMDS = {
    "run": ["orchestrator.py", "--once"],
    "idea-auto": ["ideation.py", "auto"],
    "idea-brainstorm": ["ideation.py", "brainstorm"],
    "idea-score": ["ideation.py", "score"],
    "idea-fuse": ["ideation.py", "fuse"],
    "scout": ["scout.py", "--source", "all", "--limit", "20", "--outdir", SB],
    "analyze": ["agent_analyzer.py", SB],
    "trends": ["trends.py"],
    "write": ["agent_writer.py", SB],
    "continue": ["chapter_continuer.py", SB, "--target",
                 os.environ.get("ANSRE_TARGET_CHAPTERS", "8"), "--max-per-run", "1", "--max-stories", "5"],
    "cover": ["cover_generator.py", SB],
    "audio": ["audio_engine.py", SB],
    "teaser": ["teaser_generator.py", SB, "60"],
    "publish": ["publisher.py", SB],
}


def start_argv(label, argv):
    """รัน [venv python] + argv เป็น background task ที่ track ได้ (label = ชื่อแสดง)"""
    os.makedirs(TASK_DIR, exist_ok=True)
    safe = re.sub(r"[^\w]+", "-", label)[:40]
    tid = f"{safe}-{int(time.time())}"
    logpath = os.path.join(TASK_DIR, tid + ".log")

    def runner():
        with open(logpath, "w", encoding="utf-8") as lf:
            lf.write(f"$ {label}\n")
            lf.flush()
            try:
                # -u + PYTHONUNBUFFERED: log วิ่งสดทันที (ไม่งั้น stdout ถูก buffer จนจบ → ดูเหมือนค้าง)
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"
                p = subprocess.Popen([venv_py(), "-u"] + argv, cwd=ROOT, env=env,
                                     stdout=lf, stderr=subprocess.STDOUT, bufsize=1)
                with _task_lock:
                    TASKS[tid]["pid"] = p.pid
                p.wait()
                with _task_lock:
                    TASKS[tid]["status"] = "done" if p.returncode == 0 else "error"
                    TASKS[tid]["rc"] = p.returncode
            except Exception as e:  # noqa: BLE001
                lf.write(f"\n[fatal] {e}\n")
                with _task_lock:
                    TASKS[tid]["status"] = "error"

    with _task_lock:
        TASKS[tid] = {"id": tid, "stage": label, "status": "running", "log": logpath}
    threading.Thread(target=runner, daemon=True).start()
    return tid


def start_task(stage):
    if stage not in STAGE_CMDS:
        return None
    return start_argv(stage, STAGE_CMDS[stage])


def task_info(tid):
    with _task_lock:
        t = dict(TASKS.get(tid, {}))
    if not t:
        return None
    t["output"] = _read_head(t.get("log", ""), 20000)
    return t


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
MIME = {".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "application/javascript",
        ".mp3": "audio/mpeg", ".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon"}

MEDIA_DIRS = {
    "covers": os.path.join(SB, "05_Active_Projects", "Covers"),
    "audio": os.path.join(SB, "05_Active_Projects", "Audio_Output"),
    "teasers": os.path.join(SB, "05_Active_Projects", "Teaser_Output"),
    "trailers": os.path.join(SB, "05_Active_Projects", "Trailers"),
    "audiobooks": os.path.join(SB, "05_Active_Projects", "Audiobooks"),
    "exports": os.path.join(SB, "05_Active_Projects", "Exports"),
    "podcast": os.path.join(SB, "05_Active_Projects", "Podcast_Episodes"),
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path):
        if not os.path.isfile(path):
            return self._send(404, {"error": "not found"})
        ext = os.path.splitext(path)[1].lower()
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        # กันเบราว์เซอร์ cache ไฟล์ UI เก่า (html/js/css) — เห็นอัปเดตทันทีไม่ต้อง hard refresh
        if ext in (".html", ".js", ".css"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        try:
            if p == "/" or p == "/index.html":
                return self._serve_file(os.path.join(WEB, "index.html"))
            if p.startswith("/web/"):
                return self._serve_file(os.path.join(WEB, p[5:]))
            if p == "/api/status":
                return self._send(200, api_status())
            if p == "/api/doctor":
                return self._send(200, api_doctor())
            if p == "/api/usage":
                return self._send(200, api_usage())
            if p == "/api/novels":
                return self._send(200, api_novels())
            if p == "/api/trends":
                return self._send(200, api_trends())
            if p == "/api/config":
                return self._send(200, api_config())
            if p == "/api/outputs":
                return self._send(200, api_outputs())
            if p == "/api/ideas":
                return self._send(200, api_ideas())
            if p == "/api/idea/detail":
                return self._send(200, idea_detail(parse_qs(u.query).get("id", [""])[0]))
            if p == "/api/projects":
                return self._send(200, api_projects())
            if p == "/api/studio/output":
                qs = parse_qs(u.query)
                return self._send(200, api_studio_output(qs.get("kind", [""])[0], qs.get("title", [""])[0]))
            if p == "/api/studio/status":
                return self._send(200, api_studio_status(parse_qs(u.query).get("title", [""])[0]))
            if p == "/api/studio/detail":
                return self._send(200, api_studio_detail(parse_qs(u.query).get("title", [""])[0]))
            if p == "/api/novel/detail":
                return self._send(200, api_novel_detail(parse_qs(u.query).get("title", [""])[0]))
            if p == "/api/refine/modes":
                return self._send(200, api_refine_modes())
            if p == "/api/reload-token":
                return self._send(200, {"enabled": RELOAD, "token": _reload_token()})
            if p == "/api/health/stories":
                return self._send(200, api_health_stories())
            if p == "/api/calendar":
                return self._send(200, api_calendar())
            if p == "/api/scout":
                return self._send(200, api_scout())
            if p == "/api/feedback":
                return self._send(200, api_feedback())
            if p == "/api/audiobook":
                qs = parse_qs(u.query)
                return self._send(200, api_audiobook_status(qs.get("title", [""])[0]))
            if p == "/api/versions":
                qs = parse_qs(u.query)
                return self._send(200, api_versions(qs.get("title", [""])[0], qs.get("ch", ["1"])[0]))
            if p == "/api/version":
                qs = parse_qs(u.query)
                return self._send(200, api_version_read(qs.get("title", [""])[0], qs.get("ch", ["1"])[0], qs.get("v", [""])[0]))
            if p == "/api/chapter":
                qs = parse_qs(u.query)
                return self._send(200, api_chapter(qs.get("title", [""])[0], qs.get("ch", ["1"])[0]))
            if p == "/api/kanban":
                return self._send(200, api_kanban())
            if p == "/api/backups":
                return self._send(200, api_backups())
            if p.startswith("/backup/"):
                fn = os.path.basename(unquote(p.split("/backup/", 1)[1]))
                return self._serve_file(os.path.join(ROOT, "backups", fn))
            if p == "/api/cost/advice":
                return self._send(200, api_cost_advice())
            if p == "/api/analytics":
                return self._send(200, api_analytics())
            if p == "/api/publish/status":
                return self._send(200, api_publish_status())
            if p.startswith("/api/task/"):
                info = task_info(p.split("/api/task/")[1])
                return self._send(200, info or {"error": "no task"})
            if p.startswith("/media/"):
                _, _, cat, fname = p.split("/", 3)
                fname = unquote(fname)   # ชื่อไฟล์ไทยถูก URL-encode ต้อง decode ก่อนหา
                d = MEDIA_DIRS.get(cat)
                if d:
                    # กัน path traversal: อนุญาตเฉพาะ basename
                    safe = os.path.join(d, os.path.basename(fname))
                    return self._serve_file(safe)
                return self._send(404, {"error": "bad media"})
            return self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            return self._send(500, {"error": str(e)})

    def do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except Exception:
            payload = {}
        try:
            if u.path == "/api/run":
                return self._send(200, {"task": start_task("run")})
            if u.path == "/api/stage":
                tid = start_task(payload.get("stage", ""))
                return self._send(200, {"task": tid} if tid else {"error": "bad stage"})
            if u.path == "/api/worker":
                return self._send(200, worker_action(payload.get("action", "stop")))
            if u.path == "/api/env":
                return self._send(200, update_env(payload or {}))
            if u.path == "/api/idea/add":
                return self._send(200, idea_add(payload.get("text", "")))
            if u.path == "/api/idea/promote":
                return self._send(200, idea_promote(payload.get("id", "")))
            if u.path == "/api/idea/action":
                return self._send(200, idea_action(payload))
            if u.path == "/api/idea/merge":
                return self._send(200, idea_merge(payload.get("ids", [])))
            if u.path == "/api/idea/develop":
                return self._send(200, idea_develop(payload))
            if u.path == "/api/idea/devwrite":
                return self._send(200, idea_devwrite(payload.get("id", "")))
            if u.path == "/api/idea/character":
                return self._send(200, idea_character(payload))
            if u.path == "/api/novel/write":
                return self._send(200, novel_write(payload))
            if u.path == "/api/novel/finish":
                return self._send(200, novel_finish(payload))
            if u.path == "/api/novel/autofix":
                return self._send(200, novel_autofix(payload))
            if u.path == "/api/publish/run":
                return self._send(200, publish_run(payload))
            if u.path == "/api/translate":
                return self._send(200, api_translate(payload))
            if u.path == "/api/notify/test":
                return self._send(200, notify_test())
            if u.path == "/api/backup":
                return self._send(200, backup_run())
            if u.path == "/api/version/restore":
                return self._send(200, version_restore(payload))
            if u.path == "/api/audiobook":
                return self._send(200, audiobook_run(payload))
            if u.path == "/api/export":
                return self._send(200, export_pack_run(payload))
            if u.path == "/api/podcast":
                return self._send(200, podcast_run(payload))
            if u.path == "/api/shorts":
                return self._send(200, shorts_run(payload))
            if u.path == "/api/continue":
                return self._send(200, continue_run(payload))
            if u.path == "/api/feedback/record":
                return self._send(200, feedback_record(payload))
            if u.path == "/api/calendar/add":
                return self._send(200, calendar_add(payload))
            if u.path == "/api/calendar/autoplan":
                return self._send(200, calendar_autoplan(payload))
            if u.path == "/api/calendar/remove":
                return self._send(200, calendar_remove(payload))
            if u.path == "/api/calendar/status":
                return self._send(200, calendar_status(payload))
            if u.path == "/api/trailer":
                return self._send(200, {"task": start_argv("Channel Trailer", ["trailer.py", "--clip", "5", "--limit", "6"])})
            if u.path == "/api/studio":
                return self._send(200, studio_launch(payload))
            return self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            return self._send(500, {"error": str(e)})


def main():
    os.makedirs(WEB, exist_ok=True)
    _free_port(PORT)   # ปิด instance เดิมที่ค้างพอร์ต กัน Address already in use
    if RELOAD:
        threading.Thread(target=_reload_watcher, daemon=True).start()
        print("[reload] 🔥 hot-reload เปิด — แก้ web/*.{html,js,css} → เบราว์เซอร์ refresh เอง · แก้ *.py → restart อัตโนมัติ", flush=True)
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    # flush ทันที เพื่อให้ตัว preview/launcher จับสัญญาณ "ready" ได้ (ไม่งั้น stdout ถูก buffer)
    print(f"ANSRE Dashboard ready — Listening on http://localhost:{PORT}", flush=True)
    sys.stdout.flush()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nหยุด dashboard แล้ว")


if __name__ == "__main__":
    main()
