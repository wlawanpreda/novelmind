"""
ANSRE Gateway — CONCEPT (ข้อเสนอ, ยังไม่ wire เข้า pipeline)
============================================================
HTTP service ตัวเดียวบน Mac mini ที่ห่อ llm_provider + image_provider เดิม
เพื่อให้ client ภาษาอะไรก็เรียกได้ + รวมความลับ/ledger/routing/คิว ไว้ที่เดียว

ออกแบบตาม docs/SERVICE_ARCHITECTURE.md — Phase 1:
  - LLM = sync (เร็ว)              -> POST /v1/llm/generate
  - Image = async job (ยาว)        -> POST /v1/image/generate -> job_id -> GET /v1/jobs/{id}
  - คิว in-process (asyncio) + SQLite job store + HEAVY_LOCK (กัน LLM+SDXL โหลดชนกัน = ไม่ swap)
  - ศูนย์ infra ใหม่ (ไม่ต้องลง Redis/Kafka) — Phase 3 ค่อยสลับ enqueue เป็น Redis+Arq

รัน (บน Mac mini, ใน repo root เพื่อ import provider เดิมได้):
    pip install fastapi uvicorn
    ANSRE_GATEWAY_TOKEN=secret uvicorn docs.concept.gateway:app --host 0.0.0.0 --port 9000

หมายเหตุ: นี่คือ "โครง" ให้เห็นภาพ — ตัด error handling/persistence บางส่วนให้สั้น
"""
from __future__ import annotations

import os
import json
import asyncio
import sqlite3
import tempfile
import urllib.request
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

# ของเดิม — reuse routing/fallback/ledger ทั้งหมด ไม่เขียนใหม่
import llm_provider
import image_provider

TOKEN = os.environ.get("ANSRE_GATEWAY_TOKEN", "")          # auth ชั้นบนสุด (เก็บที่ gateway ที่เดียว)
OLLAMA_URL = os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1").replace("/v1", "")
FREE_LLM_BEFORE_IMAGE = os.environ.get("ANSRE_FREE_LLM_BEFORE_IMAGE", "1") == "1"
JOB_DIR = os.environ.get("ANSRE_JOB_DIR", tempfile.gettempdir())
DB = os.path.join(JOB_DIR, "ansre_jobs.sqlite")

# ── หัวใจกัน RAM ชน: งานหนัก (image) ถือ lock นี้ → ทำทีละงาน, ไม่ทับ LLM ─────────
HEAVY_LOCK = asyncio.Lock()
JOB_QUEUE: "asyncio.Queue[str]" = asyncio.Queue()


# ── SQLite job store (durable พอสำหรับ 1 เครื่อง) ─────────────────────────────
def _db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS jobs(
        id TEXT PRIMARY KEY, status TEXT, kind TEXT, params TEXT,
        result_path TEXT, error TEXT, created REAL)""")
    return c

def _job_set(job_id, **f):
    cols = ",".join(f"{k}=?" for k in f)
    with _db() as c:
        c.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*f.values(), job_id))

def _job_get(job_id):
    with _db() as c:
        r = c.execute("SELECT id,status,kind,result_path,error FROM jobs WHERE id=?",
                      (job_id,)).fetchone()
    if not r:
        return None
    return {"job_id": r[0], "status": r[1], "kind": r[2], "result_path": r[3], "error": r[4]}


# ── ปลด Ollama ออกจาก RAM ก่อนเรนเดอร์ (คืน ~9.5GB) ──────────────────────────
def _free_ollama():
    model = os.environ.get("LOCAL_LLM_MODEL", "")
    if not (FREE_LLM_BEFORE_IMAGE and model):
        return
    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=json.dumps({"model": model, "keep_alive": 0, "prompt": ""}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass  # ปลดไม่ได้ก็ปล่อยให้ ComfyUI จัดการ memory เอง


# ── worker: หยิบงานจากคิวทีละชิ้น ทำใต้ HEAVY_LOCK ────────────────────────────
async def _worker():
    while True:
        job_id = await JOB_QUEUE.get()
        job = _job_get(job_id)
        if not job:
            continue
        try:
            async with HEAVY_LOCK:                       # ← serialize งานหนัก
                _job_set(job_id, status="running")
                await asyncio.to_thread(_run_image_job, job_id)
            _job_set(job_id, status="done")
        except Exception as e:
            _job_set(job_id, status="error", error=str(e)[:500])
        finally:
            JOB_QUEUE.task_done()

def _run_image_job(job_id):
    with _db() as c:
        params = json.loads(c.execute("SELECT params FROM jobs WHERE id=?", (job_id,)).fetchone()[0])
    out = os.path.join(JOB_DIR, f"{job_id}.png")
    _free_ollama()                                       # คืน RAM ก่อนเรนเดอร์
    ok = image_provider.generate_image(
        params["prompt"], out,
        aspect_ratio=params.get("aspect_ratio", "1:1"),
        backend=params.get("backend"))
    if not ok:
        raise RuntimeError("image generation failed (ดู log gateway/ComfyUI)")
    _job_set(job_id, result_path=out)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _db().close()
    task = asyncio.create_task(_worker())                # 1 worker (อยากได้ N ก็ loop สร้าง)
    yield
    task.cancel()

app = FastAPI(title="ANSRE Gateway", lifespan=lifespan)


def _auth(tok: str | None):
    if TOKEN and tok != TOKEN:
        raise HTTPException(401, "invalid token")


# ── LLM: sync (มี stream option) ─────────────────────────────────────────────
class LLMReq(BaseModel):
    prompt: str
    role: str = "default"
    system: str | None = None
    is_json: bool = False
    stream: bool = False

@app.post("/v1/llm/generate")
async def llm_generate(req: LLMReq, x_ansre_token: str | None = Header(None)):
    _auth(x_ansre_token)
    if req.stream:
        # SSE — ส่งทีละ chunk (provider ปัจจุบันคืนทั้งก้อน; จุดนี้ขยายเป็น token stream ได้)
        async def gen():
            text = await asyncio.to_thread(
                llm_provider.generate, req.prompt, req.role, req.is_json, None, req.system)
            yield f"data: {json.dumps({'text': text})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")
    text = await asyncio.to_thread(
        llm_provider.generate, req.prompt, req.role, req.is_json, None, req.system)
    return {"text": text}


# ── Image: async job ─────────────────────────────────────────────────────────
class ImageReq(BaseModel):
    prompt: str
    aspect_ratio: str = "1:1"
    backend: str | None = None          # local | gemini | hybrid (default = .env)
    client_job_id: str | None = None    # idempotency

@app.post("/v1/image/generate")
async def image_generate(req: ImageReq, x_ansre_token: str | None = Header(None)):
    _auth(x_ansre_token)
    import uuid, time
    job_id = req.client_job_id or uuid.uuid4().hex
    with _db() as c:
        if c.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone():
            return {"job_id": job_id, "status": "duplicate"}   # กันยิงซ้ำ
        c.execute("INSERT INTO jobs(id,status,kind,params,created) VALUES(?,?,?,?,?)",
                  (job_id, "queued", "image", req.model_dump_json(), time.time()))
    await JOB_QUEUE.put(job_id)
    return {"job_id": job_id, "status": "queued",
            "queue_size": JOB_QUEUE.qsize(), "result_url": f"/v1/image/result/{job_id}"}

@app.get("/v1/jobs/{job_id}")
async def job_status(job_id: str, x_ansre_token: str | None = Header(None)):
    _auth(x_ansre_token)
    job = _job_get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    job.pop("result_path", None)
    return job

@app.get("/v1/image/result/{job_id}")
async def image_result(job_id: str, x_ansre_token: str | None = Header(None)):
    _auth(x_ansre_token)
    job = _job_get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(409, f"not ready (status={job and job['status']})")
    return FileResponse(job["result_path"], media_type="image/png")


@app.get("/healthz")
async def healthz():
    return {
        "llm": llm_provider._local_check() if hasattr(llm_provider, "_local_check") else "?",
        "image_comfy": image_provider._comfy_ping(),
        "queue": JOB_QUEUE.qsize(),
        "rendering": HEAVY_LOCK.locked(),
    }
