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
from run_log import log_event, rotate_if_large

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

# Ensure standard binary paths are in PATH (critical for ffmpeg, ffprobe, playwright under launchd / cron)
for _p in ["/opt/homebrew/bin", "/usr/local/bin"]:
    if os.path.exists(_p) and _p not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")


def _cfg_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


MIN_POOL = _cfg_int("ANSRE_MIN_POOL", 3)
SCOUT_EVERY_HOURS = _cfg_int("ANSRE_SCOUT_EVERY_HOURS", 12)
SCOUT_LIMIT = _cfg_int("ANSRE_SCOUT_LIMIT", 15)  # ดึงลึกพอให้ทะลุเรื่องที่ทำแล้ว → ได้เรื่องใหม่จริง
LOOP_SLEEP = _cfg_int("ANSRE_LOOP_SLEEP", 1800)
TEASER_DURATION = _cfg_int("ANSRE_TEASER_DURATION", 60)
# ความลึกเป้าหมาย (จำนวนตอน/เรื่อง) + คุมงบ: เขียนต่อกี่ตอน/เรื่อง/รอบ และกี่เรื่อง/รอบ
TARGET_CHAPTERS = _cfg_int("ANSRE_TARGET_CHAPTERS", 8)
CONTINUE_PER_RUN = _cfg_int("ANSRE_CONTINUE_PER_RUN", 1)
CONTINUE_STORIES = _cfg_int("ANSRE_CONTINUE_STORIES", 3)


CYCLE_ID = None  # ตั้งใหม่ทุกรอบใน run_cycle เพื่อผูก event ทั้งรอบเข้าด้วยกัน


def log(msg: str):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(SECOND_BRAIN, exist_ok=True)
        rotate_if_large(LOG_FILE)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _publish_enabled() -> bool:
    return any(os.environ.get(k, "0").lower() in ("1", "true", "yes", "on")
               for k in ("PUBLISH_YOUTUBE", "PUBLISH_TIKTOK", "PUBLISH_BILIBILI", "PUBLISH_NOVEL"))


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


def _tail(lines, n=40, max_chars=3000) -> str:
    return "\n".join(lines[-n:])[-max_chars:]


def run_stage(name: str, cmd, dry: bool) -> bool:
    log(f"=== STAGE: {name} ===")
    if dry:
        log(f"[dry-run] would run: {' '.join(cmd)}")
        return True
    t0 = time.time()
    tail = []
    rc = None
    err = None
    try:
        sub_env = dict(os.environ, PYTHONUNBUFFERED="1")
        # stream output สดเหมือนเดิม แต่เก็บท้ายไว้ใน event เมื่อ stage ล้ม (เพื่อรู้สาเหตุย้อนหลัง)
        proc = subprocess.Popen(cmd, cwd=ROOT, env=sub_env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, errors="replace")
        for line in proc.stdout:
            print(line, end="", flush=True)
            tail.append(line.rstrip("\n"))
            if len(tail) > 200:
                del tail[:100]
        rc = proc.wait()
        ok = rc == 0
        log(f"[{name}] {'OK' if ok else 'FAILED (rc=%d)' % rc}")
    except Exception as e:
        ok = False
        err = f"{type(e).__name__}: {e}"
        log(f"[{name}] EXCEPTION: {e}")

    duration = round(time.time() - t0, 2)
    log_event("stage", cycle_id=CYCLE_ID, stage=name, ok=ok, rc=rc, duration_s=duration,
              cmd=" ".join(cmd[1:]), error=err, output_tail=None if ok else _tail(tail))
    if not ok:
        try:
            from discord_reporter import send_pipeline_error_to_discord
            detail = err or f"returncode {rc}"
            send_pipeline_error_to_discord(
                name, f"Stage '{name}' failed: {detail}\nCommand: {' '.join(cmd)}\n--- output tail ---\n{_tail(tail, 12, 700)}")
        except Exception:
            pass
    return ok


# ---------------------------------------------------------------------------
# หนึ่งรอบของ pipeline
# ---------------------------------------------------------------------------
def run_cycle(do_scout: bool = True, dry: bool = False):
    global CYCLE_ID
    py = python_bin()
    state = load_state()
    CYCLE_ID = datetime.now().strftime("%Y%m%d-%H%M%S")
    cycle_t0 = time.time()
    log_event("cycle_start", cycle_id=CYCLE_ID, dry=dry,
              pool=count_status(["Scouted", "Analyzed"]) if not dry else None)
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
                log_event("cycle_end", cycle_id=CYCLE_ID, aborted="budget_hard_cap")
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
    # เติมบทเสียงที่ขาด (ตอนมีนิยายแต่ไม่มี AudioScript) ทีละน้อย/รอบ เรียงตามเรื่องที่ใกล้ถึงเกณฑ์ Mega — ปิดได้ด้วย ANSRE_AUDIOSCRIPT_BACKFILL=0
    if os.environ.get("ANSRE_AUDIOSCRIPT_BACKFILL", "1").lower() in ("1", "true", "yes", "on"):
        run_stage("audioscript_backfill", [py, "backfill_audioscripts.py"], dry)
    run_stage("audio",   [py, "audio_engine.py", SECOND_BRAIN], dry)
    run_stage("teaser",  [py, "teaser_generator.py", SECOND_BRAIN, str(TEASER_DURATION)], dry)

    # 2.5) QA & Subagent Leak Auditor: สแกนและทำความสะอาดคำหลุด AI ทั่วระบบก่อนเข้า Quality Gate
    run_stage("auditor", [py, "agent_auditor.py", "--fix"], dry)
    run_stage("qa",      [py, "quality_gate.py", "--all"], dry)

    # 2.8) แพ็กเกจ E-Book (.epub), ชุด WEB_PUBLISH_KIT.md และ Master Audiobook ก่อนส่งขึ้นแพลตฟอร์ม
    run_stage("epub", [py, "epub_packager.py", "--all", "--min-chapters", "4"], dry)
    run_stage("audiobook", [py, "audiobook_packager.py", "--all"], dry)

    # 3) เผยแพร่ (Phase 4) — publisher จะข้ามแพลตฟอร์มที่ยังไม่เปิด/ไม่มี creds เอง
    if _publish_enabled():
        run_stage("publish", [py, "publisher.py", SECOND_BRAIN], dry)
        run_stage("web_sync", [py, "web_novel_uploader.py", "--sync-all"], dry)
    else:
        log("[publish] ข้าม — ยังไม่เปิด PUBLISH_YOUTUBE/PUBLISH_TIKTOK/PUBLISH_NOVEL")

    # 3.1) Web Novel Drip Publishing & Video Privacy Drip (ปล่อยตอนใหม่และสลับวิดีโอ YouTube เป็นสาธารณะ)
    run_stage("drip_release", [py, "auto_release_scheduler.py", "--cron-tick"], dry)
    if os.environ.get("PUBLISH_YOUTUBE", "0").lower() in ("1", "true", "yes", "on"):
        run_stage("privacy_drip", [py, "update_privacy.py", "--public", "--limit", "2"], dry)

    # 3.2) YouTube Growth Loop: คิว Double Drip → เชื่อม Funnel Shorts→Mega → A/B ชื่อคลิป → วัดความเร็ว YPP
    #      จำกัดความถี่ด้วย state เพื่อประหยัด YouTube API quota (ตั้งชม.ผ่าน .env ได้)
    if os.environ.get("PUBLISH_YOUTUBE", "0").lower() in ("1", "true", "yes", "on"):
        def _due(key: str, hours: float) -> bool:
            return (time.time() - state.get(key, 0)) >= hours * 3600

        def _growth_stage(name: str, key: str, hours: float, cmd):
            if dry or _due(key, hours):
                if run_stage(name, cmd, dry) and not dry:
                    state[key] = time.time()
                    save_state(state)
            else:
                log(f"[{name}] ข้าม — ยังไม่ครบ {hours:g} ชม.")
                log_event("stage", cycle_id=CYCLE_ID, stage=name, skipped=True, reason="interval")

        # คิวปล่อยงาน & เติมสต็อกตารางอัตโนมัติ (Rolling Schedule 30 Days)
        run_stage("plan_refill", [py, "auto_refill_schedule_plan.py", "--days", "30"], dry)
        run_stage("double_drip", [py, "scheduled_drip_publisher.py", "--cron-tick"], dry)
        _growth_stage("community_growth", "last_community_growth_ts", _cfg_int("ANSRE_COMMUNITY_GROWTH_HOURS", 24),
                      [py, "community_growth_engine.py"])
        _growth_stage("funnel_sync", "last_funnel_sync_ts", _cfg_int("ANSRE_FUNNEL_SYNC_HOURS", 12),
                      [py, "channel_wide_funnel_syncer.py", "--limit", "25"])
        _growth_stage("ab_optimizer", "last_ab_opt_ts", _cfg_int("ANSRE_AB_OPT_HOURS", 24),
                      [py, "youtube_ab_optimizer.py", "--max", "5"])
        _growth_stage("ypp_tracker", "last_ypp_ts", _cfg_int("ANSRE_YPP_HOURS", 24),
                      [py, "ypp_velocity_tracker.py"])
        # Mega Audiobook อัตโนมัติ (opt-in: งานหนัก ffmpeg + อัปโหลดยาว) — เลือกเรื่อง/เวลาเอง มี cooldown ในตัว
        if os.environ.get("ANSRE_AUTO_MEGA", "0").lower() in ("1", "true", "yes", "on"):
            run_stage("auto_mega", [py, "auto_mega.py"], dry)
    else:
        log("[growth] ข้าม — ยังไม่เปิด PUBLISH_YOUTUBE")

    # 3.6) ปรับปรุงพอร์ตโฟลิโอธุรกิจ (Portfolio Matrix & Flagship Tracking)
    run_stage("portfolio", [py, "portfolio_manager.py"], dry)

    log_event("cycle_end", cycle_id=CYCLE_ID, duration_s=round(time.time() - cycle_t0, 1))
    if not dry:
        try:
            import dashboard_gen
            dashboard_gen.main()
        except Exception as e:
            log(f"[dashboard] ข้าม: {e}")
    log("######## ORCHESTRATOR CYCLE END ########\n")
    # สำรองข้อมูลอัตโนมัติ (เฉพาะถ้าเกิน 24 ชม.จากครั้งก่อน)
    if not dry:
        try:
            import backup
            backup.auto_backup()
        except Exception:
            pass
    # แจ้งเตือน Discord (ถ้าตั้ง webhook หรือ bot token) — ส่งเฉพาะสรุปรายวัน / ราย 3 วัน / หรือเมื่อมี Error
    if not dry:
        try:
            try:
                from discord_reporter import send_daily_digest_to_discord, send_3day_performance_report_to_discord
                import youtube_stats

                # 1. Daily YouTube Digest (ส่งวันละครั้ง)
                today_str = datetime.now().strftime("%Y-%m-%d")
                if state.get("last_daily_digest_date") != today_str and _publish_enabled():
                    overview = youtube_stats.get_channel_overview(SECOND_BRAIN)
                    if overview and not overview.get("error"):
                        send_daily_digest_to_discord(overview)
                        state["last_daily_digest_date"] = today_str
                        save_state(state)

                # 2. 3-Day Performance & Intelligence Report (สรุปอันดับ Top Performers & ทิศทางกลยุทธ์ทุก 3 วัน)
                THREE_DAYS_SECS = 3 * 86400
                last_fb_ts = state.get("last_3day_feedback_ts", 0)
                if (time.time() - last_fb_ts >= THREE_DAYS_SECS or not last_fb_ts) and _publish_enabled():
                    try:
                        import feedback
                        sync_res = feedback.sync_all(use_ai=False)
                        if sync_res.get("youtube", {}).get("synced", 0) > 0 or sync_res.get("readawrite", {}).get("synced", 0) > 0:
                            overview = youtube_stats.get_channel_overview(SECOND_BRAIN)
                            brief_text = feedback.read_brief()
                            send_3day_performance_report_to_discord(overview, brief_text)
                            state["last_3day_feedback_ts"] = time.time()
                            state["last_3day_feedback_date"] = today_str
                            save_state(state)
                            log(f"[feedback] 🏆 ส่งรายงาน Top Performers & กลยุทธ์รอบ 3 วัน เข้า Discord สำเร็จ")
                    except Exception as fb_err:
                        log(f"[feedback] ❌ เกิดข้อผิดพลาดใน 3-day report: {fb_err}")
            except Exception:
                pass
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
