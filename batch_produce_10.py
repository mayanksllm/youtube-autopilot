"""
batch_produce_10.py - Daily 10-Video Hindi Short Batch Producer
================================================================
Produces 10 viral-category YouTube Shorts in Hindi, cycling across all
10 VIRAL_CATEGORIES, then uploads each to YouTube automatically.

Usage:
    python batch_produce_10.py              # Produce + upload 10 Hindi Shorts
    python batch_produce_10.py --dry-run    # Produce only, no upload
    python batch_produce_10.py --count 3   # Produce only 3 videos

Each video gets a unique output filename (hindi_short_01.mp4 to hindi_short_10.mp4).
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()
HISTORY_FILE = BASE_DIR / "history.json"
BATCH_LOG_FILE = BASE_DIR / "batch_log.json"

try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if os.path.exists(ffmpeg_exe):
        os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
        ffmpeg_dir = str(Path(ffmpeg_exe).parent)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
except Exception:
    pass

# 10 Hindi topics, one per viral category
HINDI_BATCH_TOPICS = [
    ("medical_biology_anomalies",
     "jab tatai zinda aapke gale mein chali jaaye toh kya hota hai sharir ke saath"),
    ("thriller_dark_psychology",
     "Cotard Delusion woh beemari jo insaan ko khud ko murda samajhne par majboor kar deti hai"),
    ("how_it_actually_works",
     "jahaaz ka anchor samudra ki tali ko kyun nahi choota asli raaz"),
    ("unexplained_real_mysteries",
     "1518 ki Dancing Plague log marte dam tak naachte rahe aur koi nahi ruka"),
    ("reality_simulation_paradoxes",
     "Quantum Zeno Effect jab tak aap dekh rahe ho kand mar nahi sakta"),
    ("extreme_physics_space_terrors",
     "Vacuum Decay brahmand prakash ki gati se mit sakta hai aur hame pata bhi nahi chalega"),
    ("survival_emergency_anatomy",
     "lift ki taar toot jaaye toh zinda rehne ka ek chaunkane wala tarika"),
    ("bizarre_nature_monsters",
     "Cordyceps Fungus woh zinda fafund jo cheeti ke dimag par kabza kar leti hai"),
    ("perception_sensory_traps",
     "McGurk Effect aapki aankhen aapke kaano ko jhooth sunaati hain aur aap kuch nahi kar sakte"),
    ("high_stakes_heists_scandals",
     "ek 28 saal ke ladke ne 233 saal purane bank ko 24 ghante mein barbad kar diya"),
]


def load_history():
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_video_id": None, "last_title": None, "date": None, "videos": []}


def save_history(data):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Warning] history.json write failed: {e}")


def record_upload(video_id, title, metadata=None):
    hist = load_history()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hist["last_video_id"] = video_id
    hist["last_title"] = title
    hist["date"] = now_str
    hist.setdefault("videos", []).append({
        "id": video_id,
        "title": title,
        "date": now_str,
        "topic": metadata.get("topic_used") if metadata else None,
        "category": metadata.get("category") if metadata else None,
        "language": "hi",
        "tags": metadata.get("tags", []) if metadata else [],
    })
    save_history(hist)


def get_youtube_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    TOKEN_FILE = BASE_DIR / "token.json"
    CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/youtube.force-ssl",
    ]
    if not TOKEN_FILE.exists() and not CLIENT_SECRETS_FILE.exists():
        return None
    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception:
            pass
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(TOKEN_FILE, "w", encoding="utf-8") as tf:
                    tf.write(creds.to_json())
            except Exception:
                creds = None
        if not creds:
            if not CLIENT_SECRETS_FILE.exists():
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_FILE), SCOPES)
                creds = flow.run_local_server(port=0)
                with open(TOKEN_FILE, "w", encoding="utf-8") as tf:
                    tf.write(creds.to_json())
            except Exception:
                return None
    try:
        return build("youtube", "v3", credentials=creds)
    except Exception:
        return None


def upload_to_youtube(yt, video_path, title, description, tags):
    from googleapiclient.http import MediaFileUpload
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": "27",
            "defaultLanguage": "hi",
            "defaultAudioLanguage": "hi",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"   Upload: {int(status.progress() * 100)}%", end="\r")
    print()
    return resp.get("id", "unknown")


def run_batch(count=10, dry_run=False):
    from video_engine import produce_cinematic_short

    count = min(count, 10)
    yt = None if dry_run else get_youtube_service()

    print("\n" + "=" * 70)
    print(f"  HINDI BATCH PRODUCER  |  {count} videos  |  {'DRY RUN' if dry_run else 'UPLOAD MODE'}")
    print("=" * 70)
    if not dry_run:
        status_msg = "YouTube API authenticated - videos will be uploaded." if yt else "YouTube API not available - saving locally."
        print(status_msg)

    batch_results = []
    batch_start = time.time()

    for idx in range(count):
        video_num = idx + 1
        cat_key, hindi_topic = HINDI_BATCH_TOPICS[idx % len(HINDI_BATCH_TOPICS)]
        out_path = BASE_DIR / f"hindi_short_{video_num:02d}.mp4"

        print(f"\n{'='*70}")
        print(f"  VIDEO {video_num}/{count} | Category: {cat_key}")
        print(f"  Topic: {hindi_topic[:70]}")
        print(f"{'='*70}")

        prod_result = None
        try:
            prod_result = produce_cinematic_short(
                topic_directive=hindi_topic,
                category=cat_key,
                language="hi",
                output_path=out_path,
            )
        except Exception as e:
            print(f"FAILED video {video_num}: {e}")
            batch_results.append({
                "video_num": video_num, "category": cat_key,
                "topic": hindi_topic, "status": "FAILED", "error": str(e),
            })
            continue

        title = prod_result.get("title", f"Hindi Short {video_num} #Shorts")
        description = prod_result.get(
            "description",
            f"Rozana nayi rochak jaankari #shorts #viral #hindi #thrillerfacts\n\n{hindi_topic}"
        )
        tags = list(set(prod_result.get("tags", []) + ["hindi", "shorts", "viral", "hindifacts", "thrillerhindi"]))

        video_id = None
        if not dry_run and yt:
            try:
                video_id = upload_to_youtube(yt, out_path, title, description, tags)
                record_upload(video_id, title, prod_result)
                print(f"Uploaded: https://youtube.com/shorts/{video_id}")
            except Exception as ue:
                print(f"Upload error for video {video_num}: {ue}")
                video_id = f"LOCAL_{int(time.time())}"
                record_upload(video_id, title, prod_result)
        else:
            sim_id = f"LOCAL_{video_num:02d}_{int(time.time())}"
            record_upload(sim_id, title, prod_result)
            print(f"Saved locally: {out_path}")

        batch_results.append({
            "video_num": video_num, "category": cat_key, "topic": hindi_topic,
            "title": title, "file": str(out_path), "video_id": video_id,
            "duration_s": prod_result.get("total_duration"),
            "render_time_s": prod_result.get("render_time"),
            "status": "OK",
        })

        if video_num < count:
            print(f"Cooling down 5s before next render...")
            time.sleep(5)

    total_elapsed = time.time() - batch_start
    ok_count = sum(1 for r in batch_results if r.get("status") == "OK")
    print("\n" + "=" * 70)
    print(f"  BATCH COMPLETE: {ok_count}/{count} videos produced")
    print(f"  Total time: {total_elapsed/60:.1f} minutes")
    print("=" * 70)
    for r in batch_results:
        icon = "OK" if r.get("status") == "OK" else "FAIL"
        vid_url = (
            f"https://youtube.com/shorts/{r['video_id']}"
            if r.get("video_id") and not str(r.get("video_id", "")).startswith("LOCAL")
            else r.get("file", "saved locally")
        )
        print(f"  [{icon}] [{r['video_num']:02d}] {r.get('title', r['topic'])[:60]}")
        print(f"        -> {vid_url}")

    log_entry = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count_requested": count, "count_ok": ok_count,
        "total_minutes": round(total_elapsed / 60, 1),
        "dry_run": dry_run, "results": batch_results,
    }
    existing_log = []
    if BATCH_LOG_FILE.exists():
        try:
            with open(BATCH_LOG_FILE, "r", encoding="utf-8") as f:
                existing_log = json.load(f)
        except Exception:
            pass
    existing_log.append(log_entry)
    with open(BATCH_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(existing_log, f, indent=2, ensure_ascii=False)
    print(f"\nBatch log saved: {BATCH_LOG_FILE}")
    return batch_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hindi YouTube Shorts Batch Producer")
    parser.add_argument("--dry-run", action="store_true", help="Produce only, no upload")
    parser.add_argument("--count", type=int, default=10, help="Number of videos (1-10)")
    args = parser.parse_args()
    results = run_batch(count=args.count, dry_run=args.dry_run)
    sys.exit(0 if all(r.get("status") == "OK" for r in results) else 1)
