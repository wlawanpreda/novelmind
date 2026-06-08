# 🖼️ ตั้ง Mac mini เป็น "Image-gen server" ฟรี (รูปปก ไม่ง้อ Imagen)

คู่กับ [MACMINI_SETUP.md](MACMINI_SETUP.md) (ตัวนั้นทำ **LLM/Ollama**) — ไฟล์นี้ทำ **รูป**
เป้าหมาย: ย้ายการสร้างรูปปกจาก **Imagen (เสียเงินทุกรูป)** มารันบน Mac mini **ฟรี ไม่จำกัด**

> **สำคัญ:** Ollama สร้างรูปไม่ได้ (เป็น text LLM ล้วน) — ต้องใช้คนละเครื่องมือ คือ **ComfyUI**
> (Stable Diffusion XL) ซึ่งรันบน GPU Metal/MPS ของ Apple Silicon ได้ฟรี รันคนละ port กับ Ollama
> อยู่ร่วมเครื่องเดียวกันได้สบาย (Ollama=11434, ComfyUI=8188)

---

## ความจริงเรื่องค่าใช้จ่าย (อัปเดตจากของเดิม)

| งาน | ของเดิม | แผนใหม่ |
|-----|---------|---------|
| LLM | Gemini เสียเงิน | local Ollama (ฟรี) — ดู MACMINI_SETUP.md |
| Cover (รูปปก) | **Imagen เสียเงินทุกรูป** | → **local ComfyUI/SDXL (ฟรี)** ✅ ไฟล์นี้ |

ข้อแลกเปลี่ยน: คุณภาพ SDXL ดีระดับใช้งานได้สำหรับปกนิยาย แต่ Imagen อาจเนียนกว่าบางเคส
→ จึงแนะนำโหมด **hybrid**: ใช้ Mac mini เป็นหลัก ถ้าเครื่องดับค่อย fallback ไป Imagen เอง

---

## RAM ที่ต้องใช้

SDXL ใช้ unified memory ~8–10GB ระหว่างเรนเดอร์ → Mac mini **16GB ขึ้นไป** สบาย
(รันพร้อม Ollama ตัวเล็กได้ ถ้า RAM 24GB+ ยิ่งสบาย)

---

## ⚡ ทางลัด: ติดตั้งคำสั่งเดียว (บน Mac mini)
```bash
bash macmini_image_setup.sh
```
สคริปต์จะ: clone ComfyUI → ติดตั้ง PyTorch(MPS)+deps → โหลด **SDXL base 1.0** (~6.9GB ครั้งเดียว)
→ ตั้ง launchd service (`com.ansre.comfyui`, port 8188, `--listen 0.0.0.0`)
→ กันเครื่องหลับ → บอกค่า `.env` ที่ต้องใส่ในเครื่อง ANSRE

จากนั้นบนเครื่อง ANSRE:
```bash
python3 image_provider.py --selftest                                  # ต่อได้ไหม / เห็นโมเดลไหม
python3 image_provider.py --probe "a serene thai temple at dawn, cinematic" -o /tmp/t.png --backend local
```

---

## ชี้ ANSRE → Mac mini — แก้ `.env`
```bash
IMAGE_BACKEND=hybrid                                # local | gemini | hybrid
LOCAL_IMAGE_BASE_URL=http://macmini.local:8188      # หรือ http://100.x.x.x:8188 (Tailscale)
LOCAL_IMAGE_MODEL=sd_xl_base_1.0.safetensors
LOCAL_IMAGE_STEPS=30                                # มาก=สวยขึ้น/ช้าลง
LOCAL_IMAGE_CFG=7.0
```
> ออกนอกบ้านให้ใช้ **Tailscale** (เหมือน LLM) — อย่าเปิด port 8188 ออกเน็ตตรงๆ ComfyUI ไม่มี auth

หลังจากนั้น pipeline เดิมทำงานเหมือนเดิม — `cover_generator.py` จะวิ่งผ่าน `image_provider.py`
ให้อัตโนมัติตาม `IMAGE_BACKEND`

---

## สถาปัตยกรรม (ตรงกับ llm_provider)

```
cover_generator.py ─→ image_provider.generate_image(prompt, out, ratio)
                          ├─ local  → ComfyUI /prompt → poll /history → /view  (Mac mini, ฟรี)
                          ├─ gemini → Imagen 4.0                                (cloud, เสียเงิน)
                          └─ hybrid → ลอง local, ดับ/พัง → fallback gemini อัตโนมัติ
```
ปรับ negative prompt / ขนาดต่อ aspect ratio ได้ใน `image_provider.py`
(แมป `1:1→1024² · 3:4 · 9:16 ...` ให้ SDXL อยู่แล้ว)

---

## ⚠️ RAM ตึง — รัน LLM + image-gen พร้อมกันบนเครื่องเดียว
SDXL ใช้ ~8-10GB, Ollama `qwen2.5:14b` ใช้ ~9.5GB → บน **24GB** สองตัวพร้อมกันเบียดกัน
จน macOS swap → เรนเดอร์ช้ามาก (อาการ: `--probe` ค้างจน timeout ทั้งที่ ComfyUI ไม่ error)

เช็คว่าใช่อาการนี้ไหม:
```bash
curl -s http://<mac-mini>:8188/system_stats | python3 -c "import sys,json;d=json.load(sys.stdin);print('vram_free %.1fGB'%(d['devices'][0]['vram_free']/1e9))"
curl -s http://<mac-mini>:11434/api/ps     # Ollama ถือโมเดลอะไรอยู่
```
ถ้า `vram_free` < 5GB = ตึงแน่ — เลือกทางใดทางหนึ่ง:

**ก) ลด setting (ง่ายสุด — ตั้งใน `.env`):**
```bash
LOCAL_IMAGE_DIM_SCALE=0.75    # 768px แทน 1024 → กิน RAM น้อยลง/เร็วขึ้น
LOCAL_IMAGE_STEPS=22
LOCAL_IMAGE_TIMEOUT=600        # เผื่อเวลา ถ้ายัง swap บ้าง
```
**ข) ปลด LLM ก่อนทำปก** (cover ทำเป็นชุด ไม่ชนงานเขียน): unload Ollama ก่อนรัน
```bash
curl http://<mac-mini>:11434/api/generate -d '{"model":"qwen2.5:14b","keep_alive":0,"prompt":""}'
```
**ค) ใช้โมเดลเบา** (SDXL-Turbo/SD1.5 ~4GB, 4-8 steps) อยู่ร่วมกับ LLM ได้สบาย — โหลด `.safetensors`
วางที่ `~/ComfyUI/models/checkpoints/` แล้วตั้ง `LOCAL_IMAGE_MODEL` + ลด `LOCAL_IMAGE_STEPS`/`LOCAL_IMAGE_CFG`

## แก้ปัญหา
- ดู log service: `tail -f /tmp/comfyui.err` (บน Mac mini)
- งานค้างในคิว/อยากเริ่มใหม่: `curl -X POST http://<mac-mini>:8188/interrupt` แล้ว
  `curl -X POST http://<mac-mini>:8188/queue -H 'Content-Type: application/json' -d '{"clear":true}'`
- โหลดโมเดลเองได้: วาง `.safetensors` ที่ `~/ComfyUI/models/checkpoints/` แล้วตั้ง `LOCAL_IMAGE_MODEL`
- อยากได้คุณภาพ/สไตล์เฉพาะทาง: โหลด checkpoint ชุมชน (เช่น SDXL fine-tune) วางที่โฟลเดอร์เดียวกัน
- restart service: `launchctl unload ~/Library/LaunchAgents/com.ansre.comfyui.plist && launchctl load -w ~/Library/LaunchAgents/com.ansre.comfyui.plist`

---

## สรุปสั้นๆ
1. `bash macmini_image_setup.sh` บน Mac mini
2. แก้ `.env` เครื่อง ANSRE: `IMAGE_BACKEND=hybrid` + `LOCAL_IMAGE_BASE_URL`
3. `python3 image_provider.py --selftest` ให้ผ่าน
4. รัน pipeline เดิม — รูปปกออกจาก Mac mini ฟรี (ดับเมื่อไรเด้งกลับ Imagen เอง)
