"""
ANSRE Unified Image Provider
============================

จุดเดียวที่ทุก stage เรียก "สร้างรูป" ได้ โดยสลับ backend ได้ระหว่าง:
  - "gemini" : Google Imagen 4.0 (คุณภาพสูง, เสียค่าเงินทุกรูป) — ของเดิม
  - "local"  : ComfyUI ที่รันบน Mac mini ที่บ้าน (Stable Diffusion XL บน Metal)
               -> ฟรี ไม่จำกัดจำนวนรูป
  - "hybrid" : ลอง local ก่อน ถ้า Mac mini ดับ/พัง -> fallback ไป Imagen อัตโนมัติ

ปรัชญาเดียวกับ llm_provider.py: ตั้งค่าทั้งหมดผ่าน .env, มี auto-fallback
ให้ pipeline ไม่สะดุดเมื่อเครื่อง local ไม่พร้อม

ตั้งค่าใน .env:
  IMAGE_BACKEND        = gemini | local | hybrid   (default: gemini = ของเดิม ไม่กระทบ)
  LOCAL_IMAGE_BASE_URL = http://macmini.local:8188 (ComfyUI default port 8188)
  LOCAL_IMAGE_MODEL    = sd_xl_base_1.0.safetensors
  LOCAL_IMAGE_STEPS    = 30
  LOCAL_IMAGE_CFG      = 7.0
  LOCAL_IMAGE_NEGATIVE = "text, watermark, signature, blurry, lowres, deformed"
  LOCAL_IMAGE_TIMEOUT  = 300        (วินาที — รอ ComfyUI เรนเดอร์)

ใช้งาน:
    from image_provider import generate_image
    ok = generate_image(prompt, "cover.jpg", aspect_ratio="1:1")

CLI ทดสอบ:
    python image_provider.py --selftest                 # ComfyUI ต่อได้ไหม / มีโมเดลอะไร
    python image_provider.py --probe "a misty thai temple at dawn" -o /tmp/test.png
"""
from __future__ import annotations

import os
import io
import sys
import json
import time
import random
import urllib.request
import urllib.parse
import urllib.error

# ---------------------------------------------------------------------------
# โหลด .env (รูปแบบเดียวกับไฟล์อื่นในโปรเจกต์)
# ---------------------------------------------------------------------------
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
IMAGE_BACKEND = os.environ.get("IMAGE_BACKEND", "gemini").lower()

LOCAL_BASE_URL = os.environ.get("LOCAL_IMAGE_BASE_URL", "http://localhost:8188").rstrip("/")
LOCAL_MODEL = os.environ.get("LOCAL_IMAGE_MODEL", "sd_xl_base_1.0.safetensors")
LOCAL_STEPS = int(os.environ.get("LOCAL_IMAGE_STEPS", "30"))
LOCAL_CFG = float(os.environ.get("LOCAL_IMAGE_CFG", "7.0"))
LOCAL_SAMPLER = os.environ.get("LOCAL_IMAGE_SAMPLER", "dpmpp_2m")
LOCAL_SCHEDULER = os.environ.get("LOCAL_IMAGE_SCHEDULER", "karras")
LOCAL_NEGATIVE = os.environ.get(
    "LOCAL_IMAGE_NEGATIVE",
    "text, words, letters, watermark, signature, blurry, lowres, deformed, ugly, extra limbs",
)
LOCAL_TIMEOUT = int(os.environ.get("LOCAL_IMAGE_TIMEOUT", "300"))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "imagen-4.0-generate-001")


# แปลง aspect ratio -> ขนาดที่ SDXL ถนัด (รวมพิกเซลใกล้ 1024^2)
_SDXL_DIMS = {
    "1:1": (1024, 1024),
    "3:4": (896, 1152),
    "4:3": (1152, 896),
    "9:16": (768, 1344),
    "16:9": (1344, 768),
    "2:3": (832, 1216),
    "3:2": (1216, 832),
}


# ===========================================================================
# Local backend: ComfyUI (Stable Diffusion XL บน Mac mini)
# ===========================================================================
def _comfy_workflow(prompt: str, width: int, height: int, seed: int) -> dict:
    """สร้าง ComfyUI API-format workflow แบบ SDXL txt2img มินิมอล (base only)."""
    return {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": LOCAL_MODEL},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": LOCAL_NEGATIVE, "clip": ["4", 1]},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": LOCAL_STEPS,
                "cfg": LOCAL_CFG,
                "sampler_name": LOCAL_SAMPLER,
                "scheduler": LOCAL_SCHEDULER,
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "ansre", "images": ["8", 0]},
        },
    }


def _http_json(url: str, payload: dict | None = None, timeout: int = 30):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _comfy_ping() -> bool:
    try:
        _http_json(f"{LOCAL_BASE_URL}/system_stats", timeout=5)
        return True
    except Exception:
        return False


def _comfy_generate(prompt: str, output_path: str, aspect_ratio: str) -> bool:
    """ส่งงานเข้า ComfyUI, รอเรนเดอร์เสร็จ, ดึงรูปมาเซฟ. คืน True ถ้าสำเร็จ."""
    width, height = _SDXL_DIMS.get(aspect_ratio, _SDXL_DIMS["1:1"])
    seed = random.randint(0, 2**32 - 1)
    workflow = _comfy_workflow(prompt, width, height, seed)

    # 1) คิวงาน
    try:
        res = _http_json(f"{LOCAL_BASE_URL}/prompt", {"prompt": workflow}, timeout=30)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        print(f"    [!] ComfyUI ปฏิเสธ workflow ({e.code}): {body}")
        return False
    except Exception as e:
        print(f"    [!] ต่อ ComfyUI ไม่ได้ ({LOCAL_BASE_URL}): {e}")
        return False

    prompt_id = res.get("prompt_id")
    if not prompt_id:
        print(f"    [!] ComfyUI ไม่คืน prompt_id: {res}")
        return False
    print(f"    [*] ComfyUI กำลังเรนเดอร์ ({width}x{height}, seed={seed})...")

    # 2) poll /history จนกว่าจะเสร็จ
    deadline = time.monotonic() + LOCAL_TIMEOUT
    image_info = None
    while time.monotonic() < deadline:
        try:
            hist = _http_json(f"{LOCAL_BASE_URL}/history/{prompt_id}", timeout=15)
        except Exception:
            time.sleep(2)
            continue
        entry = hist.get(prompt_id)
        if entry and entry.get("outputs"):
            for node_out in entry["outputs"].values():
                imgs = node_out.get("images")
                if imgs:
                    image_info = imgs[0]
                    break
            if image_info:
                break
        time.sleep(2)

    if not image_info:
        print(f"    [!] ComfyUI เรนเดอร์ไม่เสร็จใน {LOCAL_TIMEOUT}s")
        return False

    # 3) ดึงไฟล์รูปผ่าน /view
    q = urllib.parse.urlencode({
        "filename": image_info["filename"],
        "subfolder": image_info.get("subfolder", ""),
        "type": image_info.get("type", "output"),
    })
    try:
        with urllib.request.urlopen(f"{LOCAL_BASE_URL}/view?{q}", timeout=60) as resp:
            img_bytes = resp.read()
    except Exception as e:
        print(f"    [!] ดึงรูปจาก ComfyUI ไม่ได้: {e}")
        return False

    _save_image_bytes(img_bytes, output_path)
    print(f"    [+] บันทึกรูป (local/ComfyUI) -> {output_path}")
    return True


def _save_image_bytes(img_bytes: bytes, output_path: str) -> None:
    """เซฟ bytes เป็นไฟล์; แปลงนามสกุลให้ตรง (ComfyUI ออกมาเป็น PNG)."""
    ext = os.path.splitext(output_path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        try:
            from PIL import Image  # type: ignore
            im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            im.save(output_path, "JPEG", quality=92)
            return
        except Exception:
            # ไม่มี Pillow -> เซฟดิบเป็น .png ข้างๆ แทน
            output_path = os.path.splitext(output_path)[0] + ".png"
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(img_bytes)


# ===========================================================================
# Cloud backend: Google Imagen (ของเดิม)
# ===========================================================================
def _gemini_generate(prompt: str, output_path: str, aspect_ratio: str) -> bool:
    if not GEMINI_API_KEY:
        print("    [!] GEMINI_API_KEY ไม่ได้ตั้ง — สร้างรูปผ่าน Imagen ไม่ได้")
        return False
    try:
        from google import genai
    except Exception as e:
        print(f"    [!] import google-genai ไม่ได้: {e}")
        return False
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        result = client.models.generate_images(
            model=GEMINI_IMAGE_MODEL,
            prompt=prompt,
            config=dict(number_of_images=1, output_mime_type="image/jpeg",
                        aspect_ratio=aspect_ratio),
        )
        if not result.generated_images:
            print("    [!] Imagen ไม่คืนรูป")
            return False
        _save_image_bytes(result.generated_images[0].image.image_bytes, output_path)
        print(f"    [+] บันทึกรูป (gemini/Imagen) -> {output_path}")
        return True
    except Exception as e:
        print(f"    [!] Imagen error: {e}")
        return False


# ===========================================================================
# Public API
# ===========================================================================
def generate_image(prompt: str, output_path: str, aspect_ratio: str = "1:1",
                   backend: str | None = None) -> bool:
    """
    สร้างรูปจาก prompt -> เซฟที่ output_path. คืน True/False.
    routing ตาม IMAGE_BACKEND (หรือ override ด้วย arg backend):
      local  -> ComfyUI เท่านั้น
      gemini -> Imagen เท่านั้น
      hybrid -> ลอง ComfyUI ก่อน, ดับ/พัง -> fallback Imagen
    """
    be = (backend or IMAGE_BACKEND).lower()

    if be == "local":
        return _comfy_generate(prompt, output_path, aspect_ratio)

    if be == "hybrid":
        if _comfy_ping():
            if _comfy_generate(prompt, output_path, aspect_ratio):
                return True
            print("    [~] ComfyUI ล้มเหลว — fallback ไป Imagen")
        else:
            print(f"    [~] ต่อ ComfyUI ({LOCAL_BASE_URL}) ไม่ได้ — fallback ไป Imagen")
        return _gemini_generate(prompt, output_path, aspect_ratio)

    # default: gemini
    return _gemini_generate(prompt, output_path, aspect_ratio)


# ===========================================================================
# CLI
# ===========================================================================
def _selftest() -> None:
    print(f"IMAGE_BACKEND = {IMAGE_BACKEND}")
    print(f"LOCAL_IMAGE_BASE_URL = {LOCAL_BASE_URL}")
    if _comfy_ping():
        print("[local ] OK — ComfyUI ตอบ /system_stats")
        try:
            info = _http_json(f"{LOCAL_BASE_URL}/object_info/CheckpointLoaderSimple", timeout=10)
            ckpts = (info.get("CheckpointLoaderSimple", {})
                         .get("input", {}).get("required", {})
                         .get("ckpt_name", [[]])[0])
            print(f"         checkpoints: {ckpts or '(ไม่พบ — ยังไม่ได้โหลดโมเดล)'}")
            if LOCAL_MODEL not in (ckpts or []):
                print(f"    [!] โมเดล '{LOCAL_MODEL}' ไม่อยู่ในรายการ — ตรวจ LOCAL_IMAGE_MODEL")
        except Exception as e:
            print(f"         (ดึงรายชื่อ checkpoint ไม่ได้: {e})")
    else:
        print(f"[local ] FAIL — ต่อ ComfyUI ที่ {LOCAL_BASE_URL} ไม่ได้")
    print(f"[gemini] {'OK — มี GEMINI_API_KEY' if GEMINI_API_KEY else 'FAIL — ไม่มี GEMINI_API_KEY'}")


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        _selftest()
        return 0
    if "--probe" in argv:
        i = argv.index("--probe")
        prompt = argv[i + 1] if i + 1 < len(argv) else "a serene thai temple at golden hour, digital art"
        out = "/tmp/ansre_probe.png"
        if "-o" in argv:
            out = argv[argv.index("-o") + 1]
        be = None
        if "--backend" in argv:
            be = argv[argv.index("--backend") + 1]
        ok = generate_image(prompt, out, aspect_ratio="1:1", backend=be)
        print("RESULT:", "OK ->" + out if ok else "FAILED")
        return 0 if ok else 1
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
