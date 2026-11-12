"""
HTTP full-loop E2E — รัน gateway จริง (คนละ process) + stub backend → พิสูจน์ทั้งสาย:
  client image_provider.generate_image()  ──HTTP──▶  gateway :PORT  ──▶  (stub gen)  ──▶  ไฟล์กลับถึง client
  client llm_provider.generate()          ──HTTP──▶  gateway /v1/llm/generate
ไม่ยิง Ollama/ComfyUI/Imagen จริง (ศูนย์ค่าใช้จ่าย, ไม่แตะ Mac mini) แต่ผ่าน socket จริง
รัน: python3 test_gateway_http_e2e.py
"""
import os, sys, time, json, tempfile, subprocess, importlib, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT, TOKEN = "9079", "httpe2e"
JOB = tempfile.mkdtemp(prefix="ansre_http_")
PNG_HEX = ("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
           "0000000d49444154789c63f8cf00000000ffff03000001000001a0a0a000000000"
           "0049454e44ae426082")
PNG = bytes.fromhex(PNG_HEX)
BASE = f"http://127.0.0.1:{PORT}"

# --- server bootstrap: stub backends แล้ว serve gateway จริง ---
server_code = f'''
import os
os.environ["ANSRE_GATEWAY_TOKEN"] = {TOKEN!r}
os.environ["ANSRE_JOB_DIR"] = {JOB!r}
import image_provider, llm_provider
_PNG = bytes.fromhex({PNG_HEX!r})
def _img(prompt, out, aspect_ratio="1:1", backend=None):
    open(out, "wb").write(_PNG); return True
image_provider.generate_image = _img
llm_provider.generate = lambda prompt, role="default", is_json=False, temperature=None, system=None, **k: f"ECHO[{{role}}]"
import gateway, uvicorn
uvicorn.run(gateway.app, host="127.0.0.1", port={int(PORT)}, log_level="warning")
'''

srv = subprocess.Popen([sys.executable, "-c", server_code], cwd=ROOT)
fails = []
def check(name, cond):
    print(("✅" if cond else "❌"), name)
    if not cond: fails.append(name)

try:
    # รอ gateway ขึ้น
    up = False
    for _ in range(40):
        try:
            urllib.request.urlopen(BASE + "/healthz", timeout=2); up = True; break
        except Exception:
            time.sleep(0.5)
    check("gateway (process จริง) ขึ้นและตอบ /healthz", up)

    # --- เป็น "client": ตั้ง env แล้ว reload provider ให้ route ผ่าน gateway ---
    os.environ["ANSRE_GATEWAY_URL"] = BASE
    os.environ["ANSRE_GATEWAY_TOKEN"] = TOKEN
    os.environ.pop("ANSRE_GATEWAY_INTERNAL", None)
    ip = importlib.reload(importlib.import_module("image_provider"))
    lp = importlib.reload(importlib.import_module("llm_provider"))
    check("client provider เปิด gateway routing", ip._USE_GATEWAY and lp._USE_GATEWAY)

    # image: client เรียก generate_image → ผ่าน HTTP จริง → ได้ไฟล์กลับ
    out = os.path.join(JOB, "client_cover.png")
    ok = ip.generate_image("a thai temple", out, backend="local")
    got_png = os.path.exists(out) and open(out, "rb").read(8) == PNG[:8]
    check("image full-loop ผ่าน HTTP → ไฟล์ PNG ถึง client", ok and got_png)

    # llm: client เรียก generate → ผ่าน HTTP จริง
    txt = lp.generate("hi", role="analyzer")
    check("llm full-loop ผ่าน HTTP", txt.startswith("ECHO"))
finally:
    srv.terminate()
    try: srv.wait(timeout=5)
    except Exception: srv.kill()

print("\n" + ("🎉 HTTP full-loop PASS ทั้งหมด" if not fails else f"💥 FAIL: {fails}"))
raise SystemExit(1 if fails else 0)
