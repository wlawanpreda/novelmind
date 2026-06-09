# 🏗️ ข้อเสนอ: แยก LLM + Image เป็น Service (Gateway + Job Queue)

> สถานะ: **ข้อเสนอ/แนะนำ — ยังไม่ลงมือ** (concept code อยู่ใน `docs/concept/`)
> ตอบคำถาม: "ทำเป็น message queue / แยกเป็น service เพื่อ decouple + ให้ client อื่นเรียกง่าย ดีไหม?"

---

## 0. TL;DR — แนะนำอะไร (อ่านอันเดียวพอ)

**ได้ และคุ้ม** แต่ขอปรับ framing ให้ตรงปัญหา:

1. **message queue ไม่ได้เพิ่ม RAM** — มันช่วย *decouple + คุมคิว + ให้หลาย client เรียก* ไม่ได้แก้ปัญหา
   Mac mini swap ที่เจอ ตัวที่แก้ efficiency จริงบนเครื่องเดียวคือ **"ห้ามโหลดโมเดลหนัก 2 ตัวพร้อมกัน"**
   (serialize LLM↔image ด้วย lock/คิว single-worker) — ซึ่ง pattern queue ให้ผลข้อนี้มาฟรีอยู่แล้ว
2. **แยกเป็น service = คุ้มมาก** เพราะตอนนี้ provider ถูก `import` ตรงใน 9 ไฟล์ → มีแต่ Python ANSRE เรียกได้
   ทำเป็น **HTTP gateway ตัวเดียว** บน Mac mini แล้ว client ภาษาอะไรก็เรียกได้ + รวมความลับ/ledger/routing ไว้ที่เดียว
3. **อย่าเพิ่งใช้ Kafka/RabbitMQ/Celery** — over-engineer สำหรับ 1 เครื่อง เริ่มที่ **FastAPI + คิว in-process + SQLite**
   (ศูนย์ infra ใหม่) แล้วค่อยอัปเป็น **Redis + Arq** เมื่อต้องการ durability/หลาย worker จริงๆ

### สถาปัตยกรรมที่แนะนำ (เป้าหมาย)
```
                         ┌─────────────────────────── Mac mini ───────────────────────────┐
  ANSRE (MacBook) ─┐     │  ┌──────────────── ANSRE Gateway (FastAPI :9000) ─────────────┐ │
  client อื่น (JS) ─┼─Tailscale→ │  /v1/llm/generate   (sync + stream)  →  llm_provider     │ │
  curl / n8n ──────┘     │  │  /v1/image/generate (async job → job_id) →  image_provider   │ │
                         │  │  /v1/jobs/{id}      (poll สถานะ/ผล)                          │ │
                         │  │  ───────────────────────────────────────────────────────── │ │
                         │  │  Job queue (1 worker) + HEAVY_LOCK: image มาคิว→ปลด Ollama→  │ │
                         │  │  เรนเดอร์ ComfyUI→คืนผล (กันโหลด LLM+SDXL ชนกัน = ไม่ swap)   │ │
                         │  └────────────┬───────────────────────────┬───────────────────┘ │
                         │      Ollama :11434 (LLM)          ComfyUI :8188 (SDXL)           │
                         └─────────────────────────────────────────────────────────────────┘
```
ของเดิม (`llm_provider.py` / `image_provider.py`) **ไม่ถูกทิ้ง** — gateway เรียกมันต่อ (routing/fallback/ledger
อยู่ครบ) ANSRE แค่เปลี่ยนจาก `import` → เรียกผ่าน **client SDK บางๆ** (`docs/concept/ansre_client.py`)

---

## 1. ปัญหาปัจจุบัน (ทำไมต้องแยก)

| ปัญหา | ตอนนี้ | ผลเสีย |
|------|--------|--------|
| Coupling | provider ถูก `import` ใน 9 ไฟล์ | client ที่ไม่ใช่ Python เรียกไม่ได้ · อัปเกรด provider กระทบทุกไฟล์ |
| ความลับกระจาย | `GEMINI_API_KEY` อยู่ใน `.env` ทุกเครื่องที่รัน | คีย์หลุดง่าย · เพิ่ม client = ก๊อปคีย์ไปอีกที่ |
| RAM ชนกัน | LLM(9.5GB)+SDXL(8-10GB) โหลดพร้อมกันบน 24GB | swap → เรนเดอร์คลาน (ที่เพิ่งเจอ) |
| ไม่มีคิว | image ยิงตรง ComfyUI งานยาว 1-3 นาที | ยิงพร้อมกันหลายงาน = แย่งกัน · ไม่มี retry/priority |
| สังเกตยาก | สถานะงานกระจายในแต่ละ process | ดูไม่ได้ว่ามีงานค้างกี่ชิ้น/พังตรงไหน |

---

## 2. ตัดสินใจเลือกเทคให้พอดี scale (อย่า over-engineer)

| ตัวเลือก | เหมาะเมื่อ | ความเห็น |
|---------|----------|---------|
| **FastAPI + asyncio queue + SQLite** | 1 เครื่อง, volume ต่ำ, อยากเริ่มไว | ✅ **เริ่มที่นี่** — ศูนย์ infra ใหม่ ได้ครบ 80% |
| **Redis + Arq (หรือ RQ)** | ต้องการ durable job, retry/backoff, หลาย worker, แยก worker คนละเครื่อง | ✅ **อัปเกรดเป้าหมาย** — `brew install redis` ตัวเดียว เปลี่ยนโค้ดนิดเดียว |
| **NATS / NATS JetStream** | หลาย service คุยกันแบบ pub/sub + request-reply | ⚪ ทางเลือกถ้าโตเป็น service mesh — เพิ่ม concept ใหม่ |
| **RabbitMQ + Celery** | งาน enterprise, routing ซับซ้อน, ทีมใหญ่ | 🔴 หนักเกินสำหรับตอนนี้ |
| **Kafka** | event streaming, log replay, throughput สูงมาก | 🔴 ผิดเครื่องมือสำหรับ task queue |

> หลักการ: **เริ่มเล็กสุดที่ยังตอบโจทย์** แล้วอัปเฉพาะเมื่อชน limit จริง — โครง API เหมือนกันหมด เปลี่ยน backend คิวทีหลังได้

---

## 3. API ที่จะ expose (ออกแบบให้ client เรียกง่าย)

**LLM = เร็ว → sync (มี stream ได้)** · **Image = ยาว → async job (job_id → poll/ผล)**

| Method | Path | ใช้ทำ | คืน |
|--------|------|------|-----|
| POST | `/v1/llm/generate` | ข้อความ (role routing เดิม) | `{text}` หรือ SSE stream |
| POST | `/v1/image/generate` | สั่งสร้างรูป (เข้าคิว) | `{job_id, status:"queued"}` |
| GET | `/v1/jobs/{job_id}` | เช็คสถานะ | `{status, result_url?, error?}` |
| GET | `/v1/image/result/{job_id}` | ดึงไฟล์รูป | image bytes |
| GET | `/healthz` | liveness + backend พร้อมไหม | `{llm, image}` |

- **Auth:** header `X-ANSRE-Token` (กันแม้อยู่หลัง Tailscale แล้ว — defense in depth) คีย์เก็บที่ gateway ที่เดียว
- **Idempotency:** ส่ง `client_job_id` ได้ กันยิงซ้ำ
- **Webhook (option):** ใส่ `callback_url` → งานเสร็จ gateway ยิงกลับ (ไม่ต้อง poll)

---

## 4. หัวใจที่แก้ปัญหา RAM — Resource Coordination

```
image job เข้าคิว → worker หยิบ (ทีละ 1) → acquire HEAVY_LOCK
   → (option) ปลด Ollama: POST /api/generate keep_alive=0   ← คืน RAM 9.5GB
   → เรนเดอร์ ComfyUI จนเสร็จ
   → release HEAVY_LOCK → Ollama โหลดกลับเองตอนมีงาน LLM ถัดไป
```
- LLM request = เร็ว ไม่ต้องถือ lock (หรือถือแบบ shared) → งานเขียนยังลื่น
- ผล: เครื่อง **ไม่มีวันโหลด LLM+SDXL หนักพร้อมกัน** → เลิก swap → เรนเดอร์กลับมาเร็ว
- นี่คือ "efficiency" จริงที่ถามหา — ได้จาก single-worker + lock ไม่ใช่จากตัว queue เอง

---

## 5. Migration path (ไม่ rewrite ทีเดียว — ความเสี่ยงต่ำ)

| Phase | ทำอะไร | ความเสี่ยง | ของเดิมพังไหม |
|-------|--------|-----------|--------------|
| **0** | คงไว้ — provider import ตรง | - | - |
| **1 ✅ ทำแล้ว** | สร้าง gateway (FastAPI) ครอบ provider เดิม + คิว in-proc + SQLite + HEAVY_LOCK + `ansre_client.py` SDK + `macmini_gateway_setup.sh` | ต่ำ | ไม่ — เพิ่ม service ใหม่ ของเดิมยังใช้ได้ |
| **2 ✅ ทำแล้ว** | ใส่ gateway-routing **ใน provider เอง** (`llm_provider`/`image_provider`): ถ้าตั้ง `ANSRE_GATEWAY_URL` → route ผ่าน gateway, ล่ม → fallback ทำเองในเครื่อง · กัน recursion ด้วย `ANSRE_GATEWAY_INTERNAL=1` | ต่ำมาก | ไม่ — **ไม่แก้ 9 ไฟล์ pipeline เลย** ทุกไฟล์ได้ gateway ฟรีเมื่อเปิด env (ปิด=พฤติกรรมเดิมเป๊ะ) |
| **3** | ย้ายคิวเป็น Redis+Arq *เมื่อ* ต้องการ durability/หลาย worker | กลาง | โครง API เดิม เปลี่ยนแค่ชั้น enqueue |
| **4 (option)** | webhook, priority queue, หลาย worker/เครื่อง, dashboard ผูก `/v1/jobs` | - | - |

### Phase 2 ทำไมเลือก "routing ใน provider" แทนแก้ทีละไฟล์
ทั้ง 9 ไฟล์เรียก `llm_provider.generate()` / `image_provider.generate_image()` อยู่แล้ว →
ใส่ทางแยกใน 2 ฟังก์ชันนี้จุดเดียว = ครอบทุกไฟล์ทันที, churn = 0, reversible ด้วย env ตัวเดียว

**วิธีเปิดใช้** (หลัง deploy gateway บน Mac mini ด้วย `macmini_gateway_setup.sh`):
```bash
# ใส่ใน .env ฝั่ง client — เท่านี้ทุก stage วิ่งผ่าน gateway อัตโนมัติ (ล่ม→fallback เอง)
ANSRE_GATEWAY_URL=http://pj-mac-mini.tail9bbbd4.ts.net:9000
ANSRE_GATEWAY_TOKEN=<token ที่ setup สุ่มให้>
```
ไม่ตั้ง = ทำงานเหมือนเดิม (import ตรง) · กลับค่าเดิม = ลบ 2 บรรทัดนี้

---

## 6. Concept code (ตัวอย่างให้ client เรียกง่าย)

อยู่ใน [`docs/concept/`](concept/):
- [`gateway.py`](concept/gateway.py) — โครง FastAPI gateway (LLM sync + image async job + HEAVY_LOCK)
- [`ansre_client.py`](concept/ansre_client.py) — Python SDK บางๆ: `cli.llm(...)` / `cli.image(...)`
- [`examples.md`](concept/examples.md) — เรียกด้วย curl / JS(fetch) / Python ใน 3 บรรทัด

ตัวอย่างฝั่ง client (ปลายทางที่อยากให้เป็น):
```python
from ansre_client import Ansre
cli = Ansre("http://pj-mac-mini.tail9bbbd4.ts.net:9000", token="...")

text = cli.llm("วิเคราะห์จุดขายนิยายย้อนเวลา", role="analyzer")     # sync
cli.image("a serene thai temple at dawn", "/tmp/cover.jpg")          # รอจนเสร็จ (poll ให้)
job = cli.image("...", wait=False)                                   # async → job["job_id"]
```

---

## 7. สรุปคำแนะนำ (ทำตามลำดับนี้)

1. ✅ **Phase 1 ทำแล้ว** — gateway + คิว + SQLite + HEAVY_LOCK + SDK + setup script (test ผ่าน)
2. ✅ **Phase 2 ทำแล้ว** — gateway-routing ใน provider + fallback + กัน recursion (test ผ่าน, ไม่แตะ pipeline)
3. ⏳ **Deploy** — รัน `macmini_gateway_setup.sh` บน Mac mini แล้วตั้ง `ANSRE_GATEWAY_URL` ฝั่ง client
4. ⏳ **อย่าเพิ่ง** Redis/Kafka/Celery — อัปเป็น Redis+Arq เฉพาะตอนต้องการ durable/หลาย worker จริง
5. ⏳ webhook/priority/หลายเครื่อง = อนาคต

> เป้าใหญ่: Mac mini = "AI service node" ตัวเดียวที่ทุก client ในบ้าน/ทีมยิงเข้ามาได้ ปลอดภัย คุมคิว
> ไม่ swap และเพิ่ม client ใหม่ = แค่แจก token ไม่ต้องก๊อปคีย์/โค้ด
