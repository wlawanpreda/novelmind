"""
Hermetic test: single-flight Gemini lock ใน llm_provider._gemini_gate
=====================================================================
พิสูจน์ว่าหลาย process เข้า critical section "ทีละ 1" (ไม่ทับเวลากัน)
ไม่มีการเรียก LLM จริง — ศูนย์ค่าใช้จ่าย

รัน: .venv/bin/python test_singleflight.py
"""
import os
import time
import json
import tempfile
import multiprocessing as mp

LOCK = os.path.join(tempfile.gettempdir(), "ansre_sf_test.lock")
os.environ["ANSRE_LLM_SINGLEFLIGHT"] = "1"
os.environ["ANSRE_LLM_LOCK"] = LOCK
os.environ["ANSRE_CALL_GAP"] = "0"
os.environ.setdefault("GEMINI_API_KEY", "x")  # กันโหลด .env ไม่มี key


def _worker(idx, q, hold=0.6):
    import llm_provider as L
    with L._gemini_gate():
        t_in = time.time()
        time.sleep(hold)          # จำลองช่วงยิง API จริง
        t_out = time.time()
    q.put((idx, t_in, t_out))


def _overlap(intervals):
    """คืนจำนวนคู่ที่ critical section ทับเวลากัน (ควรเป็น 0)"""
    intervals = sorted(intervals, key=lambda x: x[1])
    bad = 0
    for i in range(1, len(intervals)):
        prev_out = intervals[i - 1][2]
        cur_in = intervals[i][1]
        if cur_in < prev_out - 0.01:   # เผื่อความคลาดเคลื่อน 10ms
            bad += 1
    return bad


def test_single_flight_serializes():
    if not os.path.exists(LOCK):
        open(LOCK, "a").close()
    n = 4
    q = mp.Queue()
    procs = [mp.Process(target=_worker, args=(i, q)) for i in range(n)]
    t0 = time.time()
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
    wall = time.time() - t0

    intervals = [q.get() for _ in range(n)]
    bad = _overlap(intervals)

    # serialize → wall-clock ต้อง ≳ n*hold (ทีละตัว) ไม่ใช่ ~hold (ขนาน)
    print(f"  workers={n} · hold=0.6s · wall={wall:.2f}s · overlaps={bad}")
    for idx, ti, to in sorted(intervals, key=lambda x: x[1]):
        print(f"    worker {idx}: [{ti - t0:5.2f} → {to - t0:5.2f}]")
    assert bad == 0, f"พบ critical section ทับกัน {bad} คู่ — single-flight ไม่ทำงาน!"
    assert wall >= n * 0.6 * 0.85, f"wall {wall:.2f}s สั้นเกิน — ดูเหมือนรันขนาน ไม่ serialize"
    print("  ✅ single-flight serialize ถูกต้อง (ไม่มี Gemini call ซ้อนกัน)")


def test_disabled_runs_parallel():
    """ปิด SINGLEFLIGHT → ควรรันขนาน (wall ~hold ไม่ใช่ n*hold)"""
    os.environ["ANSRE_LLM_SINGLEFLIGHT"] = "0"
    n = 4
    q = mp.Queue()
    procs = [mp.Process(target=_worker, args=(i, q)) for i in range(n)]
    t0 = time.time()
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
    wall = time.time() - t0
    _ = [q.get() for _ in range(n)]
    os.environ["ANSRE_LLM_SINGLEFLIGHT"] = "1"
    print(f"  [disabled] workers={n} · wall={wall:.2f}s (ควร ~0.6s = ขนาน)")
    assert wall < n * 0.6 * 0.7, f"wall {wall:.2f}s ยาวเกิน — ปิดแล้วยัง serialize?"
    print("  ✅ ปิด SINGLEFLIGHT แล้วรันขนานตามคาด")


if __name__ == "__main__":
    try:
        mp.set_start_method("fork")
    except RuntimeError:
        pass
    print("[1] single-flight serialize:")
    test_single_flight_serializes()
    print("[2] disabled = parallel:")
    test_disabled_runs_parallel()
    print("\n✅ ผ่านทั้งหมด")
