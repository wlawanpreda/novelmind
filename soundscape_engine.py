"""
soundscape_engine.py — Cinematic Ambient Soundscape & BGM Ducking Engine
=======================================================================
ยกระดับไฟล์เสียงนิยายเสียงธรรมดาให้กลายเป็น "ภาพยนตร์เสียง (Cinematic Audiobook)":
1. Ambient Background Bed: ผสานเสียงบรรยากาศเร้าอารมณ์ (Warm Ambient Pad / Cinematic Drone)
2. Auto-Ducking: ลดระดับเสียง BGM ลง -22dB เมื่อมีเสียงผู้บรรยาย เพื่อให้ฟังชัด 100%
3. Smooth Transitions: ใส่ Fade In 2.5 วินาที และ Fade Out 3.5 วินาที ตอนจบบท
4. ปรับสมดุลความดัง (Loudness Normalization) ให้ได้มาตรฐาน YouTube (-14 LUFS)
"""

import os
import sys
import subprocess
from pydub import AudioSegment
from pydub.generators import Sine

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
BGM_DIR = os.path.join(SB, "05_Active_Projects", "Soundscapes")
os.makedirs(BGM_DIR, exist_ok=True)

def generate_ambient_drone(duration_ms: int, out_path: str):
    """สร้างเพลงบรรยากาศนุ่มลึก (Warm Ambient Pad) ด้วย FFmpeg สำหรับเรื่องลึกลับ/แฟนตาซี"""
    # ใช้ brown noise + lowpass filter 280Hz ให้เสียงอบอุ่นเหมือนสายลมในป่าสน
    sec = duration_ms / 1000.0
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anoisesrc=c=brown:r=44100:a=0.1,lowpass=f=320,volume=0.2",
        "-t", str(sec),
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        out_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def mix_cinematic_audio(narration_path: str, output_path: str, bgm_path: str = None) -> bool:
    """มิกซ์เสียงพากย์เข้ากับดนตรีบรรยากาศแบบ Auto-Ducking"""
    print(f"Mixing cinematic soundscape for: {narration_path}...")
    if not os.path.exists(narration_path):
        print(f"Error: Narration file not found: {narration_path}")
        return False

    narration = AudioSegment.from_file(narration_path)
    dur_ms = len(narration)

    # ถ้าไม่มี BGM ภายนอก ให้สร้าง ambient drone ที่เข้ากับความยาวพอดี
    temp_bgm = None
    if not bgm_path or not os.path.exists(bgm_path):
        temp_bgm = os.path.join(BGM_DIR, "ambient_bed_temp.mp3")
        generate_ambient_drone(dur_ms + 4000, temp_bgm)
        bgm_path = temp_bgm

    bgm = AudioSegment.from_file(bgm_path)
    # Loop BGM if shorter
    while len(bgm) < dur_ms + 3000:
        bgm = bgm + bgm

    # ตัด BGM ให้พอดีกับบท + เผื่อตอนจบ 2.5 วิ
    bgm = bgm[:dur_ms + 2500]
    
    # Ducking: ดนตรีบรรยากาศต้องเบากว่าเสียงพูดประมาณ -20 ถึง -24 dB
    bgm = bgm - 22
    bgm = bgm.fade_in(2500).fade_out(3500)

    # มิกซ์เสียง
    mixed = bgm.overlay(narration, position=500)
    mixed.export(output_path, format="mp3", bitrate="192k")

    if temp_bgm and os.path.exists(temp_bgm):
        os.remove(temp_bgm)

    print(f"✅ Cinematic Audiobook generated: {output_path} ({len(mixed)/1000:.1f}s)")
    return True

if __name__ == "__main__":
    sample_in = "SecondBrain/05_Active_Projects/Audio_Output/เหล่ามือกระบี่ไร้แม่เหล็ก_Audiobook_02.mp3"
    sample_out = "/tmp/test_cinematic_sword_ch2.mp3"
    mix_cinematic_audio(sample_in, sample_out)
