"""
ANSRE Orchestrator — ตัวขับเคลื่อน pipeline ให้ "รันเรื่อยๆ" ได้เอง
====================================================================

หัวใจของการทำงานต่อเนื่อง (roadmap Phase 1-2): สแกน SecondBrain แล้วดันงานทุกชิ้น
ไปข้างหน้าทีละ stage โดยไม่ต้องสั่งมือ ออกแบบให้เรียกซ้ำได้ปลอดภัย (idempotent)
เหมาะกับการตั้ง launchd/cron บน Mac mini ให้ยิงทุก 15-30 นาที

โหมดใช้งาน:
    python orchestrator.py --once        # เดิน 1 รอบแล้วจบ (ใช้กับ launchd/cron)
    python orchestrator.py --loop        # วนเรื่อยๆ เว้นช่วงตาม ANSRE_LOOP_SLEEP
    python orchestrator.py --dry-run     # ดูว่าจะทำอะไร โดยไม่ยิงจริง
    python orchestrator.py --no-scout    # ข้ามการ scout (เคลียร์ของเก่าอย่างเดียว)

แต่ละ stage เรียกสคริปต์เดิม (idempotent: ข้ามงานที่เสร็จแล้ว) ผ่าน subprocess
เพื่อความทนทาน — stage ใด crash จะไม่ลากทั้ง process ตาย

ตั้งค่าได้ผ่าน .env:
    ANSRE_MIN_POOL          = 3     # ถ้างานค้างใน pool < ค่านี้ ค่อย scout เพิ่ม
    ANSRE_SCOUT_EVERY_HOURS = 12    # เว้นระยะ scout อย่างน้อยกี่ชม.
    ANSRE_SCOUT_LIMIT       = 2     # scout กี่เรื่องต่อแหล่งต่อรอบ
    ANSRE_LOOP_SLEEP        = 1800  # โหมด --loop พักกี่วินาทีต่อรอบ
    ANSRE_TEASER_DURATION   = 60
"""
from __future__ import annotations

import os
import sys
import glob
import json
import time
import subprocess
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
SECOND_BRAIN = os.path.join(ROOT, "SecondBrain")
LOCK_FILE = os.path.join(SECOND_BRAIN, ".orchestrator.lock")
STATE_FILE = os.path.join(SECOND_BRAIN, ".orchestrator_state.json")
LOG_FILE = os.path.join(SECOND_BRAIN, "orchestrator.log")
LOCK_STALE_SECONDS = 2 * 3600  # lock เก่ากว่า 2 ชม. ถือว่าค้าง ลบทิ้งได้

# ---- load .env (รูปแบบเดียวกับไฟล์อื่น) ----
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def _cfg_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


MIN_POOL = _cfg_int("ANSRE_MIN_POOL", 3)
SCOUT_EVERY_HOURS = _cfg_int("ANSRE_SCOUT_EVERY_HOURS", 12)
SCOUT_LIMIT = _cfg_int("ANSRE_SCOUT_LIMIT", 2)
LOOP_SLEEP = _cfg_int("ANSRE_LOOP_SLEEP", 1800)
TEASER_DURATION = _cfg_int("ANSRE_TEASER_DURATION", 60)
# ความลึกเป้าหมาย (จำนวนตอน/เรื่อง) + คุมงบ: เขียนต่อกี่ตอน/เรื่อง/รอบ และกี่เรื่อง/รอบ
TARGET_CHAPTERS = _cfg_int("ANSRE_TARGET_CHAPTERS", 8)
CONTINUE_PER_RUN = _cfg_int("ANSRE_CONTINUE_PER_RUN", 1)
CONTINUE_STORIES = _cfg_int("ANSRE_CONTINUE_STORIES", 3)


def log(msg: str):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(SECOND_BRAIN, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _publish_enabled() -> bool:
    return any(os.environ.get(k, "0").lower() in ("1", "true", "yes", "on")
               for k in ("PUBLISH_YOUTUBE", "PUBLISH_TIKTOK", "PUBLISH_NOVEL"))


def python_bin() -> str:
    cand = os.path.join(ROOT, ".venv", "bin", "python")
    return cand if os.path.exists(cand) else "python3"


# ---------------------------------------------------------------------------
# Lock (กันรันซ้อนเวลา schedule ถี่)
# ---------------------------------------------------------------------------
def acquire_lock() -> bool:
    os.makedirs(SECOND_BRAIN, exist_ok=True)
    if os.path.exists(LOCK_FILE):
        try:
            age = time.time() - os.path.getmtime(LOCK_FILE)
        except OSError:
            age = 0
        if age < LOCK_STALE_SECONDS:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                log(f"[lock] อีก process ทำงานอยู่ ({f.read().strip()}); ข้ามรอบนี้")
            return False
        log(f"[lock] พบ lock ค้าง (อายุ {int(age)}s) — ลบแล้วทำต่อ")
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        f.write(f"pid={os.getpid()} at={datetime.now().isoformat()}")
    return True


def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# State (จำเวลา scout ครั้งล่าสุด)
# ---------------------------------------------------------------------------
def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"[state] เขียน state ไม่สำเร็จ: {e}")


# ---------------------------------------------------------------------------
# สำรวจสถานะ pool
# ---------------------------------------------------------------------------
def count_status(status_values) -> int:
    pool = os.path.join(SECOND_BRAIN, "01_Scouting_Pool")
    n = 0
    for fp in glob.glob(os.path.join(pool, "*.md")):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                head = f.read(1500)
            for s in status_values:
                if f'status: "{s}"' in head or f"status: {s}" in head:
                    n += 1
                    break
        except Exception:
            continue
    return n


def run_stage(name: str, cmd, dry: bool) -> bool:
    log(f"=== STAGE: {name} ===")
    if dry:
        log(f"[dry-run] would run: {' '.join(cmd)}")
        return True
    try:
        proc = subprocess.run(cmd, cwd=ROOT)
        ok = proc.returncode == 0
        log(f"[{name}] {'OK' if ok else 'FAILED (rc=%d)' % proc.returncode}")
        return ok
    except Exception as e:
        log(f"[{name}] EXCEPTION: {e}")
        return False


# ---------------------------------------------------------------------------
# หนึ่งรอบของ pipeline
# ---------------------------------------------------------------------------
def run_cycle(do_scout: bool = True, dry: bool = False):
    py = python_bin()
    state = load_state()
    log("######## ORCHESTRATOR CYCLE START ########")

    # 0) Budget hard-cap guard: ถ้าใช้เกินเพดานแข็งวันนี้ → หยุดทั้งรอบ + แจ้งเตือน (ครั้งเดียว/วัน)
    if not dry:
        try:
            from llm_provider import budget_status
            bs = budget_status()
            if bs["over_hard"]:
                today = time.strftime("%Y-%m-%d")
                log(f"[budget] ⛔ แตะเพดานแข็ง ${bs['hard_cap']:.2f} (ใช้ไป ${bs['spent']:.2f}) — หยุด pipeline รอบนี้")
                if state.get("budget_paused_date") != today:
                    state["budget_paused_date"] = today
                    save_state(state)
                    try:
                        from notify import notify as _notify
                        _notify(f"ใช้ไป ${bs['spent']:.2f} / เพดานแข็ง ${bs['hard_cap']:.2f} วันนี้ — "
                                f"หยุด pipeline อัตโนมัติเพื่อกันบิลบาน (เริ่มใหม่พรุ่งนี้ หรือปรับเพดานใน .env)",
                                "⛔ แตะเพดานงบรายวัน — หยุดอัตโนมัติ", "warn")
                    except Exception:
                        pass
                return
        except Exception:
            pass

    # 1) ตัดสินใจ scout: เฉพาะเมื่อ pool ร่อยหรอ และเว้นระยะพอ (backpressure)
    if do_scout:
        pending = count_status(["Scouted", "Analyzed"])
        last_scout = state.get("last_scout_ts", 0)
        hours_since = (time.time() - last_scout) / 3600 if last_scout else 1e9
        if pending >= MIN_POOL:
            log(f"[scout] ข้าม — งานค้างใน pool {pending} >= MIN_POOL {MIN_POOL} (backpressure)")
        elif hours_since < SCOUT_EVERY_HOURS:
            log(f"[scout] ข้าม — เพิ่ง scout ไป {hours_since:.1f} ชม. (< {SCOUT_EVERY_HOURS})")
        else:
            ok = run_stage("scout", [py, "scout.py", "--source", "all",
                                     "--limit", str(SCOUT_LIMIT), "--outdir", SECOND_BRAIN], dry)
            if ok and not dry:
                state["last_scout_ts"] = time.time()
                save_state(state)

    # 1.5) คลังไอเดีย: คิด/ให้คะแนน/auto-promote ตัวท็อปเข้าคิวเขียน (มี guardrail ใน ideation.py)
    if os.environ.get("ANSRE_IDEATION", "1").lower() in ("1", "true", "yes", "on"):
        run_stage("ideate", [py, "ideation.py", "auto"], dry)

    # 2) ดันงานผ่านแต่ละ stage (ทุกตัว idempotent: ข้ามงานที่เสร็จแล้ว)
    #    stage ใดล้มเหลว ไม่หยุดทั้งรอบ — ให้ตัวอื่นเดินต่อ รอบหน้าค่อยลองใหม่
    run_stage("analyze", [py, "agent_analyzer.py", SECOND_BRAIN], dry)
    # สรุปเทรนด์จากนิยายที่ analyze แล้ว → ป้อนเข้า ideation รอบถัดไป
    run_stage("trends", [py, "trends.py"], dry)
    run_stage("write",   [py, "agent_writer.py", SECOND_BRAIN], dry)
    # เขียนต่อให้ลึก: ดันเรื่องที่ยังไม่ถึงเป้า ทีละน้อย/รอบ (audio stage จะตามเก็บตอนใหม่เอง)
    if TARGET_CHAPTERS > 1:
        run_stage("continue", [py, "chapter_continuer.py", SECOND_BRAIN,
                               "--target", str(TARGET_CHAPTERS),
                               "--max-per-run", str(CONTINUE_PER_RUN),
                               "--max-stories", str(CONTINUE_STORIES)], dry)
    run_stage("cover",   [py, "cover_generator.py", SECOND_BRAIN], dry)
    run_stage("audio",   [py, "audio_engine.py", SECOND_BRAIN], dry)
    run_stage("teaser",  [py, "teaser_generator.py", SECOND_BRAIN, str(TEASER_DURATION)], dry)

    # 3) เผยแพร่ (Phase 4) — publisher จะข้ามแพลตฟอร์มที่ยังไม่เปิด/ไม่มี creds เอง
    if _publish_enabled():
        run_stage("publish", [py, "publisher.py", SECOND_BRAIN], dry)
    else:
        log("[publish] ข้าม — ยังไม่เปิด PUBLISH_YOUTUBE/PUBLISH_TIKTOK/PUBLISH_NOVEL")

    log("######## ORCHESTRATOR CYCLE END ########\n")
    # สำรองข้อมูลอัตโนมัติ (เฉพาะถ้าเกิน 24 ชม.จากครั้งก่อน)
    if not dry:
        try:
            import backup
            backup.auto_backup()
        except Exception:
            pass
    # แจ้งเตือน Discord (ถ้าตั้ง webhook) — สรุปผลผลิตปัจจุบัน
    if not dry:
        try:
            import glob as _g
            ap = os.path.join(SECOND_BRAIN, "05_Active_Projects")
            cnt = lambda *p: len(_g.glob(os.path.join(ap, *p)))
            from notify import notify as _notify
            _notify(f"📖 ตอน {cnt('Chapters', '*.md')} · 🖼️ ปก {cnt('Covers', '*.jpg')+cnt('Covers','*.png')} · "
                    f"🎧 เสียง {cnt('Audio_Output', '*.mp3')} · 🎬 teaser {cnt('Teasers','*.mp4')+cnt('Teaser_Output','*.mp4')}",
                    "✅ Pipeline รอบหนึ่งเสร็จ", "good")
        except Exception:
            pass


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    do_scout = "--no-scout" not in args
    loop = "--loop" in args

    if not dry and not acquire_lock():
        sys.exit(0)
    try:
        if loop:
            log(f"[*] LOOP mode — sleep {LOOP_SLEEP}s ระหว่างรอบ (Ctrl-C เพื่อหยุด)")
            while True:
                run_cycle(do_scout=do_scout, dry=dry)
                time.sleep(LOOP_SLEEP)
        else:
            run_cycle(do_scout=do_scout, dry=dry)
    except Exception as e:  # noqa: BLE001
        try:
            from notify import notify as _notify
            _notify(f"orchestrator ล้มเหลว: {e}", "🔴 Pipeline error", "bad")
        except Exception:
            pass
        raise
    finally:
        if not dry:
            release_lock()


if __name__ == "__main__":
    main()
