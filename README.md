# ANSRE — โรงงานผลิตนิยาย→หนังสือเสียง→วิดีโออัตโนมัติ

ระบบเดียวที่: คิด/เก็บไอเดีย → หาเทรนด์ → ดัดแปลงเป็นนิยายไทยต้นฉบับ → ทำหนังสือเสียง → ตัด teaser → เผยแพร่
ทั้งหมดสั่งผ่านคำสั่งเดียว: **`./ansre`**

```
[💡 Idea Vault] → [✍️ Write] → [🖼️ Cover] → [🎧 Audio] → [🎬 Teaser] → [📤 Publish]
   คิด/ให้คะแนน/promote      6-stage      Imagen      edge-tts      FFmpeg     YT/TikTok
```

---

## 🚀 เริ่มใช้ใน 3 ขั้น

```bash
./ansre setup      # 1) ติดตั้งทุกอย่าง (venv + deps + .env)  — ทำครั้งเดียว
#    แก้ .env ใส่ GEMINI_API_KEY และ NOTION_TOKEN
./ansre doctor     # 2) เช็คว่าพร้อม — บอกชัดว่าขาดอะไร + วิธีแก้
./ansre run        # 3) เดิน pipeline 1 รอบ (scout→analyze→write→cover→audio→teaser)
```

หรือคุมทุกอย่างผ่าน **web dashboard สวยๆ**:
```bash
./ansre web        # เปิด http://localhost:8765 — กดปุ่มสั่งงาน ดูสถานะ/ผลผลิต/ค่าใช้จ่าย
```

อยากให้ทำงานเองทั้งวัน:
```bash
./ansre start      # ติดตั้ง worker (รันเองทุก 20 นาที) — ปิดด้วย ./ansre stop
```

---

## 📋 คำสั่งทั้งหมด

| คำสั่ง | ทำอะไร |
|--------|--------|
| `./ansre setup` | ติดตั้ง venv + dependencies + สร้าง .env |
| `./ansre doctor` | 🩺 เช็คสุขภาพระบบ บอกว่าอะไรพร้อม/ขาด + วิธีแก้ |
| `./ansre idea` | 💡 คลังไอเดีย: `add "…"` / `brainstorm` / `score` / `promote <id>` / `list` / `auto` |
| `./ansre web` | 🌐 เปิด web dashboard คุมทุกอย่างในเบราว์เซอร์ |
| `./ansre status` | 📊 ดูงานค้างแต่ละขั้น + ผลผลิต + ค่า LLM วันนี้ |
| `./ansre run` | เดิน pipeline 1 รอบ · `run --loop` วนต่อเนื่อง |
| `./ansre start` / `stop` | เปิด/ปิด worker อัตโนมัติ (launchd) |
| `./ansre usage` | 💰 ดูค่า token ที่ใช้ |
| `./ansre selftest` | เช็คว่า LLM backend (Gemini/local) ต่อได้ |
| `./ansre publish` | เผยแพร่ teaser ออกแพลตฟอร์ม (ดู PUBLISHING.md) |
| `./ansre feedback` | 🏆 เรียนรู้จากผลงานจริง (Phase 5): `record "เรื่อง" --views N --likes N` → `learn` |
| `./ansre scout\|analyze\|write\|cover\|audio\|teaser` | รันทีละขั้นเอง |

> **🔁 วงจรเรียนรู้ (Phase 5):** หลังปล่อยคลิป บันทึกยอดจริงด้วย `./ansre feedback record "ชื่อเรื่อง" --views 88000 --likes 7100 --platform tiktok` แล้ว `./ansre feedback learn` — ระบบจะถอดสูตรว่า genre/ธีมไหนปัง แล้วป้อนกลับเข้า scout/analyze/ideation ให้เลือกเรื่องถัดไปฉลาดขึ้นเอง

> 💡 ใช้ **`make`** แทนก็ได้ (`make help` ดูทั้งหมด) เช่น `make doctor`, `make run`, `make idea ARGS="brainstorm 3"`

---

## 💸 ประหยัดค่า token ด้วย Mac mini ที่บ้าน

ตั้ง Mac mini รัน LLM local แล้วใส่ใน `.env`:
```bash
LLM_BACKEND=hybrid                                  # ร้อยแก้วใช้ Gemini, ที่เหลือใช้ local ฟรี
LOCAL_LLM_BASE_URL=http://macmini.local:11434/v1
```
**ติดตั้งบน Mac mini ด้วยคำสั่งเดียว:** `bash macmini_setup.sh` (ลง Ollama + โมเดล + service ให้หมด)
จากนั้นบนเครื่อง ANSRE: `./ansre local` เพื่อตรวจการเชื่อมต่อ + เทียบคุณภาพไทยกับ Gemini
ดูครบใน **[MACMINI_SETUP.md](docs/MACMINI_SETUP.md)**

**สร้างรูปปกฟรีด้วย Mac mini** (แทน Imagen เสียเงิน): `bash macmini_image_setup.sh` (ComfyUI/SDXL)
→ ตั้ง `IMAGE_BACKEND=hybrid` + `LOCAL_IMAGE_BASE_URL` — ดู **[MACMINI_IMAGE_SETUP.md](docs/MACMINI_IMAGE_SETUP.md)**

**แยก LLM+Image เป็น service ตัวเดียว** (ให้ client อื่นเรียกง่าย + คุมคิว/ไม่ swap):
`bash macmini_gateway_setup.sh` บน Mac mini → ตั้ง `ANSRE_GATEWAY_URL` ฝั่ง client เท่านั้น
provider จะ route ผ่าน gateway อัตโนมัติ (ล่ม→fallback เอง) · เช็ค: `./ansre gateway health`
ดู **[SERVICE_ARCHITECTURE.md](docs/SERVICE_ARCHITECTURE.md)**

---

## 📚 เอกสารเพิ่มเติม
- **[AGENT.md](AGENT.md)** — 🤖 สถาปัตยกรรม + กติกา + แผนที่ไฟล์ (อ่านก่อนแก้โค้ด)
- **[docs/MACMINI_SETUP.md](docs/MACMINI_SETUP.md)** — ตั้ง LLM local บน Mac mini (ประหยัด token)
- **[docs/MACMINI_IMAGE_SETUP.md](docs/MACMINI_IMAGE_SETUP.md)** — สร้างรูปปกฟรี (ComfyUI/SDXL)
- **[docs/SERVICE_ARCHITECTURE.md](docs/SERVICE_ARCHITECTURE.md)** — แยก LLM/Image เป็น gateway service
- **[docs/PUBLISHING.md](docs/PUBLISHING.md)** — ตั้ง credential เผยแพร่ YouTube/TikTok/นิยาย
- **[docs/ROADMAP.md](docs/ROADMAP.md)** — แผนพัฒนาระยะยาว + สถานะแต่ละ Phase
- **[docs/DASHBOARD.md](docs/DASHBOARD.md)** — web dashboard

## 🗂️ โครงสร้างโปรเจกต์
```
ansre, ansre.py        CLI ประตูเดียว
llm_provider.py        หัวใจ routing LLM (Gemini↔local)
orchestrator.py        ขับ pipeline ต่อเนื่อง
scout/analyze/write/cover/audio/teaser/publish  ← stage ต่างๆ (root)
ideation.py, chapter_continuer.py
dashboard.py + web/    web UI
docs/                  เอกสารละเอียด
legacy/                สคริปต์เก่าที่ถูกแทนที่แล้ว
SecondBrain/           ข้อมูล/ผลผลิต (gitignored)
```
> รายละเอียดเต็มใน [AGENT.md](AGENT.md)

> ทุกอย่างเก็บใน `SecondBrain/` (Obsidian-compatible). ตั้งค่าทั้งหมดอยู่ใน `.env` (ดูตัวอย่าง `.env.example`)
