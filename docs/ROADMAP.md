# 🗺️ ANSRE Roadmap — ระบบผลิตคอนเทนต์อัตโนมัติต่อเนื่อง

แนวคิดหลัก: เปลี่ยนจาก "CLI สั่งทีละ stage ด้วยมือ" → "worker daemon ขับเคลื่อนด้วยสถานะ + scheduler"
และย้ายงาน LLM ปริมาณมากไปรันบน **Mac mini ที่บ้าน** (ฟรี) เก็บ Gemini ไว้เฉพาะงานคุณภาพคอขาด

---

## ✅ เสร็จแล้ว (verified live)

### Phase 0 — รันได้จริง
- `.venv` บน **Python 3.13.7** (requirements pin ไว้สำหรับ 3.13 — `audioop-lts` ต้อง ≥3.13)
- ติดตั้ง requirements ครบ · ทดสอบ scout→analyze ได้ผลจริง (สร้าง Thai title + market score)

### Local-LLM service layer (เป้าหมายหลักของผู้ใช้)
- **`llm_provider.py`** — abstraction กลาง route LLM ไป Gemini/local ตาม "role" + auto-fallback
- โหมด **hybrid**: `writer`+`enhancer` → Gemini Pro, อีก ~10 roles → local (Mac mini) ฟรี
- **`MACMINI_SETUP.md`** — คู่มือตั้ง Ollama เป็น launchd service + โมเดลไทย (Typhoon/Qwen2.5) + Tailscale
- migrate ครบทุก LLM caller: `agent_analyzer`, `agent_writer`, `agent_refiner`, `run_iteration_loop`,
  `run_novels_complete`, `write_*.py` (×5), `cover_generator` (prompt), `app.py` (brainstorm)
  — เหลือเฉพาะ Imagen ใน `cover_generator` ที่ต้องใช้ Gemini (image gen)

### Phase 1-2 — รันต่อเนื่อง
- **`orchestrator.py`** — สแกน SecondBrain ดันทุกงานไปข้างหน้าเอง; backpressure scout, lockfile,
  logging, `--once`/`--loop`/`--dry-run`
- **`deploy/com.ansre.worker.plist`** — launchd ยิง orchestrator ทุก 20 นาที

### Phase 3 — คุมต้นทุน
- token/cost tracking ลง `SecondBrain/llm_usage.jsonl` · `python llm_provider.py --usage`
- `ANSRE_DAILY_USD_CAP` — เกินเพดานวันนี้ reroute Gemini → local อัตโนมัติ (ทดสอบแล้ว)

---

### Phase 4 — Auto-Publishing ✅ (โครงสร้างพร้อม — เหลือใส่ credential)
- **`publisher.py`** — adapter ครบ 3 แพลตฟอร์ม, ledger กันโพสต์ซ้ำ, ข้ามเองถ้าไม่มี creds
  - **YouTube Shorts** — อัปจริงผ่าน YouTube Data API v3 (googleapiclient ติดตั้งแล้ว) ใช้ token.json
  - **TikTok** — อัปจริงผ่าน Content Posting API ใช้ access token
  - **นิยาย Dek-D/Fictionlog** — ไม่มี API → แพ็กไฟล์เข้าคิว `Publish_Queue/` ให้โพสต์เอง
- ต่อ **publish stage** เข้า `orchestrator.py` แล้ว (รันให้เองเมื่อเปิด `PUBLISH_*`)
- **`PUBLISHING.md`** — คู่มือตั้ง credential ทั้ง 3 แพลตฟอร์ม
- **เหลือทำ:** ผู้ใช้ใส่ credential (OAuth/token) + ทดสอบอัปจริง 1 ตัว; publish scheduler ตาม prime-time (ตอนนี้อัปทันทีที่ teaser เสร็จ)

---

## ⏭️ ยังไม่ทำ

### Phase 5 — Quality Feedback Loop
- ดึง engagement (วิว/ไลก์/อ่านจบ) กลับมา feed `agent_refiner.py` (ลูปให้คะแนนมีอยู่แล้ว)
- ต้องเข้าถึง analytics API ของแพลตฟอร์มที่เลือกใน Phase 4 ก่อน
- A/B teaser/ปก/ชื่อเรื่อง · เลือกแนวที่เวิร์กจากผลจริง

> **Phase 4-5 ติดที่ credential + การเลือกแพลตฟอร์ม** ไม่ใช่เรื่องโค้ด — เปิดประเด็นให้ตัดสินใจก่อน

---

## วิธีรันต่อเนื่องตอนนี้ (Phase 0-3 พร้อมใช้)
```bash
# 1) ตั้ง Mac mini ตาม MACMINI_SETUP.md (Ollama service)
# 2) .env: LLM_BACKEND=hybrid + LOCAL_LLM_BASE_URL=...
.venv/bin/python llm_provider.py --selftest        # ต้องเขียวทั้ง local + gemini
# 3) ติดตั้ง worker ให้ผลิตเองทั้งวัน
cp deploy/com.ansre.worker.plist ~/Library/LaunchAgents/   # แก้ <REPO_PATH> ก่อน
launchctl load -w ~/Library/LaunchAgents/com.ansre.worker.plist
# ดู usage/cost: .venv/bin/python llm_provider.py --usage
```
