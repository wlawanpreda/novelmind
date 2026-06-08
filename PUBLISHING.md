# 📤 ตั้งค่า Auto-Publishing (Phase 4)

`publisher.py` อ่าน teaser .mp4 ที่ผลิตเสร็จ แล้วอัปโหลดไป YouTube/TikTok + เข้าคิวนิยาย
ทุกแพลตฟอร์มข้ามได้เองถ้ายังไม่มี credential — เปิดทีละตัวได้

> orchestrator จะรัน publish stage ให้อัตโนมัติเมื่อเปิด `PUBLISH_*` อย่างน้อย 1 ตัว
> รันมือ: `.venv/bin/python publisher.py --dry-run ./SecondBrain`

---

## 1. YouTube Shorts

ต้องมี **token.json** ที่ authorize ไว้ล่วงหน้า (มี refresh_token) — ทำครั้งเดียว:

1. สร้าง project ใน [Google Cloud Console](https://console.cloud.google.com) → เปิด **YouTube Data API v3**
2. สร้าง **OAuth client ID** (Desktop app) → ดาวน์โหลด `client_secret.json`
3. authorize ครั้งแรกเพื่อสร้าง token (เครื่องที่มีเบราว์เซอร์):
   ```bash
   pip install google-auth-oauthlib   # lib สำหรับ flow ครั้งแรกเท่านั้น
   python - <<'PY'
   from google_auth_oauthlib.flow import InstalledAppFlow
   flow = InstalledAppFlow.from_client_secrets_file(
       "client_secret.json", ["https://www.googleapis.com/auth/youtube.upload"])
   creds = flow.run_local_server(port=0)
   open("youtube_token.json","w").write(creds.to_json())
   print("saved youtube_token.json")
   PY
   ```
4. ตั้ง `.env`:
   ```bash
   PUBLISH_YOUTUBE=1
   YOUTUBE_TOKEN_FILE=youtube_token.json
   YOUTUBE_PRIVACY=unlisted          # เริ่มที่ unlisted ก่อน แล้วค่อยเปลี่ยนเป็น public
   ```
> `publisher.py` ใส่ `#Shorts` ให้อัตโนมัติ + วิดีโอเป็น 9:16 < 60s = ขึ้น Shorts feed

---

## 2. TikTok

1. สมัคร [TikTok for Developers](https://developers.tiktok.com) → สร้าง app → ขอสิทธิ์ **Content Posting API**
   (ช่วงรีวิว/ยังไม่ audit จะโพสต์ได้แบบ `SELF_ONLY` — publisher ตั้งค่านี้ไว้ให้ปลอดภัยก่อน)
2. ได้ access token แล้วตั้ง `.env`:
   ```bash
   PUBLISH_TIKTOK=1
   TIKTOK_ACCESS_TOKEN=act....
   ```
> เปลี่ยน `privacy_level` ใน `publisher.py` เป็น `PUBLIC_TO_EVERYONE` เมื่อ app ผ่าน audit แล้ว

---

## 3. นิยาย Dek-D / Fictionlog

ทั้งสองเว็บ **ไม่มี public API** → publisher จะแพ็กบทนิยาย + คำโปรยเป็นไฟล์เดียวใส่
`SecondBrain/05_Active_Projects/Publish_Queue/{เรื่อง}_PUBLISH.md` ให้ก๊อปไปวางโพสต์เอง

```bash
PUBLISH_NOVEL=1
```

> ถ้าต้องการอัตโนมัติเต็มรูปแบบในอนาคต ต้องใช้ browser automation (Playwright/Selenium)
> ซึ่งเปราะและเสี่ยงผิด ToS — แนะนำคงเป็นกึ่งอัตโนมัติ (คิว manual) ไว้ก่อน

---

## ทดสอบ
```bash
.venv/bin/python publisher.py --dry-run ./SecondBrain   # ดูว่าจะทำอะไร ไม่อัปจริง
```
ทุกการเผยแพร่บันทึกใน `SecondBrain/05_Active_Projects/publish_ledger.json` (กันโพสต์ซ้ำ)
