#!/usr/bin/env python3
"""
ANSRE — single entry point. ใช้ผ่านตัวห่อ ./ansre <command>

คำสั่งหลัก (ใช้บ่อย):
  ./ansre setup            ติดตั้งทุกอย่าง (venv + deps + .env)
  ./ansre doctor           เช็คว่าทุกอย่างพร้อม/ขาดอะไร พร้อมวิธีแก้
  ./ansre status           ดูสถานะ pipeline (งานค้างแต่ละขั้น + ค่าใช้จ่ายวันนี้)
  ./ansre web              🌐 เปิด web dashboard สวยๆ คุมทุกอย่าง (http://localhost:8765)
  ./ansre run [--loop]     เดิน pipeline 1 รอบ (หรือวนต่อเนื่องด้วย --loop)
  ./ansre start | stop     เปิด/ปิด worker ให้รันเองทั้งวัน (launchd)

คำสั่งย่อย (รันทีละขั้นได้):
  idea (คลังไอเดีย: add/brainstorm/score/promote/list/auto)
  studio (visual/video/audio-script/bible/idea-loop/chapter-loop)
  scout · analyze · write · continue (เขียนตอนต่อ) · cover · audio · teaser · pipeline · publish
  usage (ดูค่า token) · selftest (เช็ค LLM backend) · local (เช็ค+เบนช์มาร์ก Mac mini)
  gateway [health|serve] (เช็ค/เปิด LLM+Image gateway — ดู SERVICE_ARCHITECTURE.md)
"""
import os
import sys
import json
import glob
import socket
import subprocess
from datetime import datetime
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
LAUNCH_LABEL = "com.ansre.worker"
LAUNCH_PLIST = os.path.expanduser(f"~/Library/LaunchAgents/{LAUNCH_LABEL}.plist")

OK, BAD, WARN = "✅", "❌", "⚠️ "


# ---------------------------------------------------------------------------
def load_env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def venv_py():
    cand = os.path.join(ROOT, ".venv", "bin", "python")
    return cand if os.path.exists(cand) else "python3"


def have_venv():
    return os.path.exists(os.path.join(ROOT, ".venv", "bin", "python"))


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT).returncode


def count_status(*statuses):
    n = 0
    for fp in glob.glob(os.path.join(SB, "01_Scouting_Pool", "*.md")):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                head = f.read(1500)
            if any(f'status: "{s}"' in head or f"status: {s}" in head for s in statuses):
                n += 1
        except Exception:
            pass
    return n


def count_files(*parts):
    return len(glob.glob(os.path.join(SB, *parts)))


def today_spend():
    log = os.path.join(SB, "llm_usage.jsonl")
    if not os.path.exists(log):
        return 0.0
    today = datetime.now().strftime("%Y-%m-%d")
    total = 0.0
    with open(log, "r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
                if e.get("date") == today:
                    total += e.get("est_usd", 0.0)
            except Exception:
                pass
    return total


# ---------------------------------------------------------------------------
def cmd_doctor():
    print("🩺 ANSRE Doctor\n" + "=" * 40)
    problems = []

    # venv + python
    if have_venv():
        ver = subprocess.run([venv_py(), "-c", "import sys;print(f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}')"],
                             capture_output=True, text=True).stdout.strip()
        ok = ver.startswith("3.13")
        print(f"{OK if ok else WARN} venv Python: {ver}" + ("" if ok else "  (แนะนำ 3.13)"))
        if not ok:
            problems.append("venv ไม่ใช่ Python 3.13 — ลบ .venv แล้ว ./ansre setup ใหม่")
    else:
        print(f"{BAD} ยังไม่มี .venv")
        problems.append("รัน:  ./ansre setup")

    # deps
    if have_venv():
        r = subprocess.run([venv_py(), "-c", "import streamlit, google.genai, edge_tts, pydub, requests, googleapiclient"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print(f"{OK} dependencies ครบ")
        else:
            print(f"{BAD} dependencies ขาด: {r.stderr.strip().splitlines()[-1] if r.stderr else '?'}")
            problems.append("รัน:  ./ansre setup")

    # ffmpeg
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0:
        print(f"{OK} ffmpeg")
    else:
        print(f"{BAD} ไม่มี ffmpeg")
        problems.append("ติดตั้ง:  brew install ffmpeg")

    # .env keys
    if os.path.exists(os.path.join(ROOT, ".env")):
        print(f"{OK} .env")
        backend = os.environ.get("LLM_BACKEND", "gemini")
        gem = os.environ.get("GEMINI_API_KEY")
        notion = os.environ.get("NOTION_TOKEN")
        need_gem = backend in ("gemini", "hybrid")
        print(f"   {OK if gem else (WARN if backend=='local' else BAD)} GEMINI_API_KEY "
              + ("set" if gem else ("ไม่จำเป็น (backend=local)" if not need_gem else "ขาด!")))
        print(f"   {OK if notion else WARN} NOTION_TOKEN " + ("set" if notion else "ขาด (จำเป็นถ้าจะ sync Notion)"))
        if need_gem and not gem:
            problems.append("ใส่ GEMINI_API_KEY ใน .env")
        print(f"   ℹ️  LLM_BACKEND = {backend}")
    else:
        print(f"{BAD} ไม่มี .env")
        problems.append("รัน:  ./ansre setup  แล้วใส่คีย์ใน .env")

    # local LLM (ollama) reachability
    backend = os.environ.get("LLM_BACKEND", "gemini")
    if backend in ("local", "hybrid"):
        url = os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
        u = urlparse(url)
        host, port = u.hostname or "localhost", u.port or 11434
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"{OK} local LLM ต่อได้: {host}:{port}")
        except Exception:
            print(f"{WARN} local LLM ต่อไม่ได้: {host}:{port} (จะ fallback ไป Gemini)")
            problems.append(f"เปิด Ollama บน {host}:{port} (ดู MACMINI_SETUP.md) — หรือใช้ LLM_BACKEND=gemini ชั่วคราว")

    # gateway (เฉพาะเมื่อเปิดใช้)
    gw = os.environ.get("ANSRE_GATEWAY_URL")
    if gw:
        try:
            import urllib.request
            urllib.request.urlopen(gw.rstrip("/") + "/healthz", timeout=5).read()
            print(f"{OK} gateway ต่อได้: {gw}  (LLM+Image route ผ่าน gateway)")
        except Exception:
            print(f"{WARN} gateway ต่อไม่ได้: {gw} (provider จะ fallback ทำเองในเครื่อง)")
            problems.append(f"เปิด gateway: ./ansre gateway serve หรือ bash macmini_gateway_setup.sh บน Mac mini")

    # worker
    if os.path.exists(LAUNCH_PLIST):
        running = subprocess.run(["launchctl", "list", LAUNCH_LABEL], capture_output=True).returncode == 0
        print(f"{OK if running else WARN} worker (launchd): {'running' if running else 'installed แต่ยังไม่โหลด'}")
    else:
        print(f"ℹ️  worker ยังไม่ติดตั้ง (./ansre start เพื่อรันต่อเนื่อง)")

    print("=" * 40)
    if problems:
        print("🔧 ต้องแก้:")
        for p in problems:
            print(f"   - {p}")
    else:
        print("🎉 พร้อมใช้งานครบทุกอย่าง!")
    return 1 if problems else 0


def cmd_status():
    if not os.path.isdir(SB):
        print("ยังไม่มีข้อมูล (SecondBrain ว่าง) — เริ่มด้วย ./ansre run")
        return 0
    print("📊 ANSRE Status\n" + "=" * 40)
    print("Pipeline (Scouting Pool):")
    print(f"   🔍 Scouted (รอวิเคราะห์)  : {count_status('Scouted')}")
    print(f"   🧠 Analyzed (รอเขียน)     : {count_status('Analyzed')}")
    print(f"   ✍️  Processed (เขียนแล้ว)  : {count_status('Processed')}")
    print("ผลผลิต:")
    print(f"   📖 บทนิยาย   : {count_files('05_Active_Projects','Chapters','*.md')}")
    print(f"   🖼️  ปก        : {count_files('05_Active_Projects','Covers','*')}")
    print(f"   🎧 หนังสือเสียง: {count_files('05_Active_Projects','Audio_Output','*.mp3')}")
    print(f"   🎬 teaser    : {count_files('05_Active_Projects','Teaser_Output','*.mp4')}")
    print(f"   📤 คิวเผยแพร่ : {count_files('05_Active_Projects','Publish_Queue','*')}")
    print("=" * 40)
    print(f"💰 ค่า LLM วันนี้: ${today_spend():.4f}")
    return 0


def cmd_start():
    """ติดตั้ง + โหลด launchd worker ให้รันต่อเนื่อง"""
    src = os.path.join(ROOT, "deploy", "com.ansre.worker.plist")
    if not os.path.exists(src):
        print(f"{BAD} ไม่พบ {src}")
        return 1
    with open(src, "r", encoding="utf-8") as f:
        content = f.read().replace("<REPO_PATH>", ROOT).replace("&lt;REPO_PATH&gt;", ROOT)
    os.makedirs(os.path.dirname(LAUNCH_PLIST), exist_ok=True)
    with open(LAUNCH_PLIST, "w", encoding="utf-8") as f:
        f.write(content)
    subprocess.run(["launchctl", "unload", LAUNCH_PLIST], capture_output=True)
    rc = subprocess.run(["launchctl", "load", "-w", LAUNCH_PLIST]).returncode
    if rc == 0:
        print(f"{OK} worker เริ่มทำงานแล้ว — จะเดิน pipeline เองทุก 20 นาที")
        print(f"   ดูล็อก:  tail -f /tmp/ansre.worker.log")
        print(f"   ปิด:     ./ansre stop")
    return rc


def cmd_stop():
    if os.path.exists(LAUNCH_PLIST):
        subprocess.run(["launchctl", "unload", LAUNCH_PLIST])
        print(f"{OK} หยุด worker แล้ว")
    else:
        print("worker ยังไม่ได้ติดตั้ง")
    return 0


def cmd_gateway(rest):
    """เช็ค/เปิด ANSRE Gateway (LLM+Image HTTP service)"""
    sub = rest[0] if rest else "health"
    url = os.environ.get("ANSRE_GATEWAY_URL", "http://localhost:9000").rstrip("/")
    token = os.environ.get("ANSRE_GATEWAY_TOKEN", "")

    if sub == "serve":
        if not have_venv():
            print(f"{WARN} ยังไม่ได้ติดตั้ง — รัน:  ./ansre setup")
            return 1
        host = os.environ.get("ANSRE_GATEWAY_HOST", "0.0.0.0")
        port = os.environ.get("ANSRE_GATEWAY_PORT", "9000")
        print(f"🚪 เปิด ANSRE Gateway ที่ http://{host}:{port}  (Ctrl+C เพื่อหยุด)")
        print("   deploy ถาวรบน Mac mini:  bash macmini_gateway_setup.sh")
        return run([venv_py(), "-m", "uvicorn", "gateway:app", "--host", host, "--port", port])

    # default: health
    import urllib.request
    req = urllib.request.Request(url + "/healthz",
                                 headers={"X-ANSRE-Token": token} if token else {})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        print(f"{OK} gateway: {url}")
        for k, v in data.items():
            print(f"   {k}: {v}")
        return 0
    except Exception as e:
        print(f"{BAD} ต่อ gateway ไม่ได้ ({url}): {e}")
        print("   เปิดเอง:        ./ansre gateway serve")
        print("   หรือ deploy:   bash macmini_gateway_setup.sh (บน Mac mini)")
        return 1


# ---------------------------------------------------------------------------
def need_gem_or_exit():
    backend = os.environ.get("LLM_BACKEND", "gemini")
    if backend in ("gemini", "hybrid") and not os.environ.get("GEMINI_API_KEY"):
        print(f"{BAD} GEMINI_API_KEY ไม่ได้ตั้ง (LLM_BACKEND={backend}). ใส่ใน .env หรือใช้ LLM_BACKEND=local")
        sys.exit(1)


def main():
    load_env()
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    rest = args[1:]
    py = venv_py()

    if cmd in ("help", "-h", "--help"):
        print(__doc__)
        return 0

    # commands ที่ไม่ต้องใช้ venv ก่อน
    if cmd == "doctor":
        return cmd_doctor()
    if cmd == "status":
        return cmd_status()
    if cmd == "start":
        return cmd_start()
    if cmd == "stop":
        return cmd_stop()
    if cmd == "gateway":
        return cmd_gateway(rest)

    if not have_venv():
        print(f"{WARN} ยังไม่ได้ติดตั้ง — รัน:  ./ansre setup")
        return 1

    # map คำสั่ง -> สคริปต์
    if cmd == "idea":
        return run([py, "ideation.py"] + rest)
    if cmd == "studio":
        return run([py, "studio.py"] + rest)
    if cmd == "continue":
        need_gem_or_exit()
        return run([py, "chapter_continuer.py", SB] + rest)
    if cmd == "web":
        port = os.environ.get("ANSRE_WEB_PORT", "8765")
        print(f"🌐 เปิด dashboard ที่ http://localhost:{port}")
        return run([py, "dashboard.py"])
    if cmd == "run":
        return run([py, "orchestrator.py"] + (rest if rest else ["--once"]))
    if cmd == "scout":
        return run([py, "scout.py", "--source", "all", "--limit", "3", "--outdir", SB] + rest)
    if cmd == "analyze":
        need_gem_or_exit(); return run([py, "agent_analyzer.py", SB])
    if cmd == "trends":
        return run([py, "trends.py"] + rest)
    if cmd == "write":
        need_gem_or_exit(); return run([py, "agent_writer.py", SB])
    if cmd == "cover":
        need_gem_or_exit(); return run([py, "cover_generator.py", SB])
    if cmd == "audio":
        return run([py, "audio_engine.py", SB])
    if cmd == "teaser":
        return run([py, "teaser_generator.py", SB, os.environ.get("ANSRE_TEASER_DURATION", "60")])
    if cmd == "publish":
        return run([py, "publisher.py", SB] + rest)
    if cmd == "usage":
        return run([py, "llm_provider.py", "--usage"])
    if cmd == "selftest":
        return run([py, "llm_provider.py", "--selftest"])
    if cmd == "local":
        return run([py, "llm_provider.py", "--local-check"])
    if cmd == "pipeline":
        need_gem_or_exit()
        for step in (["scout.py", "--source", "all", "--limit", "3", "--outdir", SB],
                     ["agent_analyzer.py", SB], ["agent_writer.py", SB],
                     ["cover_generator.py", SB], ["audio_engine.py", SB],
                     ["teaser_generator.py", SB, "60"]):
            print(f"\n=== {step[0]} ===")
            if run([py] + step) != 0:
                print(f"{BAD} หยุดที่ {step[0]}")
                return 1
        print(f"\n{OK} pipeline เสร็จครบ")
        return 0

    print(f"ไม่รู้จักคำสั่ง '{cmd}'. ดู:  ./ansre help")
    return 1


if __name__ == "__main__":
    sys.exit(main())
