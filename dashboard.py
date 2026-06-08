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
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
WEB = os.path.join(ROOT, "web")
TASK_DIR = os.path.join(SB, ".tasks")
PORT = int(os.environ.get("PORT") or os.environ.get("ANSRE_WEB_PORT") or "8765")

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
    by_date, by_backend, by_role = {}, {}, {}
    if os.path.exists(log):
        with open(log, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                d = e.get("date", "?")
                by_date[d] = round(by_date.get(d, 0) + e.get("est_usd", 0), 4)
                by_backend[e.get("backend", "?")] = by_backend.get(e.get("backend", "?"), 0) + 1
                by_role[e.get("role", "?")] = by_role.get(e.get("role", "?"), 0) + 1
    series = sorted(by_date.items())[-14:]
    return {"by_date": series, "by_backend": by_backend, "by_role": by_role,
            "today": round(today_spend(), 4)}


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

    if backend in ("local", "hybrid"):
        import socket
        u = urlparse(os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1"))
        host, port = u.hostname or "localhost", u.port or 11434
        try:
            with socket.create_connection((host, port), timeout=2):
                add(True, "Local LLM (Mac mini)", f"{host}:{port} ต่อได้")
        except Exception:
            add(False, "Local LLM (Mac mini)", f"{host}:{port} ต่อไม่ได้ (fallback Gemini)", level="warn")

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


# ---- Studio (visual/video/loops) ----
_STUDIO_OUT = {
    "visual": ("Visual_Prompts", "_Visual.md"),
    "video": ("Video_Prompts", "_Video.md"),
    "bible": ("Story_Bible", "_Bible.md"),
    "audio": ("Audio_Scripts", "_AudioScript_01.md"),
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


def studio_launch(payload):
    action = payload.get("action", "")
    title = payload.get("title", "")
    rounds = str(payload.get("rounds", 2))
    argv_map = {
        "visual": ["studio.py", "visual", title],
        "video": ["studio.py", "video", title],
        "bible": ["studio.py", "bible", title],
        "audio": ["studio.py", "audio-script", title],
        "idea-loop": ["studio.py", "idea-loop", payload.get("id", ""), rounds],
        "chapter-loop": ["studio.py", "chapter-loop", title, "1", rounds],
    }
    argv = argv_map.get(action)
    if not argv:
        return {"error": "bad action"}
    return {"task": start_argv(f"studio-{action}", argv)}


def api_outputs():
    def listing(parts, kind):
        out = []
        for fp in sorted(glob.glob(os.path.join(SB, *parts))):
            out.append({"name": os.path.basename(fp), "kind": kind,
                        "url": f"/media/{kind}/{os.path.basename(fp)}"})
        return out
    return {
        "covers": listing(("05_Active_Projects", "Covers", "*"), "covers"),
        "audio": listing(("05_Active_Projects", "Audio_Output", "*.mp3"), "audio"),
        "teasers": listing(("05_Active_Projects", "Teaser_Output", "*.mp4"), "teasers"),
    }


# ---------------------------------------------------------------------------
# Worker (launchd)
# ---------------------------------------------------------------------------
def _worker_running():
    if not os.path.exists(LAUNCH_PLIST):
        return False
    return subprocess.run(["launchctl", "list", LAUNCH_LABEL], capture_output=True).returncode == 0


EDITABLE_ENV = {"LLM_BACKEND", "WRITING_MODE", "ANSRE_DAILY_USD_CAP",
                "LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL", "TTS_ENGINE",
                "PUBLISH_YOUTUBE", "PUBLISH_TIKTOK", "PUBLISH_NOVEL"}


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
    "scout": ["scout.py", "--source", "all", "--limit", "5", "--outdir", SB],
    "analyze": ["agent_analyzer.py", SB],
    "trends": ["trends.py"],
    "write": ["agent_writer.py", SB],
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
                p = subprocess.Popen([venv_py()] + argv, cwd=ROOT,
                                     stdout=lf, stderr=subprocess.STDOUT)
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
            if p == "/api/projects":
                return self._send(200, api_projects())
            if p == "/api/studio/output":
                qs = parse_qs(u.query)
                return self._send(200, api_studio_output(qs.get("kind", [""])[0], qs.get("title", [""])[0]))
            if p.startswith("/api/task/"):
                info = task_info(p.split("/api/task/")[1])
                return self._send(200, info or {"error": "no task"})
            if p.startswith("/media/"):
                _, _, cat, fname = p.split("/", 3)
                d = MEDIA_DIRS.get(cat)
                if d:
                    return self._serve_file(os.path.join(d, fname))
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
            if u.path == "/api/studio":
                return self._send(200, studio_launch(payload))
            return self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            return self._send(500, {"error": str(e)})


def main():
    os.makedirs(WEB, exist_ok=True)
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
