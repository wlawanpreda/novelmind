"""
web_catalog.py — Public Web Reader & Interactive Showcase Generator
===================================================================

สร้างหน้าเว็บพอร์ทัลสำหรับนักอ่าน (Reader Portal) ที่สวยงาม โหลดไว และใช้งานง่าย:
1. แสดงชั้นหนังสือนิยายทั้งหมด แยกหมวดหมู่และเรื่องเรือธง (Flagship)
2. มี Web Reader ในตัว ให้อ่านตัวอย่างบทแรก (Chapter 1) พร้อมโหมดกลางคืน/ปรับขนาดฟอนต์
3. มี Audio Player ฟังเสียงพากย์ฉบับสมบูรณ์หรือ Teaser ได้ทันทีในเว็บ
4. ลิงก์ตรงสำหรับซื้อ E-Book บน Meb Market และอ่านต่อบน ReadAWrite / Dek-D / YouTube
5. พร้อมนำไป Deploy ขึ้น GitHub Pages, Cloudflare Pages หรือ Vercel ได้ทันที

CLI:
  python web_catalog.py                   # สร้าง web/portal/index.html และ stories.json
  python web_catalog.py --serve [port]    # รัน local server เปิดดูตัวอย่าง (default: 8080)
"""
from __future__ import annotations

import os
import re
import glob
import json
import http.server
import socketserver
from typing import Dict, Any, List

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AP = os.path.join(SB, "05_Active_Projects")
EXPORTS_DIR = os.path.join(AP, "Exports")
AUDIO_DIR = os.path.join(EXPORTS_DIR, "Audiobooks")
CHAPTERS_DIR = os.path.join(AP, "Chapters")
COVERS_DIR = os.path.join(AP, "Covers")
PORTAL_DIR = os.path.join(ROOT, "web", "portal")

os.makedirs(PORTAL_DIR, exist_ok=True)


def get_all_stories_data() -> List[Dict[str, Any]]:
    """รวบรวมข้อมูลนิยายทั้งหมดในระบบ SecondBrain"""
    # 1. โหลด Portfolio Matrix ถ้ามี
    matrix_path = os.path.join(SB, "portfolio_matrix.json")
    flagship_titles = []
    if os.path.exists(matrix_path):
        try:
            with open(matrix_path, "r", encoding="utf-8") as f:
                mat = json.load(f)
                flagship_titles = [s["title"] for s in mat.get("flagship", [])]
        except Exception:
            pass

    # 2. หาเรื่องทั้งหมดที่มีบทใน Chapters/
    chapter_files = glob.glob(os.path.join(CHAPTERS_DIR, "*_Chapter_*.md"))
    story_keys = sorted(set(re.sub(r"_Chapter_\d+\.md$", "", os.path.basename(f)) for f in chapter_files))

    stories = []
    for key in story_keys:
        title = key.replace("_", " ").strip()
        chs = sorted(glob.glob(os.path.join(CHAPTERS_DIR, f"{key}_Chapter_*.md")))
        ch_count = len(chs)

        # หาภาพปก
        cover_url = ""
        for ext in ("_Cover_captioned.jpg", "_Cover.jpg", "_Cover.png", ".jpg", ".png"):
            cp = os.path.join(COVERS_DIR, f"{key}{ext}")
            if os.path.exists(cp):
                cover_url = f"/covers/{os.path.basename(cp)}"
                break

        # หาเสียง Audiobook
        audio_url = ""
        full_audio = os.path.join(AUDIO_DIR, f"{key}_Full_Audiobook.mp3")
        if os.path.exists(full_audio):
            audio_url = f"/audio/{os.path.basename(full_audio)}"
        else:
            ep1_audio = os.path.join(AP, "Audio_Output", f"{key}_Audiobook_01.mp3")
            if os.path.exists(ep1_audio):
                audio_url = f"/audio/{os.path.basename(ep1_audio)}"

        # อ่านบทตัวอย่างตอนที่ 1
        ch1_text = ""
        ch1_path = os.path.join(CHAPTERS_DIR, f"{key}_Chapter_01.md")
        if os.path.exists(ch1_path):
            try:
                with open(ch1_path, "r", encoding="utf-8") as f:
                    ch1_text = f.read()
            except Exception:
                pass

        # สกัดเรื่องย่อ
        synopsis = f"การผจญภัยและเรื่องราวสุดเข้มข้นใน '{title}' ติดตามได้ทั้งแบบอ่านรายตอนและฟังหนังสือเสียงฉบับสมบูรณ์"
        out_path = os.path.join(SB, "02_Concept_Extraction", f"{key}_Outline.md")
        if os.path.exists(out_path):
            try:
                with open(out_path, "r", encoding="utf-8") as of:
                    otxt = of.read()
                    m = re.search(r"(?:เรื่องย่อ|Logline|พล็อตหลัก|Concept)[:\s]+([^\n]+)", otxt)
                    if m:
                        synopsis = m.group(1).strip()
            except Exception:
                pass

        is_flagship = key in flagship_titles or title in flagship_titles or ch_count >= 8

        stories.append({
            "id": key,
            "title": title,
            "chapters_count": ch_count,
            "is_flagship": is_flagship,
            "cover": cover_url,
            "audio": audio_url,
            "synopsis": synopsis,
            "sample_chapter": ch1_text,
            "has_epub": os.path.exists(os.path.join(EXPORTS_DIR, f"{title}.epub")) or os.path.exists(os.path.join(EXPORTS_DIR, f"{key}.epub")),
            "genre": "สืบสวนระทึกขวัญ" if "สืบ" in title else ("แฟนตาซี" if "เทพ" in title or "เวท" in title else "ผจญภัยลึกลับ")
        })

    # เรียงลำดับเรื่องเรือธงขึ้นก่อน ตามด้วยจำนวนตอน
    stories.sort(key=lambda s: (not s["is_flagship"], -s["chapters_count"]))
    return stories


def build_portal_html(stories: List[Dict[str, Any]]) -> str:
    """สร้าง HTML Responsive Single Page Reader Portal"""
    stories_json_str = json.dumps(stories, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="th" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NovelMind & ANSRE — คลังนิยายและหนังสือเสียงออนไลน์</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&family=Sarabun:wght@300;400;500;600&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          fontFamily: {{
            prompt: ['Prompt', 'sans-serif'],
            sarabun: ['Sarabun', 'sans-serif'],
          }},
          colors: {{
            brand: {{
              50: '#f0fdfa',
              500: '#14b8a6',
              600: '#0d9488',
              700: '#0f766e',
            }}
          }}
        }}
      }}
    }}
  </script>
  <style>
    body {{ font-family: 'Prompt', sans-serif; }}
    .reader-content {{ font-family: 'Sarabun', sans-serif; line-height: 1.85; }}
    .glass {{ background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }}
    .book-card {{ transition: transform 0.25s ease, box-shadow 0.25s ease; }}
    .book-card:hover {{ transform: translateY(-6px); }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col selection:bg-teal-500 selection:text-white">

  <!-- Navigation -->
  <header class="sticky top-0 z-40 glass border-b border-slate-800">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-teal-500 to-indigo-600 flex items-center justify-center text-xl shadow-lg shadow-teal-500/20">
          📖
        </div>
        <div>
          <span class="text-xl font-bold tracking-tight bg-gradient-to-r from-teal-400 via-cyan-300 to-indigo-400 bg-clip-text text-transparent">NovelMind</span>
          <span class="text-xs text-slate-400 block -mt-1 font-normal">Original Fiction & Audiobooks</span>
        </div>
      </div>
      <div class="flex items-center space-x-3">
        <input id="searchInput" type="text" placeholder="🔍 ค้นหานิยาย, ตอน, แนว..." 
               class="bg-slate-900 border border-slate-700 rounded-full px-4 py-1.5 text-sm focus:outline-none focus:border-teal-400 w-44 sm:w-64 transition-all"
               oninput="filterNovels()">
      </div>
    </div>
  </header>

  <!-- Hero Section -->
  <section class="relative overflow-hidden pt-12 pb-8 border-b border-slate-800/80 bg-gradient-to-b from-slate-900/60 to-slate-950">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
      <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-teal-500/10 text-teal-300 border border-teal-500/30 mb-4">
        ✨ อัปเดตนิยายใหม่ทุกสัปดาห์ • อ่านฟรี • ฟังฟรี
      </span>
      <h1 class="text-3xl sm:text-5xl font-extrabold tracking-tight mb-4">
        จักรวาลนิยายและเสียงพากย์ระดับสตูดิโอ
      </h1>
      <p class="text-slate-400 max-w-2xl mx-auto text-sm sm:text-base mb-6">
        สัมผัสความสนุกครบรส ทั้งนิยายแฟนตาซี สืบสวน เอาชีวิตรอด และไซไฟ <br class="hidden sm:inline">
        ทดลองอ่านตัวอย่าง หรือฟังหนังสือเสียงฉบับ Master เต็มเรื่องได้ทันที
      </p>

      <!-- Category Filter Pills -->
      <div class="flex flex-wrap justify-center gap-2 text-sm font-medium">
        <button onclick="setCategory('all')" class="cat-pill px-4 py-1.5 rounded-full bg-teal-500 text-white shadow-md shadow-teal-500/20" data-cat="all">ทั้งหมด</button>
        <button onclick="setCategory('flagship')" class="cat-pill px-4 py-1.5 rounded-full bg-slate-800 text-slate-300 hover:bg-slate-700" data-cat="flagship">👑 เรื่องเรือธง</button>
        <button onclick="setCategory('fantasy')" class="cat-pill px-4 py-1.5 rounded-full bg-slate-800 text-slate-300 hover:bg-slate-700" data-cat="fantasy">แฟนตาซี</button>
        <button onclick="setCategory('mystery')" class="cat-pill px-4 py-1.5 rounded-full bg-slate-800 text-slate-300 hover:bg-slate-700" data-cat="mystery">สืบสวนระทึกขวัญ</button>
      </div>
    </div>
  </section>

  <!-- Books Grid Container -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex-1 w-full">
    <div id="booksGrid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      <!-- Injected via JavaScript -->
    </div>
  </main>

  <!-- Reader Modal -->
  <div id="readerModal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-md hidden flex items-center justify-center p-4 sm:p-6">
    <div class="bg-slate-900 border border-slate-700 rounded-2xl max-w-3xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
      <!-- Modal Header -->
      <div class="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/80">
        <div>
          <h3 id="modalTitle" class="font-bold text-lg text-teal-400">บทที่ 1</h3>
          <span id="modalSubtitle" class="text-xs text-slate-400">ตัวอย่างทดลองอ่าน</span>
        </div>
        <div class="flex items-center space-x-2">
          <button onclick="adjustFontSize(-1)" class="w-8 h-8 rounded bg-slate-800 hover:bg-slate-700 text-sm font-bold">A-</button>
          <button onclick="adjustFontSize(1)" class="w-8 h-8 rounded bg-slate-800 hover:bg-slate-700 text-sm font-bold">A+</button>
          <button onclick="closeReader()" class="w-8 h-8 rounded-full bg-red-500/20 text-red-400 hover:bg-red-500 hover:text-white transition-all font-bold ml-2">✕</button>
        </div>
      </div>
      <!-- Modal Body -->
      <div id="readerBody" class="p-6 overflow-y-auto reader-content text-slate-200 text-base leading-relaxed space-y-4">
        <!-- Content injected here -->
      </div>
      <!-- Modal Footer -->
      <div class="p-4 border-t border-slate-800 bg-slate-950 flex flex-wrap items-center justify-between gap-3 text-xs">
        <span class="text-slate-400">📖 สิ้นสุดบททดลองอ่าน ต้องการอ่านต่อตอนต่อไป?</span>
        <div class="flex items-center space-x-2">
          <a id="modalMebBtn" href="https://www.mebmarket.com" target="_blank" class="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-medium">ซื้อ E-Book บน Meb</a>
          <a id="modalRawBtn" href="https://www.readawrite.com" target="_blank" class="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium">อ่านต่อบน ReadAWrite</a>
        </div>
      </div>
    </div>
  </div>

  <!-- Audio Player Bar (Sticky Bottom) -->
  <div id="audioBar" class="fixed bottom-0 inset-x-0 glass border-t border-slate-800 p-3 hidden z-30 shadow-2xl">
    <div class="max-w-4xl mx-auto flex items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <span class="text-2xl animate-pulse">🎧</span>
        <div>
          <h4 id="audioTitle" class="text-sm font-semibold text-teal-300">กำลังเล่นนิยายเสียง</h4>
          <span class="text-xs text-slate-400">NovelMind Master Audio</span>
        </div>
      </div>
      <audio id="globalAudioPlayer" controls class="h-9 max-w-md w-full rounded-lg"></audio>
      <button onclick="closeAudio()" class="text-slate-400 hover:text-white text-sm">✕</button>
    </div>
  </div>

  <!-- Footer -->
  <footer class="border-t border-slate-800 py-8 bg-slate-950 text-center text-xs text-slate-500">
    <p>NovelMind & ANSRE Studio © 2026 • ระบบผลิตและเผยแพร่นวนิยายมัลติแพลตฟอร์มอัตโนมัติ</p>
    <p class="mt-1">พร้อมรองรับ Meb Market, ReadAWrite, Dek-D, Spotify Podcasts, และ YouTube</p>
  </footer>

  <script>
    const novels = {stories_json_str};
    let currentCategory = 'all';
    let currentFontSize = 16;

    function renderBooks(list) {{
      const grid = document.getElementById('booksGrid');
      grid.innerHTML = '';
      if (!list.length) {{
        grid.innerHTML = '<div class="col-span-full py-16 text-center text-slate-500">ไม่พบนิยายที่ค้นหา</div>';
        return;
      }}
      list.forEach(novel => {{
        const card = document.createElement('div');
        card.className = 'book-card glass rounded-2xl p-4 flex flex-col justify-between border border-slate-800';
        
        const coverImg = novel.cover ? `<img src="${{novel.cover}}" alt="${{novel.title}}" class="w-full h-48 object-cover rounded-xl mb-3 shadow-md">` :
          `<div class="w-full h-48 bg-gradient-to-tr from-slate-800 to-slate-900 rounded-xl mb-3 flex items-center justify-center text-4xl">📚</div>`;

        const badge = novel.is_flagship ? 
          `<span class="bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs px-2.5 py-0.5 rounded-full font-medium">👑 เรื่องเรือธง</span>` :
          `<span class="bg-slate-800 text-slate-400 text-xs px-2.5 py-0.5 rounded-full">${{novel.genre}}</span>`;

        card.innerHTML = `
          <div>
            ${{coverImg}}
            <div class="flex items-center justify-between mb-2">
              ${{badge}}
              <span class="text-xs text-slate-400">📖 ${{novel.chapters_count}} ตอน</span>
            </div>
            <h3 class="font-bold text-base text-slate-100 line-clamp-1 mb-1" title="${{novel.title}}">${{novel.title}}</h3>
            <p class="text-xs text-slate-400 line-clamp-2 mb-4 leading-relaxed">${{novel.synopsis}}</p>
          </div>
          <div class="pt-3 border-t border-slate-800/80 flex items-center justify-between gap-2 text-xs">
            <button onclick="openReader('${{novel.id}}')" class="flex-1 py-2 rounded-lg bg-teal-600/90 hover:bg-teal-500 text-white font-medium text-center transition-colors">
              📖 ทดลองอ่าน
            </button>
            ${{novel.audio ? `
              <button onclick="playAudio('${{novel.audio}}', '${{novel.title}}')" class="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200" title="ฟังเสียง">
                🎧 ฟังเสียง
              </button>
            ` : ''}}
          </div>
        `;
        grid.appendChild(card);
      }});
    }}

    function filterNovels() {{
      const query = document.getElementById('searchInput').value.toLowerCase();
      const filtered = novels.filter(n => {{
        const matchText = n.title.toLowerCase().includes(query) || n.synopsis.toLowerCase().includes(query);
        const matchCat = (currentCategory === 'all') ||
                         (currentCategory === 'flagship' && n.is_flagship) ||
                         (currentCategory === 'fantasy' && n.genre.includes('แฟนตาซี')) ||
                         (currentCategory === 'mystery' && n.genre.includes('สืบสวน'));
        return matchText && matchCat;
      }});
      renderBooks(filtered);
    }}

    function setCategory(cat) {{
      currentCategory = cat;
      document.querySelectorAll('.cat-pill').forEach(btn => {{
        if (btn.dataset.cat === cat) {{
          btn.className = 'cat-pill px-4 py-1.5 rounded-full bg-teal-500 text-white shadow-md shadow-teal-500/20';
        }} else {{
          btn.className = 'cat-pill px-4 py-1.5 rounded-full bg-slate-800 text-slate-300 hover:bg-slate-700';
        }}
      }});
      filterNovels();
    }}

    function openReader(id) {{
      const novel = novels.find(n => n.id === id);
      if (!novel) return;
      document.getElementById('modalTitle').innerText = novel.title;
      document.getElementById('modalSubtitle').innerText = `ตอนที่ 1 (ตัวอย่างทดลองอ่าน)`;
      
      const formatted = (novel.sample_chapter || 'ยังไม่มีเนื้อหาสำหรับตอนแรก')
        .split('\\n\\n')
        .map(p => `<p class="indent-6">${{p.trim().replace(/^#+\\s*/, '')}}</p>`)
        .join('');
      
      document.getElementById('readerBody').innerHTML = formatted;
      document.getElementById('readerModal').classList.remove('hidden');
    }}

    function closeReader() {{
      document.getElementById('readerModal').classList.add('hidden');
    }}

    function adjustFontSize(delta) {{
      currentFontSize = Math.max(14, Math.min(24, currentFontSize + delta));
      document.getElementById('readerBody').style.fontSize = currentFontSize + 'px';
    }}

    function playAudio(url, title) {{
      const bar = document.getElementById('audioBar');
      const player = document.getElementById('globalAudioPlayer');
      document.getElementById('audioTitle').innerText = title;
      player.src = url;
      bar.classList.remove('hidden');
      player.play().catch(() => {{}});
    }}

    function closeAudio() {{
      const player = document.getElementById('globalAudioPlayer');
      player.pause();
      document.getElementById('audioBar').classList.add('hidden');
    }}

    // Initial render
    renderBooks(novels);
  </script>
</body>
</html>
"""
    portal_index = os.path.join(PORTAL_DIR, "index.html")
    with open(portal_index, "w", encoding="utf-8") as f:
        f.write(html.strip())

    # บันทึก JSON API สำหรับ Static Hosting / CDN
    json_path = os.path.join(PORTAL_DIR, "stories.json")
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(stories, jf, ensure_ascii=False, indent=2)

    print(f"✅ สร้าง Web Reader Portal สำเร็จ: {portal_index}")
    print(f"   • รวบรวมนิยายทั้งหมด: {len(stories)} เรื่อง (เรื่องเรือธง {sum(1 for s in stories if s['is_flagship'])} เรื่อง)")
    print(f"   • บันทึก Stories API: {json_path}")
    return portal_index


def serve_portal(port: int = 8080):
    """รัน Local Web Server เพื่อเปิดดู Portal ได้ทันที"""
    os.chdir(ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"\n🌐 Web Reader Portal พร้อมเปิดให้คนอ่านแล้วที่: http://localhost:{port}/web/portal/index.html")
        print("   (กด Ctrl+C เพื่อหยุด)")
        httpd.serve_forever()


if __name__ == "__main__":
    import sys
    stories = get_all_stories_data()
    build_portal_html(stories)
    if "--serve" in sys.argv:
        port = 8080
        if len(sys.argv) > 2 and sys.argv[2].isdigit():
            port = int(sys.argv[2])
        serve_portal(port)
