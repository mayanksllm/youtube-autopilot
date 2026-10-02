"""
print_cloud_secrets.py - Helper to display your GitHub Actions Secrets
=======================================================================
Run this script to inspect your GitHub Actions secrets ready to copy into:
GitHub Repo -> Settings -> Secrets and variables -> Actions -> New repository secret
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

BASE = Path(__file__).resolve().parent
token_file = BASE / "token.json"
client_file = BASE / "client_secrets.json"
env_file = BASE / ".env"

load_dotenv()

print("=" * 75)
print("  🔑 GITHUB ACTIONS SECRETS FOR AUTONOMOUS VIDEO PRODUCTION")
print("  Settings -> Secrets and variables -> Actions -> Repository Secrets")
print("=" * 75)

import base64
import json

b64_client_secret = ""
if client_file.exists():
    b64_client_secret = base64.b64encode(client_file.read_bytes()).decode("utf-8")

refresh_token_val = ""
if token_file.exists():
    try:
        t_data = json.loads(token_file.read_text(encoding="utf-8"))
        refresh_token_val = t_data.get("refresh_token", "")
    except Exception:
        pass

print("\n--- [OPTION 1 (RECOMMENDED): COMPACT SINGLE-LINE REPOSITORY SECRETS] ---")
print(f"GEMINI_API_KEY               : {os.environ.get('GEMINI_API_KEY', 'Not set in .env')}")
print(f"GROQ_API_KEY                 : {os.environ.get('GROQ_API_KEY', 'Not set in .env')}")
print(f"YOUTUBE_CLIENT_SECRET_BASE64 :\n{b64_client_secret}\n")
print(f"YOUTUBE_REFRESH_TOKEN        :\n{refresh_token_val}\n")

print("\n--- [OPTION 2 (ALTERNATIVE): RAW JSON STRINGS] ---")
print("\n--- YOUTUBE_TOKEN_JSON ---")
if token_file.exists():
    print(token_file.read_text(encoding="utf-8").strip())
else:
    print("token.json not found")

print("\n--- CLIENT_SECRETS_JSON ---")
if client_file.exists():
    print(client_file.read_text(encoding="utf-8").strip())
else:
    print("client_secrets.json not found")

print("\n" + "-" * 75)
print("  MULTI-TIER FAILOVER ENHANCEMENTS (Optional for zero-cost cascade):")
print("-" * 75)
print(f"GROQ_API_KEY       : {os.environ.get('GROQ_API_KEY', 'None (Tier 2 Scripting)')}")
print(f"OPENROUTER_API_KEY : {os.environ.get('OPENROUTER_API_KEY', 'None (Tier 3 Scripting)')}")
print(f"DEEPSEEK_API_KEY   : {os.environ.get('DEEPSEEK_API_KEY', 'None (Tier 3 Scripting)')}")
print(f"COHERE_API_KEY     : {os.environ.get('COHERE_API_KEY', 'None (Tier 4 Scripting)')}")
print(f"HF_TOKEN           : {os.environ.get('HF_TOKEN', os.environ.get('HUGGINGFACE_API_TOKEN', 'None (Tier 2 FLUX)'))}")
print(f"TOGETHER_API_KEY   : {os.environ.get('TOGETHER_API_KEY', 'None (Tier 3 SDXL)')}")
print(f"ELEVENLABS_API_KEY : {os.environ.get('ELEVENLABS_API_KEY', 'None (Using Neural Fallback hi-IN-MadhurNeural)')}")
print(f"ANTHROPIC_API_KEY  : {os.environ.get('ANTHROPIC_API_KEY', 'None')}")
print(f"TAVILY_API_KEY     : {os.environ.get('TAVILY_API_KEY', 'None')}")
print(f"PERPLEXITY_API_KEY : {os.environ.get('PERPLEXITY_API_KEY', 'None')}")
print(f"PEXELS_API_KEY     : {os.environ.get('PEXELS_API_KEY', 'None')}")
print("=" * 75 + "\n")
