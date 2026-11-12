"""
Gateway hardening test — ครอบการแก้จาก code review (8 ข้อ):
  #5 LLM ไม่ทับ image render (HEAVY_LOCK ร่วมกัน → งานหนักวิ่งทีละชิ้น)
  #7 temperature ส่งผ่าน gateway ถึง provider
  #1 path traversal: client_job_id ที่มี ../ ถูกปฏิเสธ 400
  single-flight idempotency: ยิง client_job_id ซ้ำ → ไม่สร้าง/รันซ้ำ (INSERT OR IGNORE)
  #6 คิวเต็ม → 429
  #3 durability: _requeue_pending คืนงานค้างเข้าคิว
hermetic (stub backend), ศูนย์ค่าใช้จ่าย. รัน: python3 test_gateway_hardening.py
"""
import os, time, tempfile

os.environ["ANSRE_GATEWAY_TOKEN"] = "t"
os.environ["ANSRE_FREE_LLM_BEFORE_IMAGE"] = "0"
os.environ["ANSRE_JOB_DIR"] = tempfile.mkdtemp(prefix="ansre_hard_")

import image_provider, llm_provider
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
                    "0000000d49444154789c63f8cf00000000ffff03000001000001a0a0a000000000"
                    "0049454e44ae426082")
EV = {}
def stub_img(prompt, out, aspect_ratio="1:1", backend=None):
    EV["render_start"] = time.perf_counter()
    time.sleep(0.4)                       # จำลองเรนเดอร์ (ถือ HEAVY_LOCK อยู่)
    EV["render_end"] = time.perf_counter()
    with open(out, "wb") as f: f.write(PNG)
    return True
def stub_llm(prompt, role="default", is_json=False, temperature=None, system=None, **k):
    EV["llm_run"] = time.perf_counter()
    EV["llm_temp"] = temperature
    return "OK"
image_provider.generate_image = stub_img
llm_provider.generate = stub_llm

import gateway
from fastapi.testclient import TestClient

H = {"X-ANSRE-Token": "t"}
fails = []
def check(name, cond):
    print(("✅" if cond else "❌"), name)
    if not cond: fails.append(name)

with TestClient(gateway.app) as c:
    # #5 single-flight: LLM ต้องรอจน render เสร็จ (ไม่ทับกัน)
    c.post("/v1/image/generate", json={"prompt": "x"}, headers=H)
    time.sleep(0.15)                      # ให้ worker คว้า lock + เริ่ม render ก่อน
    c.post("/v1/llm/generate", json={"prompt": "hi", "role": "analyzer", "temperature": 0.5}, headers=H)
    check("LLM ไม่ทับ image render (รันหลัง render เสร็จ)",
          "render_end" in EV and "llm_run" in EV and EV["render_end"] <= EV["llm_run"])
    check("#7 temperature ส่งผ่าน gateway ถึง provider", EV.get("llm_temp") == 0.5)

    # #1 path traversal
    r = c.post("/v1/image/generate", json={"prompt": "x", "client_job_id": "../../evil"}, headers=H)
    check("#1 path traversal client_job_id → 400", r.status_code == 400)

    # single-flight idempotency: ยิงซ้ำ id เดิม
    j = c.post("/v1/image/generate", json={"prompt": "x", "client_job_id": "job_abc"}, headers=H).json()
    j2 = c.post("/v1/image/generate", json={"prompt": "x", "client_job_id": "job_abc"}, headers=H).json()
    check("ยิงซ้ำ client_job_id → duplicate (ไม่สร้างซ้ำ)",
          j["status"] == "queued" and j2["status"] == "duplicate")

    # #6 คิวเต็ม → 429
    saved = gateway.MAX_QUEUE
    gateway.MAX_QUEUE = 0
    r = c.post("/v1/image/generate", json={"prompt": "x", "client_job_id": "qfull"}, headers=H)
    check("#6 คิวเต็ม → 429", r.status_code == 429)
    gateway.MAX_QUEUE = saved

# #3 durability: _requeue_pending คืนงานค้าง running→queued
now = time.time()
with gateway._db() as conn:
    conn.execute("DELETE FROM jobs")
    conn.execute("INSERT INTO jobs(id,status,kind,params,created,updated) VALUES('r1','running','image','{}',?,?)", (now, now))
    conn.execute("INSERT INTO jobs(id,status,kind,params,created,updated) VALUES('q1','queued','image','{}',?,?)", (now, now))
n = gateway._requeue_pending()
with gateway._db() as conn:
    running_left = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='running'").fetchone()[0]
check("#3 durability: re-enqueue งานค้าง (running→queued, คืน 2)", n == 2 and running_left == 0)

print("\n" + ("🎉 PASS ทั้งหมด" if not fails else f"💥 FAIL: {fails}"))
raise SystemExit(1 if fails else 0)
