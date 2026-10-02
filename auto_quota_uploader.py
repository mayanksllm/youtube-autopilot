"""
auto_quota_uploader.py - Instant YouTube Quota Release Uploader
==============================================================
Monitors pending local reels and uploads them the exact minute
YouTube's upload limit / quota resets. Eliminates all daily delays.

Modes:
  python auto_quota_uploader.py --once    (Check and upload right now)
  python auto_quota_uploader.py --daemon  (Run continuously, uploading as soon as quota frees up)
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "autopilot_state.json"
HISTORY_FILE = BASE_DIR / "history.json"
REPORT_FILE = BASE_DIR / "daily_report.json"

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_DIR / "quota_uploader.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("quota_uploader")

def get_seconds_until_pt_midnight() -> int:
    """
    YouTube API daily quota (10,000 units) strictly resets at Midnight Pacific Time (PT).
    Returns seconds until the next 00:00 PT.
    """
    # Pacific Time is UTC-7 (PDT) during Daylight Saving (mid-March to early Nov)
    # and UTC-8 (PST) during winter.
    # In October, PDT (UTC-7) is active.
    now_utc = datetime.now(timezone.utc)
    # Simple check for US daylight saving (approx March 2nd Sunday to Nov 1st Sunday)
    is_dst = 3 <= now_utc.month <= 10
    pt_offset = timedelta(hours=-7 if is_dst else -8)
    now_pt = now_utc.astimezone(timezone(pt_offset))

    # Next midnight PT
    tomorrow_pt = (now_pt + timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
    secs = int((tomorrow_pt - now_pt).total_seconds())
    return max(60, secs)

def get_pending_videos():
    if not STATE_FILE.exists():
        return []
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        log.error(f"Failed to read {STATE_FILE}: {e}")
        return []

    pending = []
    # 1. Shorts
    shorts = state.get("shorts", {})
    for k, v in shorts.items():
        if not isinstance(v, dict):
            continue
        vid = v.get("video_id", "")
        fpath = Path(v.get("file", ""))
        if (not vid or vid.startswith(("SAVED_LOCAL", "LOCAL", "UPLOAD_ERR"))) and fpath.exists():
            pending.append({
                "type": "short",
                "key": k,
                "title": v.get("title", f"Short #{k}"),
                "file": fpath,
                "data": v
            })

    # 2. Mythology shorts
    myth = state.get("mythology_shorts", {})
    for k, v in myth.items():
        if not isinstance(v, dict):
            continue
        vid = v.get("video_id", "")
        fpath = Path(v.get("file", ""))
        if (not vid or vid.startswith(("SAVED_LOCAL", "LOCAL", "UPLOAD_ERR"))) and fpath.exists():
            pending.append({
                "type": "mythology",
                "key": k,
                "title": v.get("title", "Mythology Reel"),
                "file": fpath,
                "data": v
            })

    # 3. Kids Long Cartoon
    kids = state.get("kids_long_cartoon", {})
    if isinstance(kids, dict):
        kids_vid = kids.get("video_id", "")
        kids_file = Path(kids.get("file", str(BASE_DIR / "kids_long_cartoon.mp4")))
        if (not kids_vid or kids_vid.startswith(("SAVED_LOCAL", "LOCAL", "UPLOAD_ERR"))) and kids_file.exists():
            pending.append({
                "type": "long_kids",
                "key": "kids_long_cartoon",
                "title": kids.get("title", "Kids Cartoon"),
                "file": kids_file,
                "data": kids
            })

    return pending

def record_upload_success(item, vid_id):
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        k = item["key"]
        t = item["type"]
        if t == "short":
            state.setdefault("shorts", {})[k]["video_id"] = vid_id
            state["shorts"][k]["status"] = "OK"
        elif t == "mythology":
            state.setdefault("mythology_shorts", {})[k]["video_id"] = vid_id
            state["mythology_shorts"][k]["status"] = "OK"
        elif t == "long_kids":
            state.setdefault("kids_long_cartoon", {})["video_id"] = vid_id
            state["kids_long_cartoon"]["status"] = "OK"

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        # Update history.json
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                hist = json.load(f)
            hist.setdefault("uploaded_videos", []).append({
                "id": vid_id,
                "title": item["title"],
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": t,
                "file": str(item["file"])
            })
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(hist, f, indent=2, ensure_ascii=False)

        log.info(f"Updated state and history for {item['title'][:40]} -> {vid_id}")
    except Exception as e:
        log.error(f"Error saving state after upload: {e}")

def process_pending_uploads(max_to_upload=5) -> str:
    """
    Attempts to upload pending videos.
    Returns:
      "ALL_DONE" - No pending videos left
      "QUOTA_HIT" - YouTube upload limit reached
      "SUCCESS" - Some uploaded successfully
      "NO_AUTH" - YouTube service unavailable
    """
    from daily_autopilot import get_youtube_service, _upload

    pending = get_pending_videos()
    if not pending:
        log.info("No pending videos found in queue. Everything is up to date!")
        return "ALL_DONE"

    log.info(f"Found {len(pending)} pending video(s) waiting in queue.")

    yt = get_youtube_service()
    if not yt:
        log.error("YouTube service authentication failed.")
        return "NO_AUTH"

    uploaded_count = 0

    for item in pending:
        if uploaded_count >= max_to_upload:
            log.info(f"Reached batch limit of {max_to_upload} uploads for this cycle.")
            break

        fpath = item["file"]
        title = item["title"]
        is_short = (item["type"] != "long_kids")
        desc = f"{title}\n\n#shorts #hindi #animation #viral"
        tags = ["shorts", "hindi", "animation", "viral", "facts"]

        log.info(f"Attempting upload: {fpath.name} | {title[:40]}...")
        vid_id = _upload(yt, fpath, title, desc, tags, dry_run=False, is_short=is_short)

        if vid_id and not vid_id.startswith(("SAVED_LOCAL", "LOCAL", "UPLOAD_ERR")):
            uploaded_count += 1
            log.info(f" SUCCESS! Video live on YouTube: https://youtube.com/{'shorts/' if is_short else 'watch?v='}{vid_id}")
            record_upload_success(item, vid_id)
            time.sleep(3)
        elif "SAVED_LOCAL" in vid_id:
            log.warning(" YouTube daily upload limit is currently ACTIVE on your account.")
            return "QUOTA_HIT"
        else:
            log.error(f" Upload failed with code {vid_id}. Stopping batch.")
            return "ERROR"

    return "SUCCESS"

def run_loop(daemon_mode=False):
    log.info("Starting Auto Quota Release Uploader...")
    while True:
        status = process_pending_uploads(max_to_upload=5)

        if not daemon_mode:
            log.info(f"Single pass completed with status: {status}")
            break

        if status == "QUOTA_HIT":
            secs = get_seconds_until_pt_midnight()
            hours = secs / 3600.0
            log.info(f"Quota is currently locked. YouTube quota resets in {hours:.2f} hours (at Midnight PT / 12:30 PM IST).")
            # Sleep in intervals or check every 30 minutes in case of rolling window reset
            sleep_time = min(1800, secs)
            log.info(f"Sleeping for {sleep_time // 60} minutes before next check...")
            time.sleep(sleep_time)
        elif status == "ALL_DONE":
            log.info("All reels are posted! Sleeping for 1 hour before next queue check...")
            time.sleep(3600)
        else:
            log.info("Batch cycle finished. Sleeping 30 minutes before next batch...")
            time.sleep(1800)

if __name__ == "__main__":
    is_daemon = "--daemon" in sys.argv
    run_loop(daemon_mode=is_daemon)
