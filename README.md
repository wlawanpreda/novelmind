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
| `./ansre scout\|analyze\|write\|cover\|audio\|teaser` | รันทีละขั้นเอง |

---

## 💸 ประหยัดค่า token ด้วย Mac mini ที่บ้าน

ตั้ง Mac mini รัน LLM local แล้วใส่ใน `.env`:
```bash
LLM_BACKEND=hybrid                                  # ร้อยแก้วใช้ Gemini, ที่เหลือใช้ local ฟรี
LOCAL_LLM_BASE_URL=http://macmini.local:11434/v1
```
**ติดตั้งบน Mac mini ด้วยคำสั่งเดียว:** `bash macmini_setup.sh` (ลง Ollama + โมเดล + service ให้หมด)
จากนั้นบนเครื่อง ANSRE: `./ansre local` เพื่อตรวจการเชื่อมต่อ + เทียบคุณภาพไทยกับ Gemini
ดูครบใน **[MACMINI_SETUP.md](MACMINI_SETUP.md)**

---

## 📚 เอกสารเพิ่มเติม
- **[MACMINI_SETUP.md](MACMINI_SETUP.md)** — ตั้ง LLM local บน Mac mini (ประหยัด token)
- **[PUBLISHING.md](PUBLISHING.md)** — ตั้ง credential เผยแพร่ YouTube/TikTok/นิยาย
- **[ROADMAP.md](ROADMAP.md)** — แผนพัฒนาระยะยาว + สถานะแต่ละ Phase

> ทุกอย่างเก็บใน `SecondBrain/` (Obsidian-compatible). ตั้งค่าทั้งหมดอยู่ใน `.env` (ดูตัวอย่าง `.env.example`)
