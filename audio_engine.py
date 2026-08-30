import os
import re
import sys
import glob
import tempfile
import requests
import asyncio
import edge_tts
from typing import List, Dict, Any, Tuple
from gtts import gTTS
from pydub import AudioSegment

# Setup Environment variables
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
TTS_ENGINE = os.environ.get("TTS_ENGINE", "edge-tts") # Default to edge-tts for high quality free Thai voice, can be: edge-tts, macos, gtts, elevenlabs

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                k_str = key.strip()
                v_str = val.strip().strip('"').strip("'")
                if k_str == "ELEVENLABS_API_KEY" and not ELEVENLABS_API_KEY:
                    ELEVENLABS_API_KEY = v_str
                    os.environ["ELEVENLABS_API_KEY"] = ELEVENLABS_API_KEY
                elif k_str == "TTS_ENGINE":
                    TTS_ENGINE = v_str

# Default ElevenLabs Voice Mapping (You can customize these voice IDs)
VOICE_MAP = {
    "ผู้บรรยาย": "21m00Tcm4TlvDq8ikWAM",  # Rachel (calm narrator)
    "วายุ": "ErXwobaYiN019PkySvjV",        # Antoni (male lead)
    "ระบบ": "AZnzlk1XvdvUeBnXmlld",        # Domi (clear system voice)
    "default": "pNInz6obpgqjVWtJ45xs"      # Lily (default helper)
}

# --- มาร์กเกอร์ที่ "ห้ามอ่านออกเสียง" (cue/stage direction ที่ปนเนื้อ) ---
_SFX_INLINE = re.compile(r"\[\s*SFX\s*:[^\]]*\]", re.IGNORECASE)        # [SFX: ...] ที่ไหนก็ได้ในบรรทัด
_TONE_INLINE = re.compile(r"\[[^\]]*โทน\s*:[^\]]*\]")                    # [ชื่อ, โทน: ...] แบบ inline
_CJK = re.compile(r"[　-〿㐀-䶿一-鿿豈-﫿]")  # อักษรจีน/ญี่ปุ่นที่หลุดมา
# speaker label แบบ "ชื่อ:" (ไม่มีวงเล็บ) ที่ต้นบรรทัด — ชื่อสั้น ไม่มีช่องว่าง
_SPEAKER_PREFIX = re.compile(r"^([^\s:：\[\]]{1,20})\s*[:：]\s+")
# tag แบบวงเล็บ [ชื่อ, โทน: x] ที่ต้นบรรทัด
_SPEAKER_BRACKET = re.compile(r"^\[([^,\]]+)(?:,\s*โทน\s*:\s*([^\]]+))?\]\s*(.*)$")


def _clean_narration(text: str) -> str:
    """ลบ cue/มาร์กเกอร์ที่ไม่ควรอ่านออกเสียงออกจากข้อความบรรยาย"""
    text = _SFX_INLINE.sub(" ", text)
    text = _TONE_INLINE.sub(" ", text)
    text = _CJK.sub("", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def parse_audio_script(filepath: str) -> List[Dict[str, Any]]:
    """แตกบทเสียง Markdown เป็น segment (speaker/tone/text) โดย "ล้าง cue ทุกชนิด และตัด meta-talk" ไม่ให้ TTS อ่าน
    ครอบ: [SFX:...] กลางบรรทัด, speaker แบบ 'ชื่อ:' (ไม่มีวงเล็บ), [ชื่อ, โทน:...], อักษรจีนหลุด"""
    segments = []
    with open(filepath, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # ล้าง AI meta-talk ออกก่อน
    try:
        from agent_auditor import sanitize_meta_talk
        raw_text = sanitize_meta_talk(raw_text)
    except Exception:
        pass

    lines = raw_text.splitlines()
    current_speaker = "ผู้บรรยาย"
    current_tone = "ปกติ"
    title_added = False

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("---"):
            current_speaker = "ผู้บรรยาย"
            current_tone = "ปกติ"
            continue

        # 0) ดึงชื่อตอนให้อ่านออกเสียงอย่างสม่ำเสมอเป็น segment แรกๆ (ไม่ว่าจะขึ้นต้นด้วย ##, **, หรือ [ชื่อตอน])
        if not title_added and re.search(r"(?:ตอนที่|บทที่)\s*\d+", line):
            m_t = re.search(r"((?:ตอนที่|บทที่)\s*\d+[^#\*\(\]]*)", line)
            if m_t:
                clean_t = re.sub(r"[*#`\[\]:]", " ", m_t.group(1)).strip()
                clean_t = re.sub(r"\s+", " ", clean_t)
                # ลบคำว่า ผู้บรรยาย หรือ ชื่อตอน ที่อาจติดมา
                clean_t = re.sub(r"^(?:ผู้บรรยาย|ชื่อตอน)\s*", "", clean_t).strip()
                if len(clean_t) >= 6:
                    segments.append({"type": "dialog", "speaker": "ผู้บรรยาย", "tone": "ปกติ", "text": clean_t})
                    title_added = True
                    continue

        if line.startswith("#"):
            continue

        # 1) SFX ที่ "ต้นบรรทัด" และทั้งบรรทัดเป็น SFX → พอส (placeholder เสียงประกอบ)
        if re.match(r"^\[\s*SFX\s*:", line, re.IGNORECASE) and _clean_narration(line) == "":
            segments.append({"type": "sfx", "speaker": "SFX", "tone": "", "text": line})
            continue

        # 2) speaker tag แบบวงเล็บ [ชื่อ, โทน: x] ที่ต้นบรรทัด
        mb = _SPEAKER_BRACKET.match(line)
        if mb and "SFX" not in mb.group(1).upper():
            current_speaker = mb.group(1).strip()
            current_tone = (mb.group(2) or "ปกติ").strip()
            line = mb.group(3).strip()

        # 3) speaker label แบบ 'ชื่อ:' (ไม่มีวงเล็บ) ที่ต้นบรรทัด → เปลี่ยนผู้พูด ไม่อ่านชื่อ
        ms = _SPEAKER_PREFIX.match(line)
        if ms:
            current_speaker = ms.group(1).strip()
            current_tone = "ปกติ"
            line = line[ms.end():].strip()

        # ข้าม bullet/quote markdown
        if line.startswith(("-", "*", ">")):
            continue

        # 4) ถ้ามี [SFX:...] แทรกกลางบรรทัด → ใส่พอสไว้ ก่อนล้างออกจากข้อความ
        had_inline_sfx = bool(_SFX_INLINE.search(line))
        clean = _clean_narration(line)
        if had_inline_sfx:
            segments.append({"type": "sfx", "speaker": "SFX", "tone": "", "text": "(pause)"})
        if clean:
            segments.append({"type": "dialog", "speaker": current_speaker,
                             "tone": current_tone, "text": clean})

    return segments


from pydub.generators import Sine, WhiteNoise, Pulse


def generate_sfx_cue(cue_text: str) -> AudioSegment:
    """สร้างเสียงประกอบ (SFX) อัตโนมัติสำหรับคิวเสียงต่าง ๆ เช่น หัวใจเต้น, นาฬิกา, เสียงระบบ, ลม"""
    low = cue_text.lower()
    try:
        if any(k in low for k in ["heart", "หัวใจ", "เต้น", "pulse", "thump"]):
            # Heartbeat: double low thump (55Hz)
            t1 = Sine(55).to_audio_segment(duration=140).fade_in(20).fade_out(70) - 4
            gap = AudioSegment.silent(duration=110)
            t2 = Sine(50).to_audio_segment(duration=160).fade_in(20).fade_out(80) - 6
            rest = AudioSegment.silent(duration=450)
            return t1 + gap + t2 + rest
        elif any(k in low for k in ["clock", "นาฬิกา", "นับถอยหลัง", "tick", "ticking", "เวลา"]):
            # Clock ticking: sharp clicks
            click1 = Pulse(1400).to_audio_segment(duration=35).fade_out(25) - 8
            pause = AudioSegment.silent(duration=450)
            click2 = Pulse(1200).to_audio_segment(duration=35).fade_out(25) - 9
            return click1 + pause + click2 + pause
        elif any(k in low for k in ["system", "ระบบ", "ding", "chime", "ping", "เตือน"]):
            # System notification: 2-tone harmonic chime
            chime1 = Sine(880).to_audio_segment(duration=160).fade_in(15).fade_out(60) - 10
            chime2 = Sine(1760).to_audio_segment(duration=380).fade_in(15).fade_out(150) - 12
            return chime1 + chime2 + AudioSegment.silent(duration=200)
        elif any(k in low for k in ["boom", "thunder", "ระเบิด", "ฟ้าผ่า", "คำราม"]):
            # Low rumble boom
            rumble = Sine(45).to_audio_segment(duration=800).fade_in(40).fade_out(400) - 3
            return rumble
        elif any(k in low for k in ["whoosh", "wind", "ลม", "สวบ", "วูบ"]):
            # Sweeping air whoosh
            air = WhiteNoise().to_audio_segment(duration=450).fade_in(150).fade_out(250) - 16
            return air
        else:
            # Default dramatic pause with subtle bass ambient tone
            subtle = Sine(70).to_audio_segment(duration=500).fade_in(100).fade_out(250) - 18
            return subtle + AudioSegment.silent(duration=300)
    except Exception:
        return AudioSegment.silent(duration=800)


def generate_tts_gtts(text: str, temp_dir: str) -> AudioSegment:
    """Generate free Thai speech using gTTS and return as AudioSegment."""
    temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", dir=temp_dir, delete=False)
    temp_file.close()
    
    tts = gTTS(text=text, lang='th', slow=False)
    tts.save(temp_file.name)
    
    segment = AudioSegment.from_file(temp_file.name)
    try:
        os.remove(temp_file.name)
    except:
        pass
    return segment

def generate_tts_macos_say(text: str, temp_dir: str) -> AudioSegment:
    """Generate free high-quality Thai speech using macOS built-in Kanya voice."""
    import subprocess
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", dir=temp_dir, delete=False)
    temp_file.close()
    
    # Run macOS 'say' command to output to wav file with high quality Kanya voice
    cmd = ["say", "-v", "Kanya", "-o", temp_file.name, "--data-format=LEI16@22050", text]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        segment = AudioSegment.from_file(temp_file.name)
    except Exception as e:
        print(f"    [!] macOS say failed: {e}. Falling back to gTTS...")
        return generate_tts_gtts(text, temp_dir)
    finally:
        try:
            os.remove(temp_file.name)
        except:
            pass
    return segment

_MALE_V = "th-TH-NiwatNeural"
_FEMALE_V = "th-TH-PremwadeeNeural"
# แผนเสียงต่อตัวละคร (สร้างต่อเรื่องด้วย assign_voices) — speaker -> (voice, pitch)
VOICE_ASSIGN = {}


MALE_NAMES = {"รัน", "ชล", "บอย", "เอก", "นนท์", "ทศ", "ก้อง", "แทน", "ภัทร", "วิน", "หมวด", "สารวัตร", "เชฟ", "บอส", "ลุง", "นาย", "อคิน", "วายุ", "พศิน", "เก่ง", "โซล", "ศิลา"}
FEMALE_NAMES = {"หญิงสาว", "พราว", "มิ้นท์", "เกล", "แพรวา", "หลิน", "ฟ้า", "เจน", "เมย์", "จิ๊บ", "คุณหญิง", "แม่", "ป้า", "ยาย", "สาว", "แอน", "นุ่น", "อัญชิสา"}


def assign_voices(segments, characters_text=""):
    """กำหนดเสียง+pitch ต่อตัวละครอัตโนมัติ (เดาเพศจากไฟล์ตัวละคร + รายชื่อตัวละคร + แยก pitch ให้เสียงไม่ซ้ำ)"""
    import itertools
    ctext = (characters_text or "").lower()
    female_kw = ["หญิง", "สาว", "นาง", "แม่", "ป้า", "ย่า", "ยาย", "ราชินี", "นางเอก", "เธอ", "หล่อน", "คุณหญิง"]
    male_kw = ["ชาย", "หนุ่ม", "นาย", "พ่อ", "ลุง", "ปู่", "กษัตริย์", "พระเอก", "เขา", "สูท", "บิ๊กไบค์", "ตำรวจ", "หมวด", "ผู้กอง"]
    mp = itertools.cycle(["+0Hz", "-15Hz", "-28Hz", "+12Hz", "-40Hz"])
    fp = itertools.cycle(["+10Hz", "-6Hz", "+25Hz", "-15Hz", "+38Hz"])
    seen, assign = [], {}
    for s in segments:
        sp = s.get("speaker", "")
        if sp and sp != "SFX" and sp not in seen:
            seen.append(sp)
    for sp in seen:
        low = sp.lower()
        if sp == "ผู้บรรยาย":
            assign[sp] = (_FEMALE_V, "+0Hz")             # ผู้บรรยาย = หญิงโทนปกติ
        elif "ระบบ" in sp or low == "system":
            assign[sp] = (_MALE_V, "-45Hz")              # ระบบ = เสียงต่ำ จักรกล
        elif sp in MALE_NAMES or any(mn in low for mn in ["รัน", "ชล", "บอย", "ตำรวจ", "หมวด"]):
            assign[sp] = (_MALE_V, next(mp))             # ตัวละครชายที่ระบุชัดเจน
        elif sp in FEMALE_NAMES or any(fn in low for fn in ["หญิง", "สาว", "นาง"]):
            assign[sp] = (_FEMALE_V, next(fp))           # ตัวละครหญิงที่ระบุชัดเจน
        else:
            i = ctext.find(low)
            ctx = ctext[max(0, i - 60):i + 350] if i >= 0 else ""
            is_f = any(k in ctx for k in female_kw)
            is_m = any(k in ctx for k in male_kw)
            # ถ้าเป็นตัวเอก และมีลักษณะชาย
            if "ตัวเอก" in ctx and not is_f:
                is_m = True
            if is_f and not is_m:
                assign[sp] = (_FEMALE_V, next(fp))
            elif is_m and not is_f:
                assign[sp] = (_MALE_V, next(mp))
            else:                                         # เดาไม่ออก → สลับให้ต่างกัน
                assign[sp] = (_MALE_V, next(mp)) if len(assign) % 2 else (_FEMALE_V, next(fp))
    return assign


def generate_tts_edgetts(text: str, speaker: str, temp_dir: str) -> AudioSegment:
    """Generate free high-quality Thai speech using edge-tts (Microsoft Edge neural voices)."""
    from concurrent.futures import ThreadPoolExecutor

    # 1) แผนเสียงต่อเรื่อง (multi-voice) ถ้ามี
    if speaker in VOICE_ASSIGN:
        voice, pitch = VOICE_ASSIGN[speaker]
    else:
        # 2) fallback heuristic เพศจากชื่อ
        voice, pitch = _FEMALE_V, "+0Hz"
        speaker_lower = speaker.lower()
        male_names = ["อคิน", "วายุ", "ชาย", "พ่อ", "หมอ", "ลุง", "ตำรวจ", "พศิน", "เอก", "นนท์", "เก่ง"]
        if speaker in ["อคิน", "วายุ", "ระบบ", "niwat"] or any(n in speaker_lower for n in male_names):
            voice = _MALE_V

    temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", dir=temp_dir, delete=False)
    temp_file.close()

    async def _speak():
        communicate = edge_tts.Communicate(text, voice, pitch=pitch)
        await communicate.save(temp_file.name)
        
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            with ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _speak())
                future.result()
        else:
            loop.run_until_complete(_speak())
            
        segment = AudioSegment.from_file(temp_file.name)
    except Exception as e:
        print(f"    [!] edge-tts failed: {e}. Falling back to gTTS...")
        return generate_tts_gtts(text, temp_dir)
    finally:
        try:
            os.remove(temp_file.name)
        except:
            pass
    return segment

def generate_tts_elevenlabs(text: str, speaker: str, temp_dir: str) -> AudioSegment:
    """Generate high-quality emotional speech using ElevenLabs API."""
    voice_id = VOICE_MAP.get(speaker, VOICE_MAP["default"])
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    
    # We request multilingual model to support Thai text
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    response = requests.post(url, json=data, headers=headers)
    if response.status_code != 200:
        print(f"[!] ElevenLabs API Error {response.status_code}: {response.text}")
        print("[*] Falling back to gTTS...")
        return generate_tts_gtts(text, temp_dir)
        
    temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", dir=temp_dir, delete=False)
    temp_file.write(response.content)
    temp_file.close()
    
    segment = AudioSegment.from_file(temp_file.name)
    try:
        os.remove(temp_file.name)
    except:
        pass
    return segment

def ms_to_srt_time(ms: int) -> str:
    """Convert milliseconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    ms %= 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"

def render_script_to_audio(script_path: str, output_path: str) -> bool:
    """Read script, generate audio segments, stitch them together, save MP3 and SRT subtitles."""
    print(f"[*] Parsing script: {script_path}")
    segments_data = parse_audio_script(script_path)
    
    if not segments_data:
        print("[!] No dialogue lines found in script.")
        return False
        
    print(f"[+] Parsed {len(segments_data)} audio segments.")

    # multi-voice: กำหนดเสียง+pitch ต่อตัวละคร จากไฟล์ตัวละครของเรื่อง
    global VOICE_ASSIGN
    try:
        base = re.sub(r"_AudioScript_.*$", "", os.path.basename(script_path))
        sb = os.path.dirname(os.path.dirname(os.path.dirname(script_path)))
        cf = os.path.join(sb, "04_Character_Database", f"{base}_Characters.md")
        ctext = open(cf, "r", encoding="utf-8").read() if os.path.exists(cf) else ""
        VOICE_ASSIGN = assign_voices(segments_data, ctext)
        _g = lambda v: ("ชาย" if v[0] == _MALE_V else "หญิง") + v[1]
        print(f"[+] Multi-voice ({len(VOICE_ASSIGN)} ตัวละคร): "
              + ", ".join(f"{k}→{_g(v)}" for k, v in list(VOICE_ASSIGN.items())[:6]))
    except Exception as e:
        VOICE_ASSIGN = {}
        print(f"[!] assign_voices: {e}")

    # Create temporary directory for audio parts
    with tempfile.TemporaryDirectory() as temp_dir:
        stitched_audio = AudioSegment.empty()
        srt_entries = []
        srt_counter = 1
        current_ms = 0
        
        # Configure silence gaps (pauses)
        pause_narration = AudioSegment.silent(duration=300) # 300ms
        pause_dialog = AudioSegment.silent(duration=600)    # 600ms
        pause_sfx = AudioSegment.silent(duration=1200)      # 1.2s
        
        for idx, seg in enumerate(segments_data):
            speaker = seg["speaker"]
            text = seg["text"]
            seg_type = seg["type"]
            
            # Skip empty lines
            if not text:
                continue
                
            print(f"    [{idx+1}/{len(segments_data)}] Processing [{speaker}]: {text[:40]}...")
            
            if seg_type == "sfx":
                print(f"    [SFX] 🔊 Synthesizing real sound effect: {text}")
                sfx_audio = generate_sfx_cue(text)
                stitched_audio += sfx_audio
                current_ms += len(sfx_audio)
            else:
                # Dialog / Narration
                try:
                    if TTS_ENGINE == "elevenlabs" and ELEVENLABS_API_KEY:
                        audio_part = generate_tts_elevenlabs(text, speaker, temp_dir)
                    elif TTS_ENGINE == "edge-tts":
                        audio_part = generate_tts_edgetts(text, speaker, temp_dir)
                    elif TTS_ENGINE == "macos":
                        audio_part = generate_tts_macos_say(text, temp_dir)
                    else:
                        audio_part = generate_tts_gtts(text, temp_dir)
                        
                    duration = len(audio_part)
                    start_time = current_ms
                    end_time = current_ms + duration
                    
                    # Store SRT entry
                    srt_entries.append({
                        "index": srt_counter,
                        "start": ms_to_srt_time(start_time),
                        "end": ms_to_srt_time(end_time),
                        "speaker": speaker,
                        "text": text
                    })
                    srt_counter += 1
                    
                    # Add to main stream with appropriate pause
                    stitched_audio += audio_part
                    current_ms += duration
                    
                    if speaker == "ผู้บรรยาย":
                        stitched_audio += pause_narration
                        current_ms += len(pause_narration)
                    else:
                        stitched_audio += pause_dialog
                        current_ms += len(pause_dialog)
                except Exception as e:
                    print(f"    [!] Error generating audio for segment {idx+1}: {e}")
                    
        # Export final audio file
        print(f"[*] Exporting compiled audiobook to: {output_path}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save as MP3
        stitched_audio.export(output_path, format="mp3", bitrate="128k")
        
        # Save SRT subtitles
        srt_path = output_path.replace(".mp3", ".srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            for entry in srt_entries:
                f.write(f"{entry['index']}\n")
                f.write(f"{entry['start']} --> {entry['end']}\n")
                if entry['speaker'] == "ผู้บรรยาย":
                    f.write(f"{entry['text']}\n\n")
                else:
                    f.write(f"{entry['speaker']}: {entry['text']}\n\n")
        print(f"[+] Saved subtitles SRT to: {srt_path}")
        
        duration_sec = len(stitched_audio) / 1000.0
        print(f"[+] Successfully exported. Duration: {duration_sec:.2f}s | Size: {os.path.getsize(output_path)/1024/1024:.2f} MB")
        return True

def process_audio_scripts(second_brain_dir: str):
    """Scan Second Brain for audio scripts and generate audiobook MP3s."""
    scripts_dir = os.path.join(second_brain_dir, "05_Active_Projects", "Audio_Scripts")
    output_dir = os.path.join(second_brain_dir, "05_Active_Projects", "Audio_Output")
    
    script_files = glob.glob(os.path.join(scripts_dir, "*.md"))
    print(f"[*] Found {len(script_files)} audio scripts to render.")
    
    print(f"[*] Selected TTS Engine: {TTS_ENGINE}")
        
    for filepath in script_files:
        filename = os.path.basename(filepath)
        out_filename = filename.replace(".md", ".mp3").replace("AudioScript_", "Audiobook_")
        output_filepath = os.path.join(output_dir, out_filename)
        
        # ข้ามถ้ามีไฟล์เสียงอยู่แล้ว (Idempotent)
        if os.path.exists(output_filepath):
            continue
            
        print(f"\n[*] Rendering: {filename} -> {out_filename}", flush=True)
        success = render_script_to_audio(filepath, output_filepath)
        if success:
            print(f"[+] Render completed for {filename}", flush=True)

if __name__ == "__main__":
    second_brain_path = "./SecondBrain"
    if len(sys.argv) > 1:
        second_brain_path = sys.argv[1]
        
    process_audio_scripts(second_brain_path)
