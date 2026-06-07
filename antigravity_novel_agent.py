import os
import sys
import asyncio
import glob
import re
from google.antigravity import Agent, LocalAgentConfig

# Setup environment variables from .env if available
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

# Ensure base paths exist
SECOND_BRAIN = "./SecondBrain"

# Import existing functions from our project modules
from scout import fetch_syosetu_novels, fetch_royalroad_novels, write_to_obsidian, ensure_dirs
from agent_analyzer import process_scouting_pool
from agent_writer import process_analyzed_novels
from audio_engine import process_audio_scripts
from teaser_generator import process_teasers

# ----------------- 🛠️ Definition of Agent Tools -----------------

def scout_novels_tool(source: str = "all", limit: int = 3) -> str:
    """
    Scouts trending novels from Royal Road and Syosetu and saves them to Obsidian.
    :param source: The source to scrape ('syosetu', 'royalroad', or 'all')
    :param limit: Number of novels to fetch per source (default 3)
    """
    ensure_dirs(SECOND_BRAIN)
    all_novels = []
    
    if source in ["syosetu", "all"]:
        novels = fetch_syosetu_novels(limit=limit, order="weekly_point")
        all_novels.extend(novels)
    if source in ["royalroad", "all"]:
        novels = fetch_royalroad_novels(limit=limit)
        all_novels.extend(novels)
        
    written = 0
    for novel in all_novels:
        try:
            write_to_obsidian(novel, SECOND_BRAIN)
            written += 1
        except Exception as e:
            pass
            
    return f"[+] Success: Scouted {written} novels and saved them to the Scouting Pool."

def analyze_pool_tool() -> str:
    """
    Scans the Scouting Pool for raw novels, processes them with AI to extract 
    Thai working titles, localized synopses, market fit, and sets status to 'Analyzed'.
    """
    try:
        process_scouting_pool(SECOND_BRAIN)
        return "[+] Success: Analyzed all raw novels in the Scouting Pool and generated market viability reviews."
    except Exception as e:
        return f"[!] Error during AI Analysis: {str(e)}"

def write_recreation_tool() -> str:
    """
    Selects 'Analyzed' novels from the pool and recreates them as new Thai Original IPs.
    Generates concept outline, character database, Chapter 1, and audiobook script.
    """
    try:
        process_analyzed_novels(SECOND_BRAIN)
        return "[+] Success: Novel outlines, character DBs, and Chapter 1 drafts generated successfully."
    except Exception as e:
        return f"[!] Error during Novel Re-creation: {str(e)}"

def render_audiobook_tool() -> str:
    """
    Scans for audio scripts in the Second Brain and renders them to MP3 audiobook files
    using the configured TTS engine (default: macOS offline Kanya voice).
    """
    try:
        process_audio_scripts(SECOND_BRAIN)
        return "[+] Success: Rendered all audio scripts to MP3 audiobooks."
    except Exception as e:
        return f"[!] Error during TTS rendering: {str(e)}"

def build_teaser_video_tool(max_duration: int = 60) -> str:
    """
    Merges MP3 audiobooks with cover art into a vertical video (9:16) for TikTok/Shorts.
    :param max_duration: Limit video length in seconds (default 60)
    """
    try:
        process_teasers(SECOND_BRAIN, max_dur=max_duration)
        return "[+] Success: Teaser videos compiled successfully using FFmpeg."
    except Exception as e:
        return f"[!] Error during Teaser generation: {str(e)}"

# ----------------- 🚀 Agent Session Execution -----------------

async def run_agent(task_prompt: str):
    print(f"[*] Connecting to the Antigravity Agent Runtime...")
    
    # Configure the agent
    config = LocalAgentConfig(
        system_instructions=(
            "You are the 'ANSRE Chief Orchestrator' - an autonomous agent supervising the "
            "entire novel scouting, analyzing, writing, and video rendering pipeline.\n"
            "You have tools for each step: scouting, analyzing, writing, audio rendering, and video teaser compilation.\n"
            "Your goal is to coordinate these tools, execute them in order, verify files are written correctly, "
            "and present a summary report to the user once finished."
        ),
        tools=[
            scout_novels_tool,
            analyze_pool_tool,
            write_recreation_tool,
            render_audiobook_tool,
            build_teaser_video_tool
        ]
    )
    
    # Execute agent chat
    async with Agent(config) as agent:
        print(f"[*] Directing agent with: \"{task_prompt}\"")
        response = await agent.chat(task_prompt)
        
        print("\n=== Agent Response ===")
        print(await response.text())

if __name__ == "__main__":
    prompt = "Execute the full pipeline: scout 2 novels, analyze them, select the best one to write, render its audiobook, and build a 30-second vertical teaser video."
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
        
    asyncio.run(run_agent(prompt))
