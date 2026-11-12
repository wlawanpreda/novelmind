"""
Phase 2 routing test — provider เลือก gateway/direct ถูกไหม + fallback + กัน recursion
hermetic: ไม่ยิง network จริง (stub ทั้ง gateway path และ direct path)
รัน: python3 test_phase2_routing.py
"""
import importlib, os

fails = []
def check(name, cond):
    print(("✅" if cond else "❌"), name)
    if not cond: fails.append(name)

# ── 1) flag logic: _USE_GATEWAY = มี URL และไม่ใช่ internal ───────────────────
def reload_with(env, mod):
    # ตั้งเป็นค่าว่าง (present) แทนการ pop — กัน .env loader (setdefault) เซ็ตคืนจาก .env จริง
    # ทำให้ test isolate จาก .env: "ไม่มี URL" = "" → _USE_GATEWAY=False อย่างแท้จริง
    for k in ("ANSRE_GATEWAY_URL", "ANSRE_GATEWAY_INTERNAL"):
        os.environ[k] = ""
    os.environ.update(env)
    m = importlib.import_module(mod)
    return importlib.reload(m)

ip = reload_with({}, "image_provider")
check("ไม่มี URL → ไม่ใช้ gateway", ip._USE_GATEWAY is False)
ip = reload_with({"ANSRE_GATEWAY_URL": "http://gw:9000"}, "image_provider")
check("มี URL → ใช้ gateway", ip._USE_GATEWAY is True)
ip = reload_with({"ANSRE_GATEWAY_URL": "http://gw:9000", "ANSRE_GATEWAY_INTERNAL": "1"}, "image_provider")
check("internal=1 (gateway เอง) → ไม่วนกลับ", ip._USE_GATEWAY is False)

lp = reload_with({"ANSRE_GATEWAY_URL": "http://gw:9000", "ANSRE_GATEWAY_INTERNAL": "1"}, "llm_provider")
check("llm internal=1 → direct", lp._USE_GATEWAY is False)

# ── 2) image: route ไป gateway เมื่อเปิด, ไม่แตะ direct ───────────────────────
ip = reload_with({"ANSRE_GATEWAY_URL": "http://gw:9000"}, "image_provider")
calls = []
ip._via_gateway_image = lambda *a, **k: (calls.append("gw"), True)[1]
ip._generate_image_direct = lambda *a, **k: (calls.append("direct"), True)[1]
ip.generate_image("p", "/tmp/x.png")
check("image: เปิด gateway → เรียก gateway เท่านั้น", calls == ["gw"])

# ── 3) image: gateway ล่ม → fallback direct ──────────────────────────────────
calls.clear()
def _boom(*a, **k): raise RuntimeError("gw down")
ip._via_gateway_image = _boom
ip._generate_image_direct = lambda *a, **k: (calls.append("direct"), True)[1]
r = ip.generate_image("p", "/tmp/x.png")
check("image: gateway ล่ม → fallback direct + คืน True", calls == ["direct"] and r is True)

# ── 4) llm: route + fallback ─────────────────────────────────────────────────
lp = reload_with({"ANSRE_GATEWAY_URL": "http://gw:9000"}, "llm_provider")
lp._via_gateway_llm = lambda *a, **k: "FROM_GATEWAY"
check("llm: เปิด gateway → ใช้ผลจาก gateway", lp.generate("hi", role="analyzer") == "FROM_GATEWAY")
lp._via_gateway_llm = _boom
lp._generate_direct = lambda *a, **k: "FROM_DIRECT"
check("llm: gateway ล่ม → fallback direct", lp.generate("hi", role="analyzer") == "FROM_DIRECT")

print("\n" + ("🎉 PASS ทั้งหมด" if not fails else f"💥 FAIL: {fails}"))
raise SystemExit(1 if fails else 0)
