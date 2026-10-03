"""
daily_autopilot.py - Full YouTube Channel Daily Autopilot
==========================================================
Runs every day via Windows Task Scheduler (no window needed).

Daily Workflow:
  STEP 1: Audit yesterday analytics on all recent Shorts
           -> Query YouTube API for views, likes, CTR, retention
           -> Call Gemini to diagnose WHY growth is slow
           -> Generate a personalized growth action plan

  STEP 2: Produce 10 Hindi Shorts (one per viral category)
           -> Full thriller engine: Gemini script + edge-tts Hindi voice
           -> Pexels character footage + vignette + Hormozi captions

  STEP 3: Produce 1 Long Hindi Video (5-8 minute YouTube video)
           -> 10-scene deep-dive on the day's highest-CPM category
           -> Narrated, educational, thriller style

  STEP 4: Upload everything to YouTube with Hindi metadata

  STEP 5: Log results to daily_report.json + autopilot_log.txt

Usage (manual):
    python daily_autopilot.py
    python daily_autopilot.py --dry-run      (no upload)

Scheduled (automatic via Windows Task Scheduler):
    schtasks /Create ... (registered via setup_scheduler.bat)
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
from pathlib import Path
from datetime import datetime, timedelta

# ─── Windows pythonw.exe Stream Fix ──────────────────────────────────────────
if sys.platform == "win32":
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    else:
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ─── Setup Logging to File (so it works with no window open) ─────────────────
BASE_DIR = Path(__file__).parent.resolve()
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_file = LOG_DIR / f"autopilot_{datetime.now().strftime('%Y%m%d')}.log"
log_handlers = [logging.FileHandler(str(log_file), encoding="utf-8")]
try:
    log_handlers.append(logging.StreamHandler(sys.stdout))
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=log_handlers,
)
log = logging.getLogger("autopilot")

# ─── Bootstrap ───────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if os.path.exists(ffmpeg_exe):
        os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
        d = str(Path(ffmpeg_exe).parent)
        if d not in os.environ.get("PATH", ""):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
except Exception:
    pass

HISTORY_FILE     = BASE_DIR / "history.json"
REPORT_FILE      = BASE_DIR / "daily_report.json"
BATCH_LOG_FILE   = BASE_DIR / "batch_log.json"
STATE_FILE       = BASE_DIR / "autopilot_state.json"
LOCK_FILE        = BASE_DIR / "autopilot.lock"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
from google import genai
from google.genai import types
ai_client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(
        timeout=20000,
        retry_options=types.HttpRetryOptions(attempts=1)
    )
)
GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]

# ─── 10 Hindi batch topics (cycle through daily) ─────────────────────────────
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
     "McGurk Effect aapki aankhen aapke kaano ko jhooth sunaati hain"),
    ("high_stakes_heists_scandals",
     "ek 28 saal ke ladke ne 233 saal purane bank ko 24 ghante mein barbad kar diya"),
]

# Long-video topics (rotate daily by weekday)
LONG_VIDEO_TOPICS = [
    ("thriller_dark_psychology",
     "Dark Psychology ki 7 techniques jo insaan ko control karne mein use hoti hain - poori guide"),
    ("unexplained_real_mysteries",
     "India ki 5 sabse badi classified mysteries jo aaj bhi explain nahi hui"),
    ("extreme_physics_space_terrors",
     "Space ki 7 sabse dangerous cheezein jo insaan ko ek second mein khatam kar sakti hain"),
    ("medical_biology_anomalies",
     "Human body ki 10 aisi hadse jo doctors bhi nahi samjha sake - real cases"),
    ("how_it_actually_works",
     "Duniya ki 7 most complex machines kaise kaam karti hain - insiders guide"),
    ("bizarre_nature_monsters",
     "Nature ke 7 most terrifying weapons jinke saamne insaan kuch nahi"),
    ("high_stakes_heists_scandals",
     "History ke 5 sabse bade financial frauds aur unke mastermind criminals"),
]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: YouTube Analytics Audit + Gemini Growth Diagnosis
# ─────────────────────────────────────────────────────────────────────────────

# Mythological short topics (rotate daily)
MYTHOLOGY_TOPICS = [
    ("mahabharat",
     "Mahabharat ka woh ek sach jo aaj bhi log nahi jaante - Karna ka asli dard"),
    ("ramayan",
     "Ramayan ki woh kahani jo kisi ne nahi sunai - Sita mata ka sabse bada imtihaan"),
    ("shiv",
     "Shiv Shankar ki shakti ka raaz - Neelkanth kyun bane aur uska asar aaj bhi kyun hai"),
    ("hanuman",
     "Hanuman ji ki woh shakti jo Ram ne khud chhupai thi - anjaan sach"),
    ("krishna",
     "Shri Krishna ki woh baat jo Arjun ko Kurukshetra mein sun ke aankhein bhar aayi"),
    ("mahabharat",
     "Draupadi ka cheerharan - us din kya hua tha jo itihas badal gaya"),
    ("ramayan",
     "Raavan itna gyaani tha phir bhi kyun hara - asli wajah koi nahi batata"),
    ("krishna",
     "Geeta ka woh shlok jise padh ke duniya ke bade scientists hairan ho gaye"),
    ("shiv",
     "Mahakaal ka Tandav - uske peeche ka vigyan jo aaj ke scientists maan rahe hain"),
    ("hanuman",
     "Sunderkand padhne se kya sach mein hoti hai shakti - vigyan kya kehta hai"),
]

MYTHOLOGY_VISUAL_DNA = (
    "shot on 35mm anamorphic lens, Arri Alexa 65 cinematography, shallow depth of field (f/1.8 aperture), "
    "divine Indian mythology cinematic, glowing divine aura, volumetric lighting, dramatic celestial rim light, "
    "golden hour atmospheric haze, photorealistic 8k, tactile details, majestic ancient India temple architecture, "
    "masterpiece award-winning color grading, no CGI cartoon sheen, vertical 9:16"
)


def get_youtube_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    TOKEN_FILE = BASE_DIR / "token.json"
    CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"

    # Support cloud environment execution (GitHub Actions / Cloud VPS)
    if not TOKEN_FILE.exists() and os.environ.get("YOUTUBE_TOKEN_JSON"):
        try:
            TOKEN_FILE.write_text(os.environ["YOUTUBE_TOKEN_JSON"].strip(), encoding="utf-8")
            log.info("Restored token.json from YOUTUBE_TOKEN_JSON environment variable.")
        except Exception as ex:
            log.warning(f"Failed to restore token.json from env: {ex}")

    if not CLIENT_SECRETS_FILE.exists() and os.environ.get("CLIENT_SECRETS_JSON"):
        try:
            CLIENT_SECRETS_FILE.write_text(os.environ["CLIENT_SECRETS_JSON"].strip(), encoding="utf-8")
            log.info("Restored client_secrets.json from CLIENT_SECRETS_JSON environment variable.")
        except Exception as ex:
            log.warning(f"Failed to restore client_secrets.json from env: {ex}")

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/youtube.force-ssl",
    ]
    if not TOKEN_FILE.exists():
        return None
    creds = None
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    except Exception:
        pass
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                with open(TOKEN_FILE, "w", encoding="utf-8") as tf:
                    tf.write(creds.to_json())
            except Exception as ex:
                log.warning(f"Failed to refresh YouTube token: {ex}")
                return None
    try:
        return build("youtube", "v3", credentials=creds)
    except Exception:
        return None


def audit_yesterday_analytics(yt) -> dict:
    """
    Query YouTube API for all recent Shorts metrics.
    Returns a dict with per-video stats and overall channel health.
    """
    log.info("=== STEP 1: Auditing Yesterday's YouTube Analytics ===")
    result = {
        "date_checked": datetime.now().strftime("%Y-%m-%d"),
        "videos_audited": [],
        "summary": {},
        "growth_issues": [],
    }

    if not yt:
        log.warning("No YouTube API - using history.json for audit")
        history = json.loads(HISTORY_FILE.read_text(encoding="utf-8")) if HISTORY_FILE.exists() else {}
        videos = history.get("videos", [])[-10:]
        result["videos_audited"] = [
            {"id": v.get("id"), "title": v.get("title"), "date": v.get("date"),
             "views": "N/A (API offline)", "likes": "N/A", "note": "Simulated"}
            for v in videos
        ]
        result["summary"]["mode"] = "offline"
        return result

    # Get recent uploads
    history = {}
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    recent_ids = [v["id"] for v in history.get("videos", [])[-20:]
                  if v.get("id") and not str(v["id"]).startswith(("SIM_", "LOCAL_"))]

    if not recent_ids:
        log.info("No previously uploaded videos found in history.json")
        result["summary"]["mode"] = "no_uploads_yet"
        return result

    total_views = 0
    total_likes = 0
    low_view_count = 0

    for vid_id in recent_ids[-10:]:
        try:
            res = yt.videos().list(
                part="statistics,snippet,contentDetails",
                id=vid_id
            ).execute()
            items = res.get("items", [])
            if not items:
                continue
            item = items[0]
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            views = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))
            comments = int(stats.get("commentCount", 0))
            title = snippet.get("title", "")
            pub_date = snippet.get("publishedAt", "")

            total_views += views
            total_likes += likes
            if views < 500:
                low_view_count += 1

            result["videos_audited"].append({
                "id": vid_id,
                "url": f"https://youtube.com/shorts/{vid_id}",
                "title": title,
                "published": pub_date,
                "views": views,
                "likes": likes,
                "comments": comments,
                "like_rate": f"{(likes/max(views,1)*100):.1f}%",
            })
            log.info(f"  [{vid_id}] '{title[:50]}' -> {views} views, {likes} likes")
        except Exception as e:
            log.warning(f"  Could not fetch stats for {vid_id}: {e}")

    result["summary"] = {
        "videos_checked": len(result["videos_audited"]),
        "total_views": total_views,
        "total_likes": total_likes,
        "avg_views_per_short": total_views // max(len(result["videos_audited"]), 1),
        "low_performing_count": low_view_count,
        "mode": "live_api",
    }
    log.info(f"Audit complete: {result['summary']}")
    return result


def gemini_diagnose_growth(audit_data: dict) -> dict:
    """
    Ask Gemini to analyze the audit data and produce a concrete growth action plan.
    """
    log.info("=== Gemini Growth Diagnosis ===")

    audit_json = json.dumps(audit_data, indent=2, ensure_ascii=False)
    prompt = f"""
You are a world-class YouTube Shorts growth strategist specializing in Hindi viral content.
Analyze the following YouTube Shorts performance audit for a Hindi channel targeting thriller,
mystery, science, and dark psychology content.

AUDIT DATA:
{audit_json}

Your task:
1. Identify the TOP 3 specific reasons why this channel is NOT growing fast enough.
2. For each reason, give ONE concrete fix the creator should implement TODAY in their next 10 Shorts.
3. Identify which of these categories is currently getting highest engagement and recommend doubling down.
   Categories: medical_biology_anomalies, thriller_dark_psychology, how_it_actually_works,
   unexplained_real_mysteries, reality_simulation_paradoxes, extreme_physics_space_terrors,
   survival_emergency_anatomy, bizarre_nature_monsters, perception_sensory_traps, high_stakes_heists_scandals
4. Give the TOP 5 Hindi hook formulas that are currently viral on YouTube Shorts India.

OUTPUT ONLY RAW JSON:
{{
  "growth_issues": [
    {{"rank": 1, "problem": "...", "fix": "...", "impact": "HIGH/MEDIUM"}},
    {{"rank": 2, "problem": "...", "fix": "...", "impact": "HIGH/MEDIUM"}},
    {{"rank": 3, "problem": "...", "fix": "...", "impact": "HIGH/MEDIUM"}}
  ],
  "best_performing_category": "category_key_from_list",
  "double_down_reason": "Why this category should get more content...",
  "viral_hindi_hook_formulas": [
    "Hook formula 1 (e.g., 'Kya aap jaante hain ki...')",
    "Hook formula 2",
    "Hook formula 3",
    "Hook formula 4",
    "Hook formula 5"
  ],
  "today_strategy": "One paragraph summary of today's content strategy"
}}
"""
    diagnosis = None
    for model in GEMINI_MODELS:
        try:
            resp = ai_client.models.generate_content(model=model, contents=prompt)
            raw = resp.text.strip().replace("```json", "").replace("```", "").strip()
            s = raw.find("{")
            e = raw.rfind("}")
            if s != -1 and e != -1:
                diagnosis = json.loads(raw[s:e+1])
            if diagnosis:
                log.info(f"Growth diagnosis from {model}: {len(diagnosis.get('growth_issues',[]))} issues found")
                break
        except Exception as ex:
            log.warning(f"Gemini model {model} failed diagnosis: {ex}")
            time.sleep(1)

    if not diagnosis:
        diagnosis = {
            "growth_issues": [{"rank": 1, "problem": "Insufficient posting frequency", "fix": "Post 10 Shorts daily", "impact": "HIGH"}],
            "best_performing_category": "thriller_dark_psychology",
            "viral_hindi_hook_formulas": ["Kya aap jaante hain ki...", "Ye sach sunke aap shock ho jaoge...", "Aaj tak kisi ne nahi bataya..."],
            "today_strategy": "Focus on thriller and dark psychology with strong Hindi hooks."
        }
    return diagnosis


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 & 3: Video Production
# ─────────────────────────────────────────────────────────────────────────────

def produce_10_hindi_shorts(yt, dry_run: bool, diagnosis: dict, reel_dna: dict = None) -> list:
    """Produce 10 Hindi Shorts, improved using analytics diagnosis."""
    from video_engine import produce_cinematic_short

    # --- Analytics-driven improvement ---
    best_cat  = diagnosis.get("best_performing_category", "thriller_dark_psychology")
    growth_issues = diagnosis.get("growth_issues", [])
    hook_formulas = diagnosis.get("viral_hindi_hook_formulas", [])
    today_strategy = diagnosis.get("today_strategy", "")
    visual_dna = (reel_dna or {}).get("pollinations_visual_dna", "")
    hook_formula = (reel_dna or {}).get("hook_formula", "")

    # Build the improvement note injected into every topic
    improvement_note = ""
    if growth_issues:
        fixes = "; ".join(g.get("fix", "") for g in growth_issues[:2])
        improvement_note += f" IMPROVEMENT FIXES: {fixes}."
    if hook_formulas:
        improvement_note += f" USE THIS HOOK: {hook_formulas[0]}."
    if today_strategy:
        improvement_note += f" STRATEGY: {today_strategy[:80]}."
    if visual_dna:
        improvement_note += f" VISUAL DNA: {visual_dna[:80]}."

    # Boost the best-performing category by putting it first in rotation
    topics = sorted(HINDI_BATCH_TOPICS, key=lambda x: 0 if x[0] == best_cat else 1)

    results = []
    log.info(f"=== STEP 2: Producing 10 Hindi Shorts (best cat: {best_cat}, fixes injected) ===")
    if improvement_note:
        log.info(f"  Analytics improvement injected: {improvement_note[:100]}...")

    for idx, (cat_key, hindi_topic) in enumerate(topics[:10]):
        video_num = idx + 1
        out_path = BASE_DIR / f"hindi_short_{video_num:02d}.mp4"
        # Inject analytics improvement into every topic
        enriched_topic = hindi_topic + improvement_note
        log.info(f"--- Short {video_num}/10: [{cat_key}] {hindi_topic[:60]} ---")

        try:
            prod = produce_cinematic_short(
                topic_directive=enriched_topic,
                category=cat_key,
                language="hi",
                output_path=out_path,
            )
        except Exception as e:
            log.error(f"Short {video_num} production FAILED: {e}")
            results.append({"num": video_num, "status": "FAILED", "error": str(e)})
            continue

        title = prod.get("title", f"Hindi Short {video_num} #Shorts")
        desc = prod.get("description", f"Rozana nayi jaankari! #shorts #viral #hindi")
        tags = list(set(prod.get("tags", []) + ["hindi", "shorts", "viral", "hindifacts"]))

        video_id = _upload(yt, out_path, title, desc, tags, dry_run)
        _record(video_id, title, prod)
        results.append({
            "num": video_num, "category": cat_key,
            "title": title, "video_id": video_id,
            "duration": prod.get("total_duration"), "status": "OK",
        })
        log.info(f"Short {video_num} done -> {video_id}")

        if video_num < 10:
            time.sleep(4)

    return results


def produce_long_video(yt, dry_run: bool, diagnosis: dict) -> dict:
    """
    Produce 1 long-form Hindi video (5-8 minute deep-dive) using a 10-scene storyboard.
    Uses the best-performing category from Gemini diagnosis.
    """
    from video_engine import produce_cinematic_short, VIRAL_CATEGORIES

    log.info("=== STEP 3: Producing Long-Form Hindi Video (10 scenes, ~5-8 min) ===")

    weekday = datetime.now().weekday()  # 0=Mon ... 6=Sun
    cat_key, long_topic = LONG_VIDEO_TOPICS[weekday % len(LONG_VIDEO_TOPICS)]

    # Override with best-performing category if diagnosis found one
    best_cat = diagnosis.get("best_performing_category")
    if best_cat and best_cat in VIRAL_CATEGORIES:
        cat_key = best_cat
        matching = [t for c, t in LONG_VIDEO_TOPICS if c == best_cat]
        if matching:
            long_topic = matching[0]

    out_path = BASE_DIR / "hindi_long_video.mp4"
    log.info(f"Long video: [{cat_key}] {long_topic[:70]}")

    try:
        # Use the same engine but request a longer narrative
        extended_topic = f"{long_topic}. Make this a DETAILED 8-scene deep dive with full explanation, examples, and shocking conclusion. Each scene should be 30-45 seconds."
        prod = produce_cinematic_short(
            topic_directive=extended_topic,
            category=cat_key,
            language="hi",
            output_path=out_path,
        )
    except Exception as e:
        log.error(f"Long video production FAILED: {e}")
        return {"status": "FAILED", "error": str(e)}

    title = prod.get("title", f"Hindi Long Video #hindi #viral")
    # Make title reflect it's a full video
    if "#Shorts" in title:
        title = title.replace("#Shorts", "#Hindi #Viral")
    desc = prod.get("description", f"{long_topic}\n\n#hindi #viral #education #thriller")
    tags = list(set(prod.get("tags", []) + ["hindi", "viral", "education", "hindivideo", "thriller"]))

    video_id = _upload(yt, out_path, title, desc, tags, dry_run, is_short=False)
    _record(video_id, title, prod)

    result = {
        "category": cat_key, "title": title,
        "video_id": video_id, "duration": prod.get("total_duration"),
        "status": "OK",
    }
    log.info(f"Long video done -> {video_id}")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: Upload & Record
# ─────────────────────────────────────────────────────────────────────────────

MAX_DAILY_UPLOADS = int(os.environ.get("MAX_DAILY_UPLOADS", "5"))
_DAILY_UPLOAD_COUNTER = 0

def _upload(yt, video_path: Path, title: str, description: str, tags: list,
            dry_run: bool, is_short: bool = True, pinned_comment: str = None) -> str:
    global _DAILY_UPLOAD_COUNTER
    if dry_run or not yt:
        sim_id = f"LOCAL_{int(time.time())}"
        log.info(f"  [{'DRY-RUN' if dry_run else 'NO-API'}] Saved: {video_path.name}")
        try:
            from thumbnail_generator import thumbnail_generator
            thumbnail_generator.produce_and_upload_thumbnail(topic=title, title=title, youtube_service=None, video_id=None)
        except Exception as th_err:
            log.warning(f"  [Thumbnail Notice] {th_err}")
        try:
            from community_manager import community_manager
            community_manager.post_engagement_question(None, sim_id, pinned_comment or f"Topic: {title}")
        except Exception:
            pass
        return sim_id

    # Protect channel health and API quota: cap daily live uploads
    if _DAILY_UPLOAD_COUNTER >= MAX_DAILY_UPLOADS:
        log.warning(
            f"  [QUOTA PROTECT] Daily upload limit ({MAX_DAILY_UPLOADS}) reached for today. "
            f"Saving '{video_path.name}' to local queue to prevent spam flags & API quota exhaustion."
        )
        return f"SAVED_LOCAL_{int(time.time())}"

    from autopilot_config import QuotaManager
    if not QuotaManager.can_run_pipeline(1600):
        log.warning(
            f"  [QUOTA PROTECT] YouTube API budget low ({QuotaManager.get_status_str()}). "
            f"Saving '{video_path.name}' to local queue to prevent API exhaustion."
        )
        return f"SAVED_LOCAL_{int(time.time())}"

    try:
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
                log.info(f"  Upload {int(status.progress()*100)}%")
        vid_id = resp.get("id", "unknown")
        QuotaManager.consume_units("videos.insert")
        _DAILY_UPLOAD_COUNTER += 1
        url = f"https://youtube.com/{'shorts/' if is_short else 'watch?v='}{vid_id}"
        log.info(f"  Uploaded ({_DAILY_UPLOAD_COUNTER}/{MAX_DAILY_UPLOADS}): {url}")

        # Produce 3 thumbnail variants and upload winner
        try:
            from thumbnail_generator import thumbnail_generator
            thumbnail_generator.produce_and_upload_thumbnail(
                topic=title,
                title=title,
                youtube_service=yt,
                video_id=vid_id
            )
        except Exception as th_err:
            log.warning(f"  [Thumbnail Notice] {th_err}")

        # Community Management: Post engagement question & auto-replies
        try:
            from community_manager import community_manager
            q_text = pinned_comment or f"What do you think about {title}? Tell us below! 👇"
            community_manager.post_engagement_question(
                youtube_service=yt,
                video_id=vid_id,
                comment_text=q_text
            )
            community_manager.run_channel_auto_replies(youtube_service=yt)
        except Exception as comm_err:
            log.warning(f"  [Community Notice] {comm_err}")

        return vid_id
    except Exception as e:
        if "uploadLimitExceeded" in str(e):
            log.warning(f"  [QUOTA] YouTube daily upload limit reached! Video saved locally: {video_path.name}")
            return f"SAVED_LOCAL_{int(time.time())}"
        log.error(f"  Upload error: {e}")
        return f"UPLOAD_ERR_{int(time.time())}"


# ─────────────────────────────────────────────────────────────────────────────
# MYTHOLOGICAL REELS ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _generate_mythology_storyboard(topic: str, deity: str) -> dict:
    """
    Gemini generates a 5-scene mythology storyboard.
    Each scene has a voiceover, subtitle, highlight_words, and pollinations_prompt.
    """
    prompt = (
        "You are the lead creative director of India's top mythology YouTube Shorts channel.\n"
        f"TOPIC: {topic!r}\n"
        f"DEITY/STORY: {deity}\n\n"
        "Create a 5-scene viral Hindi mythology Short storyboard:\n"
        "Scene 1: Hook - The most dramatic or unknown moment from this story (0-3s)\n"
        "Scene 2: The backstory or hidden truth behind the scene (3-7s)\n"
        "Scene 3: The divine lesson or shocking revelation (7-11s)\n"
        "Scene 4: The visual miracle / divine power moment (11-14s)\n"
        "Scene 5: The loop hook - connects back to scene 1, creates infinite rewatch\n\n"
        "LANGUAGE: Hindi Devanagari for voiceover, Hinglish for subtitle_display.\n"
        "VISUALS: Every pollinations_prompt MUST be in ENGLISH and describe:\n"
        f"  '{MYTHOLOGY_VISUAL_DNA}' + the exact divine scene being described.\n"
        "NEVER use generic prompts - describe the specific divine action/scene.\n\n"
        "OUTPUT ONLY RAW JSON:\n"
        "{\"title\": \"...\", \"description\": \"...\", \"tags\": [...], \"is_hindi\": true,"
        " \"scenes\": [{\"scene_id\": 1, \"voiceover\": \"...\", \"subtitle_display\": \"...\","
        " \"highlight_words\": [...], \"pollinations_prompt\": \"...\"}]}"
    )
    GEMINI_MODELS_LOCAL = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
    for model in GEMINI_MODELS_LOCAL:
        try:
            resp = ai_client.models.generate_content(model=model, contents=prompt)
            raw = resp.text.strip().replace("```json", "").replace("```", "").strip()
            s, e = raw.find("{"), raw.rfind("}")
            if s != -1 and e != -1:
                data = json.loads(raw[s:e+1])
                if "scenes" in data and len(data["scenes"]) >= 4:
                    # Ensure all scenes have pollinations_prompt
                    for i, sc in enumerate(data["scenes"]):
                        if not sc.get("pollinations_prompt", "").strip():
                            sc["pollinations_prompt"] = (
                                f"{MYTHOLOGY_VISUAL_DNA}, {deity} divine scene {i+1}, "
                                f"{topic[:40]}, epic celestial light, 3D octane render"
                            )
                    log.info(f"  [Mythology] {model} -> {len(data['scenes'])} scenes")
                    return data
        except Exception as ex:
            log.warning(f"  [Mythology] {model} failed: {ex}")
            time.sleep(1)

    # Fallback storyboard
    def _sc(i, vo, sub, hl, vis):
        return {"scene_id": i, "voiceover": vo, "subtitle_display": sub,
                "highlight_words": hl, "pollinations_prompt": vis}

    fallback_scenes = [
        _sc(1, f"{topic[:50]} - yeh sach jaankar aap hairan rah jaoge!",
            "HAIRAN kar dene wala SACH!", ["HAIRAN", "SACH"],
            f"{MYTHOLOGY_VISUAL_DNA}, {deity} in dramatic divine crisis moment, epic golden light"),
        _sc(2, f"Is kahani ke peeche ka asli raaz kya hai, yeh kisi ne nahi bataya.",
            "Asli RAAZ kisi ne nahi bataya!", ["RAAZ", "bataya"],
            f"{MYTHOLOGY_VISUAL_DNA}, {deity} divine backstory ancient India temple, sacred fire"),
        _sc(3, f"Iske peeche ek aisi seekh chhuppi hai jo aaj bhi relevant hai.",
            "Aaj bhi RELEVANT seekh!", ["RELEVANT", "seekh"],
            f"{MYTHOLOGY_VISUAL_DNA}, {deity} divine lesson revelation, glowing scripture text overlay"),
        _sc(4, f"{deity} ki shakti ne us pal sab kuch badal diya - ek chamatkar hua.",
            "CHAMATKAR! Divine SHAKTI!", ["CHAMATKAR", "SHAKTI"],
            f"{MYTHOLOGY_VISUAL_DNA}, {deity} miraculous divine power explosion, celestial rays, epic 3D"),
        _sc(5, f"Yahi wajah hai ki yeh kahani aaj bhi hamen kuch sikhati hai - share karo!",
            "Share karo aur Subscribe!", ["Share", "Subscribe"],
            f"{MYTHOLOGY_VISUAL_DNA}, {deity} blessing devotees, divine glow, subscribe button overlay"),
    ]
    return {
        "title": f"{topic[:60]} 🙏 #Shorts #Mythology",
        "description": f"{topic}. Aaj ki mythology short! #shorts #viral #hindi #mythology",
        "tags": ["mythology", "hindu", "shorts", "viral", "hindi", deity.lower(), "bhakti"],
        "is_hindi": True,
        "scenes": fallback_scenes,
    }


def _produce_mythology_short(
    topic: str,
    deity: str,
    video_num: int,
    output_path: Path,
    dry_run: bool,
    yt,
) -> dict:
    """
    Full pipeline for one mythology short:
    Gemini storyboard -> Pollinations AI visuals -> Edge TTS Hindi voice -> Assemble -> Upload
    """
    import urllib.parse
    import asyncio
    import wave, struct, math
    import numpy as np
    import requests
    from PIL import Image, ImageDraw, ImageFont
    import edge_tts

    try:
        from moviepy import VideoClip, ImageClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip, CompositeAudioClip
        MVPY2 = True
    except ImportError:
        from moviepy.editor import VideoClip, ImageClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip, CompositeAudioClip
        MVPY2 = False

    log.info(f"  [Mythology {video_num}] Generating storyboard: {topic[:50]}")
    storyboard = _generate_mythology_storyboard(topic, deity)
    scenes = storyboard["scenes"]
    video_seed = (hash(topic) % 50000) + video_num * 77
    ASSETS_DIR = BASE_DIR / "assets"
    MYTH_FRAMES_DIR = ASSETS_DIR / "mythology_frames"
    MYTH_FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    # --- Step A: Generate Pollinations AI frames ---
    log.info(f"  [Mythology {video_num}] Sourcing high-end diverse visuals for {len(scenes)} scenes...")
    frame_paths = []
    
    # 5 Distinct Cinematographic Scene Archetypes
    SCENE_CINEMATIC_PROMPTS = [
        f"hyperrealistic extreme macro closeup glowing divine eyes of {deity}, golden war crown, volumetric god rays, Unreal Engine 5 render, cinematic rim lighting, 8k vertical 9:16",
        f"cinematic panoramic wide angle view of ancient sacred Indian temple, golden flags, dramatic stormy clouds sunset, {deity} backstory, photorealistic 8k vertical 9:16",
        f"epic clash, glowing celestial Sudarshan Chakra weapon spinning with golden lightning bolts cutting dark sky, shockwave particles, {deity} power explosion, 3D octane render vertical 9:16",
        f"cosmic spiritual dimension, {deity} third eye opening with divine blue fire aura, celestial universe stars nebula vortex, sacred glowing Sanskrit aura, vertical 9:16",
        f"iconic majestic silhouette of {deity} standing victorious at divine sunrise, heavenly temple gates, blinding golden sunbeams, masterpiece 3D render vertical 9:16"
    ]
    PEXELS_QUERIES = [
        f"intense warrior face dramatic lightning dark",
        f"ancient indian temple golden light sunset",
        f"lightning storm fire explosion dramatic cosmic",
        f"cosmic galaxy space stars nebula glowing aura",
        f"sunrise golden god rays mountain silhouette dramatic"
    ]
    THEME_PALETTES = [
        ((40, 5, 5), (220, 40, 20)),      # Scene 1: Fiery Crimson (Hook)
        ((5, 15, 45), (30, 120, 220)),    # Scene 2: Royal Sapphire (Backstory)
        ((45, 20, 5), (255, 140, 10)),    # Scene 3: Volcanic Gold (Action)
        ((25, 5, 40), (180, 50, 240)),    # Scene 4: Cosmic Amethyst (Astral)
        ((40, 30, 5), (255, 215, 30)),    # Scene 5: Radiant Amber (Climax)
    ]

    for i, scene in enumerate(scenes):
        out_img = MYTH_FRAMES_DIR / f"myth_{video_seed}_{i+1}.jpg"
        scene_seed = video_seed + i * 13
        downloaded = False

        # --- Tier 1: Pollinations AI (Turbo Model First for Speed & Reliability) ---
        cinematic_p = SCENE_CINEMATIC_PROMPTS[i % len(SCENE_CINEMATIC_PROMPTS)]
        scene_poll = scene.get("pollinations_prompt", "").strip()
        full_poll = f"{cinematic_p}, {scene_poll[:40]}" if scene_poll else cinematic_p
        encoded = urllib.parse.quote(full_poll)

        urls_to_try = [
            f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&model=turbo&nologo=true&seed={scene_seed}",
            f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={scene_seed}",
            f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&model=flux&nologo=true&seed={scene_seed}",
        ]
        for url in urls_to_try:
            try:
                r = requests.get(url, timeout=14)
                if r.status_code == 200 and len(r.content) > 4000:
                    img = Image.open(__import__('io').BytesIO(r.content)).convert("RGB")
                    img = img.resize((1080, 1920), Image.LANCZOS)
                    img.save(str(out_img), quality=93)
                    frame_paths.append(out_img)
                    log.info(f"    Scene {i+1}: Pollinations AI frame OK ({len(r.content)//1024}KB)")
                    downloaded = True
                    time.sleep(0.5)
                    break
            except Exception:
                pass

        # --- Tier 2: Pexels 4K Cinematic Photography API ---
        if not downloaded and PEXELS_API_KEY:
            try:
                q = PEXELS_QUERIES[i % len(PEXELS_QUERIES)]
                p_url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(q)}&orientation=portrait&per_page=3"
                pr = requests.get(p_url, headers={"Authorization": PEXELS_API_KEY}, timeout=8).json()
                photos = pr.get("photos", [])
                if photos:
                    p_img_url = photos[0]["src"].get("large2x") or photos[0]["src"].get("original")
                    content = requests.get(p_img_url, timeout=12).content
                    img = Image.open(__import__('io').BytesIO(content)).convert("RGB")
                    img = img.resize((1080, 1920), Image.LANCZOS)
                    img.save(str(out_img), quality=93)
                    frame_paths.append(out_img)
                    log.info(f"    Scene {i+1}: Pexels 4K photo downloaded ({len(content)//1024}KB)")
                    downloaded = True
            except Exception as ex:
                log.warning(f"    Scene {i+1} Pexels fallback error: {ex}")

        # --- Tier 3: Thematic Procedural Blockbuster Art (Distinct per scene) ---
        if not downloaded:
            c_bg, c_fg = THEME_PALETTES[i % len(THEME_PALETTES)]
            fb = Image.new("RGB", (1080, 1920), c_bg)
            draw_fb = ImageDraw.Draw(fb)
            cx, cy = 540, 960
            for ang in range(0, 360, 15):
                rad = math.radians(ang)
                x2 = cx + int(1200 * math.cos(rad))
                y2 = cy + int(1200 * math.sin(rad))
                draw_fb.line([(cx, cy), (x2, y2)], fill=c_fg, width=12)
            for r in range(450, 0, -25):
                alpha = 1 - (r / 450)
                col = (
                    int(c_bg[0] + (c_fg[0] - c_bg[0]) * alpha),
                    int(c_bg[1] + (c_fg[1] - c_bg[1]) * alpha),
                    int(c_bg[2] + (c_fg[2] - c_bg[2]) * alpha),
                )
                draw_fb.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=col)
            fb.save(str(out_img), quality=90)
            frame_paths.append(out_img)
            log.info(f"    Scene {i+1}: Unique thematic poster generated (Theme {i+1})")

    # --- Step B: Hindi voiceover ---
    voice_path = ASSETS_DIR / f"myth_voice_{video_num:02d}.mp3"
    full_text = " ".join(sc["voiceover"].strip() for sc in scenes)

    async def _synth(text, out):
        comm = edge_tts.Communicate(text, "hi-IN-MadhurNeural", rate="+12%")
        boundaries = []
        with open(out, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "SentenceBoundary":
                    boundaries.append((chunk["offset"] / 1e7, chunk["duration"] / 1e7))
        return boundaries

    log.info(f"  [Mythology {video_num}] Synthesizing Hindi voiceover...")
    boundaries = asyncio.run(_synth(full_text, voice_path))
    ac = AudioFileClip(str(voice_path))
    total_dur = float(ac.duration)
    ac.close()

    # Scene timings from boundaries
    timings = []
    for i in range(len(scenes)):
        start = boundaries[i][0] if i < len(boundaries) else (timings[-1][0] + timings[-1][1] if timings else 0.0)
        end = boundaries[i+1][0] if i+1 < len(boundaries) else total_dur
        timings.append((start, max(1.5, end - start)))

    # --- Step C: Higgsfield-Style 2.5D Cinematic Camera Clips for each frame ---
    from video_engine import _make_higgsfield_camera_clip
    video_clips, sub_overlays = [], []

    # subtitle badge renderer (inline)
    def _badge(text, hl_words):
        import string as _str
        font = None
        for fp in ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"]:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, 44)
                    break
                except Exception:
                    pass
        if not font:
            font = ImageFont.load_default()
        words = text.strip().split()
        lines, curr = [], []
        for w in words:
            curr.append(w)
            if len(curr) >= 4:
                lines.append(curr); curr = []
        if curr:
            lines.append(curr)
        dummy = Image.new("RGBA", (1, 1))
        d = ImageDraw.Draw(dummy)
        sw = d.textbbox((0,0), " ", font=font)[2]
        lh, px, py = 54, 38, 16
        lmets = []
        mw = 0
        for ln in lines:
            lw = sum(d.textbbox((0,0),w,font=font)[2]-d.textbbox((0,0),w,font=font)[0] for w in ln)
            lw += sw * (len(ln)-1)
            mw = max(mw, lw)
            lmets.append((ln, lw))
        bw = int(min(1000, mw + px*2))
        bh = int(lh * len(lines) + py*2)
        img = Image.new("RGBA", (bw, bh), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([(0,0),(bw,bh)], radius=22, fill=(8,6,2,230), outline=(255,200,30,190), width=3)
        hl_clean = [h.lower().strip(_str.punctuation) for h in hl_words]
        for i2, (ln, lw) in enumerate(lmets):
            cx = (bw-lw)/2
            cy = py + i2*lh
            for w in ln:
                bb = d.textbbox((0,0),w,font=font)
                ww = bb[2]-bb[0]
                is_hl = any(h in w.lower().strip(_str.punctuation) for h in hl_clean)
                col = (255,215,0,255) if is_hl else (255,255,255,255)
                draw.text((cx+2,cy+2),w,font=font,fill=(0,0,0,210))
                draw.text((cx,cy),w,font=font,fill=col)
                cx += ww+sw
        return img

    voice_ac = AudioFileClip(str(voice_path))
    total_voice_duration = float(voice_ac.duration)
    num_scenes = max(1, len(frame_paths))
    scene_duration = total_voice_duration / num_scenes

    for i, (scene, fp) in enumerate(zip(scenes, frame_paths)):
        start_t = i * scene_duration
        dur = scene_duration
        clip = _make_higgsfield_camera_clip(fp, dur, i)
        if MVPY2:
            clip = clip.with_duration(dur)
        else:
            clip = clip.set_duration(dur)
        video_clips.append(clip)

        badge_img = _badge(scene.get("subtitle_display",""), scene.get("highlight_words",[]))
        ov = ImageClip(np.array(badge_img))
        if MVPY2:
            ov = ov.with_duration(dur).with_position(("center", 1100)).with_start(start_t)
        else:
            ov = ov.set_duration(dur).set_position(("center", 1100)).set_start(start_t)
        sub_overlays.append(ov)

    # --- Step D: Assemble ---
    base = concatenate_videoclips(video_clips, method="compose")
    if MVPY2:
        base = base.with_duration(total_voice_duration)
        final = CompositeVideoClip([base.with_audio(voice_ac), *sub_overlays]).with_duration(total_voice_duration)
    else:
        base = base.set_duration(total_voice_duration)
        final = CompositeVideoClip([base.set_audio(voice_ac), *sub_overlays]).set_duration(total_voice_duration)

    log.info(f"  [Mythology {video_num}] Rendering {final.duration:.1f}s -> {output_path.name}")
    final.write_videofile(str(output_path), fps=24, codec="libx264",
                          audio_codec="aac", logger=None, remove_temp=False,
                          ffmpeg_params=["-shortest", "-pix_fmt", "yuv420p"])
    for c in [final, base, voice_ac] + video_clips + sub_overlays:
        try: c.close()
        except Exception: pass
    for tmp_f in BASE_DIR.glob("*TEMP_MPY*"):
        try: tmp_f.unlink()
        except Exception: pass

    sz = os.path.getsize(output_path) / 1024 / 1024
    log.info(f"  [Mythology {video_num}] Done: {output_path.name} ({sz:.1f} MB)")

    # Apply studio-grade photographic clarity, micro-contrast, and 35mm film grain grade
    try:
        from video_engine import apply_photographic_clarity_grade
        apply_photographic_clarity_grade(output_path)
    except Exception:
        pass

    title = storyboard.get("title", f"{topic[:60]} 🙏 #Shorts")
    desc  = storyboard.get("description", f"{topic} #shorts #mythology #hindi")
    tags  = storyboard.get("tags", ["mythology", "hindi", "shorts", "viral"])

    video_id = _upload(yt, output_path, title, desc, tags, dry_run)
    _record(video_id, title, {"topic_used": topic, "category": deity, "tags": tags})
    return {"status": "OK", "title": title, "video_id": video_id,
            "deity": deity, "topic": topic, "file": str(output_path)}


def produce_mythology_shorts(yt, dry_run: bool, count: int = 5,
                             existing_state: dict = None) -> list:
    """
    Produces `count` Hindi mythological Shorts with Pollinations AI visuals.
    Resumable: skips already-completed videos.
    """
    log.info(f"=== MYTHOLOGY SHORTS: Producing {count} divine Hindi Reels ===")
    results = existing_state or {}
    today_weekday = datetime.now().weekday()

    for idx in range(count):
        video_num = idx + 1
        key = f"myth_{video_num}"
        if results.get(key, {}).get("status") == "OK":
            log.info(f"  [Myth {video_num}/{count}] Already done. Skipping.")
            continue

        topic_entry = MYTHOLOGY_TOPICS[(today_weekday * count + idx) % len(MYTHOLOGY_TOPICS)]
        deity, topic = topic_entry
        out_path = BASE_DIR / f"mythology_short_{video_num:02d}.mp4"

        log.info(f"  [Myth {video_num}/{count}] {deity.upper()}: {topic[:55]}")
        try:
            res = _produce_mythology_short(
                topic=topic, deity=deity,
                video_num=video_num,
                output_path=out_path,
                dry_run=dry_run,
                yt=yt,
            )
            results[key] = res
        except Exception as e:
            log.error(f"  [Myth {video_num}/{count}] FAILED: {e}")
            results[key] = {"status": "FAILED", "error": str(e)}

        if idx < count - 1:
            time.sleep(5)

    ok = sum(1 for v in results.values() if isinstance(v, dict) and v.get("status") == "OK")
    log.info(f"  Mythology batch done: {ok}/{count} uploaded")
    return results



def _record(video_id, title, metadata=None):
    history = {}
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    history.setdefault("videos", []).append({
        "id": video_id, "title": title,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "topic": metadata.get("topic_used") if metadata else None,
        "category": metadata.get("category") if metadata else None,
        "language": "hi",
    })
    history["last_video_id"] = video_id
    history["last_title"] = title
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN DAILY RUN
# ─────────────────────────────────────────────────────────────────────────────



# ─────────────────────────────────────────────────────────────────────────────
# TREND ENGINE: Fetch today's top trending YouTube videos in India
# ─────────────────────────────────────────────────────────────────────────────

def fetch_trending_india(yt) -> list:
    """
    Queries YouTube Data API for top 15 trending videos in India right now.
    Returns list of dicts with title, tags, categoryId, viewCount.
    Falls back to Gemini-synthesized trends if API is unavailable.
    """
    log.info("=== Fetching Today's YouTube Trending India ===")
    trending = []

    if yt:
        try:
            res = yt.videos().list(
                part="snippet,statistics",
                chart="mostPopular",
                regionCode="IN",
                maxResults=15,
                fields="items(snippet(title,tags,categoryId,publishedAt),statistics(viewCount,likeCount))"
            ).execute()
            for item in res.get("items", []):
                sn = item.get("snippet", {})
                st = item.get("statistics", {})
                trending.append({
                    "title":      sn.get("title", ""),
                    "tags":       sn.get("tags", [])[:5],
                    "category":   sn.get("categoryId", ""),
                    "views":      int(st.get("viewCount", 0)),
                    "likes":      int(st.get("likeCount", 0)),
                    "published":  sn.get("publishedAt", ""),
                })
            log.info(f"Trending: fetched {len(trending)} videos from YouTube API")
        except Exception as e:
            log.warning(f"YouTube trending API failed: {e} — using Gemini fallback")

    if not trending:
        # Gemini synthesizes realistic trending topics for India
        try:
            today = datetime.now().strftime("%A %d %B %Y")
            prompt = (
                f"Today is {today}. You are a YouTube India trends analyst.\n"
                "List the TOP 10 types of YouTube videos and Reels that are trending "
                "in India RIGHT NOW (Hindi audience, age 15-35).\n"
                "Focus on: education, dark facts, mystery, science, kids, motivation, news, comedy.\n"
                "OUTPUT ONLY RAW JSON array:\n"
                '[{"title": "...", "topic_type": "...", "why_trending": "...", "views_estimate": "5M+"}]'
            )
            for model in GEMINI_MODELS:
                try:
                    resp = ai_client.models.generate_content(model=model, contents=prompt)
                    raw = resp.text.strip().replace("```json","").replace("```","").strip()
                    s, e = raw.find("["), raw.rfind("]")
                    if s != -1 and e != -1:
                        trending = json.loads(raw[s:e+1])
                        log.info(f"Trending: Gemini synthesized {len(trending)} trends")
                        break
                except Exception:
                    time.sleep(1)
        except Exception as ex:
            log.warning(f"Gemini trending fallback failed: {ex}")
            trending = [{"title": "Dark Psychology facts Hindi", "topic_type": "education"},
                        {"title": "Science mystery shorts Hindi", "topic_type": "science"}]

    return trending


# ─────────────────────────────────────────────────────────────────────────────
# SMART STRATEGY: Analyze yesterday performance + today trends → adapt topics
# ─────────────────────────────────────────────────────────────────────────────

def analyze_and_adapt_strategy(audit: dict, diagnosis: dict, trending: list) -> dict:
    """
    Gemini analyzes:
      1. Which of yesterday's videos got the most views (winners)
      2. Which videos flopped (losers)
      3. What is trending TODAY in India
    Then outputs:
      - 10 adapted topics for cartoon Shorts
      - 1 kids cartoon topic (most engaging for children today)
      - 1 long-form topic (highest CPM category today)
      - Updated strategy notes
    """
    log.info("=== Smart Strategy Adaptation (Analytics + Trends) ===")

    audit_summary = {
        "videos": [
            {"title": v.get("title","")[:60], "views": v.get("views",0), "likes": v.get("likes",0)}
            for v in audit.get("videos_audited", [])
        ],
        "avg_views": audit.get("summary",{}).get("avg_views_per_short", 0),
        "low_performers": audit.get("summary",{}).get("low_performing_count", 0),
    }
    trending_summary = [t.get("title","")[:60] for t in trending[:10]]

    prompt = (
        "You are the world's top YouTube growth strategist for Hindi content (India, age 13-35).\n\n"
        f"YESTERDAY'S PERFORMANCE:\n{json.dumps(audit_summary, ensure_ascii=False, indent=2)}\n\n"
        f"GEMINI's DIAGNOSIS:\n{diagnosis.get('today_strategy','')}\n\n"
        f"TODAY'S TRENDING IN INDIA (YouTube + Reels):\n{json.dumps(trending_summary, indent=2)}\n\n"
        "YOUR TASK:\n"
        "1. Find the WINNING video type from yesterday (most views).\n"
        "2. Find the LOSING video type (least views).\n"
        "3. Cross-reference with today's trending topics.\n"
        "4. Generate 10 ADAPTED Hindi cartoon Short topics for today.\n"
        "   - Each must be a specific hook question like Zack D. Films style\n"
        "   - Must include the character Max facing the scenario physically\n"
        "   - Must be in Hindi/Hinglish\n"
        "5. Generate 1 kids cartoon long video topic (3-5 min educational, dancing/singing style).\n"
        "6. Generate 1 thriller long video topic for adults (5-8 min deep dive).\n\n"
        "OUTPUT ONLY RAW JSON:\n"
        "{\n"
        '  "winner_type": "what type of video got best views yesterday",\n'
        '  "loser_type": "what type of video flopped",\n'
        '  "today_trend": "biggest trending theme today in India",\n'
        '  "shorts_topics": [\n'
        '    {"category": "medical_biology_anomalies", "topic": "Hindi topic for Max cartoon Short"},\n'
        "    ... 10 total\n"
        "  ],\n"
        '  "kids_topic": "Max teaches kids [X] - colorful educational dancing cartoon in Hindi",\n'
        '  "long_video_topic": "Hindi deep-dive thriller topic for adults - 5-8 min",\n'
        '  "strategy_note": "one paragraph on why these topics will win today"\n'
        "}"
    )

    for model in GEMINI_MODELS:
        try:
            resp = ai_client.models.generate_content(model=model, contents=prompt)
            raw = resp.text.strip().replace("```json","").replace("```","").strip()
            s, e = raw.find("{"), raw.rfind("}")
            if s != -1 and e != -1:
                strategy = json.loads(raw[s:e+1])
                if "shorts_topics" in strategy and len(strategy["shorts_topics"]) >= 5:
                    log.info(f"Strategy from {model}: winner={strategy.get('winner_type','?'[:30])}")
                    log.info(f"Today trend: {strategy.get('today_trend','?'[:60])}")
                    log.info(f"Strategy: {strategy.get('strategy_note','')[:100]}")
                    return strategy
        except Exception as ex:
            log.warning(f"Strategy model {model} failed: {ex}")
            time.sleep(1)

    # Fallback
    log.warning("Strategy adaptation failed - using default topics")
    return {
        "winner_type": "thriller science",
        "loser_type": "unknown",
        "today_trend": "dark facts",
        "shorts_topics": [
            {"category": c, "topic": t}
            for c, t in [
                ("medical_biology_anomalies", "agar tum bleach pi lo toh Max ke andar kya hoga"),
                ("thriller_dark_psychology", "Manipulation ki 3 technique jo Max ne aazmayi aur sab hairan ho gaye"),
                ("how_it_actually_works", "Microwave mein dhatu kyun aaag lagti hai - Max ka experiment"),
                ("survival_emergency_anatomy", "Max ko saanp ne kaata - 60 second mein kya hoga"),
                ("extreme_physics_space_terrors", "Black hole ke andar Max gaya - wapas nahi aa sakta kyun"),
                ("unexplained_real_mysteries", "India ki sabse badi mystery - Max dhundh raha hai jawab"),
                ("bizarre_nature_monsters", "Mantis Shrimp ka punch - Max ko dekha aur kya hua"),
                ("perception_sensory_traps", "Max ne ye optical illusion dekha aur dimag ne dhoka diya"),
                ("reality_simulation_paradoxes", "Max ne socha woh simulation mein hai - kya sach mein hai"),
                ("high_stakes_heists_scandals", "Max ne 1 din mein 1 crore kaise churaaye - real story"),
            ]
        ],
        "kids_topic": "Max teaches kids numbers 1 to 10 in Hindi - dancing and singing cartoon",
        "long_video_topic": "Dark Psychology ki 7 secret techniques - Max ki investigation in Hindi",
        "strategy_note": "Focus on thriller + science content with strong Hindi hooks.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# REEL STYLE ANALYZER: Deep-analyze viral Reels/Shorts style DNA
# ─────────────────────────────────────────────────────────────────────────────

def analyze_reels_style(trending: list) -> dict:
    """
    Sends today's trending titles/tags to Gemini and asks it to reverse-engineer
    the EXACT viral formula being used right now:
      - Hook sentence pattern (how do the top creators open?)
      - Visual style DNA (color palette, character POV, pacing)
      - Emotional trigger (fear, curiosity, disgust, awe, humor)
      - Optimal script length and pacing per scene
      - What TOPICS are dominating today

    Returns a "reel_style_dna" dict that is injected into every Gemini
    storyboard prompt so our videos LOOK and FEEL like what's going viral TODAY.
    """
    log.info("=== Reel Style DNA Analysis (Reverse-Engineering Viral Formula) ===")

    trending_titles = [t.get("title", "")[:80] for t in trending[:15]]
    today_str = datetime.now().strftime("%A %d %B %Y")

    prompt = (
        f"Today is {today_str}. You are the world's top viral content strategist for YouTube Shorts and Instagram Reels (India).\n\n"
        f"Here are today's TOP 15 trending videos/reels in India:\n"
        + "\n".join(f"  {i+1}. {t}" for i, t in enumerate(trending_titles))
        + "\n\n"
        "Analyze these and extract the EXACT viral formula used today. Return:\n"
        "1. hook_formula: The opening sentence template that's working (e.g. 'Agar tumne X kiya toh Y ho sakta hai...')\n"
        "2. visual_style: The visual aesthetic that's dominating (e.g. 'dark thriller close-ups', 'bright colorful 3D', 'real footage + text overlay')\n"
        "3. dominant_emotion: The primary emotion driving clicks today (fear/curiosity/disgust/shock/humor/awe)\n"
        "4. optimal_scene_duration: Best seconds-per-scene for max retention today (e.g. '2-3 seconds')\n"
        "5. top_3_topics: The 3 specific content topics getting most views today\n"
        "6. script_style: Describe how top creators are scripting today (tone, pace, word choice)\n"
        "7. pollinations_visual_dna: A specific art direction string enforcing Zack D. Films 3D animated pictorial infographics, literal 1:1 physical demonstration of actions, anatomical cutaways, and green checkmark / red X cues\n"
        "   Example: '3D stylized cartoon character Max, vibrant Pixar-octane render, literal step-by-step physical postures, isometric cross-section diagrams, 3D anatomical x-ray cutaways, green checkmark and red X infographic cues, 9:16 vertical 8k render'\n"
        "8. kids_visual_dna: Visual style for children's content trending today\n\n"
        "OUTPUT ONLY RAW JSON:"
        "\n{"
        '\n  "hook_formula": "...",'
        '\n  "visual_style": "...",'
        '\n  "dominant_emotion": "fear|curiosity|shock|humor|awe",'
        '\n  "optimal_scene_duration": "2-3 seconds",'
        '\n  "top_3_topics": ["topic1", "topic2", "topic3"],'
        '\n  "script_style": "...",'
        '\n  "pollinations_visual_dna": "3D stylized character Max, vibrant Pixar-octane render, literal step-by-step physical postures, isometric cross-section diagrams, 3D anatomical x-ray cutaways, 9:16 vertical...",'
        '\n  "kids_visual_dna": "bright rainbow colors, happy characters dancing...",'
        '\n  "today_viral_formula": "One sentence that summarizes the winning formula today"'
        "\n}"
    )

    for model in GEMINI_MODELS:
        try:
            resp = ai_client.models.generate_content(model=model, contents=prompt)
            raw = resp.text.strip().replace("```json", "").replace("```", "").strip()
            s, e = raw.find("{"), raw.rfind("}")
            if s != -1 and e != -1:
                dna = json.loads(raw[s:e+1])
                if "hook_formula" in dna:
                    log.info(f"  Reel Style DNA from {model}:")
                    log.info(f"  Hook:    {dna.get('hook_formula','')[:70]}")
                    log.info(f"  Visual:  {dna.get('visual_style','')[:70]}")
                    log.info(f"  Emotion: {dna.get('dominant_emotion','')}")
                    log.info(f"  Formula: {dna.get('today_viral_formula','')[:80]}")
                    # Save DNA to disk so cartoon_agent.py can read it
                    dna_path = BASE_DIR / "reel_style_dna.json"
                    dna_path.write_text(json.dumps(dna, indent=2, ensure_ascii=False), encoding="utf-8")
                    log.info(f"  DNA saved to reel_style_dna.json")
                    return dna
        except Exception as ex:
            log.warning(f"  Reel analysis {model} failed: {ex}")
            time.sleep(1)

    # Fallback DNA
    fallback = {
        "hook_formula": "Show the immediate physical crisis in 0-2 seconds with zero filler, then demonstrate the exact pictorial solution.",
        "visual_style": "Zack D. Films 3D animated infographics, literal 1:1 pictorial demonstration of every spoken action, anatomical cutaways, mistake (red X) vs solution (green checkmark) diagrams",
        "dominant_emotion": "curiosity_urgency",
        "optimal_scene_duration": "2-3 seconds",
        "top_3_topics": ["survival mechanics", "bodily emergency anatomy", "counter-intuitive science"],
        "script_style": "High-urgency conversational Hinglish, punchy delivery, zero intro fluff, literal physical instructions",
        "pollinations_visual_dna": "3D stylized character Max, vibrant Pixar-octane render, literal step-by-step physical postures, isometric cross-section diagrams, 3D anatomical x-ray cutaways, green checkmark and red X infographic cues, 9:16 vertical 8k render",
        "kids_visual_dna": "bright colorful 3D block voxel animation, glowing neon sky, isometric playful perspective, high contrast cheerful lighting, cute expressive Minecraft-style avatars",
        "today_viral_formula": "Pair an impossible high-stakes bodily/mechanical crisis with an exact step-by-step pictorial survival demonstration, using 1:1 visual-verbal mirroring.",
    }
    log.warning("Reel style analysis failed - using fallback DNA")
    (BASE_DIR / "reel_style_dna.json").write_text(
        json.dumps(fallback, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return fallback


# ─────────────────────────────────────────────────────────────────────────────
# RESILIENT PROCESS LOCK & DAILY STATE TRACKING
# ─────────────────────────────────────────────────────────────────────────────

def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    import platform
    if platform.system() == "Windows":
        try:
            import subprocess
            out = subprocess.check_output(
                ["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                text=True,
                timeout=4
            )
            for line in out.strip().splitlines()[1:]:
                parts = [p.strip('"') for p in line.split(",")]
                if parts and len(parts) >= 2:
                    name = parts[0].lower()
                    if "python" in name:
                        return True
            return False
        except Exception:
            return False
    else:
        # Linux/macOS (GitHub Actions runs Ubuntu)
        try:
            import os as _os
            _os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # Process exists but we don't own it
        except Exception:
            return False


def acquire_lock() -> bool:
    my_pid = os.getpid()
    if LOCK_FILE.exists():
        try:
            content = LOCK_FILE.read_text(encoding="utf-8").strip()
            data = json.loads(content)
            old_pid = data.get("pid", 0)
            if old_pid and is_pid_running(old_pid):
                log.warning(f"Another instance of daily_autopilot is already running (PID: {old_pid}). Exiting to avoid duplicate work.")
                return False
            else:
                log.info(f"Removing stale lock file from inactive or non-python PID {old_pid}.")
                try:
                    LOCK_FILE.unlink()
                except Exception:
                    pass
        except Exception:
            try:
                LOCK_FILE.unlink()
            except Exception:
                pass
    try:
        LOCK_FILE.write_text(json.dumps({
            "pid": my_pid,
            "acquired_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }), encoding="utf-8")
        return True
    except Exception as e:
        log.error(f"Could not acquire lock: {e}")
        return False


def release_lock():
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


def wait_for_internet(timeout_seconds: int = 180, check_interval: int = 5) -> bool:
    """Wait for network connection when computer turns on or wakes up."""
    import socket
    log.info("Checking internet connection...")
    t0 = time.time()
    while time.time() - t0 < timeout_seconds:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            log.info("Internet connection is active.")
            return True
        except Exception:
            time.sleep(check_interval)
    log.warning("No internet connection detected within timeout. Will attempt with offline fallback.")
    return False


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception as e:
            log.warning(f"Could not read state file: {e}")
    return {}


def save_state(state: dict):
    state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STATE_FILE)
    except Exception as e:
        log.error(f"Failed to save state file: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN DAILY RUN (Resilient: Resumes if interrupted, runs anytime PC is ON)
# ─────────────────────────────────────────────────────────────────────────────

def _run_daily_internal(dry_run: bool = False):
    start = time.time()
    today = datetime.now().strftime("%Y-%m-%d")
    SEP = "=" * 70
    log.info(SEP)
    log.info(f"  SMART RESILIENT AUTOPILOT  |  {today}  |  {'DRY-RUN' if dry_run else 'LIVE'}")
    log.info(f"  Runs anytime PC is ON | Resumes if interrupted | 10 Shorts + 1 Kids + 1 Thriller")
    log.info(SEP)

    # 1. Wait for Wi-Fi/Internet connection
    if not dry_run:
        wait_for_internet(timeout_seconds=180)

    # 2. Check existing state
    state = load_state()
    is_same_day = (state.get("date") == today)

    if is_same_day:
        shorts_dict = state.get("shorts", {})
        ok_shorts_count = sum(1 for s in shorts_dict.values() if isinstance(s, dict) and s.get("status") == "OK")
        kids_ok = state.get("kids_long_cartoon", {}).get("status") == "OK"
        long_ok = state.get("thriller_long_video", {}).get("status") == "OK"

        if ok_shorts_count >= 10 and kids_ok and long_ok and state.get("status") == "COMPLETED":
            log.info(SEP)
            log.info(f"  TODAY'S WORK IS ALREADY 100% COMPLETED ({today})!")
            log.info(f"  Cartoon Shorts:    {ok_shorts_count}/10 uploaded")
            log.info(f"  Kids Long Cartoon: Uploaded")
            log.info(f"  Thriller Long:     Uploaded")
            log.info(f"  Laptop is ON, but today's quota is fulfilled. Standing by until tomorrow.")
            log.info(SEP)
            return state
        else:
            log.info(f"Resuming today's work! In progress: {ok_shorts_count}/10 shorts, kids={kids_ok}, long={long_ok}")
    else:
        log.info(f"Starting fresh cycle for new day: {today}")
        state = {
            "date": today,
            "status": "IN_PROGRESS",
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "shorts": {},
            "kids_long_cartoon": {"status": "PENDING"},
            "thriller_long_video": {"status": "PENDING"},
        }
        save_state(state)

    yt = None if dry_run else get_youtube_service()
    if not dry_run:
        log.info(f"YouTube API: {'Connected' if yt else 'Offline (local save)'}")

    # ── Intelligence Layers (Audit, Diagnosis, Trending, Reel DNA, Strategy) ──
    audit = state.get("audit")
    diagnosis = state.get("diagnosis")
    trending = state.get("trending")
    reel_dna = state.get("reel_dna")
    strategy = state.get("strategy")

    if not (audit and diagnosis and trending and reel_dna and strategy):
        log.info("--- STEP 1: Analytics Audit ---")
        audit = audit_yesterday_analytics(yt)
        state["audit"] = audit
        save_state(state)

        log.info("--- STEP 2: Growth Diagnosis ---")
        diagnosis = gemini_diagnose_growth(audit)
        state["diagnosis"] = diagnosis
        save_state(state)

        log.info("--- STEP 3: Fetching Trending India ---")
        trending = fetch_trending_india(yt)
        state["trending"] = trending
        save_state(state)

        log.info("--- STEP 3b: Reel/Shorts Style DNA Analysis ---")
        reel_dna = analyze_reels_style(trending)
        state["reel_dna"] = reel_dna
        save_state(state)

        log.info("--- STEP 4: Adapting Strategy ---")
        strategy = analyze_and_adapt_strategy(audit, diagnosis, trending)
        strategy["reel_style_dna"] = reel_dna
        state["strategy"] = strategy
        save_state(state)
    else:
        log.info("Reusing cached strategy and Reel DNA for today.")

    log.info(f"Today's viral formula: {reel_dna.get('today_viral_formula', '')[:80]}")
    log.info(f"Visual DNA:  {reel_dna.get('visual_style', '')[:70]}")
    log.info(f"Hook pattern: {reel_dna.get('hook_formula', '')[:70]}")

    # ── STEP 5: Produce 10 Cartoon Shorts (Resumable) ─────────────────────────
    log.info("--- STEP 5: Producing 10 Reel-Style Cartoon Shorts ---")
    shorts_state = state.setdefault("shorts", {})
    from cartoon_agent import produce_cartoon_short, CARTOON_PILLARS_HI
    adapted_topics = strategy.get("shorts_topics", [])
    visual_dna     = reel_dna.get("pollinations_visual_dna", "")
    hook_formula   = reel_dna.get("hook_formula", "")
    script_style   = reel_dna.get("script_style", "")
    # --- Analytics improvement note (injected into every cartoon topic) ---
    growth_issues  = diagnosis.get("growth_issues", [])
    hook_formulas  = diagnosis.get("viral_hindi_hook_formulas", [])
    improvement_note = ""
    if growth_issues:
        fixes = "; ".join(g.get("fix", "") for g in growth_issues[:2])
        improvement_note += f" FIX: {fixes}."
    if hook_formulas:
        improvement_note += f" HOOK: {hook_formulas[0]}."
    if improvement_note:
        log.info(f"  Analytics improvement injected into topics: {improvement_note[:100]}")

    for idx in range(10):
        video_num = idx + 1
        short_key = str(video_num)
        existing = shorts_state.get(short_key)

        if existing and existing.get("status") == "OK":
            log.info(f"  [{video_num}/10] ALREADY DONE: {existing.get('title', '')[:50]} (ID: {existing.get('video_id')}). Skipping!")
            continue

        chosen_cat = "medical_biology_anomalies"
        chosen_topic = ""
        if idx < len(adapted_topics):
            cand_topic = adapted_topics[idx].get("topic", "")
            cand_cat = adapted_topics[idx].get("category", "medical_biology_anomalies")
            try:
                from yt_variety import variety_engine
                is_fresh, _ = variety_engine.is_fresh(topic=cand_topic)
            except Exception:
                is_fresh = True
            if is_fresh:
                chosen_topic = cand_topic
                chosen_cat = cand_cat

        if not chosen_topic:
            # Pick fresh topic rotating through CARTOON_PILLARS_HI
            try:
                from yt_variety import variety_engine
                for offset in range(len(CARTOON_PILLARS_HI)):
                    p_cat, p_topic = CARTOON_PILLARS_HI[(idx + offset) % len(CARTOON_PILLARS_HI)]
                    is_fresh, _ = variety_engine.is_fresh(topic=p_topic)
                    if is_fresh:
                        chosen_cat, chosen_topic = p_cat, p_topic
                        break
            except Exception:
                pass
            if not chosen_topic:
                chosen_cat, chosen_topic = CARTOON_PILLARS_HI[idx % len(CARTOON_PILLARS_HI)]

        cat_key, topic = chosen_cat, chosen_topic
        enriched_topic = topic

        out_path = BASE_DIR / f"cartoon_short_{video_num:02d}.mp4"
        log.info(f"  [{video_num}/10] Starting production: {topic[:50]}...")
        try:
            res = produce_cartoon_short(
                topic=enriched_topic, cat_key=cat_key, lang="hi",
                output_path=out_path, dry_run=dry_run, video_num=video_num
            )
            shorts_state[short_key] = res
            save_state(state)  # Immediate persistence to disk
            log.info(f"  [{video_num}/10] OK: {res.get('title', '')[:55]}")
        except Exception as e:
            log.error(f"  [{video_num}/10] FAILED: {e}")
            shorts_state[short_key] = {"status": "FAILED", "error": str(e), "num": video_num}
            save_state(state)

        if idx < 9:
            time.sleep(4)

    # ── STEP 6: Kids Educational Long Cartoon (Resumable) ────────────────────
    log.info("--- STEP 6: Kids Educational Long Cartoon ---")
    kids_entry = state.get("kids_long_cartoon", {})
    if kids_entry.get("status") == "OK":
        log.info(f"  Kids Cartoon ALREADY DONE: {kids_entry.get('title', '')[:50]}. Skipping!")
        kids_result = kids_entry
    else:
        kids_result = {"status": "SKIPPED"}
        try:
            from cartoon_agent import produce_kids_long_cartoon
            kids_topic     = strategy.get("kids_topic")
            kids_visual    = reel_dna.get("kids_visual_dna", "")
            enriched_kids  = f"{kids_topic}. Visual style: {kids_visual[:80]}."
            kids_out       = BASE_DIR / "kids_long_cartoon.mp4"
            kids_result    = produce_kids_long_cartoon(
                topic=enriched_kids, output_path=kids_out,
                dry_run=dry_run, lang="hi"
            )
            state["kids_long_cartoon"] = kids_result
            save_state(state)
            log.info(f"  Kids: {kids_result.get('title','')[:60]} -> {kids_result.get('video_id')}")
        except Exception as e:
            log.error(f"Kids cartoon failed: {e}")
            kids_result = {"status": "FAILED", "error": str(e)}
            state["kids_long_cartoon"] = kids_result
            save_state(state)

    # ── STEP 7: Thriller Long Video (Adults) (Resumable) ──────────────────────
    log.info("--- STEP 7: Thriller Long Video (Adults) ---")
    thriller_entry = state.get("thriller_long_video", {})
    if thriller_entry.get("status") == "OK":
        log.info(f"  Thriller Video ALREADY DONE: {thriller_entry.get('title', '')[:50]}. Skipping!")
        long_result = thriller_entry
    else:
        long_result = {"status": "SKIPPED"}
        try:
            long_topic = strategy.get("long_video_topic")
            best_cat   = diagnosis.get("best_performing_category", "thriller_dark_psychology")
            long_result = produce_long_video(
                yt, dry_run,
                {"best_performing_category": best_cat, "long_override_topic": long_topic}
            )
            state["thriller_long_video"] = long_result
            save_state(state)
            log.info(f"  Long: {long_result.get('status')} -> {long_result.get('video_id','')}")
        except Exception as e:
            log.error(f"Long video failed: {e}")
            long_result = {"status": "FAILED", "error": str(e)}
            state["thriller_long_video"] = long_result
            save_state(state)

    # ── STEP 8: Mythology Shorts (5 divine Hindi reels) (Resumable) ───────────
    log.info("--- STEP 8: Mythology Shorts (5 divine Hindi reels with AI visuals) ---")
    myth_state = state.get("mythology_shorts", {})
    myth_ok = sum(1 for v in myth_state.values() if isinstance(v, dict) and v.get("status") == "OK")
    if myth_ok >= 5:
        log.info(f"  Mythology shorts ALREADY DONE ({myth_ok}/5). Skipping!")
    else:
        myth_state = produce_mythology_shorts(
            yt=yt, dry_run=dry_run, count=5, existing_state=myth_state
        )
        state["mythology_shorts"] = myth_state
        save_state(state)
        myth_ok = sum(1 for v in myth_state.values() if isinstance(v, dict) and v.get("status") == "OK")
        log.info(f"  Mythology: {myth_ok}/5 uploaded")

    # ── STEP 8: Save comprehensive daily report ───────────────────────────────
    elapsed = time.time() - start
    shorts_list = list(state.get("shorts", {}).values())
    ok_shorts = sum(1 for r in shorts_list if isinstance(r, dict) and r.get("status") == "OK")
    ok_kids   = 1 if state.get("kids_long_cartoon", {}).get("status") == "OK" else 0
    ok_long   = 1 if state.get("thriller_long_video", {}).get("status") == "OK" else 0
    ok_myth   = sum(1 for v in state.get("mythology_shorts", {}).values()
                    if isinstance(v, dict) and v.get("status") == "OK")
    total_ok  = ok_shorts + ok_kids + ok_long + ok_myth

    if ok_shorts >= 10 and ok_kids == 1 and ok_long == 1 and ok_myth >= 5:
        state["status"] = "COMPLETED"
        state["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_state(state)

    report = {
        "date":                     today,
        "run_time_local":           datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_runtime_minutes":    round(elapsed / 60, 1),
        "dry_run":                  dry_run,
        "status":                   state.get("status"),
        "analytics_audit_summary":  audit.get("summary", {}) if isinstance(audit, dict) else {},
        "growth_issues":            diagnosis.get("growth_issues", []) if isinstance(diagnosis, dict) else [],
        "analytics_fixes_applied":  improvement_note[:200] if improvement_note else "none",
        "trending_india_today":     [t.get("title", "")[:60] for t in trending[:10]] if isinstance(trending, list) else [],
        "reel_style_dna":           reel_dna,
        "strategy": {
            "winner_type":   strategy.get("winner_type") if isinstance(strategy, dict) else None,
            "loser_type":    strategy.get("loser_type") if isinstance(strategy, dict) else None,
            "today_trend":   strategy.get("today_trend") if isinstance(strategy, dict) else None,
            "strategy_note": strategy.get("strategy_note") if isinstance(strategy, dict) else None,
        },
        "cartoon_shorts_produced":  ok_shorts,
        "cartoon_short_results":    shorts_list,
        "kids_long_cartoon":        state.get("kids_long_cartoon"),
        "thriller_long_video":      state.get("thriller_long_video"),
        "mythology_shorts_produced":ok_myth,
        "mythology_short_results":  list(state.get("mythology_shorts", {}).values()),
        "total_videos_posted":      total_ok,
    }

    existing_reports = []
    if REPORT_FILE.exists():
        try:
            existing_reports = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    if not isinstance(existing_reports, list):
        existing_reports = [existing_reports]
    existing_reports = [r for r in existing_reports if r.get("date") != today]
    existing_reports.append(report)
    REPORT_FILE.write_text(json.dumps(existing_reports, indent=2, ensure_ascii=False), encoding="utf-8")

    log.info(SEP)
    log.info(f"  AUTOPILOT RUN STATUS  |  {today}")
    log.info(f"  Overall Status:       {state.get('status')}")
    log.info(f"  Cartoon Shorts:       {ok_shorts}/10 uploaded")
    log.info(f"  Mythology Reels:      {ok_myth}/5  uploaded")
    log.info(f"  Kids Long Cartoon:    {ok_kids}/1  uploaded")
    log.info(f"  Thriller Long:        {ok_long}/1  uploaded")
    log.info(f"  TOTAL POSTED:         {total_ok}/17")
    log.info(f"  Analytics fixes:      {improvement_note[:80] if improvement_note else 'none'}")
    log.info(f"  Runtime:              {elapsed/60:.1f} min")
    log.info(f"  State file:           {STATE_FILE}")
    log.info(SEP)
    return report


def run_daily(dry_run: bool = False):
    if not acquire_lock():
        return None
    try:
        return _run_daily_internal(dry_run=dry_run)
    finally:
        release_lock()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="No uploads, local only")
    args = parser.parse_args()
    run_daily(dry_run=args.dry_run)
