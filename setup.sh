#!/usr/bin/env bash
# ============================================================
# ANSRE one-command setup — ติดตั้งทุกอย่างให้พร้อมใช้ในคำสั่งเดียว
#   ./setup.sh
# ============================================================
set -e
cd "$(dirname "$0")"

echo "🛠️  ANSRE Setup"
echo "================"

# 1) หา Python 3.13 (requirements pin ไว้สำหรับ 3.13)
PY=""
for c in python3.13 /opt/homebrew/bin/python3.13 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    ver=$("$c" -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null || echo "0")
    if [ "$ver" = "3.13" ]; then PY="$c"; break; fi
  fi
done
if [ -z "$PY" ]; then
  echo "❌ ไม่พบ Python 3.13 — ติดตั้งก่อน:  brew install python@3.13"
  exit 1
fi
echo "✅ ใช้ Python: $PY ($($PY --version))"

# 2) สร้าง venv
if [ ! -d ".venv" ]; then
  echo "📦 สร้าง .venv ..."
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip -q
echo "✅ venv พร้อม"

# 3) ติดตั้ง dependencies
echo "📥 ติดตั้ง dependencies (อาจใช้เวลาสักครู่) ..."
.venv/bin/python -m pip install -r requirements.txt -q
echo "✅ dependencies ครบ"

# 4) สร้าง .env จากตัวอย่าง (ถ้ายังไม่มี)
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "✅ สร้าง .env แล้ว — ⚠️  ใส่ GEMINI_API_KEY และ NOTION_TOKEN ก่อนใช้งาน"
else
  echo "✅ มี .env อยู่แล้ว (ไม่ทับ)"
fi

echo ""
echo "🎉 เสร็จ! ขั้นต่อไป:"
echo "   1) แก้ .env ใส่ GEMINI_API_KEY / NOTION_TOKEN"
echo "   2) ./ansre doctor      # เช็คว่าทุกอย่างพร้อม"
echo "   3) ./ansre run         # เดิน pipeline 1 รอบ"
echo "   4) ./ansre start       # ให้รันเองต่อเนื่องทั้งวัน"
