"""
upload_today_now.py - Immediate YouTube Uploader for Today's Pipeline
Uploads all 10 Cartoon Shorts, Kids Long Video, Mythology Reels, and Thriller Long Video
"""
import os
import sys
import time
import json
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("upload_today")

def main():
    from daily_autopilot import get_youtube_service, _upload, _record, produce_mythology_shorts, produce_long_video

    log.info("Checking YouTube API authentication...")
    yt = get_youtube_service()
    if not yt:
        log.error("YouTube service is not yet authenticated! Please complete authentication in your browser first.")
        sys.exit(1)

    log.info("YouTube authenticated successfully! Starting upload of today's videos...")

    state_path = BASE_DIR / "autopilot_state.json"
    state = {}
    if state_path.exists():
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)

    uploaded_shorts = 0
    # 1. Upload Cartoon Shorts
    shorts_data = state.get("shorts", {})
    for num_str, data in shorts_data.items():
        vfile = Path(data.get("file", ""))
        vid = data.get("video_id", "")
        # If it's not a real YouTube ID (i.e. starts with LOCAL_, SIM_, SAVED_LOCAL_ or empty)
        if vfile.exists() and (not vid or vid.startswith(("LOCAL_", "SIM_", "SAVED_LOCAL_"))):
            title = data.get("title", f"Short #{num_str}")
            desc = f"{title}\n\n#shorts #hindi #animation #cartoon"
            tags = ["shorts", "hindi", "animation", "viral", "cartoon", "facts"]
            log.info(f"Uploading Short #{num_str}: {vfile.name} - {title[:40]}...")
            new_id = _upload(yt, vfile, title, desc, tags, dry_run=False, is_short=True)
            if new_id and not new_id.startswith(("LOCAL_", "UPLOAD_ERR_", "SAVED_LOCAL_")):
                data["video_id"] = new_id
                _record(new_id, title, data)
                uploaded_shorts += 1
                log.info(f"  -> Uploaded successfully: https://youtube.com/shorts/{new_id}")
            time.sleep(2)

    # 2. Upload Kids Long Cartoon
    kids_data = state.get("kids_long_cartoon", {})
    kids_file = Path(kids_data.get("file", str(BASE_DIR / "kids_long_cartoon.mp4")))
    kids_id = kids_data.get("video_id", "")
    if kids_file.exists() and (not kids_id or kids_id.startswith(("LOCAL_", "SIM_", "SAVED_LOCAL_"))):
        title = kids_data.get("title", "Kids Hindi Cartoon Animation")
        desc = f"{title}\n\n#hindi #cartoon #kids #animation"
        tags = ["kids", "hindi", "cartoon", "animation", "rhymes", "learning"]
        log.info(f"Uploading Kids Long Cartoon: {kids_file.name}...")
        new_kids_id = _upload(yt, kids_file, title, desc, tags, dry_run=False, is_short=False)
        if new_kids_id and not new_kids_id.startswith(("LOCAL_", "UPLOAD_ERR_", "SAVED_LOCAL_")):
            kids_data["video_id"] = new_kids_id
            _record(new_kids_id, title, kids_data)
            log.info(f"  -> Uploaded Kids Cartoon: https://youtube.com/watch?v={new_kids_id}")

    # Save state after existing videos upload
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    # 3. Produce and Upload Mythology Shorts (5 videos)
    log.info("Starting production and upload of 5 Mythology Reels...")
    try:
        myth_results = produce_mythology_shorts(yt, dry_run=False)
        state["mythology_shorts"] = myth_results
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"Mythology reels production error: {e}")

    # 4. Produce and Upload Thriller Long Video
    log.info("Starting production and upload of Thriller Long Video...")
    try:
        thriller_res = produce_long_video(yt, dry_run=False, diagnosis=state.get("diagnosis", {}))
        state["thriller_long_video"] = thriller_res
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"Thriller long video production error: {e}")

    log.info("ALL TODAY'S VIDEOS UPLOADED AND PROCESSED!")

if __name__ == "__main__":
    main()
