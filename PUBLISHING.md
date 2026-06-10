# 📤 คู่มือเผยแพร่จริง (Publishing Setup)

ANSRE เผยแพร่ teaser/นิยายออกแพลตฟอร์มจริงผ่าน `publisher.py` — ออกแบบให้ **ปลอดภัยเมื่อยังไม่มี credential** (แพลตฟอร์มไหนยังไม่พร้อมจะข้าม + log ไม่ทำให้ระบบล้ม).

ทุกอย่างตั้งใน `.env` (ไฟล์นี้ถูก gitignore — **ห้าม commit**).

หน้าแดชบอร์ด → **ผลผลิต** จะแสดงสถานะ credential แต่ละแพลตฟอร์ม:
- 🟢 **พร้อมปล่อยจริง** — เปิด + มี credential ครบ
- 🟡 **เปิดแล้วแต่ยังไม่มี credential** — ทำตามคู่มือด้านล่าง
- ⚪ **ปิดอยู่** — ยังไม่เปิด

---

## ▶️ YouTube (Shorts)

ใช้ YouTube Data API v3 + OAuth (ต้องมี `refresh_token` เพื่ออัปโหลดอัตโนมัติโดยไม่ต้องล็อกอินซ้ำ).

### ขั้นตอน
1. ไปที่ [Google Cloud Console](https://console.cloud.google.com/) → สร้างโปรเจกต์
2. เปิดใช้ **YouTube Data API v3** (APIs & Services → Library)
3. สร้าง **OAuth client ID** (ชนิด *Desktop app*) → ดาวน์โหลด `client_secret.json`
4. เปลี่ยนชื่อไฟล์ที่ดาวน์โหลดเป็น `client_secret.json` วางในโฟลเดอร์โปรเจกต์
5. authorize ครั้งเดียว (มีสคริปต์ช่วยแล้ว):
   ```bash
   .venv/bin/python authorize_youtube.py
   ```
   เบราว์เซอร์จะเปิดให้ล็อกอิน + อนุญาต → ได้ `youtube_token.json` (มี `refresh_token`) อัตโนมัติ
6. ตั้งใน `.env`:
   ```
   PUBLISH_YOUTUBE=1
   YOUTUBE_TOKEN_FILE=youtube_token.json
   YOUTUBE_PRIVACY=unlisted     # private | unlisted | public
   ```

> 💡 เริ่มที่ `unlisted` ก่อน ทดสอบให้มั่นใจแล้วค่อยเปลี่ยนเป็น `public`

---

## 🎵 TikTok

ใช้ Content Posting API — ต้องมี access token จาก [TikTok for Developers](https://developers.tiktok.com/).

### ขั้นตอน
1. สมัคร developer + สร้างแอป → ขอ scope `video.publish`
2. ทำ OAuth flow เพื่อได้ `access_token` (ดู docs TikTok)
3. ตั้งใน `.env`:
   ```
   PUBLISH_TIKTOK=1
   TIKTOK_ACCESS_TOKEN=xxxxxxxx
   ```

> ⚠️ access token ของ TikTok มีอายุ — ถ้าโพสต์ไม่ผ่านให้ refresh token ใหม่

---

## 📚 นิยาย (Dek-D / Fictionlog)

เว็บนิยายไทยไม่มี public API → ระบบจะ **เข้าคิวแบบกึ่งอัตโนมัติ**: แพ็กไฟล์พร้อมโพสต์ (บท + ปก) ไว้ให้ แล้วคุณอัปโหลดเอง.

```
PUBLISH_NOVEL=1
```

ใช้คู่กับปุ่ม **📦 แพ็กพร้อมปล่อย** (หน้า Studio) ที่รวมทุกอย่างเป็น zip เดียว.

---

## 🧪 ทดสอบก่อนปล่อยจริง

**แนะนำให้ dry-run ก่อนเสมอ:**

```bash
.venv/bin/python publisher.py --dry-run ./SecondBrain
```

หรือบนแดชบอร์ด → **ผลผลิต** → ปุ่ม **🧪 ทดลอง (dry-run)** — จำลองการเผยแพร่โดยไม่อัปจริง.

เมื่อมั่นใจแล้ว กด **📤 เผยแพร่จริง** (ปรากฏเมื่อมีแพลตฟอร์มสถานะ 🟢).

---

## 🔒 ความปลอดภัย

- `.env`, `youtube_token.json`, `client_secret.json` — **ห้าม commit** (อยู่ใน `.gitignore` แล้ว)
- ทุกการเผยแพร่บันทึกใน ledger → กันโพสต์ซ้ำ (idempotent)
- เริ่มที่ privacy `unlisted`/จำนวนน้อย ก่อนเปิด public เต็มที่
