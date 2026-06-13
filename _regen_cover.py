import os

# Load .env exactly like cover_generator.py (so netcfg can route LAN->Tailscale)
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

from image_provider import generate_image, IMAGE_BACKEND, GATEWAY_URL

COVERS = "SecondBrain/05_Active_Projects/Covers"
BASE = "ระบบความเกรงใจ_คุณจะปากแจ๋วได้กี่เลเวล"
out_png = os.path.join(COVERS, f"{BASE}_Cover.png")

# พราวรวี (พราว) — 28, นักการตลาดสาวออฟฟิศ มั่นใจ ปากแจ๋ว สายแซ่บ วาจาคมคาย
# โทนคอเมดี้โรแมนซ์สมัยใหม่ — ไม่มีตัวอักษรบนรูป
prompt = (
    "Book cover illustration, a single confident stylish Thai woman in her late twenties, "
    "modern office marketing professional, beautiful and chic, sassy self-assured expression "
    "with a playful smirk and one eyebrow raised, glossy bold lipstick, polished modern makeup, "
    "long sleek dark hair, wearing a fashionable tailored business blazer, bold confident pose "
    "with arms crossed or hand on hip, witty and quick-tongued vibe, "
    "sleek modern Bangkok office background with glass walls and a bright city skyline, "
    "vibrant colorful palette, bright clean cinematic lighting, romantic comedy mood, "
    "playful bold and glamorous, high quality digital art, book cover style, highly detailed, "
    "portrait composition, no text, no words, no letters, no watermark"
)

print(f"IMAGE_BACKEND={IMAGE_BACKEND}  GATEWAY_URL={GATEWAY_URL}")
print(f"[*] generating -> {out_png}")
ok = generate_image(prompt, out_png, aspect_ratio="1:1")
print("RESULT:", ok, "exists:", os.path.exists(out_png),
      "size:", os.path.getsize(out_png) if os.path.exists(out_png) else 0)
