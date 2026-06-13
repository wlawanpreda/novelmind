# 🖥️ ตั้ง Mac mini ที่บ้านเป็น "AI Compute Node" ของ ANSRE

เป้าหมาย: ย้ายงาน LLM ปริมาณมาก (วิเคราะห์, วางฉาก, รีวิว, brainstorm 50 รอบ) มารันบน Mac mini
ที่บ้าน → **ค่า token เป็นศูนย์** เก็บ Gemini ไว้เฉพาะงานคุณภาพคอขาด (เขียนร้อยแก้ว/เกลาสำนวน)

> สรุปกลยุทธ์: **Hybrid** — local ทำงานหนักได้ไม่อั้นฟรี, cloud ทำเฉพาะจุดที่คุณภาพต้องสูงสุด

---

## 0. ก่อนเริ่ม: ความจริงเรื่องค่าใช้จ่าย

| งาน | ใช้ token ไหม | ของเดิม | แผนใหม่ |
|-----|:---:|---------|---------|
| LLM (วิเคราะห์/เขียน/รีวิว) | ✅ มาก | Gemini เสียเงินทุกครั้ง | → **local บน Mac mini (ฟรี)** |
| TTS (เสียงพากย์) | ❌ **ไม่** | edge-tts (ฟรีอยู่แล้ว) | คงเดิม / +macOS say offline |
| Cover (รูปปก) | ✅ | Imagen เสียเงิน | → **local ComfyUI/SDXL (ฟรี)** — ดู [MACMINI_IMAGE_SETUP.md](MACMINI_IMAGE_SETUP.md) |

**จุดที่ประหยัดจริงคือ LLM token** — TTS ของเดิม (edge-tts) ฟรีอยู่แล้ว ไม่ได้กิน token
ดังนั้น Mac mini จะเน้นเป็น **LLM server** เป็นหลัก ส่วน TTS แค่เพิ่ม fallback แบบ offline

---

## 1. เลือกรุ่นโมเดลตาม RAM ของ Mac mini

โมเดลรันบน RAM (unified memory) — เผื่อ RAM ให้ระบบ ~6-8GB

| RAM Mac mini | โมเดลแนะนำ (ภาษาไทย) | ระดับงานที่ไหว |
|---|---|---|
| **16 GB** | `scb10x/typhoon2.1-gemma3-12b` หรือ `qwen2.5:7b` | วิเคราะห์/รีวิว/วางฉาก |
| **24 GB** | `qwen2.5:14b` + `typhoon2.1` | + brainstorm, outline คุณภาพดี |
| **32–36 GB** | `qwen2.5:32b` (Q4) | งานหนักเกือบทั้งหมด รวมร่างร้อยแก้ว |
| **64 GB+** | `qwen2.5:72b` (Q4) | แทน Gemini ได้เกือบหมด |

**ทำไมแนะนำ Typhoon:** เป็นโมเดลที่ fine-tune ภาษาไทยโดย SCB10X — สำนวนไทยลื่นกว่าโมเดลฝรั่งขนาดเท่ากัน
เหมาะกับ ANSRE ที่ผลิตคอนเทนต์ไทยโดยตรง ส่วน Qwen2.5 multilingual แข็งแรงและมีหลายขนาดให้เลือก

> ตรวจ RAM: `  ` → About This Mac → Memory

---

## ⚡ ทางลัด: ติดตั้งทั้งหมดด้วยคำสั่งเดียว (บน Mac mini)
```bash
# คัดลอก repo (หรือแค่ไฟล์ macmini_setup.sh) ไปที่ Mac mini แล้วรัน:
bash macmini_setup.sh
```
สคริปต์จะ: ติดตั้ง Ollama → เลือก+โหลดโมเดลตาม RAM อัตโนมัติ → ตั้ง launchd service
→ กันเครื่องหลับ → บอกค่า `.env` ที่ต้องใส่ในเครื่อง ANSRE

จากนั้นบนเครื่อง ANSRE ตรวจการเชื่อมต่อ + เบนช์มาร์กคุณภาพไทย:
```bash
./ansre local       # ✅ ต่อได้ไหม / มีโมเดลอะไร / เร็วแค่ไหน / เทียบคุณภาพกับ Gemini
```

> ด้านล่างคือขั้นตอนแบบ manual (ถ้าอยากทำเอง/เข้าใจรายละเอียด)

---

## 2. ติดตั้ง Ollama + โหลดโมเดล (บน Mac mini)

Ollama ให้ **OpenAI-compatible API** ที่ `llm_provider.py` ต่อได้ตรงๆ

```bash
# บน Mac mini
brew install ollama          # หรือโหลด .app จาก ollama.com

# โหลดโมเดล (เลือกตาม RAM จากตารางข้อ 1)
ollama pull qwen2.5:14b
ollama pull scb10x/typhoon2.1-gemma3-12b   # โมเดลไทยเฉพาะทาง

# ทดสอบเร็วๆ
ollama run qwen2.5:14b "เขียนประโยคเปิดนิยายสืบสวนไทยให้หน่อย"
```

---

## 3. รัน Ollama เป็น **service ถาวร** (launchd) + เปิดให้เครื่องอื่นในบ้านเรียกได้

ค่าเริ่มต้น Ollama ฟัง `127.0.0.1:11434` (localhost เท่านั้น) — ต้องตั้ง `OLLAMA_HOST=0.0.0.0`
เพื่อให้เครื่องที่รัน ANSRE เรียกข้ามเครื่องในเครือข่ายบ้านได้

สร้างไฟล์ `~/Library/LaunchAgents/com.ansre.ollama.plist` บน Mac mini:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ansre.ollama</string>
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/ollama</string>
    <string>serve</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>OLLAMA_HOST</key>
    <string>0.0.0.0:11434</string>
    <key>OLLAMA_KEEP_ALIVE</key>
    <string>30m</string>            <!-- คาโมเดลใน RAM ไว้ ไม่ต้องโหลดใหม่ทุกครั้ง -->
    <key>OLLAMA_MAX_LOADED_MODELS</key>
    <string>2</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>                            <!-- ล้มแล้วเด้งกลับเอง -->
  <key>StandardOutPath</key>
  <string>/tmp/ollama.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/ollama.err</string>
</dict>
</plist>
```

```bash
launchctl load -w ~/Library/LaunchAgents/com.ansre.ollama.plist
# ตรวจว่าฟังอยู่
curl http://localhost:11434/v1/models
```

**ตั้ง Mac mini ไม่ให้หลับ** (สำคัญมากสำหรับ "รันเรื่อยๆ"):
```bash
sudo pmset -a sleep 0 disksleep 0   # ไม่หลับเมื่อเสียบไฟ
# System Settings → Lock Screen → ปิด display หลับได้ แต่อย่าให้ "เครื่อง" หลับ
```

---

## ⚡ 3.5 จูนความเร็ว Ollama (สำคัญบนเครื่อง RAM จำกัด เช่น 24GB)

อาการ "LLM ตอบช้ามาก/ค้าง" บน 24GB มักมาจาก **โมเดลใหญ่เกิน + RAM เบียดจน swap/หลุดไป CPU**

**1) เลือกขนาดโมเดลให้พอดี RAM** — บน 24GB ที่แชร์กับงานอื่น (ComfyUI/ระบบ) แนะนำ **7–8B** ไม่ใช่ 14B:

| RAM | โมเดล local ที่ "ตอบไว" | หมายเหตุ |
|-----|------------------------|---------|
| 16–24GB | **`scb10x/llama3.1-typhoon2-8b-instruct`** (ไทยลื่น) หรือ `qwen2.5:7b` | เร็ว ~2× ของ 14B, เหลือ RAM ให้รูป |
| 32GB+ | `qwen2.5:14b` | ใช้ 14B ได้สบายขึ้น |

เปลี่ยนใน `.env` ฝั่ง client (ไม่ต้องแตะ Mac mini ถ้าโหลดโมเดลไว้แล้ว):
```bash
LOCAL_LLM_MODEL=scb10x/llama3.1-typhoon2-8b-instruct:latest
LOCAL_LLM_MODEL_HEAVY=scb10x/llama3.1-typhoon2-8b-instruct:latest
```

**2) env จูนความเร็ว** (`macmini_setup.sh` ใส่ให้แล้วในเวอร์ชันใหม่):
```
OLLAMA_FLASH_ATTENTION=1      # เร็วขึ้น + RAM attention น้อยลง
OLLAMA_KV_CACHE_TYPE=q8_0     # quantize KV cache → context ยาว/swap น้อย
OLLAMA_MAX_LOADED_MODELS=1    # 24GB อย่าโหลด 2 โมเดลใหญ่พร้อมกัน
```

**อัปเดตทันทีโดยไม่ต้องรัน setup ใหม่** (รันบน Mac mini):
```bash
launchctl setenv OLLAMA_FLASH_ATTENTION 1
P=~/Library/LaunchAgents/com.ansre.ollama.plist
launchctl unload "$P" && launchctl load -w "$P"   # โหลด plist ใหม่ที่อัปแล้ว
```

**3) วัดผล** จากเครื่อง client:
```bash
curl http://<mac-mini>:11434/api/generate \
  -d '{"model":"<model>","prompt":"เขียน 2 ประโยค","stream":false,"options":{"num_predict":48}}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('%.1f tok/s'%(d['eval_count']/(d['eval_duration']/1e9)))"
# เป้าหมาย: 8B ควรได้ >10 tok/s · ถ้า <3 tok/s = ยัง swap/CPU → ลดขนาดโมเดลอีก หรือเช็คงานอื่นกิน RAM
```

---

## 4. เชื่อมเครื่อง ANSRE → Mac mini

### ทางเลือก A: อยู่บ้านเดียวกัน (LAN) — ง่ายสุด
หา IP/ชื่อ Mac mini: `ipconfig getifaddr en0` หรือใช้ Bonjour name `macmini.local`

### ทางเลือก B: คนละที่ / ออกนอกบ้าน — แนะนำ **Tailscale** (ฟรี, ปลอดภัย)
```bash
# ติดตั้งทั้งสองเครื่อง
brew install tailscale && tailscale up
# จะได้ IP วงใน เช่น 100.x.x.x ที่เรียกข้ามเน็ตได้โดยไม่ต้องเปิด port router
```
> อย่าเปิด port 11434 ออกอินเทอร์เน็ตตรงๆ — Ollama ไม่มี auth ใครก็เรียกได้ ใช้ Tailscale ปลอดภัยกว่ามาก

### ชี้ ANSRE ไปที่ Mac mini — แก้ `.env` บนเครื่องที่รัน pipeline
```bash
LLM_BACKEND=hybrid
LOCAL_LLM_BASE_URL=http://macmini.local:11434/v1     # หรือ http://100.x.x.x:11434/v1 (Tailscale)
LOCAL_LLM_MODEL=qwen2.5:14b
LOCAL_LLM_MODEL_HEAVY=qwen2.5:32b                      # ถ้า RAM พอ; ไม่งั้นใส่เท่ากับตัวบน
```

ดู `.env.example` สำหรับคีย์ทั้งหมด

---

## 5. ทดสอบว่าใช้ได้จริง

```bash
# จากเครื่อง ANSRE
python3 llm_provider.py --selftest
# คาดหวัง: [local ] OK -> 2   และ  [gemini] OK -> 2

# ทดสอบ route จริง: analyzer ควรวิ่งไป local
python3 llm_provider.py --probe "วิเคราะห์จุดขายนิยายย้อนเวลา 1 บรรทัด" --role analyzer
```

---

## 6. กลยุทธ์ Routing (ปรับได้หมดใน `llm_provider.py` / .env)

ค่าเริ่มต้นโหมด `hybrid`:

| Role | ไป backend | เหตุผล |
|------|:---:|--------|
| `writer`, `enhancer` | **gemini** | ร้อยแก้ว/สำนวน = หัวใจคุณภาพ ยอมจ่าย |
| `analyzer`, `reviewer`, `researcher`, `editor`, `evaluator` | **local** | งานประเมิน ปริมาณมาก ทนคุณภาพรองได้ |
| `outline`, `characters`, `scene_planner`, `audio_script` | **local** | งานโครงสร้าง local ทำได้ดี |
| `brainstorm` (ลูป 50 รอบ) | **local** | กิน token มหาศาล → ประหยัดสุดเมื่อย้าย local |

**ปรับรายตัวได้ทันทีโดยไม่แตะโค้ด** เช่น อยากให้ outline ใช้ Gemini ชั่วคราว:
```bash
LLM_ROLE_OUTLINE=gemini
```
อยากประหยัดสุดขีด (ทุกอย่าง local):
```bash
LLM_BACKEND=local
```
อยากกลับไปใช้ Gemini ล้วน (เหมือนเดิมก่อนเปลี่ยน):
```bash
LLM_BACKEND=gemini
```

มี **auto-fallback**: ถ้า Mac mini ดับ/เน็ตหลุด งานจะเด้งไป Gemini ให้อัตโนมัติ pipeline ไม่สะดุด

---

## 7. TTS: ของเดิมฟรีอยู่แล้ว + เพิ่ม offline fallback

- **edge-tts** (ค่า default) = เสียง neural ไทยคุณภาพดี **ฟรี** ไม่กิน token — ใช้ต่อไป
- **macOS `say -v Kanya`** = local 100% ไม่ง้อเน็ต — มีในโค้ดแล้ว ใช้เป็น fallback ตอนเน็ตหลุด
  ```bash
  TTS_ENGINE=edge-tts     # ปกติ
  TTS_ENGINE=macos        # โหมด offline ล้วน
  ```
- โมเดล TTS ไทย local คุณภาพสูง (เช่น XTTS/F5-TTS) ยัง setup ยากและเสียงไทยยังสู้ edge-tts ไม่ได้
  → **ยังไม่คุ้มลงทุนตอนนี้** บันทึกไว้เป็นงานอนาคต

---

## 8. ทำให้ Mac mini ทำงาน "เรื่อยๆ" อัตโนมัติ (รันอัตโนมัติทุกครั้ง/บน startup)

เพื่อให้เครื่อง Mac mini รันงาน pipeline ตรวจสอบนิยาย และเขียนตอนใหม่แบบอัตโนมัติตลอดทั้งวัน:

1. **ติดตั้งและรัน worker อัตโนมัติ (ผ่าน launchd)**
   รันคำสั่งด้านล่างนี้บน Mac mini:
   ```bash
   ./ansre start      # หรือ make start
   ```
   *หมายเหตุ: คำสั่งนี้จะสร้างและโหลดไฟล์ plist ไปยัง LaunchAgents ของผู้ใช้ เพื่อสั่งรัน `orchestrator.py` ทุกๆ 20 นาทีโดยอัตโนมัติ*

2. **ดูประวัติการทำงานแบบ Real-time (Logs)**
   ```bash
   tail -f /tmp/ansre.worker.log
   ```

3. **ตรวจสอบสถานะระบบ**
   ```bash
   ./ansre status     # หรือ make status
   ```

4. **หยุดการทำงานอัตโนมัติ**
   ```bash
   ./ansre stop       # หรือ make stop
   ```

---

## สรุปขั้นตอนสั้นๆ
1. รัน `bash macmini_setup.sh` (บน Mac mini) เพื่อลง Ollama, โมเดล และตั้งค่าปิดโหมด Sleep
2. แก้ `.env`: ตั้ง `LLM_BACKEND=hybrid` และชี้ URL/Model ไปยัง Mac mini
3. รัน `./ansre local` (หรือ `make local`) เพื่อทดสอบการต่อกับ Local LLM
4. รัน `./ansre start` (หรือ `make start`) บน Mac mini เพื่อตั้งให้รันอัตโนมัติแบบต่อเนื่องทุก 20 นาที

