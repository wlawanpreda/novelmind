"""
Hermetic E2E test สำหรับ gateway — stub backend (ไม่ยิง Ollama/ComfyUI/Imagen จริง)
พิสูจน์เส้นทาง: auth · LLM sync · image job (queue→worker→SQLite→result) · SDK fetch
รัน: python3 test_gateway_e2e.py
"""
import os, time, tempfile

os.environ["ANSRE_GATEWAY_TOKEN"] = "testtoken"
os.environ["ANSRE_FREE_LLM_BEFORE_IMAGE"] = "0"        # อย่าแตะ Ollama จริง
os.environ["ANSRE_JOB_DIR"] = tempfile.mkdtemp(prefix="ansre_test_")

import llm_provider, image_provider
# --- stub backends (ไม่มี network, ไม่มีค่าใช้จ่าย) ---
llm_provider.generate = lambda prompt, role="default", is_json=False, temperature=None, system=None, **k: f"STUB[{role}]:{prompt[:20]}"
_PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63f8cf00000000ffff03000001000001a0a0a0000000000049454e44ae426082")
def _stub_img(prompt, out, aspect_ratio="1:1", backend=None):
    with open(out, "wb") as f: f.write(_PNG)
    return True
image_provider.generate_image = _stub_img

import gateway
from fastapi.testclient import TestClient

H = {"X-ANSRE-Token": "testtoken"}
fails = []
def check(name, cond):
    print(("✅" if cond else "❌"), name);
    if not cond: fails.append(name)

with TestClient(gateway.app) as c:
    # 1) auth
    check("401 เมื่อไม่มี token", c.post("/v1/llm/generate", json={"prompt": "x"}).status_code == 401)
    # 2) LLM sync
    r = c.post("/v1/llm/generate", json={"prompt": "วิเคราะห์หน่อย", "role": "analyzer"}, headers=H)
    check("LLM sync คืน text", r.status_code == 200 and r.json()["text"].startswith("STUB[analyzer]"))
    # 3) health
    check("healthz ok", c.get("/healthz").json().get("ok") is True)
    # 4) image job: enqueue → poll → result
    job = c.post("/v1/image/generate", json={"prompt": "a temple", "aspect_ratio": "1:1"}, headers=H).json()
    check("image enqueue คืน job_id+queued", job.get("status") == "queued" and "job_id" in job)
    jid = job["job_id"]
    status = None
    for _ in range(50):
        status = c.get(f"/v1/jobs/{jid}", headers=H).json()["status"]
        if status in ("done", "error"): break
        time.sleep(0.2)
    check(f"image job ถึงสถานะ done (ได้ {status})", status == "done")
    res = c.get(f"/v1/image/result/{jid}", headers=H)
    check("ดึงรูปได้ + เป็น PNG", res.status_code == 200 and res.content[:8] == _PNG[:8])
    # 5) idempotency
    j2 = c.post("/v1/image/generate", json={"prompt": "x", "client_job_id": jid}, headers=H).json()
    check("idempotent (client_job_id ซ้ำ = duplicate)", j2.get("status") == "duplicate")

print("\n" + ("🎉 PASS ทั้งหมด" if not fails else f"💥 FAIL: {fails}"))
raise SystemExit(1 if fails else 0)
