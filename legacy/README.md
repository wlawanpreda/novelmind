# 🗄️ legacy/ — สคริปต์เก่า (ถูกแทนที่แล้ว)

ไฟล์ในนี้เก็บไว้**อ้างอิง/กู้คืน**เท่านั้น — งานใหม่ให้ใช้ระบบหลักที่ root แทน

| ไฟล์เก่า | ใช้อะไรแทน |
|---------|-----------|
| `app.py` (Streamlit UI) | `dashboard.py` (`./ansre web`) |
| `agent_refiner.py` (ลูปเกลา 50 รอบ) | `ideation.py` score/refine |
| `run_iteration_loop.py` (brainstorm 50 รอบ) | `ideation.py brainstorm/auto` |
| `run_novels_complete.py` (เขียน 3 เรื่องเฉพาะ) | `agent_writer.py` + `chapter_continuer.py` |
| `write_chapters_*.py` (เขียนบทเฉพาะเรื่อง) | `chapter_continuer.py` (`./ansre continue`) |
| `notion_publisher.py` (โพสต์ Notion ครั้งเดียว) | (ฝัง Notion ใน pipeline) |
| `antigravity_novel_agent.py` (ทดลอง Google Antigravity) | `orchestrator.py` |
| `mac_ocr.py` (OCR utility) | — (ยูทิลแยก) |

## การรัน
ไฟล์เหล่านี้มี path-bootstrap ให้ import โมดูลที่ root ได้ — รันจาก **repo root**:
```bash
.venv/bin/python legacy/agent_refiner.py
```
> ⚠️ บางสคริปต์ hardcode ชื่อเรื่อง/พาธไว้ (เช่น `novel_draft.md` ที่ย้ายมาอยู่ใน legacy/ ด้วย) อาจต้องปรับพาธก่อนใช้
