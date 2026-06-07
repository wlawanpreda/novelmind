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

def parse_audio_script(filepath: str) -> List[Dict[str, Any]]:
    """Parse Markdown audio script and return a list of segments with speaker, tone, and text."""
    segments = []
    
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    sfx_pattern = r"^\[SFX:\s*(.*?)\]"
    speaker_pattern = r"^\[([^,\]]+)(?:,\s*โทน:\s*([^\]]+))?\]\s*(.*)$"
    
    current_speaker = "ผู้บรรยาย"
    current_tone = "ปกติ"
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("---"):
            # Reset speaker to narrator on blank lines or dividers
            current_speaker = "ผู้บรรยาย"
            current_tone = "ปกติ"
            continue
            
        if line.startswith("#"):
            continue
            
        # 1. Parse SFX
        sfx_match = re.match(sfx_pattern, line, re.IGNORECASE)
        if sfx_match:
            segments.append({
                "type": "sfx",
                "speaker": "SFX",
                "tone": "",
                "text": sfx_match.group(1).strip()
            })
            continue
            
        # 2. Parse Speaker Dialog Tag
        speaker_match = re.match(speaker_pattern, line)
        if speaker_match:
            speaker = speaker_match.group(1).strip()
            tone = (speaker_match.group(2) or "ปกติ").strip()
            text = speaker_match.group(3).strip()
            
            # Update state
            current_speaker = speaker
            current_tone = tone
            
            # If there is dialogue text on the same line, append it
            if text:
                segments.append({
                    "type": "dialog",
                    "speaker": current_speaker,
                    "tone": current_tone,
                    "text": text
                })
            continue
            
        # 3. Plain Text Line: Use the current state (inherited speaker/tone)
        # Avoid markdown lists, quotes, or headers
        if not (line.startswith("-") or line.startswith("*") or line.startswith(">")):
            segments.append({
                "type": "dialog",
                "speaker": current_speaker,
                "tone": current_tone,
                "text": line
            })
            
    return segments

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

def generate_tts_edgetts(text: str, speaker: str, temp_dir: str) -> AudioSegment:
    """Generate free high-quality Thai speech using edge-tts (Microsoft Edge neural voices)."""
    from concurrent.futures import ThreadPoolExecutor
    
    # Map speaker to voice
    voice = "th-TH-PremwadeeNeural" # default
    speaker_lower = speaker.lower()
    
    # Custom simple rule for speaker matching
    male_names = ["อคิน", "วายุ", "ชาย", "พ่อ", "หมอ", "ลุง", "ตำรวจ", "พศิน", "เอก", "นนท์", "เก่ง"]
    if speaker in ["อคิน", "วายุ", "ระบบ", "niwat"] or any(name in speaker_lower for name in male_names):
        voice = "th-TH-NiwatNeural"
    elif speaker in ["premwadee", "ผู้บรรยาย"]:
        voice = "th-TH-PremwadeeNeural"
        
    temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", dir=temp_dir, delete=False)
    temp_file.close()
    
    async def _speak():
        communicate = edge_tts.Communicate(text, voice)
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
                print(f"    [SFX] Adding pause placeholder for sound effect: {text}")
                stitched_audio += pause_sfx
                current_ms += len(pause_sfx)
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
        
        print(f"\n[*] Rendering: {filename} -> {out_filename}")
        success = render_script_to_audio(filepath, output_filepath)
        if success:
            print(f"[+] Render completed for {filename}")

if __name__ == "__main__":
    second_brain_path = "./SecondBrain"
    if len(sys.argv) > 1:
        second_brain_path = sys.argv[1]
        
    process_audio_scripts(second_brain_path)
