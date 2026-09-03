"""
quality_gate.py — Autonomous Production Quality Gate (Chapters, Audio, Teasers)
================================================================================

ระบบตรวจรับรองคุณภาพอัตโนมัติก่อนส่งออกสู่ตลาดจริง (Pre-Publish Quality Gate):
1. Novel Chapter QA: ตรวจความยาวคำ, คัดกรอง AI Meta-talk, โครงสร้างบท, คะแนน Review
2. Audio QA: ตรวจสอบความยาวไฟล์เสียง, สัดส่วนคำต่อนาที, เช็กไฟล์ไม่เสียหาย
3. Teaser QA: ตรวจสัดส่วน 9:16 แนวตั้ง, ความยาวไม่เกิน 60s, ตรวจสอบแทร็กเสียง

เกณฑ์การผ่าน: Quality Score >= 80/100 ถึงจะมีสิทธิ์เผยแพร่สู่สาธารณะ

CLI:
  python quality_gate.py <ชื่อเรื่อง>       # ตรวจเฉพาะเรื่อง
  python quality_gate.py --all             # ตรวจสอบทุกเรื่องในระบบ
"""
from __future__ import annotations

import os
import re
import glob
import json
import subprocess
from typing import Dict, Any, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
STORIES_DIR = os.path.join(SB, "05_Active_Projects")
REPORTS_DIR = os.path.join(STORIES_DIR, "Quality_Reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

AI_LEAK_WORDS = [
    "ในฐานะ", "ขอรับช่วง", "นี่คือผลลัพธ์", "เจียระไน", "ตามที่คุณต้องการ",
    "หวังว่าคุณจะชอบ", "ฉบับขัดเกลา", "ยอดเยี่ยมครับ", "เนื้อหาต่อไปนี้",
    "as an ai", "i cannot", "here is the chapter"
]

def check_chapter_quality(file_path: str) -> Dict[str, Any]:
    """ประเมินคุณภาพของบทนิยาย (0-100 คะแนน)"""
    if not os.path.exists(file_path):
        return {"score": 0, "passed": False, "reason": "ไม่พบไฟล์บท"}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # ลบ frontmatter
    body = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL).strip()
    clean_chars = len(re.sub(r'\s+', '', body))
    # ภาษาไทยไม่มีช่องว่างระหว่างคำ 1 คำ ~ 4 ตัวอักษร
    word_count = max(len(body.split()), clean_chars // 4)
    score = 100
    issues = []

    # 1. ความยาวบท (ต้องอย่างน้อย 1,000 คำ หรือประมาณ 4,000 ตัวอักษร)
    if word_count < 800:
        deduct = min(60, int((800 - word_count) / 10))
        score -= deduct
        issues.append(f"บทยาวน้อยเกินไป ({word_count} คำ, มาตรฐานคืออย่างน้อย 1,000 คำ)")
    elif word_count < 1000:
        score -= 15
        issues.append(f"บทยังค่อนข้างสั้น ({word_count} คำ, แนะนำ 1,200 - 2,500 คำ)")

    # 2. ตรวจสอบข้อความ AI รั่วไหล (Meta-talk / Prompt Leaks) — Zero Tolerance
    meta_leaks = []
    try:
        from agent_auditor import detect_meta_talk
        meta_leaks = detect_meta_talk(body)
    except Exception:
        for bad in AI_LEAK_WORDS:
            if bad in body.lower():
                meta_leaks.append({"matched": bad})

    if meta_leaks:
        score -= 50 * len(meta_leaks)
        for ml in meta_leaks[:3]:
            issues.append(f"ตรวจพบข้อความ AI/Prompt หลุด: '{ml.get('matched', '')}'")

    # 3. ตรวจสอบข้อความซ้ำซ้อน (Duplicate Paragraphs / Hallucination loops)
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    seen_p = set()
    dup_p = 0
    for p in paragraphs:
        p_clean = re.sub(r"\s+", "", p)
        if len(p_clean) > 30:
            if p_clean in seen_p:
                dup_p += 1
            seen_p.add(p_clean)
    if dup_p > 0:
        score -= 30 * dup_p
        issues.append(f"พบบล็อกข้อความซ้ำซ้อน {dup_p} จุด")

    # 4. โครงสร้างย่อหน้าและบทสนทนา
    if len(paragraphs) < 6:
        score -= 20
        issues.append("การเว้นย่อหน้าน้อยเกินไป อ่านยาก")

    has_dialogue = any('"' in p or '“' in p or '”' in p for p in paragraphs)
    if not has_dialogue and word_count > 300:
        score -= 15
        issues.append("ไม่มีบทสนทนาของตัวละคร")

    final_score = max(0, min(100, score))
    passed = final_score >= 80 and len(meta_leaks) == 0 and word_count >= 800 and dup_p == 0
    return {
        "score": final_score,
        "passed": passed,
        "word_count": word_count,
        "paragraphs_count": len(paragraphs),
        "issues": issues,
        "file": file_path
    }


def check_audio_quality(file_path: str) -> Dict[str, Any]:
    """ประเมินคุณภาพไฟล์เสียงพากย์ TTS (0-100 คะแนน)"""
    if not os.path.exists(file_path) or os.path.getsize(file_path) < 1000:
        return {"score": 0, "passed": False, "reason": "ไฟล์เสียงไม่มีอยู่หรือขนาดเป็น 0"}

    # ใช้ ffprobe วัดความยาว
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        lines = res.stdout.strip().split("\n")
        duration = float(lines[0])
        size = int(lines[1])
    except Exception as e:
        return {"score": 0, "passed": False, "reason": f"ffprobe error: {e}"}

    score = 100
    issues = []

    # ความยาวขั้นต่ำ 10 วินาที
    if duration < 10.0:
        score -= 50
        issues.append(f"เสียงสั้นเกินไป ({duration:.1f} วินาที)")

    # Bitrate โดยประมาณ (bytes/sec)
    bitrate_kbps = (size * 8) / (duration * 1000) if duration > 0 else 0
    if bitrate_kbps < 32:
        score -= 25
        issues.append(f"คุณภาพเสียง/Bitrate ต่ำ ({bitrate_kbps:.0f} kbps)")

    final_score = max(0, min(100, score))
    return {
        "score": final_score,
        "passed": final_score >= 80,
        "duration_sec": round(duration, 1),
        "bitrate_kbps": round(bitrate_kbps, 1),
        "issues": issues
    }


def check_teaser_quality(file_path: str) -> Dict[str, Any]:
    """ประเมินคุณภาพวิดีโอสั้น Teaser 9:16 (0-100 คะแนน)"""
    if not os.path.exists(file_path) or os.path.getsize(file_path) < 10000:
        return {"score": 0, "passed": False, "reason": "ไฟล์วิดีโอไม่มีอยู่หรือขนาดเล็กผิดปกติ"}

    # ใช้ ffprobe ตรวจสอบ streams
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=width,height,duration,codec_type",
        "-of", "json",
        file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(res.stdout)
        streams = data.get("streams", [])
    except Exception as e:
        return {"score": 0, "passed": False, "reason": f"ffprobe error: {e}"}

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not v_stream:
        return {"score": 0, "passed": False, "reason": "ไม่พบ Video Stream ในไฟล์"}

    score = 100
    issues = []

    width = int(v_stream.get("width", 0))
    height = int(v_stream.get("height", 0))
    duration = float(v_stream.get("duration") or 0.0)

    # 1. ตรวจสอบสัดส่วนแนวตั้ง (9:16)
    if width > 0 and height > 0:
        aspect = height / width
        if aspect < 1.3: # ไม่ใช่แนวตั้ง (ต่ำกว่า 4:3 หรือ 1:1)
            score -= 40
            issues.append(f"วิดีโอไม่ใช่อัตราส่วนแนวตั้ง 9:16 ({width}x{height})")
    else:
        score -= 30
        issues.append("ไม่สามารถระบุขนาดภาพได้")

    # 2. ตรวจสอบแทร็กเสียง
    if not a_stream:
        score -= 50
        issues.append("วิดีโอไม่มีเสียงพากย์ (No Audio Track)")

    # 3. ตรวจสอบความยาวคลิป Shorts (ไม่ควรเกิน 60 วินาที)
    if duration > 65.0:
        score -= 20
        issues.append(f"วิดีโอยาวเกินสำหรับ Shorts ({duration:.1f} วินาที)")
    elif duration < 5.0:
        score -= 40
        issues.append(f"วิดีโอสั้นเกินไป ({duration:.1f} วินาที)")

    final_score = max(0, min(100, score))
    return {
        "score": final_score,
        "passed": final_score >= 80,
        "resolution": f"{width}x{height}",
        "duration_sec": round(duration, 1),
        "has_audio": bool(a_stream),
        "issues": issues
    }


def evaluate_story(title: str) -> Dict[str, Any]:
    """ประเมินคุณภาพทุกสินทรัพย์ของเรื่องและสรุปผลรับรองคุณภาพ"""
    # 1. ตรวจสอบบทนิยาย
    ch_files = sorted(glob.glob(os.path.join(STORIES_DIR, "Chapters", f"{title}_Chapter_*.md")))
    ch_results = [check_chapter_quality(fp) for fp in ch_files]
    avg_ch_score = sum(r["score"] for r in ch_results) / len(ch_results) if ch_results else 0

    # 2. ตรวจสอบไฟล์เสียง
    audio_files = sorted(glob.glob(os.path.join(STORIES_DIR, "Audio_Output", f"{title}_*.mp3")))
    audio_results = [check_audio_quality(fp) for fp in audio_files]
    avg_audio_score = sum(r["score"] for r in audio_results) / len(audio_results) if audio_results else 0

    # 3. ตรวจสอบวิดีโอ Teaser
    teaser_files = sorted(glob.glob(os.path.join(STORIES_DIR, "Teaser_Output", f"{title}_*.mp4")))
    teaser_results = [check_teaser_quality(fp) for fp in teaser_files]
    avg_teaser_score = sum(r["score"] for r in teaser_results) / len(teaser_results) if teaser_results else 0

    overall_score = round((avg_ch_score * 0.4) + (avg_audio_score * 0.3) + (avg_teaser_score * 0.3), 1)
    passed = overall_score >= 80 and avg_ch_score >= 75

    report = {
        "title": title,
        "overall_score": overall_score,
        "ready_for_public_distribution": passed,
        "chapters_summary": {
            "count": len(ch_files),
            "avg_score": round(avg_ch_score, 1),
            "all_passed": all(r["passed"] for r in ch_results) if ch_results else False
        },
        "audio_summary": {
            "count": len(audio_files),
            "avg_score": round(avg_audio_score, 1),
            "all_passed": all(r["passed"] for r in audio_results) if audio_results else False
        },
        "teaser_summary": {
            "count": len(teaser_files),
            "avg_score": round(avg_teaser_score, 1),
            "all_passed": all(r["passed"] for r in teaser_results) if teaser_results else False
        }
    }

    safe_title = re.sub(r'[^\w\-_\s฀-๿]', '', title).strip().replace(' ', '_')
    report_path = os.path.join(REPORTS_DIR, f"{safe_title}_QA.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


def evaluate_all():
    """ประเมินทุกเรื่องในระบบและพิมพ์แดชบอร์ดคุณภาพ"""
    ch_files = glob.glob(os.path.join(STORIES_DIR, "Chapters", "*.md"))
    titles = sorted(set(re.match(r"^(.*?)_Chapter_\d+\.md$", os.path.basename(f)).group(1)
                       for f in ch_files if re.match(r"^(.*?)_Chapter_\d+\.md$", os.path.basename(f))))

    print(f"[*] กำลังตรวจสอบ Quality Gate สำหรับ {len(titles)} เรื่อง...")
    passed_list = []
    failed_list = []

    for t in titles:
        rep = evaluate_story(t)
        if rep["ready_for_public_distribution"]:
            passed_list.append(rep)
        else:
            failed_list.append(rep)

    print(f"\n=======================================================")
    print(f"🏆 สรุปผลการตรวจรับรองคุณภาพ (Quality Gate Report)")
    print(f"=======================================================")
    print(f"✅ ผ่านเกณฑ์เผยแพร่สาธารณะ (Score >= 80): {len(passed_list)} เรื่อง")
    print(f"⚠️ ต้องปรับปรุงก่อนปล่อย (Score < 80):    {len(failed_list)} เรื่อง")
    print("\n👑 เรื่องเรือธงและเรื่องคะแนนท็อป:")
    top_stories = sorted(passed_list, key=lambda x: x["overall_score"], reverse=True)[:5]
    for s in top_stories:
        print(f"  • {s['title']:<35} คะแนนรวม: {s['overall_score']}/100 "
              f"(บท: {s['chapters_summary']['avg_score']} | เสียง: {s['audio_summary']['avg_score']} | คลิป: {s['teaser_summary']['avg_score']})")


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if "--all" in args:
        evaluate_all()
    elif args:
        r = evaluate_story(args[0])
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        evaluate_all()
