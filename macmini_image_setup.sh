#!/usr/bin/env bash
# ============================================================
# ANSRE — ตั้ง Mac mini เป็น "Image-gen server" ฟรี (รัน "บน Mac mini")
#   bash macmini_image_setup.sh
# จะ: ติดตั้ง ComfyUI (Stable Diffusion XL บน Metal/MPS) → โหลดโมเดล SDXL
#     → ตั้ง launchd service (port 8188) → บอกค่าที่ต้องใส่ใน .env ของเครื่อง ANSRE
#
# คู่กับ macmini_setup.sh (ตัวนั้นทำ LLM/Ollama, ตัวนี้ทำรูป) — รันคนละ port อยู่ร่วมกันได้
# ============================================================
set -e
echo "🖼️  ANSRE Mac mini Image-gen Setup (ComfyUI + SDXL)"
echo "=================================================="

# 0) ต้องเป็น Apple Silicon ถึงจะเร็ว (Metal/MPS)
ARCH=$(uname -m)
[ "$ARCH" = "arm64" ] || echo "⚠️  เครื่องนี้ไม่ใช่ Apple Silicon ($ARCH) — จะช้ามาก"

# 1) เครื่องมือพื้นฐาน (git + python3)
command -v git >/dev/null 2>&1 || { echo "📥 ติดตั้ง git..."; brew install git; }
PY=$(command -v python3 || true)
[ -n "$PY" ] || { echo "📥 ติดตั้ง python..."; brew install python; PY=$(command -v python3); }
echo "✅ python: $($PY --version)"

# 2) วาง ComfyUI ไว้ที่ ~/ComfyUI
COMFY_DIR="$HOME/ComfyUI"
if [ ! -d "$COMFY_DIR" ]; then
  echo "📥 clone ComfyUI -> $COMFY_DIR"
  git clone https://github.com/comfyanonymous/ComfyUI "$COMFY_DIR"
else
  echo "✅ มี ComfyUI อยู่แล้ว ($COMFY_DIR) — ดึงอัปเดต"
  git -C "$COMFY_DIR" pull --ff-only || true
fi

# 3) virtualenv + deps (PyTorch รุ่น MPS ใช้ได้เลยจาก wheel ปกติ)
VENV="$COMFY_DIR/.venv"
[ -d "$VENV" ] || "$PY" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
echo "📦 ติดตั้ง PyTorch + ComfyUI deps (ครั้งแรกใช้เวลาหน่อย)..."
pip install --upgrade pip >/dev/null
pip install torch torchvision torchaudio >/dev/null
pip install -r "$COMFY_DIR/requirements.txt" >/dev/null
echo "✅ deps พร้อม"

# 4) โหลดโมเดล SDXL base 1.0 (~6.9GB) เข้า models/checkpoints
CKPT_DIR="$COMFY_DIR/models/checkpoints"
mkdir -p "$CKPT_DIR"
CKPT="$CKPT_DIR/sd_xl_base_1.0.safetensors"
if [ ! -f "$CKPT" ]; then
  echo "📥 โหลด SDXL base 1.0 (~6.9GB) — โหลดครั้งเดียว..."
  curl -L --fail -o "$CKPT" \
    "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors?download=true" \
    || { echo "❌ โหลดโมเดลไม่สำเร็จ — โหลดเองวางที่ $CKPT_DIR แล้วรันใหม่"; exit 1; }
else
  echo "✅ มีโมเดล SDXL อยู่แล้ว"
fi
echo "✅ checkpoint: $(basename "$CKPT")"

# 5) launchd service — ฟัง 0.0.0.0:8188 ให้เครื่องอื่นในบ้านเรียกได้
PLIST="$HOME/Library/LaunchAgents/com.ansre.comfyui.plist"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ansre.comfyui</string>
  <key>ProgramArguments</key><array>
    <string>$VENV/bin/python</string>
    <string>$COMFY_DIR/main.py</string>
    <string>--listen</string><string>0.0.0.0</string>
    <string>--port</string><string>8188</string>
  </array>
  <key>WorkingDirectory</key><string>$COMFY_DIR</string>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/comfyui.log</string>
  <key>StandardErrorPath</key><string>/tmp/comfyui.err</string>
</dict></plist>
EOF
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load -w "$PLIST"
echo "✅ ตั้ง ComfyUI เป็น service แล้ว (port 8188)"

# 6) กันเครื่องหลับเมื่อเสียบไฟ (เหมือน LLM service)
sudo pmset -a sleep 0 disksleep 0 2>/dev/null && echo "✅ ตั้งไม่ให้เครื่องหลับ" || echo "⚠️  ตั้ง pmset ไม่ได้ (ต้องใช้ sudo) — ตั้งเองใน System Settings"

# 7) รอ service ขึ้น แล้วเช็ก
echo "⏳ รอ ComfyUI เริ่ม..."
for i in $(seq 1 30); do
  curl -fs http://localhost:8188/system_stats >/dev/null 2>&1 && break
  sleep 2
done
curl -fs http://localhost:8188/system_stats >/dev/null 2>&1 \
  && echo "✅ ComfyUI ตอบแล้ว (http://localhost:8188)" \
  || echo "⚠️  ยังไม่ตอบ — ดู log: tail -f /tmp/comfyui.err"

# 8) บอกค่าที่ต้องใส่ใน .env ของเครื่อง ANSRE
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "macmini.local")
echo ""
echo "🎉 เสร็จ! ใส่ค่านี้ใน .env ของเครื่องที่รัน ANSRE:"
echo "   IMAGE_BACKEND=hybrid"
echo "   LOCAL_IMAGE_BASE_URL=http://${IP}:8188"
echo "   LOCAL_IMAGE_MODEL=sd_xl_base_1.0.safetensors"
echo ""
echo "ทดสอบจากเครื่อง ANSRE:"
echo "   python3 image_provider.py --selftest"
echo "   python3 image_provider.py --probe \"a serene thai temple at dawn, cinematic\" -o /tmp/test.png --backend local"
