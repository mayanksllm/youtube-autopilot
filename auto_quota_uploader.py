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
from typing import Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path

if sys.platform == "win32":
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if sys.stderr is not None:
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

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


def resolve_video_file(raw_path_str: str) -> Optional[Path]:
    """Resolves video path across local directories and handles cross-machine path discrepancies."""
    if not raw_path_str:
        return None
    p = Path(raw_path_str)
    try:
        if p.exists() and p.is_file() and p.stat().st_size > 1000:
            return p
    except Exception:
        pass

    try:
        p_base = BASE_DIR / p.name
        if p_base.exists() and p_base.is_file() and p_base.stat().st_size > 1000:
            return p_base
    except Exception:
        pass

    try:
        p_out = BASE_DIR / "assets" / "output" / p.name
        if p_out.exists() and p_out.is_file() and p_out.stat().st_size > 1000:
            return p_out
    except Exception:
        pass

    return None

def get_seconds_until_pt_midnight() -> int:
    """
    YouTube API daily quota (10,000 units) strictly resets at Midnight Pacific Time (PT).
    Returns seconds until the next 00:00 PT.
    """
    now_utc = datetime.now(timezone.utc)
    is_dst = 3 <= now_utc.month <= 10
    pt_offset = timedelta(hours=-7 if is_dst else -8)
    now_pt = now_utc.astimezone(timezone(pt_offset))

    tomorrow_pt = (now_pt + timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
    secs = int((tomorrow_pt - now_pt).total_seconds())
    return max(60, secs)

def get_pending_videos():
    pending = []

    # 1. Check autopilot_state.json
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

            # Shorts
            shorts = state.get("shorts", {})
            for k, v in shorts.items():
                if not isinstance(v, dict):
                    continue
                vid = v.get("video_id", "")
                fpath = resolve_video_file(v.get("file", ""))
                if (not vid or vid.startswith(("SAVED_LOCAL", "LOCAL", "UPLOAD_ERR"))) and fpath:
                    pending.append({
                        "type": "short",
                        "key": k,
                        "title": v.get("title", f"Short #{k}"),
                        "file": fpath,
                        "data": v
                    })

            # Mythology shorts
            myth = state.get("mythology_shorts", {})
            for k, v in myth.items():
                if not isinstance(v, dict):
                    continue
                vid = v.get("video_id", "")
                fpath = resolve_video_file(v.get("file", ""))
                if (not vid or vid.startswith(("SAVED_LOCAL", "LOCAL", "UPLOAD_ERR"))) and fpath:
                    pending.append({
                        "type": "mythology",
                        "key": k,
                        "title": v.get("title", "Mythology Reel"),
                        "file": fpath,
                        "data": v
                    })

            # Kids Long Cartoon
            kids = state.get("kids_long_cartoon", {})
            if isinstance(kids, dict):
                kids_vid = kids.get("video_id", "")
                kids_file = resolve_video_file(kids.get("file", str(BASE_DIR / "kids_long_cartoon.mp4")))
                if (not kids_vid or kids_vid.startswith(("SAVED_LOCAL", "LOCAL", "UPLOAD_ERR"))) and kids_file:
                    pending.append({
                        "type": "long_kids",
                        "key": "kids_long_cartoon",
                        "title": kids.get("title", "Kids Cartoon"),
                        "file": kids_file,
                        "data": kids
                    })
        except Exception as e:
            log.error(f"Failed to read {STATE_FILE}: {e}")

    # 2. Check assets/output for un-uploaded freshly rendered reels
    out_dir = BASE_DIR / "assets" / "output"
    if out_dir.exists():
        for vid_file in sorted(out_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
            if vid_file.stat().st_size < 100000:
                continue
            # Check if this file is already in pending
            if any(p["file"].name == vid_file.name for p in pending):
                continue
            # Check if recorded in history.json
            already_uploaded = False
            if HISTORY_FILE.exists():
                try:
                    with open(HISTORY_FILE, "r", encoding="utf-8") as hf:
                        hdata = json.load(hf)
                        for item in hdata.get("uploaded_videos", []):
                            if vid_file.name in str(item.get("file", "")) or vid_file.name in str(item.get("id", "")):
                                already_uploaded = True
                                break
                except Exception:
                    pass
            if not already_uploaded:
                pending.append({
                    "type": "fresh_reel",
                    "key": vid_file.stem,
                    "title": f"Viral Short {vid_file.stem.split('_')[-1]} #Shorts",
                    "file": vid_file,
                    "data": {"file": str(vid_file)}
                })

    return pending

def record_upload_success(item, vid_id):
    try:
        state = {}
        if STATE_FILE.exists():
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

        k = item["key"]
        t = item["type"]
        if t == "short":
            state.setdefault("shorts", {}).setdefault(k, {})["video_id"] = vid_id
            state["shorts"][k]["status"] = "OK"
            state["shorts"][k]["file"] = str(item["file"])
        elif t == "mythology":
            state.setdefault("mythology_shorts", {}).setdefault(k, {})["video_id"] = vid_id
            state["mythology_shorts"][k]["status"] = "OK"
            state["mythology_shorts"][k]["file"] = str(item["file"])
        elif t == "long_kids":
            state.setdefault("kids_long_cartoon", {})["video_id"] = vid_id
            state["kids_long_cartoon"]["status"] = "OK"
            state["kids_long_cartoon"]["file"] = str(item["file"])
        elif t == "fresh_reel":
            state.setdefault("fresh_reels", {}).setdefault(k, {})["video_id"] = vid_id
            state["fresh_reels"][k]["status"] = "OK"
            state["fresh_reels"][k]["file"] = str(item["file"])

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        # Update history.json
        hist = {}
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

def trigger_daily_automation():
    """
    Executes the full automated pipeline to generate, score, render,
    and publish today's fresh viral trend video as soon as the quota allows.
    """
    log.info("\n" + "=" * 70)
    log.info("🚀 TRIGGERING FRESH AUTONOMOUS VIRAL REELS GENERATION & UPLOAD")
    log.info("=" * 70)
    try:
        from autonomous_viral_reels_engine import run_autonomous_viral_reels_engine
        result_vid = run_autonomous_viral_reels_engine(dry_run=False)
        if result_vid:
            log.info(f"🎉 [Pipeline Success] New Daily Viral Reel Live: https://youtube.com/shorts/{result_vid}")
        else:
            log.warning("⚠️ Daily pipeline finished with local render or deferred upload.")
    except Exception as e:
        log.error(f"❌ Automation engine error: {e}", exc_info=True)

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
    log.info("Starting Auto Quota Release Uploader & Automation Trigger...")
    while True:
        status = process_pending_uploads(max_to_upload=5)

        if status == "QUOTA_HIT":
            secs = get_seconds_until_pt_midnight()
            hours = secs / 3600.0
            log.info(f"⏳ YouTube upload limit / quota is currently ACTIVE.")
            log.info(f"   Quota strictly resets at Midnight PT / 12:30 PM IST (in ~{hours:.2f} hours).")
            if not daemon_mode:
                log.info("Single check complete. Run with --daemon to auto-trigger at quota release.")
                break
            sleep_time = min(1800, secs)
            log.info(f"   Sleeping for {sleep_time // 60} minutes before testing if limit lifted...")
            time.sleep(sleep_time)

        elif status in ("SUCCESS", "ALL_DONE"):
            log.info(f"✅ Quota is AVAILABLE! (Status: {status})")
            # Trigger fresh daily generation and live publishing
            trigger_daily_automation()

            from autopilot_config import QuotaManager, MIN_REMAINING_QUOTA_FOR_RUN
            if not QuotaManager.can_run_pipeline(MIN_REMAINING_QUOTA_FOR_RUN):
                secs = get_seconds_until_pt_midnight()
                hours = secs / 3600.0
                log.info(f"📊 [Quota Budget] Safe daily units consumed ({QuotaManager.get_status_str()}).")
                log.info(f"⏳ Next batch will trigger automatically at Midnight PT / 12:30 PM IST (in ~{hours:.2f} hours).")
                if not daemon_mode:
                    log.info("Single pass completed successfully.")
                    break
                sleep_time = min(1800, secs)
                log.info(f"   Sleeping for {sleep_time // 60} minutes before re-checking quota reset...")
                time.sleep(sleep_time)
                continue

            if not daemon_mode:
                log.info("Single pass completed successfully.")
                break

            log.info("Automation cycle finished. Monitoring queue; next check in 2 hours...")
            time.sleep(7200)

        else:
            log.warning(f"Pass ended with status: {status}")
            if not daemon_mode:
                break
            time.sleep(1800)

if __name__ == "__main__":
    is_daemon = "--daemon" in sys.argv
    run_loop(daemon_mode=is_daemon)
