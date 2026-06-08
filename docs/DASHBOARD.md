# 🌐 ANSRE Web Dashboard

หน้าควบคุมระบบทั้งหมดในเบราว์เซอร์ — สวย ใช้ง่าย ไม่ต้องลง dependency เพิ่ม
(ใช้ `http.server` ของ Python ล้วน + หน้าเว็บ custom)

## เปิดใช้
```bash
./ansre web          # แล้วเปิด http://localhost:8765
```

## มีอะไรบ้าง
- **ภาพรวม** — การ์ดสถานะ, สายการผลิตแบบ visual, ปุ่มลัดสั่งงานทุก stage
- **นิยาย** — รายการในคลังพร้อมสถานะ + คะแนนตลาด
- **ผลผลิต** — แกลเลอรีปก, เครื่องเล่นหนังสือเสียง, วิดีโอ teaser (เล่นในหน้าได้เลย)
- **ค่าใช้จ่าย** — กราฟ token/cost 14 วัน + แยกตาม backend (เห็นว่า local ฟรีไปเท่าไร)
- **LLM Routing** — ตาราง role→backend + ตั้งค่าด่วน (เปลี่ยน backend/โหมด/เพดานเงิน บันทึกลง .env ทันที)
- **สุขภาพระบบ** — ผลตรวจ doctor + ปุ่มเปิด/ปิด worker อัตโนมัติ
- **Live log drawer** — กดสั่งงานแล้วเห็น log วิ่งสดๆ + toast แจ้งเตือนเมื่อเสร็จ

---

## บันทึกการพัฒนา 20 รอบ

| รอบ | สิ่งที่ทำ |
|----:|-----------|
| 1 | โครง HTTP server (stdlib `ThreadingHTTPServer`) เสิร์ฟหน้าเว็บ + API |
| 2 | `/api/status` — สรุปงานค้างแต่ละขั้น + ผลผลิต + ค่าใช้จ่ายวันนี้ |
| 3 | `/api/doctor` — health check แบบ structured (venv/deps/ffmpeg/keys/ollama/worker) |
| 4 | `/api/usage` — รวม token/cost รายวัน + แยก backend/role |
| 5 | `/api/novels` — อ่าน frontmatter ทุกเรื่องในคลัง |
| 6 | `/api/config` — backend ปัจจุบัน + ตาราง routing จาก llm_provider จริง |
| 7 | `/api/outputs` + เสิร์ฟไฟล์สื่อ (`/media/...`) ปก/เสียง/teaser |
| 8 | Background task runner + `/api/task/<id>` — รัน stage แบบ async มี log |
| 9 | `/api/worker` — เปิด/ปิด launchd worker จากหน้าเว็บ |
| 10 | ดีไซน์ dark glass-morphism + ฟอนต์ไทย Sarabun + gradient ฟ้า-ม่วง |
| 11 | 6 มุมมอง + sidebar navigation + หัวข้อ/คำบรรยายต่อหน้า |
| 12 | สายการผลิตแบบ visual — การ์ดต่อ stage + ปุ่ม "run" รายขั้น |
| 13 | Log drawer สด (polling) + toast notifications + auto-refresh ทุก 8 วิ |
| 14 | รองรับ HTTP/1.1 + `do_HEAD` + flush readiness ให้ทำงานกับ launcher/preview |
| 15 | กราฟแท่งค่าใช้จ่าย 14 วัน (วาดด้วย CSS) + การ์ดสรุป |
| 16 | Responsive layout — ย่อใช้บนมือถือ/แท็บเล็ตได้ |
| 17 | ตั้งค่าจาก UI (`/api/env`) — เปลี่ยน backend/โหมด/เพดานเงิน เซฟลง .env ทันที |
| 18 | แก้บั๊ก: .env ที่บรรทัดสุดท้ายไม่มี newline ทำให้ append แล้วค่าพัง |
| 19 | จัดการ error เวลาต่อ server ไม่ได้ + สถานะปุ่ม busy + empty states สวยๆ |
| 20 | ต่อ `./ansre web` + เอกสาร + favicon/branding + ขัดเกลา UI รอบสุดท้าย |

> ทุกอย่างผ่านการทดสอบ endpoint จริง (curl) — HTML/CSS/JS + 8 API ทำงานครบ
> เปิดในเบราว์เซอร์ปกติได้ทันทีที่ `./ansre web`
