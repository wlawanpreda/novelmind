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

from agent_writer import generate_content_safe, strip_meta, NO_META, run_stage_6_audio_script

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

    outline = _read(os.path.join(sb, "02_Concept_Extraction", f"{title}_Outline.md"))
    characters = _read(os.path.join(sb, "04_Character_Database", f"{title}_Characters.md"))
    prev = _read(os.path.join(ch_dir, f"{title}_Chapter_{n-1:02d}.md"))
    if not outline or not prev:
        print(f"[!] ข้าม {title} ตอน {n}: ขาด outline หรือบทก่อนหน้า")
        return False

    print(f"\n[📖] เขียน '{title}' ตอนที่ {n}...")
    prev_tail = prev[-3500:]
    scene_words = int(os.environ.get("ANSRE_SCENE_WORDS", "450"))

    # A) วาง beats 4 ฉากของตอนนี้
    beat_prompt = f"""คุณคือ Narrative Planner วางฉากนิยายไทย
โครงเรื่องรวม (มีสรุปรายตอน + กฎของโลก/ระบบ):
{outline[:3000]}

ตอนก่อนหน้า (ช่วงท้าย) จบไว้แบบนี้:
{prev_tail}

จงวาง 4 ฉากย่อย (beats) สำหรับ "ตอนที่ {n}" ให้ต่อเนื่องจากตอนก่อนอย่างสมเหตุผล เดินเรื่องคืบหน้า
ตอบ JSON เท่านั้น: [{{"scene_number":"1","setting":"...","goal":"...","action":"...","climax":"..."}}, ... 4 ฉาก]"""
    try:
        beats = json.loads(generate_content_safe("planner", beat_prompt, is_json=True))
    except Exception:
        beats = [{"scene_number": str(i + 1), "setting": f"ฉาก {i+1}", "goal": "เดินเรื่อง",
                  "action": "เหตุการณ์ต่อเนื่อง", "climax": "ปมตอน"} for i in range(4)]

    # B) เขียนทีละฉาก
    scenes, prev_in_chapter = [], ""
    for i, b in enumerate(beats[:4]):
        print(f"    ฉาก {i+1}/4...")
        sp = f"""คุณคือ Master Novelist เขียนนิยายไทยกระชับ ลื่นไหล
เรื่อง: {title} | ตอนที่ {n} | ฉากที่ {i+1}

กฎของโลก/ระบบ (ห้ามขัดแย้งตัวเลข/สถานะ):
{outline[:2200]}

ตัวละคร: {characters[:1500]}

ช่วงท้ายตอนก่อน: {prev_tail[-1500:]}
ฉากก่อนหน้าในตอนนี้: {prev_in_chapter[-1800:] or '(เริ่มตอน)'}

แผนฉากนี้: สถานที่={b.get('setting')} | เป้าหมาย={b.get('goal')} | เหตุการณ์={b.get('action')} | จุดสำคัญ={b.get('climax')}

เขียนฉากนี้ ~{scene_words} คำ ต่อเนื่องเป็นธรรมชาติ ไม่ยืดเยื้อ คงความสอดคล้องของกฎ/ตัวเลข/สถานะ"""
        sc = strip_meta(generate_content_safe("writer", sp + NO_META))
        scenes.append(sc)
        prev_in_chapter += "\n\n" + sc

    draft = "\n\n".join(scenes)

    # C) เกลา + cliffhanger
    polish = f"""คุณคือ Chief Literary Editor เกลานิยายไทยตอนที่ {n} ของเรื่อง {title}:
{draft}

กฎของโลก/ระบบ (แก้จุดที่ขัดแย้งให้ถูก): {outline[:2000]}

เกลาสำนวนให้คม ลื่นไหล แก้จุดขัดแย้งกฎ/ตัวเลข ปิดท้ายด้วย cliffhanger ชวนอ่านต่อ
**ห้ามขยายความยาว** คงความยาวใกล้เคียงเดิม"""
    final = strip_meta(generate_content_safe("enhancer", polish + NO_META))

    # ป้องกัน silent-fail: ถ้าบทสั้นผิดปกติ (LLM ล่ม/หลุดกลางคัน) อย่าบันทึกทับเป็น garbage
    # ใช้ draft (ก่อนเกลา) แทนถ้ายาวกว่า แล้วถ้ายังสั้นมากก็ข้ามไป (กันไฟล์ 300 ตัวอักษร)
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

    # save
    with open(os.path.join(ch_dir, f"{title}_Chapter_{n:02d}.md"), "w", encoding="utf-8") as f:
        f.write(final)
    with open(os.path.join(as_dir, f"{title}_AudioScript_{n:02d}.md"), "w", encoding="utf-8") as f:
        f.write(audio_script)
    print(f"[+] บันทึก {title} ตอนที่ {n} ({len(final)} ตัวอักษร)")
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
                if not write_next_chapter(sb, title, n):
                    break
        return

    for title in projects:
        for _ in range(count):
            n = _next_n(sb, title)
            if not write_next_chapter(sb, title, n):
                break


if __name__ == "__main__":
    main()
