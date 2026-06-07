import argparse
import sys
import os
import subprocess

def run_command(cmd_list, env=None):
    """Helper to run command as subprocess and stream output."""
    process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in process.stdout:
        print(line, end="")
    process.wait()
    return process.returncode

def main():
    # Load environment variables from .env file if it exists
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

    parser = argparse.ArgumentParser(description="ANSRE - Agentic Novel Scouting & Re-creation Engine CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")
    
    # 1. Scout Command
    scout_parser = subparsers.add_parser("scout", help="Scrape trending novels and save to Second Brain")
    scout_parser.add_argument("--source", type=str, default="all", choices=["syosetu", "royalroad", "all"],
                              help="Sources to scrape (default: all)")
    scout_parser.add_argument("--limit", type=int, default=5,
                              help="Number of novels to scrape per source (default: 5)")
    scout_parser.add_argument("--outdir", type=str, default="./SecondBrain",
                              help="Second Brain vault path")
    
    # 2. Analyze Command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze scouted novels using AI (Gemini)")
    analyze_parser.add_argument("--outdir", type=str, default="./SecondBrain",
                                help="Second Brain vault path")
    
    # 3. Write Command
    write_parser = subparsers.add_parser("write", help="Re-create novel concepts, outlines, and write Chapter 1 drafts")
    write_parser.add_argument("--outdir", type=str, default="./SecondBrain",
                              help="Second Brain vault path")
    
    # 4. Cover Command
    cover_parser = subparsers.add_parser("cover", help="Generate book cover art using Imagen 3")
    cover_parser.add_argument("--outdir", type=str, default="./SecondBrain",
                              help="Second Brain vault path")
    
    # 5. Audio Command
    audio_parser = subparsers.add_parser("audio", help="Render audio scripts in Second Brain to MP3 audiobooks")
    audio_parser.add_argument("--outdir", type=str, default="./SecondBrain",
                              help="Second Brain vault path")
    
    # 5. Teaser Command
    teaser_parser = subparsers.add_parser("teaser", help="Generate mobile-friendly video teasers (MP4) from audiobooks and covers")
    teaser_parser.add_argument("--outdir", type=str, default="./SecondBrain",
                              help="Second Brain vault path")
    teaser_parser.add_argument("--duration", type=int, default=60,
                              help="Max video duration in seconds (default: 60)")
    
    # 6. Pipeline Command
    pipeline_parser = subparsers.add_parser("pipeline", help="Run the full pipeline: Scout -> Analyze -> Write -> Audio -> Teaser")
    pipeline_parser.add_argument("--source", type=str, default="all", choices=["syosetu", "royalroad", "all"],
                                 help="Sources to scrape (default: all)")
    pipeline_parser.add_argument("--limit", type=int, default=3,
                                 help="Number of novels to scrape per source (default: 3)")
    pipeline_parser.add_argument("--outdir", type=str, default="./SecondBrain",
                                 help="Second Brain vault path")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
        
    python_bin = os.path.join(".venv", "bin", "python")
    if not os.path.exists(python_bin):
        python_bin = "python3" # fallback
        
    # Environment copy
    my_env = os.environ.copy()
    
    if args.command == "scout":
        cmd = [python_bin, "scout.py", "--source", args.source, "--limit", str(args.limit), "--outdir", args.outdir]
        print(f"[*] Running Scouting Module...")
        run_command(cmd, env=my_env)
        
    elif args.command == "analyze":
        if "GEMINI_API_KEY" not in os.environ:
            print("[!] Error: GEMINI_API_KEY environment variable is not set.")
            print("Please export your API key before running: export GEMINI_API_KEY='your_key'")
            sys.exit(1)
        cmd = [python_bin, "agent_analyzer.py", args.outdir]
        print(f"[*] Running AI Analysis Module...")
        run_command(cmd, env=my_env)
        
    elif args.command == "write":
        if "GEMINI_API_KEY" not in os.environ:
            print("[!] Error: GEMINI_API_KEY environment variable is not set.")
            print("Please export your API key before running: export GEMINI_API_KEY='your_key'")
            sys.exit(1)
        cmd = [python_bin, "agent_writer.py", args.outdir]
        print(f"[*] Running Novel Re-creation & Writing Module...")
        run_command(cmd, env=my_env)
        
    elif args.command == "cover":
        if "GEMINI_API_KEY" not in os.environ:
            print("[!] Error: GEMINI_API_KEY environment variable is not set.")
            print("Please export your API key before running: export GEMINI_API_KEY='your_key'")
            sys.exit(1)
        cmd = [python_bin, "cover_generator.py", args.outdir]
        print(f"[*] Running Automated Cover Generator Module...")
        run_command(cmd, env=my_env)
        
    elif args.command == "audio":
        cmd = [python_bin, "audio_engine.py", args.outdir]
        print(f"[*] Running Audio TTS Engine Module...")
        run_command(cmd, env=my_env)
        
    elif args.command == "teaser":
        cmd = [python_bin, "teaser_generator.py", args.outdir, str(args.duration)]
        print(f"[*] Running TikTok Teaser Generator Module...")
        run_command(cmd, env=my_env)
        
    elif args.command == "pipeline":
        if "GEMINI_API_KEY" not in os.environ:
            print("[!] Error: GEMINI_API_KEY environment variable is not set.")
            print("Please export your API key before running: export GEMINI_API_KEY='your_key'")
            sys.exit(1)
            
        print("\n=== STEP 1: SCOUTING TRENDS ===")
        scout_cmd = [python_bin, "scout.py", "--source", args.source, "--limit", str(args.limit), "--outdir", args.outdir]
        code = run_command(scout_cmd, env=my_env)
        if code != 0:
            print("[!] Scout step failed. Aborting pipeline.")
            sys.exit(code)
            
        print("\n=== STEP 2: RUNNING AI ANALYZER ===")
        analyze_cmd = [python_bin, "agent_analyzer.py", args.outdir]
        code = run_command(analyze_cmd, env=my_env)
        if code != 0:
            print("[!] Analysis step failed. Aborting pipeline.")
            sys.exit(code)
            
        print("\n=== STEP 3: RUNNING NOVEL RE-CREATOR & WRITER ===")
        write_cmd = [python_bin, "agent_writer.py", args.outdir]
        code = run_command(write_cmd, env=my_env)
        if code != 0:
            print("[!] Writing step failed. Aborting pipeline.")
            sys.exit(code)
            
        print("\n=== STEP 3.5: GENERATING COVER ART ===")
        cover_cmd = [python_bin, "cover_generator.py", args.outdir]
        code = run_command(cover_cmd, env=my_env)
        if code != 0:
            print("[!] Cover generation step failed. Aborting pipeline.")
            sys.exit(code)
            
        print("\n=== STEP 4: RENDERING AUDIOBOOKS ===")
        audio_cmd = [python_bin, "audio_engine.py", args.outdir]
        code = run_command(audio_cmd, env=my_env)
        if code != 0:
            print("[!] Audio rendering step failed. Aborting pipeline.")
            sys.exit(code)
            
        print("\n=== STEP 5: GENERATING TEASER VIDEOS ===")
        teaser_cmd = [python_bin, "teaser_generator.py", args.outdir, "60"]
        code = run_command(teaser_cmd, env=my_env)
        if code != 0:
            print("[!] Teaser generation step failed. Aborting pipeline.")
            sys.exit(code)
            
        print("\n[+] Full ANSRE pipeline finished successfully!")

if __name__ == "__main__":
    main()
