import os
import sys
import glob
import subprocess
from typing import Optional

def find_cover_image(audio_filename: str, covers_dir: str) -> Optional[str]:
    """
    Search for a matching cover image in the covers directory.
    If 'Mock_Audiobook_01.mp3' is provided, it searches for:
    - Mock_Audiobook_01.png/jpg
    - Mock_Cover.png/jpg
    - Any image with 'Mock' in its name
    - Default_Cover.png
    """
    # Try exact name matches (different extensions)
    base_name = os.path.splitext(audio_filename)[0] # e.g. Mock_Audiobook_01
    prefix = base_name.split("_")[0] if "_" in base_name else base_name # e.g. Mock
    
    extensions = ["png", "jpg", "jpeg", "webp"]
    
    # 1. Check exact match: Mock_Audiobook_01.png
    for ext in extensions:
        path = os.path.join(covers_dir, f"{base_name}.{ext}")
        if os.path.exists(path):
            return path
            
    # 2. Check prefix cover: Mock_Cover.png
    for ext in extensions:
        path = os.path.join(covers_dir, f"{prefix}_Cover.{ext}")
        if os.path.exists(path):
            return path
            
    # 3. Check generic name match in folder
    for file in os.listdir(covers_dir):
        if prefix.lower() in file.lower() and file.split(".")[-1].lower() in extensions:
            return os.path.join(covers_dir, file)
            
    # 4. Check if there is any image in covers folder
    for ext in extensions:
        pattern = os.path.join(covers_dir, f"*.{ext}")
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
            
    return None

def generate_teaser(
    audio_path: str,
    cover_path: str,
    output_path: str,
    max_duration_sec: int = 60
) -> bool:
    """
    Execute FFmpeg command to merge cover image and audio into a vertical 9:16 MP4 video.
    Includes a waveform overlay and embedded subtitles if .srt is found.
    """
    import shutil
    print(f"[*] Formatting Teaser Video...")
    print(f"    Audio: {audio_path}")
    print(f"    Cover Image: {cover_path}")
    print(f"    Output Path: {output_path}")
    
    # Check if subtitle file exists
    srt_path = audio_path.replace(".mp3", ".srt")
    use_subtitles = os.path.exists(srt_path)
    
    # Copy srt file to current directory under a clean relative filename to bypass FFmpeg path escaping issues
    temp_srt_name = "temp_teaser_subs.srt"
    if use_subtitles:
        try:
            shutil.copy(srt_path, temp_srt_name)
            print(f"    [Subtitles] Found and copied subtitle file to: {temp_srt_name}")
        except Exception as e:
            print(f"    [!] Failed to copy subtitle file: {e}. Disabling subtitles.")
            use_subtitles = False
            
    # Filter Complex:
    # 1. Scale cover image to 1080x1080 and pad to 1080x1920 (centered, black background)
    # 2. Convert audio to waveform with showwaves, colored cyan (0x00FFFF), black keyed out to transparent, placed in bottom region (y=1520)
    # 3. If subtitles exist, burn them using subtitles filter positioned nicely above the waveform
    filter_parts = [
        "[0:v]scale=1080:1080,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[bg]",
        "[1:a]showwaves=s=1080x250:mode=line:colors=0x00FFFF:rate=25,colorkey=black:0.01:0.01[wave]",
        "[bg][wave]overlay=0:1520[bg_wave]"
    ]
    
    if use_subtitles:
        # burn in subtitles. MarginV=280 moves it above the waveform (which starts at 1520)
        filter_parts.append(
            f"[bg_wave]subtitles=filename={temp_srt_name}:force_style='Alignment=2,MarginV=280,FontSize=24,PrimaryColour=&H00FFFF,OutlineColour=&H000000,Outline=3'[outv]"
        )
        map_video = "[outv]"
    else:
        map_video = "[bg_wave]"
        
    filter_complex = ";".join(filter_parts)
    
    # FFmpeg command
    cmd = [
        "ffmpeg",
        "-y", # overwrite output
        "-loop", "1",
        "-i", cover_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", map_video,
        "-map", "1:a",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(max_duration_sec),
        "-shortest",
        output_path
    ]
    
    try:
        # Run FFmpeg command and hide output unless it fails
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Self-healing fallback: if the subtitles filter is missing, retry without it
        if result.returncode != 0 and ("No such filter: 'subtitles'" in result.stderr or "Error parsing filterchain" in result.stderr):
            print("    [!] FFmpeg 'subtitles' filter not supported (requires libass). Retrying without subtitles...")
            
            filter_parts_no_sub = [
                "[0:v]scale=1080:1080,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[bg]",
                "[1:a]showwaves=s=1080x250:mode=line:colors=0x00FFFF:rate=25,colorkey=black:0.01:0.01[wave]",
                "[bg][wave]overlay=0:1520[bg_wave]"
            ]
            filter_complex_no_sub = ";".join(filter_parts_no_sub)
            
            cmd_no_sub = [
                "ffmpeg",
                "-y", # overwrite output
                "-loop", "1",
                "-i", cover_path,
                "-i", audio_path,
                "-filter_complex", filter_complex_no_sub,
                "-map", "[bg_wave]",
                "-map", "1:a",
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-t", str(max_duration_sec),
                "-shortest",
                output_path
            ]
            result = subprocess.run(cmd_no_sub, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Cleanup temporary subtitles file
        if os.path.exists(temp_srt_name):
            try:
                os.remove(temp_srt_name)
            except:
                pass
                
        if result.returncode != 0:
            print(f"[!] FFmpeg Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"[!] Exception during FFmpeg execution: {e}")
        if os.path.exists(temp_srt_name):
            try:
                os.remove(temp_srt_name)
            except:
                pass
        return False

def process_teasers(second_brain_dir: str, max_duration: int = 60):
    """Scan Second Brain for audiobooks, pair them with cover art, and export teasers."""
    audio_dir = os.path.join(second_brain_dir, "05_Active_Projects", "Audio_Output")
    covers_dir = os.path.join(second_brain_dir, "05_Active_Projects", "Covers")
    output_dir = os.path.join(second_brain_dir, "05_Active_Projects", "Teaser_Output")
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(covers_dir, exist_ok=True)
    
    audio_files = glob.glob(os.path.join(audio_dir, "*.mp3"))
    print(f"[*] Found {len(audio_files)} rendered audiobooks to process into teasers.")
    
    processed_count = 0
    for audio_path in audio_files:
        filename = os.path.basename(audio_path)
        out_filename = filename.replace(".mp3", ".mp4").replace("Audiobook_", "Teaser_")
        output_filepath = os.path.join(output_dir, out_filename)
        
        cover_path = find_cover_image(filename, covers_dir)
        if not cover_path:
            print(f"[!] Cover image for {filename} not found. Skipping teaser generation.")
            continue
            
        print(f"\n[*] Generating Teaser: {filename} -> {out_filename}")
        success = generate_teaser(audio_path, cover_path, output_filepath, max_duration_sec=max_duration)
        if success:
            print(f"[+] Teaser created successfully: {output_filepath}")
            processed_count += 1
            
    print(f"\n[+] Teaser generation completed. Processed {processed_count} videos.")

if __name__ == "__main__":
    second_brain_path = "./SecondBrain"
    max_dur = 60
    
    if len(sys.argv) > 1:
        second_brain_path = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            max_dur = int(sys.argv[2])
        except ValueError:
            pass
            
    process_teasers(second_brain_path, max_dur)
