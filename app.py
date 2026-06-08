import os
import re
import sys
import glob
import subprocess
from typing import Dict, Any, Tuple, List
import streamlit as st
import pandas as pd
from llm_provider import generate

# Setup Gemini API Key
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")
    API_KEY = os.environ.get("GEMINI_API_KEY")

# LLM calls go through llm_provider.generate (gemini/local by role)

# ----------------- Page Configuration -----------------
st.set_page_config(
    page_title="ANSRE Creator Studio",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ----------------- Theme Setup -----------------
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

def toggle_theme():
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"

IS_DARK = st.session_state.theme == "dark"

# Define CSS custom property values based on active theme
if IS_DARK:
    bg = "#09090b"
    bg_subtle = "#0c0c0f"
    card = "#0c0c0f"
    card_hover = "#131316"
    border = "#1e1e24"
    border_subtle = "#16161a"
    text = "#fafafa"
    text_muted = "#71717a"
    text_dim = "#52525b"
    accent = "#00FFFF"
    accent_muted = "#00cccc"
    green = "#22c55e"
    green_muted = "rgba(34,197,94,0.12)"
    red = "#ef4444"
    red_muted = "rgba(239,68,68,0.12)"
    amber = "#f59e0b"
    amber_muted = "rgba(245,158,11,0.12)"
    shadow = "none"
else:
    bg = "#ffffff"
    bg_subtle = "#f9fafb"
    card = "#ffffff"
    card_hover = "#f4f4f5"
    border = "#e4e4e7"
    border_subtle = "#f0f0f2"
    text = "#09090b"
    text_muted = "#71717a"
    text_dim = "#a1a1aa"
    accent = "#0284c7"
    accent_muted = "#0369a1"
    green = "#16a34a"
    green_muted = "rgba(22,163,74,0.08)"
    red = "#dc2626"
    red_muted = "rgba(220,38,38,0.08)"
    amber = "#d97706"
    amber_muted = "rgba(217,119,6,0.08)"
    shadow = "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)"

# Inject Custom CSS Styling
css = f"""
<style>
:root {{
    --bg: {bg};
    --bg-subtle: {bg_subtle};
    --card: {card};
    --card-hover: {card_hover};
    --border: {border};
    --border-subtle: {border_subtle};
    --text: {text};
    --text-muted: {text_muted};
    --text-dim: {text_dim};
    --accent: {accent};
    --accent-muted: {accent_muted};
    --green: {green};
    --green-muted: {green_muted};
    --red: {red};
    --red-muted: {red_muted};
    --amber: {amber};
    --amber-muted: {amber_muted};
    --shadow: {shadow};
    --radius: 10px;
}}

/* Hide Streamlit chrome */
header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"], .stDeployButton,
div[data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
}}

/* Global App Styling */
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .main, .block-container, section[data-testid="stMain"] {{
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'DM Sans', -apple-system, sans-serif !important;
}}
.block-container {{
    padding: 2rem 2.5rem 3rem !important;
    max-width: 1400px !important;
}}

/* Grid layout gap */
[data-testid="stHorizontalBlock"] {{ gap: 1.25rem !important; }}

/* Metric Cards */
.metric-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem 1.4rem;
    box-shadow: var(--shadow);
    margin-bottom: 1rem;
}}
.metric-label {{
    font-size: 0.78rem;
    color: var(--text-muted);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.metric-value {{
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.03em;
    margin-top: 0.2rem;
}}

/* Styled card wrappers */
.card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    box-shadow: var(--shadow);
    margin-bottom: 1rem;
}}
.card-title {{
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 0.8rem;
    display: flex;
    align-items: center;
    gap: 8px;
}}

/* HTML Table */
.data-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.825rem;
}}
.data-table th {{
    text-align: left;
    padding: 0.75rem 1rem;
    color: var(--text-muted);
    font-weight: 600;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-bottom: 1px solid var(--border);
    background: var(--bg-subtle);
}}
.data-table td {{
    padding: 0.8rem 1rem;
    color: var(--text);
    border-bottom: 1px solid var(--border-subtle);
    vertical-align: middle;
}}
.data-table tr:hover td {{
    background: var(--card-hover);
}}
.data-table tr:last-child td {{
    border-bottom: none;
}}

/* Status Badges */
.badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}}
.badge-new {{ color: var(--text-muted); background: var(--border); border: 1px solid var(--border); }}
.badge-analyzed {{ color: var(--amber); background: var(--amber-muted); border: 1px solid rgba(245, 158, 11, 0.2); }}
.badge-processed {{ color: var(--green); background: var(--green-muted); border: 1px solid rgba(34, 197, 94, 0.2); }}
.badge-default {{ color: var(--accent); background: rgba(0, 255, 255, 0.08); border: 1px solid rgba(0, 255, 255, 0.2); }}

/* App Header Brand */
.brand {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2rem;
}}
.brand-logo {{
    font-size: 2.2rem;
}}
.brand-name {{
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.02em;
}}
.brand-tagline {{
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 0.1rem;
}}

/* Tabs (pill-style) */
button[data-baseweb="tab"] {{
    background: transparent !important;
    color: var(--text-muted) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    padding: 0.6rem 1.2rem !important;
    border: 1px solid transparent !important;
    border-radius: 7px !important;
    transition: all 0.2s ease !important;
}}
button[data-baseweb="tab"]:hover {{
    color: var(--text) !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: var(--text) !important;
    background: var(--card) !important;
    border-color: var(--border) !important;
}}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{
    display: none !important;
}}
[data-baseweb="tab-list"] {{
    gap: 6px !important;
    background: var(--bg-subtle) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 4px !important;
}}
</style>
"""
st.markdown(css, unsafe_allow_html=True)

# ----------------- Helper Functions -----------------
def parse_markdown_file(filepath: str) -> Tuple[Dict[str, Any], str]:
    """Parse Obsidian markdown file and separate frontmatter from body content."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    frontmatter = {}
    body = content
    
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if match:
        yaml_text = match.group(1)
        body = match.group(2)
        
        current_list_key = None
        for line in yaml_text.splitlines():
            line_strip = line.strip()
            if not line_strip:
                continue
            if line.startswith("  - ") and current_list_key:
                val = line.replace("  - ", "").strip().strip('"').strip("'")
                frontmatter[current_list_key].append(val)
            elif ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if not val and (line.endswith(":") or key == "tags"):
                    frontmatter[key] = []
                    current_list_key = key
                else:
                    frontmatter[key] = val
                    current_list_key = None
    return frontmatter, body

def get_clean_title(thai_title: str) -> str:
    """Derive file-safe titles using the same logic as agent_writer.py."""
    clean_title = re.sub(r'[^\w\-_\s]', '', thai_title)
    clean_title = clean_title.strip().replace(' ', '_')
    return clean_title

def metric_card(label: str, value: str, delta: str = None, delta_type: str = "up"):
    cls = f"delta-{delta_type}"
    arrow = "↑" if delta_type == "up" else ("↓" if delta_type == "down" else "→")
    delta_html = f'<div class="metric-delta {cls}">{arrow} {delta}</div>' if delta else ""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

def load_scouting_pool(second_brain_dir: str) -> List[Dict[str, Any]]:
    scouting_pool_dir = os.path.join(second_brain_dir, "01_Scouting_Pool")
    if not os.path.exists(scouting_pool_dir):
        return []
    md_files = glob.glob(os.path.join(scouting_pool_dir, "*.md"))
    novels = []
    
    for filepath in md_files:
        try:
            frontmatter, _ = parse_markdown_file(filepath)
            frontmatter["filename"] = os.path.basename(filepath)
            frontmatter["filepath"] = filepath
            novels.append(frontmatter)
        except Exception:
            pass
    return novels

def run_cli_command(args_list: List[str], env_vars: Dict[str, str] = None):
    python_bin = os.path.join(".venv", "bin", "python")
    if not os.path.exists(python_bin):
        python_bin = "python3"
        
    cmd = [python_bin, "ansre.py"] + args_list
    
    my_env = os.environ.copy()
    if env_vars:
        my_env.update(env_vars)
        
    log_placeholder = st.empty()
    log_lines = []
    
    with st.spinner(f"Executing: ansre.py {' '.join(args_list)}..."):
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=my_env
        )
        
        for line in process.stdout:
            log_lines.append(line)
            log_placeholder.code("".join(log_lines[-20:])) # display last 20 lines
        process.wait()
        
    if process.returncode == 0:
        st.success(f"Successfully finished: {' '.join(args_list)}")
        st.balloons()
        return True
    else:
        st.error(f"Failed with exit code: {process.returncode}")
        st.code("".join(log_lines))
        return False

# ----------------- Data Loading -----------------
second_brain_path = "./SecondBrain"
novels = load_scouting_pool(second_brain_path)

# ----------------- UI Header -----------------
head_left, head_right = st.columns([8, 2])
with head_left:
    st.markdown("""
    <div class="brand">
        <span class="brand-logo">📝</span>
        <div>
            <span class="brand-name">ANSRE Creator Studio</span>
            <div class="brand-tagline">Agentic Novel Scouting & Re-creation Engine • Powered by Gemini 2.5</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
with head_right:
    theme_label = "☀️ Light Mode" if IS_DARK else "🌙 Dark Mode"
    st.button(theme_label, on_click=toggle_theme, use_container_width=True)

# ----------------- KPI Metric Cards -----------------
c1, c2, c3, c4 = st.columns(4)

total_novels = len(novels)
recreated_count = 0
market_fit_scores = []

for n in novels:
    status = n.get("status", "New")
    if status == "Processed":
        recreated_count += 1
    mfit = n.get("market_fit_score", "0")
    try:
        market_fit_scores.append(int(mfit))
    except:
        pass

avg_market_fit = f"{sum(market_fit_scores) / len(market_fit_scores):.1f}/10" if market_fit_scores else "N/A"

chapters_dir = os.path.join(second_brain_path, "05_Active_Projects", "Chapters")
audio_dir = os.path.join(second_brain_path, "05_Active_Projects", "Audio_Output")
teaser_dir = os.path.join(second_brain_path, "05_Active_Projects", "Teaser_Output")

chapters_count = len(glob.glob(os.path.join(chapters_dir, "*.md"))) if os.path.exists(chapters_dir) else 0
audio_count = len(glob.glob(os.path.join(audio_dir, "*.mp3"))) if os.path.exists(audio_dir) else 0
teaser_count = len(glob.glob(os.path.join(teaser_dir, "*.mp4"))) if os.path.exists(teaser_dir) else 0
total_assets = chapters_count + audio_count + teaser_count

with c1:
    metric_card("Total Scouted Novels", str(total_novels), delta="Observed trends")
with c2:
    metric_card("Average Market Fit Score", avg_market_fit, delta="Potential rating")
with c3:
    metric_card("Re-created Chapters", f"{recreated_count} / {total_novels}", delta="Engine conversion rate")
with c4:
    metric_card("Total Media Assets", str(total_assets), delta=f"{chapters_count} Ch | {audio_count} Aud | {teaser_count} Vid")

# ----------------- Navigation Tabs -----------------
tab1, tab2, tab3, tab4 = st.tabs(["📁 Scouting Pool & Actions", "✍️ Creative Writing Studio", "🎙️ Media Production Studio", "💡 Interactive Plot Brainstorming"])

# --- TAB 1: SCOUTING POOL ---
with tab1:
    # Sidebar control panel style inside columns
    col_table, col_actions = st.columns([7, 3])
    
    with col_table:
        st.markdown('<div class="card-title">📖 Scouted Novel Repository</div>', unsafe_allow_html=True)
        if not novels:
            st.warning("No novels found in the Scouting Pool. Run 'Scout Trends' to fetch trending data.")
        else:
            # Build Table HTML
            table_rows = []
            for n in novels:
                status = n.get("status", "New")
                badge_class = "badge-new"
                if status == "Analyzed":
                    badge_class = "badge-analyzed"
                elif status == "Processed":
                    badge_class = "badge-processed"
                
                title = n.get("title", "Unknown")
                source = n.get("source", "Unknown")
                genre = n.get("genre", "Unknown")
                thai_title = n.get("thai_working_title", "N/A")
                mfit = n.get("market_fit_score", "N/A")
                
                table_rows.append(
                    f"<tr>"
                    f"<td><b>{title}</b><br><small style='color:var(--text-muted)'>{source}</small></td>"
                    f"<td>{thai_title}</td>"
                    f"<td>{genre}</td>"
                    f"<td><span class='badge {badge_class}'>{status}</span></td>"
                    f"<td><b>{mfit}/10</b></td>"
                    f"</tr>"
                )
            
            table_html = (
                f'<table class="data-table">'
                f'<thead><tr>'
                f'<th>Original Title / Source</th>'
                f'<th>Thai Title</th>'
                f'<th>Genre</th>'
                f'<th>Status</th>'
                f'<th>Market Fit</th>'
                f'</tr></thead>'
                f'<tbody>{"".join(table_rows)}</tbody>'
                f'</table>'
            )
            st.html(table_html)
            
    with col_actions:
        st.markdown('<div class="card-title">⚙️ Engine Operations</div>', unsafe_allow_html=True)
        
        # Quality Settings
        st.markdown("##### 🛠️ Pipeline Configurations")
        writing_mode = st.selectbox(
            "Writing Quality Mode",
            ["Premium (Gemini 2.5 Pro for prose)", "Master (Gemini 2.5 Pro for all stages)", "Draft (Gemini 2.5 Flash - fast)"],
            index=0
        )
        mode_env = "premium"
        if "Master" in writing_mode:
            mode_env = "master"
        elif "Draft" in writing_mode:
            mode_env = "draft"
            
        tts_engine = st.selectbox(
            "TTS Engine Mode",
            ["Edge-TTS (Premium Free Neural)", "macOS Say (Local Voice)", "Google TTS (Standard)"],
            index=0
        )
        tts_env = "edge-tts"
        if "macOS" in tts_engine:
            tts_env = "macos"
        elif "Google" in tts_engine:
            tts_env = "gtts"
            
        st.write("---")
        
        # Scouting trigger
        st.markdown("##### 📡 Global Execution Actions")
        scout_source = st.selectbox("Scouting Source", ["all", "syosetu", "royalroad"])
        scout_limit = st.slider("Limit per source", 1, 10, 3)
        if st.button("📡 Run Scouting & Analysis Loop", use_container_width=True):
            run_cli_command(
                ["pipeline", "--source", scout_source, "--limit", str(scout_limit)],
                env_vars={"WRITING_MODE": mode_env, "TTS_ENGINE": tts_env}
            )
            st.rerun()
            
        st.write("---")
        
        # Single actions
        st.markdown("##### 🎯 Granular Process Commands")
        single_novel = st.selectbox(
            "Select Novel for Specific Action",
            [n.get("title") for n in novels] if novels else ["No novels in pool"]
        )
        
        selected_novel_obj = next((n for n in novels if n.get("title") == single_novel), None)
        
        col_cmd1, col_cmd2 = st.columns(2)
        with col_cmd1:
            analyze_btn = st.button("🔍 Analyze Details", use_container_width=True, disabled=not novels)
            write_btn = st.button("✍️ Recreate Script", use_container_width=True, disabled=not novels)
        with col_cmd2:
            cover_btn = st.button("🎨 Gen Cover Art", use_container_width=True, disabled=not novels)
            audio_btn = st.button("🎬 Render Audio & Vid", use_container_width=True, disabled=not novels)
            
        if analyze_btn and selected_novel_obj:
            run_cli_command(["analyze"], env_vars={"WRITING_MODE": mode_env, "TTS_ENGINE": tts_env})
            st.rerun()
            
        if write_btn and selected_novel_obj:
            run_cli_command(["write"], env_vars={"WRITING_MODE": mode_env, "TTS_ENGINE": tts_env})
            st.rerun()
            
        if cover_btn and selected_novel_obj:
            run_cli_command(["cover"], env_vars={"WRITING_MODE": mode_env, "TTS_ENGINE": tts_env})
            st.rerun()
            
        if audio_btn and selected_novel_obj:
            st.info("Rendering Audiobook & Video Teaser...")
            run_cli_command(["audio"], env_vars={"WRITING_MODE": mode_env, "TTS_ENGINE": tts_env})
            run_cli_command(["teaser"], env_vars={"WRITING_MODE": mode_env, "TTS_ENGINE": tts_env})
            st.rerun()

# --- TAB 2: CREATIVE WRITING STUDIO ---
with tab2:
    processed_novels = [n for n in novels if n.get("status") == "Processed"]
    
    if not processed_novels:
        st.warning("No novels have completed the re-creation process. Re-create a novel in Tab 1 first.")
    else:
        selected_p_novel = st.selectbox(
            "Select Chapter to Review",
            [p.get("thai_working_title") for p in processed_novels]
        )
        
        active_novel = next((p for p in processed_novels if p.get("thai_working_title") == selected_p_novel), None)
        
        if active_novel:
            clean_title = get_clean_title(active_novel.get("thai_working_title"))
            
            # Asset Path definitions
            outline_path = os.path.join(second_brain_path, "02_Concept_Extraction", f"{clean_title}_Outline.md")
            chars_path = os.path.join(second_brain_path, "04_Character_Database", f"{clean_title}_Characters.md")
            chapter_path = os.path.join(second_brain_path, "05_Active_Projects", "Chapters", f"{clean_title}_Chapter_01.md")
            script_path = os.path.join(second_brain_path, "05_Active_Projects", "Audio_Scripts", f"{clean_title}_AudioScript_01.md")
            
            # Sub-tabs for book assets
            st_out, st_char, st_chap, st_script = st.tabs([
                "📋 Master Outline", "👥 Character Database", "✍️ Chapter 1 Draft", "🎙️ Audio Production Script"
            ])
            
            with st_out:
                if os.path.exists(outline_path):
                    with open(outline_path, "r", encoding="utf-8") as f:
                        st.markdown(f.read())
                else:
                    st.error("Outline file not found.")
                    
            with st_char:
                if os.path.exists(chars_path):
                    with open(chars_path, "r", encoding="utf-8") as f:
                        st.markdown(f.read())
                else:
                    st.error("Character Database not found.")
                    
            with st_chap:
                if os.path.exists(chapter_path):
                    with open(chapter_path, "r", encoding="utf-8") as f:
                        st.markdown(f.read())
                else:
                    st.error("Chapter draft file not found.")
                    
            with st_script:
                if os.path.exists(script_path):
                    with open(script_path, "r", encoding="utf-8") as f:
                        st.code(f.read(), language="markdown")
                else:
                    st.error("Audio script file not found.")

# --- TAB 3: MEDIA PRODUCTION STUDIO ---
with tab3:
    processed_novels_media = [n for n in novels if n.get("status") == "Processed"]
    
    if not processed_novels_media:
        st.warning("No media assets available. Re-create and render a novel first.")
    else:
        selected_m_novel = st.selectbox(
            "Select Novel Media Asset",
            [p.get("thai_working_title") for p in processed_novels_media],
            key="media_novel_select"
        )
        
        active_media = next((p for p in processed_novels_media if p.get("thai_working_title") == selected_m_novel), None)
        
        if active_media:
            clean_title = get_clean_title(active_media.get("thai_working_title"))
            
            # Paths
            cover_path = os.path.join(second_brain_path, "05_Active_Projects", "Covers", f"{clean_title}_Cover.jpg")
            audio_path = os.path.join(second_brain_path, "05_Active_Projects", "Audio_Output", f"{clean_title}_Audiobook_01.mp3")
            teaser_path = os.path.join(second_brain_path, "05_Active_Projects", "Teaser_Output", f"{clean_title}_Teaser_01.mp4")
            
            col_cover, col_players = st.columns([4, 6])
            
            with col_cover:
                st.markdown('<div class="card-title">🎨 AI Generated Cover Art</div>', unsafe_allow_html=True)
                if os.path.exists(cover_path):
                    st.image(cover_path, use_container_width=True)
                else:
                    st.info("No cover art generated. Trigger 'Gen Cover Art' in Tab 1 to generate one.")
                    
            with col_players:
                st.markdown('<div class="card-title">🎙️ Audio & Video Player</div>', unsafe_allow_html=True)
                
                # Audiobook
                st.markdown("##### 🔊 Chapter 1 Audiobook")
                if os.path.exists(audio_path):
                    st.audio(audio_path, format="audio/mp3")
                    with open(audio_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Audiobook MP3",
                            data=f.read(),
                            file_name=os.path.basename(audio_path),
                            mime="audio/mp3",
                            use_container_width=True
                        )
                else:
                    st.warning("Audiobook MP3 not rendered. Trigger 'Render Audio & Vid' in Tab 1.")
                
                st.write("---")
                
                # Teaser Video
                st.markdown("##### 🎬 TikTok/Shorts Video Teaser")
                if os.path.exists(teaser_path):
                    st.video(teaser_path)
                    with open(teaser_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Teaser Video MP4",
                            data=f.read(),
                            file_name=os.path.basename(teaser_path),
                            mime="video/mp4",
                            use_container_width=True
                        )
                else:
                    st.warning("Teaser video not generated. Trigger 'Render Audio & Vid' in Tab 1.")

# --- TAB 4: INTERACTIVE PLOT BRAINSTORMING ---
with tab4:
    st.markdown('<div class="card-title">💡 Interactive Plot Brainstorming & Iterative Refinement</div>', unsafe_allow_html=True)
    st.write("ระบายไอเดียพล็อตนิยายของคุณที่นี่ แล้วให้ AI ช่วยออกแบบโครงเรื่อง (Outline) 10 ตอน จากนั้นค่อยๆ ปรับปรุงคำและรายละเอียดของพล็อตตามฟีดแบ็กไปทีละก้าวได้ตามใจชอบ!")
    
    # Initialize states
    if "brainstorm_outline" not in st.session_state:
        st.session_state.brainstorm_outline = ""
    if "brainstorm_history" not in st.session_state:
        st.session_state.brainstorm_history = []
    if "brainstorm_title" not in st.session_state:
        st.session_state.brainstorm_title = ""
        
    col_input, col_result = st.columns([4, 6])
    
    with col_input:
        st.markdown("### 1. วางคอนเซ็ปต์เริ่มต้น")
        initial_title = st.text_input("ชื่อเรื่องชั่วคราว (Working Title)", value=st.session_state.brainstorm_title)
        initial_concept = st.text_area("อธิบายแนวคิดย่อ/โครงเรื่องหลักที่คุณอยากเขียน", placeholder="เช่น ตัวเอกเปิดร้านขายวัตถุมงคลในยุคอนาคตที่ล่าผีด้วยปืนเลเซอร์...", height=150)
        genre_opt = st.selectbox("เลือกแนวเรื่อง (Genre)", ["แฟนตาซีต่างโลก (Isekai)", "สยองขวัญ/ระทึกขวัญ (Horror/Mystery)", "ไซไฟอนาคต (Sci-Fi Cyberpunk)", "โรแมนซ์/ดราม่า (Romance/Drama)"])
        
        if st.button("🚀 สร้างโครงร่าง Master Outline แรก", use_container_width=True):
            if not initial_concept.strip():
                st.error("กรุณากรอกแนวคิดย่อ/โครงเรื่องหลักก่อนเริ่มร่างครับ")
            elif not client:
                st.error("API Key ไม่พร้อมทำงาน")
            else:
                with st.spinner("กำลังออกแบบโครงเรื่อง 10 ตอนแรก..."):
                    st.session_state.brainstorm_title = initial_title if initial_title else "นิยายเรื่องใหม่"
                    prompt = f"""คุณคือ "Chief Outline Architect" ผู้แต่งโครงสร้างนิยายมืออาชีพ
                    อ้างอิงจากคอนเซ็ปต์ของผู้เขียน:
                    ชื่อเรื่อง: {st.session_state.brainstorm_title}
                    แนวเรื่อง: {genre_opt}
                    แนวคิดเริ่มต้น: {initial_concept}
                    
                    จงขยายความและวางโครงเรื่องรายละเอียด 10 ตอนแรกอย่างน่าตื่นเต้นและลื่นไหล
                    ให้ผลลัพธ์เป็นข้อความ Markdown ประกอบด้วย:
                    1. ชื่อเรื่องที่เป็นทางการ (Thai/English) และคำโปรยสั้น (Logline)
                    2. แนวคิดแกนเรื่องและกฎเกณฑ์ของโลก (Premise & World Rules)
                    3. รายละเอียดตอนที่ 1 ถึงตอนที่ 10 (อธิบายเนื้อหา ปมความขัดแย้งย่อย และทิ้งท้ายบทกระชับแต่เห็นภาพ)
                    """
                    try:
                        st.session_state.brainstorm_outline = generate(prompt, role="brainstorm")
                        st.session_state.brainstorm_history = [{"role": "system", "content": "เริ่มต้นร่างโครงเรื่องแรกสำเร็จ"}]
                        st.success("สร้างพล็อตตั้งต้นสำเร็จ!")
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {e}")
                        
        st.write("---")
        
        # Iterative Refinement Section
        if st.session_state.brainstorm_outline:
            st.markdown("### 🔄 2. ค่อยๆ คิดและปรับคำละเอียดทีละส่วน")
            st.write("ใส่ฟีดแบ็กหรือความต้องการในการแก้คำ/พล็อต เช่น *'อยากให้เปลี่ยนชื่อตัวเอกเป็นกวิน'*, *'อยากให้ตอนที่ 3 มีฉากแอ็กชันสู้กับวิญญาณเพิ่ม'*, หรือ *'ปรับการพรรณนาคำเปิดตอน 1 ให้หรูหราขึ้น'*")
            feedback = st.text_area("ระบุสิ่งที่ต้องการปรับปรุง", placeholder="บอก AI ได้เลย เช่น ปรับตอนที่ 2 ให้ตึงเครียดขึ้น หรือเปลี่ยนจุดหักมุมตอนจบ...", height=100)
            
            if st.button("🔄 ส่งข้อเสนอแนะปรับพล็อตทันที", use_container_width=True):
                if not feedback.strip():
                    st.error("กรุณาระบุสิ่งที่ต้องการปรับปรุงก่อนกดปุ่มครับ")
                else:
                    with st.spinner("กำลังคุยกับผู้กำกับนิยาย AI เพื่อขัดเกลาและปรับพล็อตตามคำสั่ง..."):
                        refine_prompt = f"""คุณคือ "Chief Outline Architect & Literary Strategist"
                        นี่คือโครงร่างนิยายเวอร์ชันปัจจุบัน:
                        {st.session_state.brainstorm_outline}
                        
                        ผู้เขียนต้องการปรับปรุงพล็อตตามฟีดแบ็กนี้:
                        "{feedback}"
                        
                        จงนำเสนอโครงร่างที่อัปเดตและขัดเกลาคำใหม่ตามฟีดแบ็กอย่างเป็นมืออาชีพ โดยคงโครงสร้าง 10 ตอนเหมือนเดิม ปรับเฉพาะจุดที่ผู้เขียนระบุ หรือขยายความเพิ่มเติมให้ลงตัว
                        """
                        try:
                            st.session_state.brainstorm_outline = generate(refine_prompt, role="brainstorm")
                            st.session_state.brainstorm_history.append({"role": "user", "content": feedback})
                            st.success("ปรับปรุงพล็อตและคำเรียบร้อยแล้ว!")
                        except Exception as e:
                            st.error(f"เกิดข้อผิดพลาดในการวิเคราะห์: {e}")
            
            st.write("---")
            st.markdown("### 💾 3. บันทึกเข้าคลังงาน")
            save_name = st.text_input("ชื่อไฟล์สำหรับบันทึก (ภาษาอังกฤษ/ตัวเลข ไม่มีเว้นวรรค)", value="Interactive_Brainstorm_Outline")
            if st.button("💾 บันทึกลง Second Brain", use_container_width=True):
                try:
                    out_dir = os.path.join(second_brain_path, "02_Concept_Extraction")
                    os.makedirs(out_dir, exist_ok=True)
                    clean_filename = re.sub(r'[^\w\-_\s]', '', save_name).strip().replace(' ', '_')
                    save_path = os.path.join(out_dir, f"{clean_filename}_Outline.md")
                    
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(st.session_state.brainstorm_outline)
                    st.success(f"บันทึกไฟล์สำเร็จที่: {save_path}")
                except Exception as e:
                    st.error(f"บันทึกไม่สำเร็จ: {e}")
                    
    with col_result:
        st.markdown("### 📋 โครงร่างปัจจุบัน (Current Outline)")
        if st.session_state.brainstorm_outline:
            st.markdown(st.session_state.brainstorm_outline)
            
            # Display history log
            if st.session_state.brainstorm_history:
                with st.expander("⏳ ประวัติการปรับปรุงคำ (Revision History)"):
                    for idx, h in enumerate(st.session_state.brainstorm_history):
                        st.write(f"**ขั้นตอนที่ {idx+1}:** {h['content']}")
        else:
            st.info("กรอกแนวคิดเริ่มต้นด้านซ้ายและคลิกปุ่มเพื่อเริ่มร่างโครงเรื่องระบบอัจฉริยะ")
