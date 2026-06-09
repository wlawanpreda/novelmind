# ============================================================
# ANSRE — Makefile (ครอบทั้งระบบ)
#   make            แสดงคำสั่งทั้งหมด
#   make setup      ติดตั้งทุกอย่าง
#   make run        เดิน pipeline 1 รอบ
#   ส่ง args ได้ เช่น  make idea ARGS="brainstorm 3"
# ============================================================
PY    := .venv/bin/python
ANSRE := ./ansre
SB    := ./SecondBrain
ARGS  ?=

.DEFAULT_GOAL := help

# ---------- Setup / ติดตั้ง ----------
.PHONY: setup install reinstall env
setup: ## ติดตั้งทุกอย่าง (venv + deps + .env)  [ทำครั้งเดียว]
	@bash setup.sh

install: ## ลง dependencies เข้า venv ที่มีอยู่
	@$(PY) -m pip install -r requirements.txt

reinstall: ## ลบ venv แล้วติดตั้งใหม่ทั้งหมด
	@rm -rf .venv && bash setup.sh

env: ## สร้าง .env จากตัวอย่าง (ถ้ายังไม่มี)
	@test -f .env || cp .env.example .env && echo "พร้อมแล้ว — แก้ .env ใส่ GEMINI_API_KEY/NOTION_TOKEN"

# ---------- สถานะ / สุขภาพ ----------
.PHONY: doctor status usage selftest local gateway
doctor: ## 🩺 เช็คสุขภาพระบบ (ขาดอะไร + วิธีแก้)
	@$(ANSRE) doctor

status: ## 📊 งานค้างแต่ละขั้น + ผลผลิต + ค่าใช้จ่าย
	@$(ANSRE) status

usage: ## 💰 ดูค่า token/cost วันนี้
	@$(ANSRE) usage

selftest: ## เช็คว่า LLM backend (Gemini/local) ต่อได้
	@$(ANSRE) selftest

local: ## 🖥️ เช็ค + เบนช์มาร์ก Mac mini local LLM
	@$(ANSRE) local

gateway: ## 🚪 เช็ค/เปิด LLM+Image gateway — make gateway ARGS="serve"
	@$(ANSRE) gateway $(ARGS)

# ---------- เดินระบบ ----------
.PHONY: run loop start stop web pipeline
run: ## เดิน pipeline 1 รอบ
	@$(ANSRE) run

loop: ## เดิน pipeline วนต่อเนื่อง (Ctrl-C หยุด)
	@$(ANSRE) run --loop

start: ## ▶ เปิด worker อัตโนมัติ (launchd, ทุก 20 นาที)
	@$(ANSRE) start

stop: ## ■ ปิด worker อัตโนมัติ
	@$(ANSRE) stop

web: ## 🌐 เปิด web dashboard (http://localhost:8765)
	@$(ANSRE) web

pipeline: ## เดินทุก stage เรียงกัน (scout→...→teaser)
	@$(ANSRE) pipeline

# ---------- ไอเดีย ----------
.PHONY: idea brainstorm ideas auto
idea: ## คลังไอเดีย — make idea ARGS="add ..." / "promote <id>"
	@$(ANSRE) idea $(ARGS)

brainstorm: ## ให้ AI คิดไอเดียใหม่ — make brainstorm ARGS="5"
	@$(ANSRE) idea brainstorm $(ARGS)

ideas: ## แสดงคลังไอเดียเรียงตามคะแนน
	@$(ANSRE) idea list

auto: ## รัน ideation อัตโนมัติเต็มวงจร (คิด→score→promote)
	@$(ANSRE) idea auto

# ---------- Studio (prompt ภาพ/วิดีโอ, loop) ----------
.PHONY: studio visual video
studio: ## studio engine — make studio ARGS="visual <title>"
	@$(ANSRE) studio $(ARGS)
visual: ## prompt ภาพตัวละคร/ฉาก — make visual ARGS="<title>"
	@$(ANSRE) studio visual $(ARGS)
video: ## prompt วิดีโอ/Google Flow — make video ARGS="<title>"
	@$(ANSRE) studio video $(ARGS)

# ---------- pipeline ทีละขั้น ----------
.PHONY: scout analyze write continue cover audio teaser publish
scout: ## ดึง trending novels
	@$(ANSRE) scout $(ARGS)
analyze: ## วิเคราะห์ novels ที่ scout มา (สกัดจุดเด่น/hook/adapt)
	@$(ANSRE) analyze
trends: ## 📈 สรุปเทรนด์ตลาด → คำแนะนำเรื่องต่อไป
	@$(ANSRE) trends
feedback: ## 🏆 เรียนรู้จากผลงานจริง (Phase 5) — make feedback ARGS="record '...' --views N"
	@$(ANSRE) feedback $(ARGS)
write: ## เขียนนิยาย (6-stage) จากที่ analyze แล้ว
	@$(ANSRE) write
continue: ## เขียนตอนถัดไป — make continue ARGS="2 --title ป้า"
	@$(ANSRE) continue $(ARGS)
cover: ## สร้างปก (Imagen)
	@$(ANSRE) cover
audio: ## ทำหนังสือเสียง (TTS)
	@$(ANSRE) audio
teaser: ## ตัดวิดีโอ teaser (FFmpeg)
	@$(ANSRE) teaser
publish: ## เผยแพร่ teaser → YouTube/TikTok/คิวนิยาย
	@$(ANSRE) publish

# ---------- Dev / ดูแลโค้ด ----------
.PHONY: check test clean clean-tasks tree
check: ## compile-check ทุกไฟล์ .py (root + legacy + scraper)
	@$(PY) -m py_compile *.py legacy/*.py scraper/*.py && echo "✅ ทุกไฟล์ compile ผ่าน"

test: ## รัน test ทั้งหมด (hermetic, ศูนย์ค่าใช้จ่าย)
	@for t in test_gateway_e2e.py test_phase2_routing.py test_gateway_http_e2e.py test_singleflight.py; do \
		$(PY) $$t >/tmp/_ansre_test.out 2>&1 && echo "✅ $$t" || { echo "❌ $$t"; tail -8 /tmp/_ansre_test.out; }; \
	done; rm -f /tmp/_ansre_test.out

clean: ## ลบ __pycache__ / ไฟล์ชั่วคราว
	@find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null; true
	@echo "🧹 ลบ __pycache__ แล้ว"

clean-tasks: ## ล้าง log งาน background ของ dashboard
	@rm -rf $(SB)/.tasks && echo "🧹 ล้าง task logs แล้ว"

tree: ## แสดงโครงสร้างไฟล์ (ไม่รวมข้อมูล/venv)
	@ls -1 *.py 2>/dev/null | sed 's/^/  core: /'; echo "  docs/ legacy/ web/ deploy/ scraper/"

# ---------- Mac mini (รันสคริปต์นี้บน Mac mini) ----------
.PHONY: macmini
macmini: ## พิมพ์วิธีตั้ง Mac mini (รันบนเครื่อง Mac mini เอง)
	@echo "บน Mac mini รัน:  bash macmini_setup.sh   (ดู docs/MACMINI_SETUP.md)"

# ---------- Help ----------
.PHONY: help
help: ## แสดงคำสั่งทั้งหมด
	@echo ""
	@echo "  ANSRE — โรงงานผลิตนิยายอัตโนมัติ | make <target>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  ส่ง args:  make idea ARGS=\"brainstorm 3\""
	@echo ""
