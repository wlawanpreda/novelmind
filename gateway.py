"""
ANSRE Gateway — HTTP service หน้าเดียวสำหรับ LLM + Image
=======================================================
ห่อ llm_provider + image_provider เดิมให้ client ภาษาอะไรก็เรียกได้ผ่าน HTTP
รวม คีย์/ledger/routing/คิว/coordination ไว้ที่เดียว (ดู docs/SERVICE_ARCHITECTURE.md)

  - LLM   = sync (เร็ว)        POST /v1/llm/generate          {prompt, role, system, is_json, stream}
  - Image = async job (ยาว)    POST /v1/image/generate        {prompt, aspect_ratio, backend}
                               GET  /v1/jobs/{job_id}
                               GET  /v1/image/result/{job_id}
  - คิว in-process + SQLite + HEAVY_LOCK (กัน LLM+SDXL โหลดชนกัน บนเครื่อง RAM ตึง)

รัน (บน Mac mini หรือเครื่องที่เข้าถึง Ollama+ComfyUI ได้):
    pip install fastapi uvicorn
    ANSRE_GATEWAY_TOKEN=secret uvicorn gateway:app --host 0.0.0.0 --port 9000
หรือใช้ macmini_gateway_setup.sh ตั้งเป็น launchd service

ENV:
    ANSRE_GATEWAY_TOKEN          คีย์ auth (ว่าง = ไม่เช็ค, ใช้เฉพาะหลัง Tailscale)
    ANSRE_GATEWAY_WORKERS        จำนวน worker คิว image (default 1 = serialize งานหนัก)
    ANSRE_FREE_LLM_BEFORE_IMAGE  1=ปลด Ollama ก่อนเรนเดอร์ (คืน RAM), 0=ไม่ปลด (default 1)
    ANSRE_JOB_DIR                ที่เก็บ job db + ไฟล์ผล (default: tempdir)
    ANSRE_GATEWAY_CORS           "*" หรือ origin คั่นด้วย , (default ปิด)
"""
from __future__ import annotations

import os
import json
import time
import uuid
import asyncio
import sqlite3
import tempfile
import urllib.request
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

# กัน recursion: บอก provider ว่า "นี่คือ gateway เอง" ก่อน import (provider อ่าน env ตอน import)
os.environ["ANSRE_GATEWAY_INTERNAL"] = "1"
import llm_provider
import image_provider

TOKEN = os.environ.get("ANSRE_GATEWAY_TOKEN", "")
WORKERS = max(1, int(os.environ.get("ANSRE_GATEWAY_WORKERS", "1")))
FREE_LLM_BEFORE_IMAGE = os.environ.get("ANSRE_FREE_LLM_BEFORE_IMAGE", "1") == "1"
JOB_DIR = os.environ.get("ANSRE_JOB_DIR") or os.path.join(tempfile.gettempdir(), "ansre_gateway")
DB = os.path.join(JOB_DIR, "jobs.sqlite")
OLLAMA_ROOT = os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
if OLLAMA_ROOT.endswith("/v1"):
    OLLAMA_ROOT = OLLAMA_ROOT[:-3]

os.makedirs(JOB_DIR, exist_ok=True)

# งานหนัก (image) ถือ lock นี้ → ทำทีละชิ้น ไม่ทับ LLM → เครื่องไม่ swap
HEAVY_LOCK = asyncio.Lock()
JOB_QUEUE: "asyncio.Queue[str]" = asyncio.Queue()


# ── SQLite job store ─────────────────────────────────────────────────────────
def _db():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("""CREATE TABLE IF NOT EXISTS jobs(
        id TEXT PRIMARY KEY, status TEXT, kind TEXT, params TEXT,
        result_path TEXT, error TEXT, created REAL, updated REAL)""")
    return c

def _job_set(job_id, **f):
    f["updated"] = time.time()
    cols = ",".join(f"{k}=?" for k in f)
    with _db() as c:
        c.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*f.values(), job_id))

def _job_get(job_id):
    with _db() as c:
        r = c.execute(
            "SELECT id,status,kind,result_path,error,created,updated FROM jobs WHERE id=?",
            (job_id,)).fetchone()
    if not r:
        return None
    return {"job_id": r[0], "status": r[1], "kind": r[2], "result_path": r[3],
            "error": r[4], "created": r[5], "updated": r[6]}


# ── ปลด Ollama ออกจาก RAM ก่อนเรนเดอร์ (คืน ~9.5GB) ──────────────────────────
def _free_ollama():
    model = os.environ.get("LOCAL_LLM_MODEL", "")
    if not (FREE_LLM_BEFORE_IMAGE and model):
        return
    try:
        req = urllib.request.Request(
            f"{OLLAMA_ROOT}/api/generate",
            data=json.dumps({"model": model, "keep_alive": 0, "prompt": ""}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass


# ── worker: หยิบงานทีละชิ้น ทำใต้ HEAVY_LOCK ─────────────────────────────────
def _run_image_job(job_id):
    job = _job_get(job_id)
    params = json.loads(_db().execute(
        "SELECT params FROM jobs WHERE id=?", (job_id,)).fetchone()[0]) if job else {}
    out = os.path.join(JOB_DIR, f"{job_id}.png")
    _free_ollama()
    ok = image_provider.generate_image(
        params["prompt"], out,
        aspect_ratio=params.get("aspect_ratio", "1:1"),
        backend=params.get("backend"))
    # image_provider อาจเซฟเป็น .png ถ้าไม่มี Pillow แปลง .jpg
    if not ok:
        raise RuntimeError("image generation failed (ดู log gateway/ComfyUI)")
    final = out if os.path.exists(out) else os.path.splitext(out)[0] + ".png"
    _job_set(job_id, result_path=final)

async def _worker(idx: int):
    while True:
        job_id = await JOB_QUEUE.get()
        try:
            if not _job_get(job_id):
                continue
            async with HEAVY_LOCK:
                _job_set(job_id, status="running")
                await asyncio.to_thread(_run_image_job, job_id)
            _job_set(job_id, status="done")
        except Exception as e:
            _job_set(job_id, status="error", error=str(e)[:500])
        finally:
            JOB_QUEUE.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _db().close()
    tasks = [asyncio.create_task(_worker(i)) for i in range(WORKERS)]
    yield
    for t in tasks:
        t.cancel()

app = FastAPI(title="ANSRE Gateway", version="1.0", lifespan=lifespan)

_cors = os.environ.get("ANSRE_GATEWAY_CORS", "").strip()
if _cors:
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if _cors == "*" else [o.strip() for o in _cors.split(",")],
        allow_methods=["*"], allow_headers=["*"])


def _auth(tok: str | None):
    if TOKEN and tok != TOKEN:
        raise HTTPException(401, "invalid token")


# ── LLM ──────────────────────────────────────────────────────────────────────
class LLMReq(BaseModel):
    prompt: str
    role: str = "default"
    system: str | None = None
    is_json: bool = False
    stream: bool = False

@app.post("/v1/llm/generate")
async def llm_generate(req: LLMReq, x_ansre_token: str | None = Header(None)):
    _auth(x_ansre_token)
    text = await asyncio.to_thread(
        llm_provider.generate, req.prompt, req.role, req.is_json, None, req.system)
    if req.stream:
        async def gen():
            yield f"data: {json.dumps({'text': text})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")
    return {"text": text}


# ── Image (async job) ────────────────────────────────────────────────────────
class ImageReq(BaseModel):
    prompt: str
    aspect_ratio: str = "1:1"
    backend: str | None = None
    client_job_id: str | None = None

@app.post("/v1/image/generate")
async def image_generate(req: ImageReq, x_ansre_token: str | None = Header(None)):
    _auth(x_ansre_token)
    job_id = req.client_job_id or uuid.uuid4().hex
    with _db() as c:
        if c.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone():
            return {"job_id": job_id, "status": "duplicate",
                    "result_url": f"/v1/image/result/{job_id}"}
        now = time.time()
        c.execute("INSERT INTO jobs(id,status,kind,params,created,updated) VALUES(?,?,?,?,?,?)",
                  (job_id, "queued", "image", req.model_dump_json(), now, now))
    await JOB_QUEUE.put(job_id)
    return {"job_id": job_id, "status": "queued", "queue_size": JOB_QUEUE.qsize(),
            "result_url": f"/v1/image/result/{job_id}"}

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
    if not job:
        raise HTTPException(404, "job not found")
    if job["status"] != "done":
        raise HTTPException(409, f"not ready (status={job['status']})")
    path = job["result_path"]
    media = "image/jpeg" if path and path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return FileResponse(path, media_type=media)


# ── Health ───────────────────────────────────────────────────────────────────
def _ollama_up() -> bool:
    try:
        urllib.request.urlopen(f"{OLLAMA_ROOT}/api/version", timeout=5).read()
        return True
    except Exception:
        return False

@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "llm_backend": llm_provider.LLM_BACKEND,
        "image_backend": image_provider.IMAGE_BACKEND,
        "ollama_up": _ollama_up(),
        "comfy_up": image_provider._comfy_ping(),
        "queue_size": JOB_QUEUE.qsize(),
        "rendering": HEAVY_LOCK.locked(),
        "workers": WORKERS,
    }
