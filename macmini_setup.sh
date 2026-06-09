#!/usr/bin/env bash
# ============================================================
# ANSRE — ตั้ง Mac mini เป็น LLM server (รันสคริปต์นี้ "บน Mac mini")
#   bash macmini_setup.sh
# จะ: ติดตั้ง Ollama → เลือก+โหลดโมเดลตาม RAM → ตั้ง service launchd
#     → กันเครื่องหลับ → บอกค่าที่ต้องใส่ใน .env ของเครื่อง ANSRE
# ============================================================
set -e
echo "🖥️  ANSRE Mac mini LLM Setup"
echo "============================"

# 1) Ollama
if ! command -v ollama >/dev/null 2>&1; then
  echo "📥 ติดตั้ง Ollama..."
  if command -v brew >/dev/null 2>&1; then brew install ollama
  else echo "❌ ไม่มี brew — ติดตั้งจาก https://ollama.com แล้วรันใหม่"; exit 1; fi
fi
echo "✅ ollama: $(ollama --version 2>/dev/null | head -1)"

# 2) เลือกโมเดลตาม RAM (unified memory)
RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
echo "🧠 RAM: ${RAM_GB} GB"
if   [ "$RAM_GB" -ge 60 ]; then MODEL="qwen2.5:72b";  HEAVY="qwen2.5:72b"
elif [ "$RAM_GB" -ge 32 ]; then MODEL="qwen2.5:14b";  HEAVY="qwen2.5:32b"
elif [ "$RAM_GB" -ge 24 ]; then MODEL="qwen2.5:14b";  HEAVY="qwen2.5:14b"
else                            MODEL="qwen2.5:7b";   HEAVY="qwen2.5:7b"; fi
THAI_MODEL="scb10x/typhoon2.1-gemma3-12b"   # โมเดลไทยเฉพาะทาง
echo "📦 แนะนำ: $MODEL (heavy: $HEAVY) + $THAI_MODEL"

read -r -p "โหลดโมเดลเลยไหม? [Y/n] " ans
if [ "${ans:-y}" != "n" ]; then
  ollama pull "$MODEL"
  [ "$HEAVY" != "$MODEL" ] && ollama pull "$HEAVY" || true
  ollama pull "$THAI_MODEL" || echo "(ข้าม typhoon — โหลดเองภายหลังได้)"
fi

# 3) launchd service (เปิดให้เครื่องอื่นในบ้านเรียก: OLLAMA_HOST=0.0.0.0)
PLIST="$HOME/Library/LaunchAgents/com.ansre.ollama.plist"
OLLAMA_BIN="$(command -v ollama)"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ansre.ollama</string>
  <key>ProgramArguments</key><array><string>$OLLAMA_BIN</string><string>serve</string></array>
  <key>EnvironmentVariables</key><dict>
    <key>OLLAMA_HOST</key><string>0.0.0.0:11434</string>
    <key>OLLAMA_KEEP_ALIVE</key><string>30m</string>
    <key>OLLAMA_MAX_LOADED_MODELS</key><string>1</string>   <!-- 24GB: กันโหลด 2 โมเดลใหญ่พร้อมกัน=swap -->
    <key>OLLAMA_FLASH_ATTENTION</key><string>1</string>     <!-- เร็วขึ้น + ใช้ RAM attention น้อยลง -->
    <key>OLLAMA_KV_CACHE_TYPE</key><string>q8_0</string>    <!-- quantize KV cache → context ยาวขึ้น/swap น้อยลง -->
  </dict>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/ollama.log</string>
  <key>StandardErrorPath</key><string>/tmp/ollama.err</string>
</dict></plist>
EOF
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load -w "$PLIST"
echo "✅ ตั้ง Ollama เป็น service แล้ว (port 11434)"

# 4) กันเครื่องหลับเมื่อเสียบไฟ
sudo pmset -a sleep 0 disksleep 0 2>/dev/null && echo "✅ ตั้งไม่ให้เครื่องหลับ" || echo "⚠️  ตั้ง pmset ไม่ได้ (ต้องใช้ sudo) — ตั้งเองใน System Settings"

# 5) บอกค่าที่ต้องใส่ใน .env ของเครื่อง ANSRE
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "macmini.local")
echo ""
echo "🎉 เสร็จ! ใส่ค่านี้ใน .env ของเครื่องที่รัน ANSRE:"
echo "   LLM_BACKEND=hybrid"
echo "   LOCAL_LLM_BASE_URL=http://${IP}:11434/v1"
echo "   LOCAL_LLM_MODEL=$MODEL"
echo "   LOCAL_LLM_MODEL_HEAVY=$HEAVY"
echo ""
echo "ทดสอบจากเครื่อง ANSRE:  ./ansre local"
