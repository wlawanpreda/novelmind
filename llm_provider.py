"""
ANSRE Unified LLM Provider
==========================

จุดเดียวที่ทุก stage เรียกใช้ LLM ได้ โดยสลับ backend ได้ระหว่าง:
  - "gemini" : Google Gemini (คุณภาพสูง, เสียค่า token)
  - "local"  : LLM ที่รันบน Mac mini ที่บ้านผ่าน OpenAI-compatible API
               (Ollama / LM Studio / llama.cpp server) -> ฟรี ไม่จำกัด token

ปรัชญาออกแบบ: ใช้ "บทบาท (role)" ของงานเป็นตัวตัดสินว่าจะส่งไป backend ไหน
งานปริมาณมาก/ทนคุณภาพรองได้ (วิเคราะห์, วางฉาก, รีวิว, brainstorm) -> local เพื่อประหยัด
งานคุณภาพคอขาด (เขียนร้อยแก้ว, เกลาสำนวน) -> gemini เพื่อรักษาคุณภาพ

ตั้งค่าทั้งหมดผ่าน .env:
  LLM_BACKEND          = gemini | local | hybrid   (default: gemini = ของเดิม ไม่กระทบ)
  LOCAL_LLM_BASE_URL   = http://macmini.local:11434/v1   (Ollama default port 11434)
  LOCAL_LLM_MODEL      = qwen2.5:14b
  LOCAL_LLM_MODEL_HEAVY= qwen2.5:32b   (ถ้ามี ใช้กับ role งานหนัก)
  LOCAL_LLM_API_KEY    = ollama        (Ollama/LM Studio ไม่เช็คค่านี้)
  WRITING_MODE         = master | premium | draft  (ใช้กับ gemini เหมือนเดิม)
  LLM_ROLE_<ROLE>      = gemini | local             (override รายบทบาท เช่น LLM_ROLE_WRITER=gemini)

ใช้งาน:
    from llm_provider import generate
    text = generate(prompt, role="analyzer", is_json=True)

CLI ทดสอบ:
    python llm_provider.py --selftest          # ตรวจว่าทั้ง 2 backend ต่อได้ไหม
    python llm_provider.py --probe "สวัสดี" --role writer
"""
from __future__ import annotations

import os
import re
import sys
import json
import time
from datetime import datetime
from contextlib import contextmanager

try:
    import fcntl as _fcntl  # POSIX (macOS/Linux) — ใช้ทำ cross-process lock
except ImportError:
    _fcntl = None  # Windows: ไม่มี flock → ตกไปใช้ pacing แบบ per-process

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

# LAN-first / Tailscale-fallback: resolve URL Mac mini ให้ใช้ตัวที่ต่อได้ (ก่อนอ่าน config ด้านล่าง)
# ครอบ image ด้วย เพราะ cover_generator import llm_provider ก่อน image_provider
try:
    import netcfg as _netcfg  # apply() รันตอน import → เขียน os.environ[*_URL] ที่ต่อได้
except Exception:
    _netcfg = None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LLM_BACKEND = os.environ.get("LLM_BACKEND", "gemini").lower()
WRITING_MODE = os.environ.get("WRITING_MODE", "premium").lower()

LOCAL_BASE_URL = os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
LOCAL_MODEL = os.environ.get("LOCAL_LLM_MODEL", "qwen2.5:14b")
LOCAL_MODEL_HEAVY = os.environ.get("LOCAL_LLM_MODEL_HEAVY", LOCAL_MODEL)
LOCAL_API_KEY = os.environ.get("LOCAL_LLM_API_KEY", "ollama")
LOCAL_TIMEOUT = int(os.environ.get("LOCAL_LLM_TIMEOUT", "600"))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Phase 2: ถ้าตั้ง ANSRE_GATEWAY_URL จะ route ผ่าน gateway (มี fallback ทำเองในเครื่อง) ---
# ANSRE_GATEWAY_INTERNAL=1 = กระบวนการ gateway เอง → ทำเองตรง ไม่วนกลับ (กัน recursion)
GATEWAY_URL = os.environ.get("ANSRE_GATEWAY_URL", "").rstrip("/")
GATEWAY_TOKEN = os.environ.get("ANSRE_GATEWAY_TOKEN", "")
_INTERNAL = os.environ.get("ANSRE_GATEWAY_INTERNAL") == "1"
_USE_GATEWAY = bool(GATEWAY_URL) and not _INTERNAL

# บทบาทที่ต้องใช้ "โมเดลหนัก" ฝั่ง local (งานสร้างสรรค์ร้อยแก้ว)
_HEAVY_ROLES = {"writer", "enhancer", "outline"}

# Routing เริ่มต้นสำหรับโหมด hybrid: คุมคุณภาพร้อยแก้วไว้ที่ gemini, ที่เหลือไป local
# ปรับได้ด้วย env LLM_ROLE_<ROLE>
_HYBRID_DEFAULT = {
    # --- งานคุณภาพคอขาด -> gemini ---
    "writer": "gemini",
    "enhancer": "gemini",
    # --- งานปริมาณมาก ทนคุณภาพรองได้ -> local (ประหยัด) ---
    "analyzer": "local",
    "outline": "local",
    "characters": "local",
    "scene_planner": "local",
    "planner": "local",        # agent_writer stage name
    "audio_script": "local",
    "audio": "local",          # agent_writer stage name
    "reviewer": "local",
    "researcher": "local",
    "editor": "local",
    "evaluator": "local",
    "brainstorm": "local",
    "ideation": "local",
    "visual": "local",
    "video": "local",
    "default": "local",
}


# ---------------------------------------------------------------------------
# Cost / token tracking (Phase 3) — กัน Gemini ค่าบาน + ดู usage ย้อนหลังได้
# ---------------------------------------------------------------------------
USAGE_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SecondBrain", "llm_usage.jsonl")
# เพดานค่าใช้จ่าย Gemini ต่อวัน (USD); 0 = ไม่จำกัด. เกินแล้วจะ reroute ไป local อัตโนมัติ (soft)
DAILY_USD_CAP = float(os.environ.get("ANSRE_DAILY_USD_CAP", "0") or 0)
# เพดานแข็ง (hard) ต่อวัน (USD); 0 = ไม่จำกัด. เกินแล้ว pipeline หยุดทั้งรอบ + แจ้งเตือน
DAILY_HARD_CAP = float(os.environ.get("ANSRE_DAILY_HARD_CAP", "0") or 0)


def budget_status() -> dict:
    """สถานะงบวันนี้: ใช้ไปเท่าไร · เพดาน soft/hard · แตะเพดานหรือยัง"""
    spent = today_spend_usd()
    return {
        "spent": round(spent, 4),
        "soft_cap": DAILY_USD_CAP,
        "hard_cap": DAILY_HARD_CAP,
        "over_soft": bool(DAILY_USD_CAP and spent >= DAILY_USD_CAP),
        "over_hard": bool(DAILY_HARD_CAP and spent >= DAILY_HARD_CAP),
        "pct_hard": round(spent / DAILY_HARD_CAP * 100, 1) if DAILY_HARD_CAP else None,
        "pct_soft": round(spent / DAILY_USD_CAP * 100, 1) if DAILY_USD_CAP else None,
    }

# ราคาโดยประมาณ (USD ต่อ 1M tokens) = (input, output) — ปรับให้ตรงบิลจริงได้
PRICING = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.0),
}


def _record_usage(backend: str, role: str, model: str, in_tok: int, out_tok: int) -> float:
    cost = 0.0
    if backend == "gemini":
        pin, pout = PRICING.get(model, (0.0, 0.0))
        cost = in_tok / 1e6 * pin + out_tok / 1e6 * pout
    now = datetime.now()
    entry = {
        "ts": now.isoformat(timespec="seconds"),
        "date": now.strftime("%Y-%m-%d"),
        "backend": backend, "role": role, "model": model,
        "in_tokens": int(in_tok), "out_tokens": int(out_tok),
        "est_usd": round(cost, 6),
    }
    try:
        os.makedirs(os.path.dirname(USAGE_LOG), exist_ok=True)
        with open(USAGE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return cost


def today_spend_usd() -> float:
    if not os.path.exists(USAGE_LOG):
        return 0.0
    today = datetime.now().strftime("%Y-%m-%d")
    total = 0.0
    try:
        with open(USAGE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if e.get("date") == today:
                        total += e.get("est_usd", 0.0)
                except Exception:
                    continue
    except Exception:
        pass
    return total


def resolve_backend(role: str) -> str:
    """ตัดสินว่า role นี้จะวิ่งไป backend ไหน"""
    # 1) override รายบทบาทผ่าน env ชนะทุกอย่าง
    override = os.environ.get(f"LLM_ROLE_{role.upper()}")
    if override:
        return override.lower()
    # 2) โหมดบังคับทั้งระบบ
    if LLM_BACKEND in ("gemini", "local"):
        return LLM_BACKEND
    # 3) hybrid: ใช้ตาราง routing
    return _HYBRID_DEFAULT.get(role, _HYBRID_DEFAULT["default"])


def gemini_model_for_role(role: str) -> str:
    """แมป role -> ชื่อรุ่น Gemini (คงตรรกะเดิมจาก agent_writer.get_model)"""
    if WRITING_MODE == "master":
        return "gemini-2.5-pro"
    if WRITING_MODE == "premium":
        # matches the original agent_writer.get_model: only prose stages use pro
        return "gemini-2.5-pro" if role in ("writer", "enhancer") else "gemini-2.5-flash"
    return "gemini-2.5-flash"  # draft


def local_model_for_role(role: str) -> str:
    return LOCAL_MODEL_HEAVY if role in _HEAVY_ROLES else LOCAL_MODEL


# ---------------------------------------------------------------------------
# Circuit breaker — กัน Gemini โดน throttle แล้ว hammer ซ้ำ (เจอ empty-storm 2026-06-08)
# ---------------------------------------------------------------------------
GEMINI_FAIL_THRESHOLD = int(os.environ.get("GEMINI_FAIL_THRESHOLD", "3") or 3)
GEMINI_COOLDOWN_SEC = int(os.environ.get("GEMINI_COOLDOWN_SEC", "120") or 120)
_gemini_fail_streak = 0
_gemini_cooldown_until = 0.0

# Auto-pacing: เว้นจังหวะขั้นต่ำระหว่างการเรียก Gemini (กัน rate-limit/throttle)
# 0 = ปิด (ค่า default). แนะนำ ~6-8 วิ ถ้าผลิตจำนวนมากโดยยังไม่มี Mac mini local
CALL_GAP = float(os.environ.get("ANSRE_CALL_GAP", "0") or 0)
_last_gemini_call = 0.0


def _pace_gemini():
    """หน่วงให้ห่างจากการเรียก Gemini ครั้งก่อนอย่างน้อย CALL_GAP วินาที (local ไม่ต้อง — ไม่มี limit)"""
    global _last_gemini_call
    if CALL_GAP <= 0:
        return
    elapsed = time.time() - _last_gemini_call
    if 0 < elapsed < CALL_GAP:
        wait = CALL_GAP - elapsed
        print(f"[llm] pacing: รอ {wait:.1f}s กัน Gemini rate-limit")
        time.sleep(wait)
    _last_gemini_call = time.time()


# --- Single-flight cross-process lock ---------------------------------------
# ปัญหา: หลาย ANSRE process (worker อัตโนมัติ + งาน manual) ยิง Gemini พร้อมกัน
#        → ชนโควต้า/throttle จน "empty response" รัวๆ
# แก้: อนุญาตให้มี Gemini call ในอากาศได้ "ทีละ 1 ทั้งเครื่อง" (single-flight)
#     + เว้นจังหวะ (CALL_GAP) แบบแชร์ timestamp ข้าม process ผ่านไฟล์ล็อก
# ปิดได้ด้วย ANSRE_LLM_SINGLEFLIGHT=0 · เฉพาะ Gemini (local ปล่อยขนานได้ ไม่มี limit ฝั่งเรา)
SINGLEFLIGHT = os.environ.get("ANSRE_LLM_SINGLEFLIGHT", "1").lower() in ("1", "true", "yes", "on")
_LOCK_PATH = os.environ.get("ANSRE_LLM_LOCK") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "SecondBrain", ".llm_gemini.lock")
_LOCK_WAIT_MAX = float(os.environ.get("ANSRE_LLM_LOCK_TIMEOUT", "300") or 300)


@contextmanager
def _gemini_gate():
    """ยอมให้ Gemini call ทีละ 1 ทั้งเครื่อง + pacing ร่วมกันข้าม process.
    ถ้าปิด SINGLEFLIGHT หรือไม่มี fcntl → ใช้ pacing เดิม (per-process)."""
    if not SINGLEFLIGHT or _fcntl is None:
        _pace_gemini()
        yield
        return
    try:
        os.makedirs(os.path.dirname(_LOCK_PATH), exist_ok=True)
        f = open(_LOCK_PATH, "a+")
    except Exception:
        _pace_gemini()
        yield
        return
    locked = False
    try:
        deadline = time.time() + _LOCK_WAIT_MAX
        announced = False
        while True:
            try:
                _fcntl.flock(f, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                locked = True
                break
            except OSError:
                if not announced:
                    print("[llm] single-flight: รอคิว Gemini (process อื่นกำลังเรียกอยู่)...")
                    announced = True
                if time.time() > deadline:
                    print("[llm] single-flight: รอเกินเวลา — ดำเนินต่อโดยไม่ล็อก")
                    break
                time.sleep(0.25)
        # cross-process pacing: อ่าน timestamp ครั้งล่าสุดจากไฟล์ล็อก
        if CALL_GAP > 0:
            try:
                f.seek(0)
                raw = f.read().strip()
                last = float(raw) if raw else 0.0
            except Exception:
                last = 0.0
            elapsed = time.time() - last
            if 0 < elapsed < CALL_GAP:
                wait = CALL_GAP - elapsed
                print(f"[llm] pacing(ร่วม): รอ {wait:.1f}s กัน Gemini rate-limit")
                time.sleep(wait)
        yield
    finally:
        # บันทึก timestamp ล่าสุดลงไฟล์ล็อก (ให้ process ถัดไปเว้นจังหวะถูก) แล้วปลดล็อก
        try:
            f.seek(0)
            f.truncate()
            f.write(str(time.time()))
            f.flush()
        except Exception:
            pass
        if locked:
            try:
                _fcntl.flock(f, _fcntl.LOCK_UN)
            except Exception:
                pass
        try:
            f.close()
        except Exception:
            pass


def _reset_gemini_streak():
    global _gemini_fail_streak
    _gemini_fail_streak = 0


def _note_gemini_failure():
    """นับความล้มเหลวต่อเนื่องของ Gemini; ถึงเกณฑ์แล้วเปิด cooldown ให้ reroute ไป local"""
    global _gemini_fail_streak, _gemini_cooldown_until
    _gemini_fail_streak += 1
    if _gemini_fail_streak >= GEMINI_FAIL_THRESHOLD:
        _gemini_cooldown_until = time.time() + GEMINI_COOLDOWN_SEC
        _gemini_fail_streak = 0
        print(f"[llm] ⚡ gemini ล้มต่อเนื่อง {GEMINI_FAIL_THRESHOLD} ครั้ง → พัก {GEMINI_COOLDOWN_SEC}s, "
              f"reroute ไป local ชั่วคราว")


def gemini_in_cooldown():
    return time.time() < _gemini_cooldown_until


# ---------------------------------------------------------------------------
# Backend: Gemini
# ---------------------------------------------------------------------------
_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY ไม่ได้ตั้งค่า แต่ route ไปยัง backend 'gemini'")
        from google import genai  # lazy import
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


def _gemini_generate(prompt, role, is_json, temperature, system):
    from google.genai import types  # lazy import
    client = _get_gemini_client()
    model = gemini_model_for_role(role)

    safety = [
        types.SafetySetting(category=c, threshold=types.HarmBlockThreshold.BLOCK_NONE)
        for c in (
            types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        )
    ]
    cfg_kwargs = {
        "safety_settings": safety,
        "response_mime_type": "application/json" if is_json else "text/plain",
    }
    if temperature is not None:
        cfg_kwargs["temperature"] = temperature
    if system:
        cfg_kwargs["system_instruction"] = system
    config = types.GenerateContentConfig(**cfg_kwargs)

    last_err = None
    for attempt in range(1, 4):
        try:
            # single-flight: ล็อกเฉพาะช่วงยิง API จริง (ไม่ถือยาวข้าม retry) + pacing ร่วม
            with _gemini_gate():
                resp = client.models.generate_content(model=model, contents=prompt, config=config)
            um = getattr(resp, "usage_metadata", None)
            in_tok = getattr(um, "prompt_token_count", 0) or 0
            out_tok = getattr(um, "candidates_token_count", 0) or 0
            _record_usage("gemini", role, model, in_tok, out_tok)
            if resp.text:
                _reset_gemini_streak()
                return resp.text
            print(f"[llm:gemini] empty response (attempt {attempt}/3), retrying...")
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"[llm:gemini] error (attempt {attempt}/3): {e}")
        time.sleep(2 * attempt)
    # ล้มทุก attempt (error หรือ empty) → นับ streak + raise เพื่อให้ fallback ไป local ทำงาน
    _note_gemini_failure()
    raise last_err if last_err else RuntimeError("gemini ตอบว่าง (อาจโดน throttle/safety)")


# ---------------------------------------------------------------------------
# Backend: Local (OpenAI-compatible: Ollama / LM Studio / llama.cpp)
# ---------------------------------------------------------------------------
def _local_generate(prompt, role, is_json, temperature, system):
    import requests  # already a project dependency
    model = local_model_for_role(role)
    url = f"{LOCAL_BASE_URL}/chat/completions"

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.8 if temperature is None else temperature,
        # สำคัญ: Ollama default num_predict = 128 token → output ถูกตัดสั้น ต้องตั้งให้ยาวพอ
        "max_tokens": int(os.environ.get("LOCAL_LLM_MAX_TOKENS", "4096")),
        "stream": False,
    }
    if is_json:
        # รองรับทั้ง LM Studio และ Ollama เวอร์ชันใหม่
        payload["response_format"] = {"type": "json_object"}

    headers = {"Authorization": f"Bearer {LOCAL_API_KEY}", "Content-Type": "application/json"}

    last_err = None
    delay = 3
    for attempt in range(1, 4):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=LOCAL_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                if is_json:
                    content = _coerce_json(content)
                return content
            last_err = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            print(f"[llm:local] {last_err} (attempt {attempt}/3)")
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"[llm:local] error (attempt {attempt}/3): {e}")
        time.sleep(delay)
        delay *= 2
    raise last_err if last_err else RuntimeError("local backend failed")


def _coerce_json(text: str) -> str:
    """โมเดล local บางตัวห่อ JSON ด้วย ```json ... ``` หรือมีข้อความนำ ดึงเฉพาะ JSON ออกมา"""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    # หา object/array ก้อนแรก
    for opener, closer in (("{", "}"), ("[", "]")):
        start = t.find(opener)
        end = t.rfind(closer)
        if start != -1 and end != -1 and end > start:
            candidate = t[start : end + 1]
            try:
                json.loads(candidate)
                return candidate
            except Exception:
                continue
    return t


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate(prompt: str, role: str = "default", is_json: bool = False,
             temperature=None, system: str = None,
             fallback: bool = True) -> str:
    """
    สร้างข้อความจาก LLM โดยเลือก backend ตาม role อัตโนมัติ

    fallback=True : ถ้า backend ที่เลือกล้ม จะ fallback ไปอีก backend หนึ่งให้ (กัน pipeline สะดุด)

    ถ้าตั้ง ANSRE_GATEWAY_URL: ส่งผ่าน gateway ก่อน, ล่ม -> fallback ทำเองในเครื่อง (ตรรกะเดิม)
    """
    if _USE_GATEWAY:
        try:
            return _via_gateway_llm(prompt, role, is_json, temperature, system)
        except Exception as e:  # noqa: BLE001
            print(f"[llm] gateway ล้มเหลว ({e}); fallback -> ทำเองในเครื่อง")
    return _generate_direct(prompt, role, is_json, temperature, system, fallback)


def _via_gateway_llm(prompt, role, is_json, temperature, system) -> str:
    """ส่ง prompt ไป ANSRE Gateway (ใช้ SDK บางๆ)."""
    from ansre_client import Ansre
    return Ansre(GATEWAY_URL, GATEWAY_TOKEN).llm(
        prompt, role=role, system=system, is_json=is_json, temperature=temperature)


# --- Auto-route #34: ตรวจ output ที่ "ควรเป็นไทย" แต่ Gemini drift หลุดเป็นภาษาอื่น ---
# (เคสจริง: บทเสียงวิญญาณฯ ออกมาเป็นจีน/เกาหลี — non-empty เลยไม่เข้า fallback เดิม)
_THAI_ROLES = {"writer", "enhancer", "outline", "characters", "audio_script", "audio",
               "planner", "scene_planner", "reviewer", "editor", "brainstorm",
               "ideation", "researcher", "evaluator", "default"}
_CJK_RE = re.compile(r"[一-鿿가-힯぀-ヿ]")   # จีน/เกาหลี/ญี่ปุ่น
_THAI_RE = re.compile(r"[฀-๿]")


def _looks_garbled(text: str, role: str, is_json: bool) -> bool:
    """ผลลัพธ์เพี้ยนไหม: role ที่ควรเป็นไทย แต่มีอักษร CJK เยอะ/ไทยน้อยผิดปกติ"""
    if is_json or role not in _THAI_ROLES:
        return False
    t = (text or "").strip()
    if len(t) < 40:
        return False
    cjk = len(_CJK_RE.findall(t))
    thai = len(_THAI_RE.findall(t))
    if cjk >= 8 and cjk > thai * 0.15:      # CJK โผล่เยอะเทียบกับไทย
        return True
    if cjk > 0 and thai < len(t) * 0.2:     # แทบไม่มีไทยเลยทั้งที่ควรเป็นไทย
        return True
    return False


def _generate_direct(prompt: str, role: str = "default", is_json: bool = False,
                     temperature=None, system: str = None, fallback: bool = True) -> str:
    """เรียก LLM เองในเครื่องนี้ (Gemini/local) — ตรรกะเดิมก่อนมี gateway."""
    backend = resolve_backend(role)

    # Circuit breaker: ถ้า Gemini เพิ่งล้มต่อเนื่อง (โดน throttle) อยู่ในช่วงพัก → ใช้ local ไปก่อน
    if backend == "gemini" and gemini_in_cooldown():
        print(f"[llm] gemini อยู่ในช่วงพัก (cooldown) → ใช้ local สำหรับ role '{role}'")
        backend = "local"

    # Phase 3 budget guard: ถ้า Gemini ใช้เกินเพดานวันนี้ ให้ reroute ไป local (ฟรี) อัตโนมัติ
    if backend == "gemini" and DAILY_USD_CAP:
        spent = today_spend_usd()
        if spent >= DAILY_USD_CAP:
            print(f"[llm] แตะเพดานวันนี้ ${DAILY_USD_CAP:.2f} (ใช้ไป ${spent:.2f}); "
                  f"reroute role '{role}' -> local")
            backend = "local"

    primary = _gemini_generate if backend == "gemini" else _local_generate
    secondary_name = "local" if backend == "gemini" else "gemini"
    secondary = _local_generate if backend == "gemini" else _gemini_generate

    try:
        out = primary(prompt, role, is_json, temperature, system)
    except Exception as e:  # noqa: BLE001
        if not fallback:
            raise
        print(f"[llm] backend '{backend}' ล้มเหลว ({e}); fallback -> '{secondary_name}'")
        return secondary(prompt, role, is_json, temperature, system)

    # Auto-route #34: ผลลัพธ์เพี้ยน (Gemini หลุดภาษาอื่น) → retry ที่ local อัตโนมัติ
    if backend == "gemini" and fallback and _looks_garbled(out, role, is_json):
        print(f"[llm] ⚠️ output เพี้ยน (ภาษาหลุด CJK) จาก gemini role '{role}' → retry '{secondary_name}'")
        try:
            alt = secondary(prompt, role, is_json, temperature, system)
            if alt and not _looks_garbled(alt, role, is_json):
                return alt
        except Exception as e:  # noqa: BLE001
            print(f"[llm] retry local ล้มเหลว ({e}) — คืนผลเดิม")
    return out


def generate_json(prompt: str, role: str = "default", temperature=None, system: str = None):
    """เหมือน generate แต่ parse JSON ให้เลย"""
    raw = generate(prompt, role=role, is_json=True, temperature=temperature, system=system)
    return json.loads(_coerce_json(raw))


# ---------------------------------------------------------------------------
# CLI / self-test
# ---------------------------------------------------------------------------
def _local_check():
    """ตรวจ + เบนช์มาร์ก Mac mini local LLM: ต่อได้ไหม / มีโมเดลอะไร / เร็วแค่ไหน / คุณภาพไทย"""
    import requests
    print("🖥️  ANSRE Local LLM Check")
    print("=" * 40)
    print(f"endpoint: {LOCAL_BASE_URL}")
    print(f"model   : {LOCAL_MODEL} (heavy: {LOCAL_MODEL_HEAVY})")
    print("-" * 40)

    # 1) ต่อได้ไหม + ลิสต์โมเดล
    try:
        r = requests.get(f"{LOCAL_BASE_URL}/models", timeout=5,
                         headers={"Authorization": f"Bearer {LOCAL_API_KEY}"})
        if r.status_code == 200:
            ids = [m.get("id", "?") for m in r.json().get("data", [])]
            print(f"✅ ต่อได้ — มีโมเดล {len(ids)} ตัว: {', '.join(ids[:8]) or '(ว่าง)'}")
            if LOCAL_MODEL.split(':')[0] not in " ".join(ids):
                print(f"⚠️  ยังไม่มี '{LOCAL_MODEL}' — บน Mac mini รัน: ollama pull {LOCAL_MODEL}")
        else:
            print(f"❌ ต่อได้แต่ตอบ HTTP {r.status_code}")
            return
    except Exception as e:  # noqa: BLE001
        print(f"❌ ต่อ Mac mini ไม่ได้: {e}")
        print("   เช็ค: Ollama รันอยู่ไหม (OLLAMA_HOST=0.0.0.0) / IP ถูกไหม / Tailscale ขึ้นไหม")
        return

    # 2) เบนช์มาร์ก latency + คุณภาพไทย
    sample = "เขียนประโยคเปิดนิยายสืบสวนไทยที่ดึงดูดใน 1 ประโยค"
    print("-" * 40)
    print("⏱️  เบนช์มาร์ก (เขียน hook นิยายไทย)...")
    t0 = time.time()
    try:
        out = _local_generate(sample, "ideation", False, 0.8, None)
        dt = time.time() - t0
        print(f"✅ local ({dt:.1f}s): {out.strip()[:160]}")
    except Exception as e:  # noqa: BLE001
        print(f"❌ local generate ล้มเหลว: {e}")
        return

    # 3) เทียบกับ Gemini (ถ้ามีคีย์) ให้เห็นคุณภาพ
    if GEMINI_API_KEY and not gemini_in_cooldown():
        try:
            t0 = time.time()
            g = _gemini_generate(sample, "ideation", False, 0.8, None)
            print(f"🟣 gemini ({time.time()-t0:.1f}s): {g.strip()[:160]}")
            print("\n→ เทียบคุณภาพ 2 บรรทัดบน ถ้า local ใกล้เคียงพอใช้ ก็ตั้ง LLM_BACKEND=local ประหยัดสุด")
        except Exception:
            pass


def _selftest():
    print("=== ANSRE LLM Provider self-test ===")
    print(f"LLM_BACKEND       = {LLM_BACKEND}")
    print(f"WRITING_MODE      = {WRITING_MODE}")
    print(f"LOCAL_LLM_BASE_URL= {LOCAL_BASE_URL}")
    print(f"LOCAL_LLM_MODEL   = {LOCAL_MODEL} (heavy: {LOCAL_MODEL_HEAVY})")
    print(f"GEMINI key set    = {bool(GEMINI_API_KEY)}")
    print("-" * 40)

    # local
    try:
        out = _local_generate("ตอบสั้นๆ: 1+1 เท่ากับเท่าไหร่", "default", False, 0, None)
        print(f"[local ] OK -> {out.strip()[:80]}")
    except Exception as e:  # noqa: BLE001
        print(f"[local ] FAIL -> {e}")

    # gemini
    if GEMINI_API_KEY:
        try:
            out = _gemini_generate("ตอบสั้นๆ: 1+1 เท่ากับเท่าไหร่", "default", False, 0, None)
            print(f"[gemini] OK -> {out.strip()[:80]}")
        except Exception as e:  # noqa: BLE001
            print(f"[gemini] FAIL -> {e}")
    else:
        print("[gemini] skipped (no GEMINI_API_KEY)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--usage" in args:
        spent = today_spend_usd()
        cap = f"/ ${DAILY_USD_CAP:.2f} cap" if DAILY_USD_CAP else "(no cap)"
        print(f"=== ANSRE LLM usage วันนี้: ${spent:.4f} {cap} ===")
        print(f"ledger: {USAGE_LOG}")
        if os.path.exists(USAGE_LOG):
            from collections import Counter
            by_backend = Counter()
            with open(USAGE_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        e = json.loads(line)
                        if e.get("date") == datetime.now().strftime("%Y-%m-%d"):
                            by_backend[e["backend"]] += 1
                    except Exception:
                        continue
            for b, n in by_backend.items():
                print(f"  {b}: {n} calls วันนี้")
    elif "--local-check" in args or "--local" in args:
        _local_check()
    elif "--selftest" in args:
        _selftest()
    elif "--probe" in args:
        i = args.index("--probe")
        prompt = args[i + 1] if i + 1 < len(args) else "สวัสดี"
        role = "default"
        if "--role" in args:
            role = args[args.index("--role") + 1]
        print(f"[*] role={role} backend={resolve_backend(role)}")
        print(generate(prompt, role=role))
    else:
        print(__doc__)
