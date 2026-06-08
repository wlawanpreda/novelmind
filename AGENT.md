# 🤖 AGENT.md — คู่มือสถาปัตยกรรม & กติกาโปรเจกต์ ANSRE

> เอกสารกลาง (single source of truth) สำหรับคน + AI ที่เข้ามาทำงานกับโปรเจกต์นี้
> อ่านไฟล์นี้ก่อนแก้โค้ดเสมอ

---

## 1. ANSRE คืออะไร
**ANSRE** (Agentic Novel Scouting & Re-creation Engine) = โรงงานผลิตคอนเทนต์นิยายไทยอัตโนมัติ
ครบวงจร: **คิดไอเดีย → เขียนนิยาย → ทำหนังสือเสียง → ตัด teaser → เผยแพร่** สั่งผ่านคำสั่งเดียว `./ansre`

ปรัชญา:
- **State-driven** — ขับเคลื่อนด้วยสถานะใน frontmatter ของไฟล์ markdown (ไม่ใช่ DB)
- **Provider-routed** — ทุกการเรียก LLM ผ่าน `llm_provider.py` จุดเดียว สลับ Gemini ↔ local (Mac mini) ได้
- **รันต่อเนื่องเอง** — `orchestrator.py` + worker (launchd) ดันงานทุกชิ้นไปข้างหน้าทีละ stage

---

## 2. คำสั่งหลัก (ประตูเดียว)
```bash
./ansre setup       # ติดตั้ง venv + deps + .env (ครั้งเดียว)
./ansre doctor      # เช็คสุขภาพระบบ
./ansre status      # งานค้างแต่ละขั้น + ค่าใช้จ่าย
./ansre web         # เปิด dashboard (http://localhost:8765)
./ansre idea ...    # คลังไอเดีย (add/brainstorm/score/promote/list/auto)
./ansre run [--loop]# เดิน pipeline
./ansre continue    # เขียนตอนถัดไป (ch2+)
./ansre local       # เช็ค+เบนช์มาร์ก Mac mini
./ansre start|stop  # worker อัตโนมัติ
```

---

## 3. สถาปัตยกรรม & สายการผลิต

```
[00 Idea Vault] →(promote)→ [01 Pool] → write → [Chapters] → cover/audio/teaser → publish
  ideation.py                 status:           agent_writer.py    *_generator.py   publisher.py
                              state machine
```

**State machine** (ฟิลด์ `status` ใน frontmatter ของไฟล์ใน `01_Scouting_Pool/`):
```
Scouted → Analyzed → Processed          (นิยายจาก trend)
              ↑
        (ideation promote)              (ไอเดียต้นฉบับ → ฉีดเป็น Analyzed)
```
แต่ละ stage เป็น **idempotent** (ข้ามงานที่เสร็จแล้ว) → เรียกซ้ำปลอดภัย → orchestrator วนได้

---

## 4. โครงสร้างไฟล์

### 🟢 Core (อยู่ root — ถูกเรียกด้วยชื่อโดย subprocess ห้ามย้าย)
| ไฟล์ | หน้าที่ |
|------|---------|
| `llm_provider.py` | **หัวใจ** — route LLM (Gemini/local) ตาม role + cost/circuit-breaker/pacing |
| `ansre` / `ansre.py` | CLI ประตูเดียว (wrapper + router) |
| `orchestrator.py` | ขับ pipeline ต่อเนื่อง (state-driven, lock, backpressure) |
| `scout.py` | ดึง trending novels (Syosetu/RoyalRoad) → 01_Pool |
| `agent_analyzer.py` | วิเคราะห์ → Thai title, market score, inspired concept |
| `agent_writer.py` | เครื่องเขียน 6 stage (outline→chars→beats→scenes→polish→audio) |
| `chapter_continuer.py` | เขียนตอนถัดไป (ch2+) จาก outline+บทก่อน |
| `ideation.py` | คลังไอเดีย + engine (capture/brainstorm/score/promote) |
| `cover_generator.py` | สร้างปก (Imagen) — prompt ผ่าน provider |
| `audio_engine.py` | TTS → MP3 + SRT (edge-tts/macOS/gTTS/ElevenLabs) |
| `teaser_generator.py` | ตัดวิดีโอ 9:16 (FFmpeg) |
| `publisher.py` | เผยแพร่ YouTube/TikTok + คิวนิยาย |
| `dashboard.py` + `web/` | web UI (stdlib http.server, ไม่มี dep เพิ่ม) |

### 🗂️ โฟลเดอร์
| โฟลเดอร์ | เนื้อหา |
|---------|---------|
| `web/` | หน้าเว็บ dashboard (index.html/style.css/app.js) |
| `deploy/` | launchd plist (ollama + worker) |
| `scraper/` | ตัวดึงข้อมูล syosetu/royalroad |
| `docs/` | เอกสารละเอียด (ROADMAP, MACMINI_SETUP, PUBLISHING, DASHBOARD) |
| `legacy/` | **สคริปต์เก่า/ครั้งเดียวที่ถูกแทนที่แล้ว** — เก็บไว้อ้างอิง อย่าใช้กับงานใหม่ |
| `SecondBrain/` | ข้อมูล/ผลผลิตทั้งหมด (gitignored) |

### 🔴 legacy/ (ถูกแทนที่แล้ว — ดู `legacy/README.md`)
`app.py` (Streamlit UI เดิม → ใช้ `dashboard.py` แทน), `agent_refiner.py`, `run_iteration_loop.py`,
`run_novels_complete.py`, `write_chapters_*.py`, `notion_publisher.py`, `antigravity_novel_agent.py`, `mac_ocr.py`
> ไฟล์ใน legacy มี path-bootstrap ให้ import โมดูล root ได้ รันด้วย `.venv/bin/python legacy/xxx.py` จาก repo root

---

## 5. โครงสร้าง SecondBrain (ข้อมูล)
```
SecondBrain/
├── 00_Idea_Vault/         idea_*.md          (Captured→Scored→Promoted)
├── 01_Scouting_Pool/      *.md               (Scouted→Analyzed→Processed)
├── 02_Concept_Extraction/ {title}_Outline.md
├── 04_Character_Database/ {title}_Characters.md
├── 05_Active_Projects/
│   ├── Chapters/          {title}_Chapter_NN.md
│   ├── Audio_Scripts/     {title}_AudioScript_NN.md
│   ├── Audio_Output/      {title}_Audiobook_NN.mp3 / .srt
│   ├── Covers/            {title}_Cover.jpg
│   ├── Teaser_Output/     {title}_Teaser_NN.mp4
│   └── Publish_Queue/     {title}_PUBLISH.md
├── llm_usage.jsonl        (cost ledger)
└── orchestrator.log
```

---

## 6. กติกา & Convention (สำคัญ)

### 6.1 การตั้งชื่อไฟล์ (ดู `.cursorrules` ด้วย)
- ใช้ `clean_title` = ชื่อไทยล้วน เก็บวรรณยุกต์ (regex `[^\w\-_\s฀-๿]`) เว้นวรรค→`_`
- บท: `{title}_Chapter_NN.md` · เสียง: `{title}_Audiobook_NN.mp3` · ปก: `{title}_Cover.jpg`
- ❗ `\w` ใน regex **ไม่จับ** วรรณยุกต์ไทย (combining marks) → ต้องใส่ช่วง `฀-๿` เสมอ

### 6.2 Frontmatter markdown
YAML ธรรมดา key: "value" · list ใช้ `  - item` · ฟิลด์ `status` คือ state machine

### 6.3 LLM Routing (role → backend) — โหมด hybrid
| role | backend | เหตุผล |
|------|---------|--------|
| `writer`, `enhancer` | **gemini** | ร้อยแก้ว = คุณภาพคอขาด (local 8b ยังสู้ไม่ได้) |
| `analyzer`, `outline`, `planner`, `characters`, `audio`, `reviewer`, `researcher`, `editor`, `brainstorm`, `ideation` | **local** | งานเยอะ ทนคุณภาพรองได้ → ฟรี |

- เรียก LLM ใหม่ **ต้องผ่าน** `from llm_provider import generate` + ระบุ `role` เสมอ (อย่าเรียก genai ตรง)
- ยกเว้น Imagen (cover) ที่ต้องใช้ genai client ตรง

### 6.4 Output ของ LLM
- เขียน prose ต้องต่อท้าย prompt ด้วย `NO_META` + ครอบด้วย `strip_meta()` (กัน AI พูดถึงตัวเอง)
- งานยาว (audio) แบ่ง chunk กัน output ทะลุ token limit
- JSON จาก local อาจไม่ strict → ใช้ coerce + fallback (อย่า `json.loads` ดิบ)

### 6.5 Environment (ดู `.env.example`)
| กลุ่ม | คีย์ |
|------|------|
| Cloud | `GEMINI_API_KEY`, `NOTION_TOKEN` |
| Routing | `LLM_BACKEND` (gemini/local/hybrid), `LLM_ROLE_<ROLE>` |
| Local | `LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL`, `LOCAL_LLM_MODEL_HEAVY`, `LOCAL_LLM_MAX_TOKENS` |
| กัน throttle | `ANSRE_CALL_GAP`, `GEMINI_FAIL_THRESHOLD`, `GEMINI_COOLDOWN_SEC` |
| คุณภาพ/โทน | `WRITING_MODE`, `ANSRE_TONE`, `ANSRE_SCENE_WORDS` |
| Cost | `ANSRE_DAILY_USD_CAP` |
| Orchestrator | `ANSRE_MIN_POOL`, `ANSRE_SCOUT_EVERY_HOURS`, `ANSRE_IDEATION` |

---

## 7. วิธีต่อยอด (สำหรับ agent ที่มาแก้)
- **เพิ่ม pipeline stage:** สร้าง `xxx.py` ที่ scan SecondBrain ตาม status → ทำงาน → อัปเดต status (idempotent) แล้วเพิ่มใน `orchestrator.py` + `ansre.py` + `dashboard.py STAGE_CMDS`
- **เพิ่ม role LLM:** เพิ่มใน `_HYBRID_DEFAULT` (llm_provider) + เลือก backend
- **ห้าม** เรียก `genai.Client` ตรงในไฟล์ใหม่ — ใช้ provider เสมอ
- **ห้าม** ย้ายไฟล์ core ออกจาก root (ถูกเรียกด้วยชื่อ)

---

## 8. บทเรียน/กับดัก (gotchas)
- **Ollama default num_predict=128** → ต้องส่ง `max_tokens` ไม่งั้น local output โดนตัดสั้น
- **Gemini free tier throttle** เมื่อเรียกรัวๆ → ใช้ `ANSRE_CALL_GAP` (pacing) หรือมี Mac mini รับงาน
- **Typhoon 8b เขียนร้อยแก้วนิยายยังไม่ไหว** → คงร้อยแก้วที่ Gemini (hybrid)
- **qwen เป็นโมเดลจีน** → บางทีหลุดภาษาจีน; Typhoon ไทยลื่นกว่าสำหรับงานสั้น
- **`safety_settings=BLOCK_NONE`** ทุก Gemini call (กันบล็อกงานสร้างสรรค์) — จัดการใน provider แล้ว

---

## 9. เอกสารอื่น
- `README.md` — quickstart 3 คำสั่ง
- `docs/ROADMAP.md` — แผนพัฒนา (Phase 0-5)
- `docs/MACMINI_SETUP.md` — ตั้ง Mac mini local LLM
- `docs/PUBLISHING.md` — ตั้ง credential เผยแพร่
- `docs/DASHBOARD.md` — web dashboard + บันทึก 20 รอบ
