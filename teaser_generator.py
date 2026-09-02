import os
import re
import sys
import glob
import subprocess
from typing import Optional

# ฟอนต์ไทยสำหรับเบิร์น caption (ffmpeg minimal ไม่มี libass/drawtext เราจึงเบิร์นด้วย PIL)
_THAI_FONT = next((f for f in [
    "/System/Library/Fonts/Supplemental/Ayuthaya.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Thonburi.ttc",
] if os.path.exists(f)), None)


def _wrap(draw, text, font, max_w):
    """ตัดบรรทัดภาษาไทย (ไม่มีช่องว่าง) ตามความกว้างพิกเซล"""
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        chunk = (cur + " " + w).strip()
        if draw.textlength(chunk, font=font) <= max_w:
            cur = chunk
        else:
            if cur:
                lines.append(cur)
            # ถ้าคำเดียวยังยาวเกิน ตัดทีละตัวอักษร
            while draw.textlength(w, font=font) > max_w and len(w) > 1:
                i = len(w)
                while i > 1 and draw.textlength(w[:i], font=font) > max_w:
                    i -= 1
                lines.append(w[:i]); w = w[i:]
            cur = w
    if cur:
        lines.append(cur)
    return lines


def caption_cover(cover_path: str, title: str, hook: str = "", tiktok_safe: bool = False) -> str:
    """เบิร์นชื่อเรื่อง (บน) + hook (ล่าง) ลงปกเป็นภาพแนวตั้ง 9:16 (1080x1920)
    รองรับปกทุกอัตราส่วน: เติมพื้นหลังด้วยปกที่เบลอ+มืด แล้ววางปกคมชัดกลางเฟรม (ไม่บีบเพี้ยน)
    tiktok_safe=True: ดัน hook ขึ้นโซนปลอดภัย (~66% ของจอ) เลี่ยง UI TikTok ล่าง (caption/ปุ่ม) บัง
    คืน path ภาพใหม่ (.jpg) — ไม่ง้อ libass"""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
    except Exception:
        return cover_path
    if not _THAI_FONT:
        return cover_path
    try:
        W, H = 1080, 1920
        src = Image.open(cover_path).convert("RGB")

        # --- พื้นหลัง: ปกขยายให้เต็มเฟรม (cover) แล้วเบลอ+มืด กันขอบดำว่าง ---
        sw, sh = src.size
        scale_bg = max(W / sw, H / sh)
        bg = src.resize((int(sw * scale_bg) + 1, int(sh * scale_bg) + 1))
        bx, by = (bg.width - W) // 2, (bg.height - H) // 2
        bg = bg.crop((bx, by, bx + W, by + H)).filter(ImageFilter.GaussianBlur(28))
        dark = Image.new("RGB", (W, H), (0, 0, 0))
        canvas = Image.blend(bg, dark, 0.45)

        # --- ปกคมชัด: ย่อให้พอดีกว้าง 1080 (คงสัดส่วน) วางกลางแนวตั้ง ---
        scale_fg = W / sw
        fg = src.resize((W, int(sh * scale_fg)))
        fy = max(0, (H - fg.height) // 2)
        canvas.paste(fg, (0, fy))

        draw = ImageDraw.Draw(canvas, "RGBA")
        title_f = ImageFont.truetype(_THAI_FONT, 68)
        hook_f = ImageFont.truetype(_THAI_FONT, 52)

        def draw_bubble_badge(lines, font, y_start, text_color="white", bg_color=(15, 15, 20, 220),
                              border_color=(255, 215, 0, 255), tag_text=None, stroke_color="black", stroke_w=4):
            if not lines:
                return
            line_h = font.size + 16
            max_w = max(draw.textlength(ln, font=font) for ln in lines)
            pad_x = 36
            pad_y = 18
            box_w = min(W - 80, max(max_w + pad_x * 2, 480))
            box_h = line_h * len(lines) + pad_y * 2
            bx0 = (W - box_w) // 2
            by0 = y_start
            bx1 = bx0 + box_w
            by1 = by0 + box_h

            # เงาตกกระทบ (Drop Shadow) ให้กล่องดูลอยเด่นชัด
            draw.rounded_rectangle([bx0 + 6, by0 + 6, bx1 + 6, by1 + 6], radius=24, fill=(0, 0, 0, 140))
            # กล่องข้อความสไตล์ Viral Shorts พร้อมเส้นขอบคมชัด
            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=24, fill=bg_color, outline=border_color, width=3)

            # แท็กสะดุดตาด้านบนกล่อง (Call-to-Action Mini Tag)
            if tag_text:
                tag_f = ImageFont.truetype(_THAI_FONT, 28)
                tw = draw.textlength(tag_text, font=tag_f)
                tx0 = bx0 + 28
                ty0 = by0 - 18
                draw.rounded_rectangle([tx0 - 12, ty0, tx0 + tw + 12, ty0 + 34], radius=10, fill=(255, 45, 85, 255))
                draw.text((tx0, ty0 + 3), tag_text, font=tag_f, fill="#FFFFFF")

            # พิมพ์ตัวหนังสือจัดกึ่งกลาง
            y = by0 + pad_y + 4
            for ln in lines:
                w = draw.textlength(ln, font=font)
                x = (W - w) // 2
                draw.text((x, y), ln, font=font, fill=text_color, stroke_width=stroke_w, stroke_fill=stroke_color)
                y += line_h

        # ชื่อเรื่อง (บน) — วางในโซนปลอดภัย y=160 (กล่องเข้มหรูหรา ขอบทอง ป้ายนิยายเสียง)
        tlines = _wrap(draw, title, title_f, W - 140)[:3]
        draw_bubble_badge(tlines, title_f, 160, text_color="#FFFFFF",
                          bg_color=(12, 16, 28, 230), border_color=(255, 215, 0, 240),
                          tag_text="นิยายเสียง | สปอยล์บทเดือด", stroke_color="#000000", stroke_w=4)

        # hook: จุดพีคดึงดูดสายตา (ล่างหรือโซนปลอดภัย TikTok) — สไตล์กล่องไฮไลต์สีเหลืองสดใส สะกดสายตาแม้ปิดเสียง
        if hook:
            hlines = _wrap(draw, hook, hook_f, W - 140)[:3]
            line_h = hook_f.size + 16
            y_hook = int(H * 0.64) if tiktok_safe else (1480 - (line_h * len(hlines) + 40))
            draw_bubble_badge(hlines, hook_f, y_hook, text_color="#0A0A0A",
                              bg_color=(255, 230, 0, 240), border_color=(255, 255, 255, 255),
                              tag_text="ไฮไลต์จุดพีคประจำตอน", stroke_color="#FFE600", stroke_w=0)

        out = os.path.splitext(cover_path)[0] + ("_tt.jpg" if tiktok_safe else "_captioned.jpg")
        canvas.save(out, "JPEG", quality=92)
        return out
    except Exception as e:
        print(f"    [!] caption_cover ล้มเหลว: {e} — ใช้ปกเดิม")
        return cover_path


def find_cover_image(audio_filename: str, covers_dir: str) -> Optional[str]:
    """
    ค้นหาภาพปกที่ตรงกับเรื่องและตอนอย่างแม่นยำ:
    - ตัด _Audiobook_NN ออกเพื่อหา stem ชื่อเรื่องที่แท้จริง (รองรับชื่อเรื่องที่มี _)
    - ตรวจสอบ {stem}_Cover, {stem}_Chapter_NN_Cover, {base_name}
    - หากไม่พบ จะไม่สุ่มภาพอื่นเด็ดขาด (ป้องกันการจับคู่ปกข้ามเรื่อง)
    """
    base_name = os.path.splitext(audio_filename)[0]
    # สกัด stem ชื่อเรื่องโดยตัด suffix เกี่ยวกับเสียงออกอย่างแม่นยำ
    stem = re.sub(r"_(?:Audiobook|AudioScript|Audio|Teaser)_\d+.*$", "", base_name)
    stem = re.sub(r"_(?:Audiobook|AudioScript|Audio|Teaser).*$", "", stem)

    extensions = ["png", "jpg", "jpeg", "webp"]

    # 1. ตรวจสอบชื่อไฟล์ตรงเผง
    for ext in extensions:
        p = os.path.join(covers_dir, f"{base_name}.{ext}")
        if os.path.exists(p):
            return p

    # 2. ตรวจสอบ {stem}_Cover
    for ext in extensions:
        p = os.path.join(covers_dir, f"{stem}_Cover.{ext}")
        if os.path.exists(p):
            return p

    # 3. ตรวจสอบ {stem}.{ext}
    for ext in extensions:
        p = os.path.join(covers_dir, f"{stem}.{ext}")
        if os.path.exists(p):
            return p

    # 4. ตรวจสอบไฟล์ที่มี stem เต็มอยู่ในชื่อ
    clean_stem = stem.lower().replace("_", "")
    for file in os.listdir(covers_dir):
        fl = file.lower().replace("_", "")
        if clean_stem in fl and file.split(".")[-1].lower() in extensions:
            return os.path.join(covers_dir, file)

    return None

def generate_teaser(
    audio_path: str,
    cover_path: str,
    output_path: str,
    max_duration_sec: int = 60,
    display_title: str = "",
    hook: str = ""
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

    # เบิร์น caption (ชื่อเรื่อง+hook) ลงปกด้วย PIL — ได้ข้อความบนวิดีโอแม้ ffmpeg ไม่มี libass
    if display_title or hook:
        capped = caption_cover(cover_path, display_title, hook)
        if capped != cover_path:
            print(f"    [Caption] เบิร์นชื่อเรื่อง/hook ลงปกแล้ว")
            cover_path = capped
    
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
    # Ken Burns: ซูมเข้าช้าๆ ให้ปกมีชีวิต (scale ใหญ่ก่อนกัน zoompan กระตุก) + fade in/out
    fps = 25
    try:
        _dur = int(float(max_duration_sec))
    except (TypeError, ValueError):
        _dur = 60
    frames = max(_dur * fps, fps)
    fade_out_st = max(_dur - 1, 1)
    kenburns = os.environ.get("ANSRE_TEASER_KENBURNS", "1").lower() in ("1", "true", "yes")
    # ปก (captioned) เป็น 9:16 อยู่แล้ว → เติมเต็มเฟรม 1080x1920 (รองรับปกอัตราส่วนอื่นด้วย crop)
    if kenburns:
        bg_chain = (
            "[0:v]scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
            f"zoompan=z='min(zoom+0.0002,1.06)':d={frames}:"
            "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s=1080x1920:fps={fps},"
            f"fade=t=in:st=0:d=0.8,fade=t=out:st={fade_out_st}:d=0.8[bg]"
        )
    else:
        bg_chain = "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg]"
    filter_parts = [
        bg_chain,
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
            
            # ใช้ Ken Burns chain เดิม (zoompan/fade) — อย่าตกกลับเป็นภาพนิ่ง
            # caption ชื่อเรื่อง/hook เบิร์นบนปกด้วย PIL แล้ว จึงไม่เสียข้อความแม้ทิ้ง SRT
            filter_parts_no_sub = [
                bg_chain,
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
    # 1 teaser ต่อเรื่อง: ใช้เฉพาะตอนแรก (Audiobook_01) เป็น hook — กัน teaser ซ้ำต่อตอน
    # (ตั้ง ANSRE_TEASER_PER_CHAPTER=1 ถ้าต้องการ teaser ทุกตอนแบบเดิม)
    if os.environ.get("ANSRE_TEASER_PER_CHAPTER", "0").lower() not in ("1", "true", "yes", "on"):
        audio_files = [f for f in audio_files
                       if re.search(r"_Audiobook_0*1\.mp3$", os.path.basename(f))]
    print(f"[*] Found {len(audio_files)} audiobooks to process into teasers (1 ต่อเรื่อง).")
    
    processed_count = 0
    for audio_path in audio_files:
        filename = os.path.basename(audio_path)
        out_filename = filename.replace(".mp3", ".mp4").replace("Audiobook_", "Teaser_")
        output_filepath = os.path.join(output_dir, out_filename)
        
        # ข้ามถ้ามีวิดีโอ Teaser อยู่แล้ว (Idempotent)
        if os.path.exists(output_filepath):
            continue
            
        cover_path = find_cover_image(filename, covers_dir)
        if not cover_path:
            print(f"[!] Cover image for {filename} not found. Skipping teaser generation.")
            continue
            
        # ดึงชื่อเรื่อง (จาก outline) + hook (จากบรรทัดแรกของ SRT) มาเบิร์นลงปก
        base = re.sub(r"_Audiobook_\d+$", "", filename.replace(".mp3", ""))
        display_title = base.replace("_", " ")
        ol = os.path.join(second_brain_dir, "02_Concept_Extraction", base + "_Outline.md")
        if os.path.exists(ol):
            otxt = open(ol, encoding="utf-8").read()
            m = re.search(r"ชื่อเรื่อง[:：]?\s*\*{0,2}(.+)", otxt)
            if m:
                display_title = re.sub(r"[*#`]", "", m.group(1)).strip()[:60]
        hook = ""
        srt_p = audio_path.replace(".mp3", ".srt")
        if os.path.exists(srt_p):
            for ln in open(srt_p, encoding="utf-8").read().splitlines():
                s = ln.strip()
                if s and "-->" not in s and not s.isdigit() and not s.startswith("["):
                    hook = s
                    if len(hook) > 95:           # ตัดที่ขอบคำ ไม่ตัดกลางคำ
                        cut = hook[:95].rfind(" ")
                        hook = (hook[:cut] if cut > 45 else hook[:95]).rstrip() + "…"
                    break

        print(f"\n[*] Generating Teaser: {filename} -> {out_filename}")
        success = generate_teaser(audio_path, cover_path, output_filepath, max_duration_sec=max_duration,
                                  display_title=display_title, hook=hook)
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
