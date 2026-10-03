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
    "thumbnail_layout": int(os.environ.get("COOLDOWN_THUMB_LAYOUT", "3")),
    "thumbnail_font": int(os.environ.get("COOLDOWN_THUMB_FONT", "3")),
    "thumbnail_badge": int(os.environ.get("COOLDOWN_THUMB_BADGE", "3")),
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


# -----------------------------------------------------------------------------
# 7. Quota Manager Engine
# -----------------------------------------------------------------------------
class QuotaManager:
    """
    Monitors and budgets YouTube Data API quota units across runs.
    Daily free project quota: 10,000 units. Resets at 00:00 Pacific Time (PT).
    Persists estimated usage in variety_store.json.
    """
    @staticmethod
    def get_pt_date_str() -> str:
        from datetime import datetime, timezone, timedelta
        now_utc = datetime.now(timezone.utc)
        is_dst = 3 <= now_utc.month <= 10
        pt_offset = timedelta(hours=-7 if is_dst else -8)
        now_pt = now_utc.astimezone(timezone(pt_offset))
        return now_pt.strftime("%Y-%m-%d")

    @classmethod
    def get_estimated_used_units(cls) -> int:
        try:
            import json
            if VARIETY_STORE_PATH.exists():
                with open(VARIETY_STORE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                today_pt = cls.get_pt_date_str()
                quota_meta = data.get("quota_tracking", {})
                if quota_meta.get("date") == today_pt:
                    return int(quota_meta.get("used_units", 0))
        except Exception:
            pass
        return 0

    @classmethod
    def consume_units(cls, operation: str, count: int = 1) -> int:
        unit_cost = QUOTA_COSTS.get(operation, 1) * count
        today_pt = cls.get_pt_date_str()
        try:
            import json
            data = {}
            if VARIETY_STORE_PATH.exists():
                with open(VARIETY_STORE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            quota_meta = data.setdefault("quota_tracking", {})
            if quota_meta.get("date") != today_pt:
                quota_meta["date"] = today_pt
                quota_meta["used_units"] = 0
            quota_meta["used_units"] = quota_meta.get("used_units", 0) + unit_cost
            with open(VARIETY_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return quota_meta["used_units"]
        except Exception:
            return unit_cost

    @classmethod
    def can_run_pipeline(cls, required_margin: int = MIN_REMAINING_QUOTA_FOR_RUN) -> bool:
        used = cls.get_estimated_used_units()
        remaining = QUOTA_DAILY_MAX - used
        return remaining >= required_margin

    @classmethod
    def get_status_str(cls) -> str:
        used = cls.get_estimated_used_units()
        remaining = max(0, QUOTA_DAILY_MAX - used)
        return f"Daily API Quota: ~{used}/{QUOTA_DAILY_MAX} units consumed (Est. {remaining} units remaining today)"

