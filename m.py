"""
Autonomous YouTube Shorts Agent (Entry Point: m.py)
====================================================
Integrates the Autonomous Viral Video Director & Research Engine:
- Dynamic breakout research before upload (Anti-repetition gate: last 2 runs checked)
- High-retention scripting engine (0-2s hook, 140-160 WPM, infinite loop, clean Hindi/Hinglish)
- Cinematic 3D hyper-realism & Unreal Engine 5 visual composition
- Modern high-contrast typography subtitles (2-3 words per burst, drop shadow)
- Master audio mixing: Neural voiceover + cut-point SFX (-16dB) + ambient score (-20dB)
"""

import sys
import argparse
from pathlib import Path

from viral_director_engine import (
    execute_viral_director,
    DynamicResearchEngine,
    RetentionScriptingEngine,
    ViralDirectorPipeline
)

from autonomous_viral_reels_engine import (
    run_autonomous_viral_reels_engine
)

from autonomous_youtube_agent import (
    execute_pipeline,
    optimize_profile,
    optimize_channel_profile,
    get_youtube_service,
    audit_previous_performance,
    get_current_trends,
    upload_to_youtube
)


def run_viral_cli_listener():
    """Interactive CLI listener for the Autonomous Viral Video Director."""
    print("\n" + "=" * 70)
    print("  🚀 AUTONOMOUS VIRAL VIDEO DIRECTOR (AntiGravity IDE)")
    print("  High-Retention Scripting • Anti-Repetition Research • 1080x1920")
    print("=" * 70)
    print("\nAvailable Commands:")
    print("  • start                  -> Autonomous trend research & viral reel generation")
    print("  • reels                  -> Run AutonomousViralReelsEngine (Perplexity+Claude+ElevenLabs+Remotion)")
    print("  • start with <topic>     -> Generate viral reel on custom topic")
    print("  • research               -> Scan breakout mysteries & check history")
    print("  • optimize [niche]       -> AI Channel branding optimization")
    print("  • legacy                 -> Run original basic pipeline")
    print("  • exit / quit            -> Terminate agent")
    print("=" * 70 + "\n")

    history_file = Path(__file__).parent / "history.json"

    while True:
        try:
            cmd = input("\nViral Director > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nShutting down Director.")
            break

        if not cmd:
            continue

        lower = cmd.lower()
        if lower in ("exit", "quit", "q"):
            print("👋 Exiting Autonomous Director.")
            break
        elif lower in ("help", "?"):
            print("\nCommands: 'start', 'start with <topic>', 'research', 'optimize', 'legacy', 'exit'")
        elif lower == "start":
            print("\n🚀 Launching Autonomous Production with Dynamic Research...")
            execute_viral_director(topic_override=None, dry_run=False)
        elif lower == "reels":
            print("\n🚀 Launching AutonomousViralReelsEngine (Perplexity/Tavily + Claude + ElevenLabs + Remotion)...")
            run_autonomous_viral_reels_engine(dry_run=False)
        elif lower.startswith("start with"):
            topic = cmd[len("start with"):].strip()
            print(f"\n🎯 Directing custom viral reel for: '{topic}'...")
            execute_viral_director(topic_override=topic, dry_run=False)
        elif lower == "research":
            chosen = DynamicResearchEngine.select_unique_topic(history_file)
            print(f"\n💡 Next Recommended Breakout Topic:\n   • {chosen['topic']}")
            print(f"   • Category: {chosen['category']}")
            print(f"   • Headline: {chosen['headline']}")
        elif lower.startswith("optimize"):
            niche = cmd.replace("optimize", "").replace("channel", "").replace("profile", "").strip()
            optimize_profile(niche if niche else "Indian mysteries, scientific paradoxes, and ancient enigmas")
        elif lower == "legacy":
            print("\nRunning legacy agent pipeline...")
            execute_pipeline(directive=None)
        else:
            # Treat unknown command as topic directive
            print(f"\n🎯 Directing reel on: '{cmd}'...")
            execute_viral_director(topic_override=cmd, dry_run=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Viral Video Director (m.py)")
    parser.add_argument("--topic", type=str, default=None, help="Custom topic override")
    parser.add_argument("--dry-run", action="store_true", help="Render video locally without publishing")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive CLI prompt")

    args = parser.parse_args()

    if args.interactive or (len(sys.argv) == 1 and sys.stdin.isatty()):
        run_viral_cli_listener()
    elif args.topic:
        execute_viral_director(topic_override=args.topic, dry_run=args.dry_run)
    else:
        execute_viral_director(topic_override=None, dry_run=args.dry_run)