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



# -----------------------------------------------------------------------------
# 8. Centralized YouTube Authentication & Credential Management
# -----------------------------------------------------------------------------
DEFAULT_YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]


def restore_youtube_credentials(force: bool = False) -> bool:
    """
    Restores client_secrets.json and token.json from environment variables.
    In CI (GitHub Actions) or when force=True, environment variables take precedence.
    """
    import base64
    import json

    token_file = BASE_DIR / "token.json"
    client_secrets_file = BASE_DIR / "client_secrets.json"
    is_ci = os.environ.get("GITHUB_ACTIONS") == "true"

    # 1. Restore client_secrets.json
    if not client_secrets_file.exists() or force or is_ci:
        b64_cs = os.environ.get("YOUTUBE_CLIENT_SECRET_BASE64", "").strip()
        raw_cs = os.environ.get("CLIENT_SECRETS_JSON", "").strip()
        if b64_cs:
            try:
                decoded = base64.b64decode(b64_cs)
                client_secrets_file.write_bytes(decoded)
                print("   [Auth] Restored client_secrets.json from YOUTUBE_CLIENT_SECRET_BASE64.")
            except Exception as e:
                print(f"   [Auth Warning] Failed to decode YOUTUBE_CLIENT_SECRET_BASE64: {e}")
        elif raw_cs:
            try:
                client_secrets_file.write_text(raw_cs, encoding="utf-8")
                print("   [Auth] Restored client_secrets.json from CLIENT_SECRETS_JSON.")
            except Exception as e:
                print(f"   [Auth Warning] Failed to write CLIENT_SECRETS_JSON: {e}")

    # 2. Restore token.json
    raw_token = os.environ.get("YOUTUBE_TOKEN_JSON", "").strip()
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

    if raw_token and (not token_file.exists() or force or is_ci):
        try:
            token_file.write_text(raw_token, encoding="utf-8")
            print("   [Auth] Restored token.json from YOUTUBE_TOKEN_JSON.")
        except Exception as e:
            print(f"   [Auth Warning] Failed to write YOUTUBE_TOKEN_JSON: {e}")

    # 3. If YOUTUBE_REFRESH_TOKEN is explicitly given, ensure it updates or creates token.json
    if refresh_token:
        try:
            if token_file.exists():
                tok_data = json.loads(token_file.read_text(encoding="utf-8"))
                if tok_data.get("refresh_token") != refresh_token:
                    tok_data["refresh_token"] = refresh_token
                    token_file.write_text(json.dumps(tok_data, indent=2), encoding="utf-8")
                    print("   [Auth] Synchronized token.json refresh_token with YOUTUBE_REFRESH_TOKEN.")
            elif client_secrets_file.exists():
                cs_data = json.loads(client_secrets_file.read_text(encoding="utf-8"))
                app_info = cs_data.get("installed") or cs_data.get("web") or {}
                tok_struct = {
                    "token": "",
                    "refresh_token": refresh_token,
                    "token_uri": app_info.get("token_uri", "https://oauth2.googleapis.com/token"),
                    "client_id": app_info.get("client_id", ""),
                    "client_secret": app_info.get("client_secret", ""),
                    "scopes": DEFAULT_YOUTUBE_SCOPES
                }
                token_file.write_text(json.dumps(tok_struct, indent=2), encoding="utf-8")
                print("   [Auth] Generated token.json from client_secrets.json + YOUTUBE_REFRESH_TOKEN.")
        except Exception as e:
            print(f"   [Auth Warning] Failed to process YOUTUBE_REFRESH_TOKEN: {e}")

    return token_file.exists()


_LAST_AUTH_ERROR = None

def get_youtube_service(scopes=None, force_restore: bool = False):
    """
    Builds and returns an authenticated YouTube Data API v3 service resource.
    Automatically refreshes expired access tokens and persists updated credentials.
    Raises RuntimeError in CI if authentication fails so CI alerts the developer.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if scopes is None:
        scopes = DEFAULT_YOUTUBE_SCOPES

    restore_youtube_credentials(force=force_restore)
    token_file = BASE_DIR / "token.json"
    if not token_file.exists():
        msg = (
            "YouTube token.json not found on disk or environment.\n"
            "Action required: Run 'python auth_youtube.py' locally or add YOUTUBE_TOKEN_JSON to GitHub Secrets."
        )
        print(f"❌ [Auth Error] {msg}")
        if os.environ.get("GITHUB_ACTIONS") == "true":
            raise RuntimeError(msg)
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
        elif not creds or not creds.valid:
            if creds and creds.refresh_token:
                creds.refresh(Request())
                token_file.write_text(creds.to_json(), encoding="utf-8")

        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        global _LAST_AUTH_ERROR
        err_str = str(e)
        _LAST_AUTH_ERROR = err_str
        print(f"❌ [Auth Error] Failed to authenticate YouTube API client: {err_str}")
        if "invalid_grant" in err_str:
            print(
                "\n" + "=" * 75 + "\n"
                "⚠️ CRITICAL: The YouTube refresh token has EXPIRED or been REVOKED by Google.\n"
                "Why this happens:\n"
                "1. If Google Cloud OAuth Consent Screen is in 'Testing' mode, tokens expire in 7 days.\n"
                "   Fix: Switch to 'In production' (Publish App) in Google Cloud Console.\n"
                "2. The GitHub Action Secret (YOUTUBE_TOKEN_JSON / YOUTUBE_REFRESH_TOKEN) is outdated.\n"
                "   Fix: Run 'python auth_youtube.py' and update GitHub Secrets.\n"
                + "=" * 75 + "\n"
            )
        if os.environ.get("GITHUB_ACTIONS") == "true":
            raise RuntimeError(f"YouTube authentication failed: {err_str}") from e
        return None


def verify_youtube_credentials(force_restore: bool = True):
    """
    Tests YouTube API connection by fetching the authenticated channel's snippet.
    Returns (success: bool, info_or_error: str, channel_id: Optional[str])
    """
    try:
        yt = get_youtube_service(force_restore=force_restore)
        if not yt:
            return False, _LAST_AUTH_ERROR or "Failed to build YouTube service (missing or invalid credentials)", None

        resp = yt.channels().list(mine=True, part="snippet,statistics").execute()
        items = resp.get("items", [])
        if not items:
            return True, "Authenticated, but no channel found for this Google account", None

        ch = items[0]
        title = ch.get("snippet", {}).get("title", "Unknown Channel")
        cid = ch.get("id", "")
        return True, f"Channel: '{title}' (ID: {cid})", cid
    except Exception as e:
        return False, str(e), None
