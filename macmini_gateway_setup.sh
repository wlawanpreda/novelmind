#!/usr/bin/env bash
# ============================================================
# ANSRE — ตั้ง Gateway (LLM+Image HTTP service) เป็น launchd บน Mac mini
#   bash macmini_gateway_setup.sh
# ต้องรัน "บน Mac mini" ในโฟลเดอร์ repo ANSRE (มี gateway.py + .venv + .env)
# จะ: ติดตั้ง fastapi/uvicorn ใน .venv → ตั้ง launchd service (port 9000)
#     → บอกค่าที่ client ใส่ใน .env
# คู่กับ macmini_setup.sh (Ollama :11434) + macmini_image_setup.sh (ComfyUI :8188)
# ============================================================
set -e
echo "🚪 ANSRE Gateway Setup (FastAPI :9000)"
echo "======================================"

REPO="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO"
[ -f gateway.py ] || { echo "❌ ไม่เจอ gateway.py — รันในโฟลเดอร์ repo ANSRE"; exit 1; }

# 1) venv + deps
VENV="$REPO/.venv"
[ -d "$VENV" ] || python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
echo "📦 ติดตั้ง fastapi + uvicorn..."
pip install --upgrade pip >/dev/null
pip install fastapi uvicorn >/dev/null
echo "✅ deps พร้อม"

# 2) token (สุ่มถ้ายังไม่มี) — เก็บไว้ใน .env ของ Mac mini
TOKEN=$(grep -E '^ANSRE_GATEWAY_TOKEN=' .env 2>/dev/null | cut -d= -f2-)
if [ -z "$TOKEN" ]; then
  TOKEN=$(python3 -c "import secrets;print(secrets.token_hex(16))")
  echo "ANSRE_GATEWAY_TOKEN=$TOKEN" >> .env
  echo "🔑 สร้าง token ใหม่ใส่ .env แล้ว"
fi

# 3) launchd service — ฟัง 0.0.0.0:9000
PLIST="$HOME/Library/LaunchAgents/com.ansre.gateway.plist"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ansre.gateway</string>
  <key>ProgramArguments</key><array>
    <string>$VENV/bin/python</string><string>-m</string><string>uvicorn</string>
    <string>gateway:app</string>
    <string>--host</string><string>0.0.0.0</string>
    <string>--port</string><string>9000</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>EnvironmentVariables</key><dict>
    <key>ANSRE_GATEWAY_TOKEN</key><string>$TOKEN</string>
    <key>ANSRE_FREE_LLM_BEFORE_IMAGE</key><string>1</string>
    <key>ANSRE_GATEWAY_WORKERS</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/ansre_gateway.log</string>
  <key>StandardErrorPath</key><string>/tmp/ansre_gateway.err</string>
</dict></plist>
EOF
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load -w "$PLIST"
echo "✅ ตั้ง Gateway เป็น service แล้ว (port 9000)"

# 4) รอ + เช็ก
echo "⏳ รอ gateway เริ่ม..."
for i in $(seq 1 20); do
  curl -fs http://localhost:9000/healthz >/dev/null 2>&1 && break; sleep 1
done
curl -fs http://localhost:9000/healthz 2>/dev/null | python3 -m json.tool 2>/dev/null \
  && echo "✅ gateway ตอบแล้ว" || echo "⚠️  ยังไม่ตอบ — ดู: tail -f /tmp/ansre_gateway.err"

# 5) ค่าที่ client ใส่
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "macmini.local")
echo ""
echo "🎉 เสร็จ! ใส่ค่านี้ใน .env ของ client (เครื่องที่เรียก ANSRE Gateway):"
echo "   ANSRE_GATEWAY_URL=http://${IP}:9000"
echo "   ANSRE_GATEWAY_TOKEN=$TOKEN"
echo ""
echo "ทดสอบจาก client:  python3 ansre_client.py http://${IP}:9000"
