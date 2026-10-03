"""
autopilot_config.py - Centralized Configuration & Tunables for YouTube Autopilot
==============================================================================
All system constants, quota limits, cooldowns, model pools, and quality thresholds.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
LOGS_DIR = BASE_DIR / "logs"
OUTPUT_DIR = ASSETS_DIR / "output"
THUMBNAILS_DIR = ASSETS_DIR / "thumbnails"

for d in [ASSETS_DIR, LOGS_DIR, OUTPUT_DIR, THUMBNAILS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# 1. Similarity & Variety Configuration
# -----------------------------------------------------------------------------
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.65"))

COOLDOWNS = {
    "visual_style": int(os.environ.get("COOLDOWN_STYLE", "15")),
    "hook_format": int(os.environ.get("COOLDOWN_HOOK", "4")),
    "camera_move": int(os.environ.get("COOLDOWN_CAMERA", "3")),
    "caption_style": int(os.environ.get("COOLDOWN_CAPTION", "4")),
    "music_mood": int(os.environ.get("COOLDOWN_MUSIC", "4")),
    "voice": int(os.environ.get("COOLDOWN_VOICE", "3")),
    "category": int(os.environ.get("COOLDOWN_CATEGORY", "3")),
}

# Master Variety Stores
VARIETY_STORE_PATH = BASE_DIR / "variety_store.json"
HISTORY_LOG_PATH = BASE_DIR / "history_log.json"
HISTORY_PATH = BASE_DIR / "history.json"
STATE_PATH = BASE_DIR / "autopilot_state.json"

# -----------------------------------------------------------------------------
# 2. YouTube Data API Quota Budgeting
# -----------------------------------------------------------------------------
# Daily free project quota is 10,000 units. Resets at midnight Pacific Time.
QUOTA_DAILY_MAX = 10000
QUOTA_COSTS = {
    "videos.insert": 1600,
    "thumbnails.set": 50,
    "commentThreads.insert": 50,
    "comments.insert": 50,
    "commentThreads.list": 1,
    "videos.list": 1,
    "channels.list": 1,
}
# Safety margin: stop gracefully if estimated remaining quota is below this threshold
MIN_REMAINING_QUOTA_FOR_RUN = 1750

# -----------------------------------------------------------------------------
# 3. Auto-Reply Community Engine Tunables
# -----------------------------------------------------------------------------
MAX_REPLIES_PER_RUN = int(os.environ.get("MAX_REPLIES_PER_RUN", "5"))

# -----------------------------------------------------------------------------
# 4. Scriptwriter + Critic Quality Engine
# -----------------------------------------------------------------------------
CRITIC_MIN_SCORE = float(os.environ.get("CRITIC_MIN_SCORE", "7.0"))
MAX_SCRIPT_REVISIONS = int(os.environ.get("MAX_SCRIPT_REVISIONS", "2"))

# -----------------------------------------------------------------------------
# 5. Gemini & AI Model Cascades
# -----------------------------------------------------------------------------
GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest"
]

# -----------------------------------------------------------------------------
# 6. Global Browser User-Agent Header
# -----------------------------------------------------------------------------
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
