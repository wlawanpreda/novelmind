"""
ANSRE Chapter Continuer — เขียนตอนถัดไป (บทที่ 2, 3, ...) ต่อจากบทที่ 1
======================================================================
อ่าน Outline + Characters + บทก่อนหน้า แล้วเขียนตอนถัดไปให้ต่อเนื่อง
(beats -> scenes -> polish -> audio) โดยคงกฎของโลก/ระบบและความต่อเนื่อง

ใช้ stage helpers ร่วมกับ agent_writer (generate_content_safe / strip_meta / NO_META)

CLI:
  python chapter_continuer.py [SecondBrain] [จำนวนตอนที่จะเขียนต่อ] [--title "..."]
  ตัวอย่าง: python chapter_continuer.py ./SecondBrain 2          # เขียนต่อ 2 ตอนทุกเรื่อง
            python chapter_continuer.py ./SecondBrain 1 --title ระบบความเกรงใจ
"""
from __future__ import annotations

import os
import re
import sys
import glob
import json

ROOT = os.path.dirname(os.path.abspath(__file__))
_VENV_PY = os.path.join(ROOT, ".venv", "bin", "python")
if os.path.exists(_VENV_PY) and sys.executable != _VENV_PY:
    try:
        import requests
        import google.genai
    except ImportError:
        os.execv(_VENV_PY, [_VENV_PY] + sys.argv)


from agent_writer import generate_content_safe, strip_meta, NO_META, run_stage_6_audio_script

try:
    from multi_reviewer import run_multi_agent_review_loop
except Exception:
    run_multi_agent_review_loop = None

try:
    from story_bible import get_continuity_prompt_context, update_story_bible_from_chapter
except Exception:
    get_continuity_prompt_context = None
    update_story_bible_from_chapter = None

try:
    from discord_reporter import send_review_summary_to_discord
except Exception:
    send_review_summary_to_discord = None

THAI = "฀-๿"


def _clean_title(t):
    return re.sub(r'[^\w\-_\s' + THAI + r']', '', t).strip().replace(' ', '_')


def _read(fp):
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _projects(sb):
    """หาเรื่องที่มีบทแล้ว (จากไฟล์ *_Chapter_01.md)"""
    ch_dir = os.path.join(sb, "05_Active_Projects", "Chapters")
    titles = set()
    for fp in glob.glob(os.path.join(ch_dir, "*_Chapter_01.md")):
        titles.add(os.path.basename(fp).rsplit("_Chapter_01.md", 1)[0])
    return sorted(titles)


def _next_n(sb, title):
    ch_dir = os.path.join(sb, "05_Active_Projects", "Chapters")
    n = 0
    for fp in glob.glob(os.path.join(ch_dir, f"{title}_Chapter_*.md")):
        m = re.search(r"_Chapter_(\d+)\.md$", fp)
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def write_next_chapter(sb, title, n):
    ch_dir = os.path.join(sb, "05_Active_Projects", "Chapters")
    as_dir = os.path.join(sb, "05_Active_Projects", "Audio_Scripts")
    os.makedirs(as_dir, exist_ok=True)

    outline_fp = os.path.join(sb, "02_Concept_Extraction", f"{title}_Outline.md")
    if not os.path.exists(outline_fp):
        cands = glob.glob(os.path.join(sb, "02_Concept_Extraction", f"*{title[:4]}*_Outline.md"))
        if cands:
            outline_fp = cands[0]
    outline = _read(outline_fp)

    char_fp = os.path.join(sb, "04_Character_Database", f"{title}_Characters.md")
    if not os.path.exists(char_fp):
        cands = glob.glob(os.path.join(sb, "04_Character_Database", f"*{title[:4]}*_Characters.md"))
        if cands:
            char_fp = cands[0]
    characters = _read(char_fp)

    prev = _read(os.path.join(ch_dir, f"{title}_Chapter_{n-1:02d}.md"))
    if not outline or not prev:
        print(f"[!] ข้าม {title} ตอน {n}: ขาด outline หรือบทก่อนหน้า")
        return False

    print(f"\n[📖] เขียน '{title}' ตอนที่ {n}...")
    prev_tail = prev[-3500:]
    scene_words = int(os.environ.get("ANSRE_SCENE_WORDS", "450"))
    bible_context = get_continuity_prompt_context(title, n) if get_continuity_prompt_context else ""

    # A) วาง beats 4 ฉากของตอนนี้
    beat_prompt = f"""คุณคือ Narrative Planner วางฉากนิยายไทย
โครงเรื่องรวม (มีสรุปรายตอน + กฎของโลก/ระบบ):
{outline[:2500]}

{bible_context}

ตอนก่อนหน้า (ช่วงท้าย) จบไว้แบบนี้:
{prev_tail}

จงวาง 4 ฉากย่อย (beats) สำหรับ "ตอนที่ {n}" ให้ต่อเนื่องจากตอนก่อนอย่างสมเหตุผล เดินเรื่องคืบหน้า
ตอบ JSON เท่านั้น: [{{"scene_number":"1","setting":"...","goal":"...","action":"...","climax":"..."}}, ... 4 ฉาก]"""
    try:
        raw_beats = generate_content_safe("planner", beat_prompt, is_json=True)
        beats = json.loads(raw_beats)
        if isinstance(beats, dict):
            beats = beats.get("scenes") or beats.get("beats") or list(beats.values())
        if not isinstance(beats, list):
            raise ValueError("beats is not a list")
    except Exception:
        beats = [{"scene_number": str(i + 1), "setting": f"ฉาก {i+1}", "goal": "เดินเรื่อง",
                  "action": "เหตุการณ์ต่อเนื่อง", "climax": "ปมตอน"} for i in range(4)]

    # B) เขียนทีละฉาก
    scenes, prev_in_chapter = [], ""
    for i, b in enumerate(beats[:4]):
        print(f"    ฉาก {i+1}/4...")
        sp = f"""คุณคือ Master Novelist เขียนนิยายไทยกระชับ ลื่นไหล
เรื่อง: {title} | ตอนที่ {n} | ฉากที่ {i+1}

{bible_context}

กฎของโลก/ระบบ (ห้ามขัดแย้งตัวเลข/สถานะ):
{outline[:1800]}

ตัวละคร: {characters[:1200]}

ช่วงท้ายตอนก่อน: {prev_tail[-1500:]}
ฉากก่อนหน้าในตอนนี้: {prev_in_chapter[-1800:] or '(เริ่มตอน)'}

แผนฉากนี้: สถานที่={b.get('setting')} | เป้าหมาย={b.get('goal')} | เหตุการณ์={b.get('action')} | จุดสำคัญ={b.get('climax')}

เขียนฉากนี้ ~{scene_words} คำ ต่อเนื่องเป็นธรรมชาติ ไม่ยืดเยื้อ คงความสอดคล้องของกฎ/ตัวเลข/สถานะ"""
        sc = strip_meta(generate_content_safe("writer", sp + NO_META))
        scenes.append(sc)
        prev_in_chapter += "\n\n" + sc

    draft = "\n\n".join(scenes)

    # C) Multi-Agent Editorial Review Board (>= 3 Iteration Rounds & Discord Reporting)
    min_rev_rounds = int(os.environ.get("ANSRE_REVIEW_MIN_ROUNDS", "3"))
    max_rev_rounds = int(os.environ.get("ANSRE_REVIEW_MAX_ROUNDS", "5"))
    target_rev_score = float(os.environ.get("ANSRE_REVIEW_TARGET_SCORE", "8.5"))
    
    review_report = None
    if run_multi_agent_review_loop:
        try:
            final, review_report = run_multi_agent_review_loop(
                title=f"{title} ตอนที่ {n}",
                chapter_text=draft,
                outline=outline,
                characters=characters,
                world=outline,
                min_rounds=min_rev_rounds,
                max_rounds=max_rev_rounds,
                target_score=target_rev_score,
                verbose=True
            )
            if send_review_summary_to_discord and review_report:
                try:
                    send_review_summary_to_discord(title, n, review_report)
                except Exception as de:
                    print(f"    [!] Discord reporter warning: {de}")
        except Exception as e:
            print(f"    [!] Multi-agent review loop error: {e} — กำลัง fallback สู่ standard editor...")
            polish = f"""คุณคือ Chief Literary Editor เกลานิยายไทยตอนที่ {n} ของเรื่อง {title}:
{draft}

กฎของโลก/ระบบ (แก้จุดที่ขัดแย้งให้ถูก): {outline[:2000]}

เกลาสำนวนให้คม ลื่นไหล แก้จุดขัดแย้งกฎ/ตัวเลข ปิดท้ายด้วย cliffhanger ชวนอ่านต่อ
**ห้ามขยายความยาว** คงความยาวใกล้เคียงเดิม"""
            final = strip_meta(generate_content_safe("enhancer", polish + NO_META))
    else:
        polish = f"""คุณคือ Chief Literary Editor เกลานิยายไทยตอนที่ {n} ของเรื่อง {title}:
{draft}

กฎของโลก/ระบบ (แก้จุดที่ขัดแย้งให้ถูก): {outline[:2000]}

เกลาสำนวนให้คม ลื่นไหล แก้จุดขัดแย้งกฎ/ตัวเลข ปิดท้ายด้วย cliffhanger ชวนอ่านต่อ
**ห้ามขยายความยาว** คงความยาวใกล้เคียงเดิม"""
        final = strip_meta(generate_content_safe("enhancer", polish + NO_META))

    # ป้องกัน silent-fail: ถ้าบทสั้นผิดปกติ (LLM ล่ม/หลุดกลางคัน) อย่าบันทึกทับเป็น garbage
    min_chars = int(os.environ.get("ANSRE_MIN_CHAPTER_CHARS", "1500"))
    if len(final) < min_chars and len(draft) > len(final):
        print(f"    [!] บทเกลาสั้นผิดปกติ ({len(final)}) — ใช้ draft ก่อนเกลา ({len(draft)}) แทน")
        final = draft
    if len(final) < min_chars:
        print(f"[!] ข้าม {title} ตอน {n}: ผลลัพธ์สั้นเกินไป ({len(final)}<{min_chars}) "
              "— อาจเพราะ LLM ล่ม/หลุดกลางคัน ลองใหม่ภายหลัง")
        return False

    # D) audio script (ใช้ฟังก์ชันเดียวกับ stage 6 ที่แบ่ง chunk กัน token limit)
    audio_script = run_stage_6_audio_script(f"{title} ตอนที่ {n}", final)

    # Automatic Inspection & Sanitization: ล้าง meta-talk อัตโนมัติก่อนบันทึกไฟล์เสมอ
    try:
        from agent_auditor import sanitize_meta_talk
        final = sanitize_meta_talk(final)
        audio_script = sanitize_meta_talk(audio_script)
    except Exception:
        pass

    # save
    with open(os.path.join(ch_dir, f"{title}_Chapter_{n:02d}.md"), "w", encoding="utf-8") as f:
        f.write(final)
    with open(os.path.join(as_dir, f"{title}_AudioScript_{n:02d}.md"), "w", encoding="utf-8") as f:
        f.write(audio_script)
    print(f"[+] บันทึก {title} ตอนที่ {n} ({len(final)} ตัวอักษร)")

    if update_story_bible_from_chapter:
        try:
            update_story_bible_from_chapter(title, n, final)
        except Exception as be:
            print(f"    [!] Story Bible update warning: {be}")

    return True


def _opt(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def main():
    args = [a for a in sys.argv[1:]]
    sb = "./SecondBrain"
    count = 1
    only_title = _opt(args, "--title")
    # --target N: เขียนจนแต่ละเรื่องมี N ตอน · --max-per-run: เพิ่มได้สูงสุดกี่ตอน/เรื่อง/รอบ
    # --max-stories: ทำได้กี่เรื่อง/รอบ (กันงบบาน — เลือกเรื่องที่ "ห่างเป้าสุด" ก่อน)
    target = _opt(args, "--target")
    target = int(target) if target and target.isdigit() else None
    max_per_run = int(_opt(args, "--max-per-run", "99") or 99)
    max_stories = int(_opt(args, "--max-stories", "999") or 999)

    pos = [a for a in args if not a.startswith("--")
           and a not in (only_title or "", str(target or ""))]
    # ระวัง: ค่าตามหลัง flag ไม่ใช่ positional
    skip = set()
    for fl in ("--title", "--target", "--max-per-run", "--max-stories"):
        if fl in args:
            skip.add(args.index(fl) + 1)
    pos = [a for idx, a in enumerate(args) if not a.startswith("--") and idx not in skip]
    if pos:
        sb = pos[0]
    if len(pos) > 1:
        try:
            count = int(pos[1])
        except ValueError:
            pass

    projects = _projects(sb)
    if only_title:
        projects = [t for t in projects if only_title in t]
    if not projects:
        print("[!] ไม่พบเรื่องที่มีบทที่ 1 แล้ว — เขียนบทแรกก่อนด้วย agent_writer")
        return

    if target:
        # เขียนเรื่องที่ยังไม่ถึงเป้า เรียงตาม "ห่างเป้าสุด" ก่อน → กระจายความลึกทั่วถึง
        gaps = [(t, target - (_next_n(sb, t) - 1)) for t in projects]
        gaps = sorted([g for g in gaps if g[1] > 0], key=lambda x: -x[1])[:max_stories]
        if not gaps:
            print(f"[continue] ทุกเรื่องถึงเป้า {target} ตอนแล้ว ✅")
            return
        print(f"[continue] เป้า {target} ตอน · ทำ {len(gaps)} เรื่อง (สูงสุด {max_per_run} ตอน/เรื่อง/รอบ)")
        for title, gap in gaps:
            for _ in range(min(gap, max_per_run)):
                n = _next_n(sb, title)
                try:
                    if not write_next_chapter(sb, title, n):
                        break
                except Exception as e:
                    print(f"[!] เกิดข้อผิดพลาดในการเขียน {title} ตอนที่ {n}: {e}")
                    break
        return

    for title in projects:
        for _ in range(count):
            n = _next_n(sb, title)
            try:
                if not write_next_chapter(sb, title, n):
                    break
            except Exception as e:
                print(f"[!] เกิดข้อผิดพลาดในการเขียน {title} ตอนที่ {n}: {e}")
                break


if __name__ == "__main__":
    main()
