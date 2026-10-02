"""
Autonomous YouTube Shorts Production & Publishing CLI Agent
============================================================
A closed-loop, self-optimizing system that automates YouTube Shorts:
1. Analytics Audit of prior uploads
2. YouTube trend scraping
3. Gemini retention-optimized scriptwriting
4. Edge-TTS voice synthesis
5. Smart asset sourcing (Local personal assets -> Pexels vertical B-roll)
6. MoviePy 1080x1920 24fps vertical video rendering
7. YouTube Data API v3 Shorts distribution
8. Channel profile branding optimization tool
"""

import os
import sys
import json
import time
import random
import asyncio
import logging
from datetime import datetime
from pathlib import Path

# Safe UTF-8 encoding configuration for Windows terminals
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

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import requests
import schedule

# Voice & AI libraries
from google import genai
import edge_tts

# MoviePy imports (handling both MoviePy 2.x and MoviePy 1.x)
try:
    from moviepy import VideoFileClip, AudioFileClip, ImageClip, concatenate_videoclips
    import moviepy.video.fx as vfx
    MOVIEPY_V2 = True
except ImportError:
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, concatenate_videoclips
        import moviepy.video.fx.all as vfx
        MOVIEPY_V2 = False
    except ImportError as e:
        raise ImportError("MoviePy is required. Please install moviepy.") from e

# YouTube Data API client libraries
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# --- Configuration & Paths ---
BASE_DIR = Path(__file__).parent.resolve()
ENV_FILE = BASE_DIR / ".env"
HISTORY_FILE = BASE_DIR / "history.json"
CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
TOKEN_FILE = BASE_DIR / "token.json"
ASSETS_DIR = BASE_DIR / "assets"
PHOTOS_DIR = ASSETS_DIR / "my_photos"
VIDEOS_DIR = ASSETS_DIR / "my_videos"

OUTPUT_VOICE = BASE_DIR / "voice.mp3"
OUTPUT_BROLL = BASE_DIR / "pexels_broll.mp4"
OUTPUT_VIDEO = BASE_DIR / "final_short.mp4"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

# Ensure required directories exist
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize Gemini Client
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Preferred active Gemini models in priority order
GEMINI_MODELS = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.8-flash"]


# =====================================================================
# 1. MoviePy Adapter (Universal compatibility between v1 and v2)
# =====================================================================
def resize_clip(clip, **kwargs):
    if hasattr(clip, 'resized'):
        return clip.resized(**kwargs)
    return clip.resize(**kwargs)

def crop_clip(clip, **kwargs):
    if hasattr(clip, 'cropped'):
        return clip.cropped(**kwargs)
    return clip.crop(**kwargs)

def subclip_clip(clip, start, end):
    if hasattr(clip, 'subclipped'):
        return clip.subclipped(start, end)
    return clip.subclip(start, end)

def set_duration_clip(clip, duration):
    if hasattr(clip, 'with_duration'):
        return clip.with_duration(duration)
    return clip.set_duration(duration)

def set_audio_clip(clip, audio):
    if hasattr(clip, 'with_audio'):
        return clip.with_audio(audio)
    return clip.set_audio(audio)

def loop_clip(clip, duration):
    if hasattr(clip, 'with_effects') and hasattr(vfx, 'Loop'):
        return clip.with_effects([vfx.Loop(duration=duration)])
    elif hasattr(clip, 'loop'):
        return clip.loop(duration=duration)
    else:
        repeats = max(1, int(duration / max(clip.duration, 0.1)) + 1)
        extended = concatenate_videoclips([clip] * repeats)
        return subclip_clip(extended, 0, duration)


# =====================================================================
# 2. History & Performance Store
# =====================================================================
def load_history():
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "last_video_id": None,
        "last_title": None,
        "date": None,
        "videos": []
    }

def save_history(data):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        print(f"[Warning] Failed to write history.json: {e}")

def record_upload(video_id, title, metadata=None):
    hist = load_history()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hist["last_video_id"] = video_id
    hist["last_title"] = title
    hist["date"] = now_str
    if "videos" not in hist:
        hist["videos"] = []
    hist["videos"].append({
        "id": video_id,
        "title": title,
        "date": now_str,
        "topic": metadata.get("topic_used") if metadata else None,
        "tags": metadata.get("tags") if metadata else []
    })
    save_history(hist)


# =====================================================================
# 3. YouTube Authentication (with graceful Mock/Dry-Run Fallback)
# =====================================================================
def is_placeholder_client_secrets():
    """Detect if client_secrets.json is missing or contains placeholder values."""
    if not CLIENT_SECRETS_FILE.exists():
        return True
    try:
        with open(CLIENT_SECRETS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            if "YOUR_CLIENT_ID" in content or "YOUR_CLIENT_SECRET" in content:
                return True
    except Exception:
        return True
    return False

def get_youtube_service():
    """
    Returns an authenticated YouTube API service if credentials are configured,
    or None if running in mock/offline mode with placeholder secrets.
    """
    if is_placeholder_client_secrets() and not TOKEN_FILE.exists():
        print("\n[Auth Note] client_secrets.json is a placeholder. Operating in simulated YouTube Data API mode.")
        print("            To enable live uploads, paste your Google Cloud OAuth Client ID & Secret into client_secrets.json.")
        return None

    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), YOUTUBE_SCOPES)
        except Exception as e:
            print(f"[Auth] Could not load existing token.json: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"[Auth] Token refresh failed: {e}. Re-authenticating...")
                creds = None

        if not creds:
            if not CLIENT_SECRETS_FILE.exists() or is_placeholder_client_secrets():
                print("[Auth] No valid client_secrets.json found for new token generation. Using simulation mode.")
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_FILE), YOUTUBE_SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"[Auth Error] Interactive OAuth failed: {e}")
                return None

        try:
            with open(TOKEN_FILE, "w", encoding="utf-8") as token_f:
                token_f.write(creds.to_json())
        except OSError as e:
            print(f"[Warning] Failed to cache token.json: {e}")

    try:
        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f"[Auth Error] Could not initialize YouTube API client: {e}")
        return None


# =====================================================================
# 4. Analytics Audit & Trend Scout
# =====================================================================
def audit_previous_performance(youtube, video_id):
    """
    Queries YouTube Data API to analyze yesterday's video statistics (views, likes, comments).
    Falls back to history.json baseline if YouTube API is unavailable.
    """
    if not video_id:
        return {
            "status": "Day 1 Baseline",
            "notes": "No prior video recorded. Prioritize high-arousal hook."
        }

    if youtube:
        try:
            res = youtube.videos().list(part="statistics,snippet", id=video_id).execute()
            items = res.get("items", [])
            if items:
                snippet = items[0]["snippet"]
                stats = items[0]["statistics"]
                return {
                    "title": snippet.get("title", ""),
                    "views": int(stats.get("viewCount", "0")),
                    "likes": int(stats.get("likeCount", "0")),
                    "comments": int(stats.get("commentCount", "0")),
                    "status": "Live YouTube Analytics Retrieved"
                }
        except Exception as e:
            print(f"[Audit] Live query failed ({e}), using baseline log.")

    # Fallback to history log
    hist = load_history()
    return {
        "title": hist.get("last_title", "Previous Short"),
        "views": random.randint(120, 1850),
        "likes": random.randint(15, 230),
        "comments": random.randint(2, 45),
        "status": "Historical baseline simulated metrics"
    }

def get_current_trends(youtube, category_id="27"):
    """
    Scrapes top-ranking educational / mystery topics from YouTube's mostPopular chart,
    with an elite curated fallback list.
    """
    if youtube:
        try:
            res = youtube.videos().list(
                part="snippet",
                chart="mostPopular",
                regionCode="US",
                videoCategoryId=category_id,
                maxResults=5
            ).execute()
            titles = [item["snippet"]["title"] for item in res.get("items", [])]
            if titles:
                return titles
        except Exception as e:
            print(f"[Trends] Live trend query failed ({e}), using trending patterns fallback.")

    return [
        "Dark Psychology Secrets That Manipulate Your Decisions",
        "The Voynich Manuscript: Cryptographers Just Found Something",
        "Why Scientists Are Terrified of the Mariana Trench Mystery",
        "The Mandela Effect: Proof of Parallel Realities?",
        "Neuroscience Hack to Read Anyone's Subconscious Mind"
    ]


# =====================================================================
# 5. Script Engine with Gemini
# =====================================================================
def generate_optimized_content(last_perf, trends, user_directive=None):
    """
    Uses Gemini to critique yesterday's retention and craft a sub-60-word script
    with a 2-second pattern interrupt, seamless looping ending, and a 9:16 Pexels query.
    """
    if user_directive:
        mode_instruction = f"""
        *** USER COMMAND DIRECTIVE (HIGHEST PRIORITY) ***
        The user explicitly instructed the topic: "{user_directive}".
        Focus the entire video content on this exact topic while maximizing virality.
        """
    else:
        mode_instruction = """
        *** FULL AUTONOMOUS MODE ***
        Synthesize an irresistible mystery/education topic inspired by current trend patterns
        and psychological curiosity gaps.
        """

    prompt = f"""
    You are an elite YouTube Short-Form Retention Strategist and Viral Scriptwriter.

    YESTERDAY'S VIDEO METRICS:
    {json.dumps(last_perf, indent=2)}

    CURRENT TRENDING PATTERNS:
    {json.dumps(trends, indent=2)}

    {mode_instruction}

    ALGORITHMIC RETENTION & VIRALITY RULES:
    1. Pattern Interrupt Hook (0-2s): Start with a startling, counter-intuitive statement or immediate mystery. ZERO greetings or filler ("Hey guys", "Did you know", "Have you ever wondered"). Drop the viewer immediately into media res.
    2. Seamless Looping Ending: The final sentence MUST grammatically and thematically lead directly back into the opening hook sentence, creating an infinite retention loop for the YouTube Shorts algorithm.
    3. Script Length: Strictly under 60 spoken words (approximately 45-55 words).
    4. Visual Query: Exactly one ultra-specific, high-aesthetic search keyword for vertical 9:16 stock video (e.g. "deep ocean dark", "storm lightning night", "ancient dusty book", "neon microscope", "cyber brain glitch").

    OUTPUT ONLY RAW VALID JSON MATCHING THIS EXACT SCHEMA (no markdown fences, no extra text):
    {{
      "critique_of_yesterday": "1-2 sentence algorithmic diagnosis of prior retention and the specific hook adaptation used today",
      "topic_used": "Short concept name",
      "title": "High-CTR Title under 50 chars #Shorts",
      "description": "Compelling description with #shorts #viral #mystery #mindset",
      "tags": ["shorts", "mindset", "facts", "mystery", "viral"],
      "search_query": "one single video search keyword (e.g. storm, neon, space, deep ocean)",
      "script": "Narration text under 60 words."
    }}
    """

    last_error = None
    for attempt in range(2):
        for model_name in GEMINI_MODELS:
            try:
                response = ai_client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                raw_text = response.text.strip()
                # Clean possible markdown json fences
                cleaned = raw_text.replace("```json", "").replace("```", "").strip()
                # Handle potential outer braces extraction
                start_idx = cleaned.find("{")
                end_idx = cleaned.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    cleaned = cleaned[start_idx:end_idx + 1]

                data = json.loads(cleaned)
                # Validate required fields
                required_keys = ["critique_of_yesterday", "topic_used", "title", "description", "tags", "search_query", "script"]
                for k in required_keys:
                    if k not in data:
                        data[k] = ""
                return data
            except Exception as e:
                last_error = e
                time.sleep(1.5)
                continue

    raise RuntimeError(f"Gemini script generation failed across models: {last_error}")


# =====================================================================
# 6. Realistic Voiceover (Edge-TTS)
# =====================================================================
async def create_voiceover(text, output_path=OUTPUT_VOICE, voice="en-US-ChristopherNeural"):
    """
    Generates realistic voiceover using edge-tts (en-US-ChristopherNeural at +5% rate).
    """
    print(f"🎙️ Generating voiceover using {voice}...")
    comm = edge_tts.Communicate(text, voice=voice, rate="+5%")
    await comm.save(str(output_path))
    print(f"✅ Voiceover saved to {output_path}")
    return str(output_path)


# =====================================================================
# 7. Visual Asset Hierarchy & Pexels Sourcing
# =====================================================================
def get_personal_asset(target_duration=3.5):
    """
    Visual Asset Hierarchy:
    1. Checks assets/my_videos for vertical MP4/MOV clips.
    2. Checks assets/my_photos for PNG/JPG images.
    Returns a resized/cropped MoviePy clip, or None if empty.
    """
    # Check personal videos
    if VIDEOS_DIR.exists():
        video_files = [f for f in VIDEOS_DIR.iterdir() if f.suffix.lower() in ('.mp4', '.mov', '.mkv', '.webm')]
        if video_files:
            chosen = random.choice(video_files)
            print(f"📸 Sourcing custom local video: {chosen.name}")
            try:
                clip = VideoFileClip(str(chosen))
                sub_dur = min(clip.duration, target_duration)
                trimmed = subclip_clip(clip, 0, sub_dur)
                resized = resize_clip(trimmed, height=1920)
                cropped = crop_clip(resized, x_center=resized.w / 2, width=1080)
                return cropped
            except Exception as e:
                print(f"[Warning] Could not load local video {chosen}: {e}")

    # Check personal photos
    if PHOTOS_DIR.exists():
        photo_files = [f for f in PHOTOS_DIR.iterdir() if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp')]
        if photo_files:
            chosen = random.choice(photo_files)
            print(f"📸 Sourcing custom local photo: {chosen.name}")
            try:
                img_clip = ImageClip(str(chosen))
                timed_clip = set_duration_clip(img_clip, target_duration)
                resized = resize_clip(timed_clip, height=1920)
                cropped = crop_clip(resized, x_center=resized.w / 2, width=1080)
                return cropped
            except Exception as e:
                print(f"[Warning] Could not load local photo {chosen}: {e}")

    return None

def download_pexels_broll(query, output_path=OUTPUT_BROLL):
    """
    Downloads vertical 1080x1920 stock video from Pexels API matching the query.
    Falls back to atmospheric portrait B-roll if query returns no results.
    """
    print(f"🔍 Searching Pexels for 9:16 vertical B-roll: '{query}'...")
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={requests.utils.quote(query)}&orientation=portrait&per_page=5"

    video_link = None
    try:
        res = requests.get(url, headers=headers, timeout=15).json()
        videos = res.get("videos", [])
        if not videos:
            print("   [Pexels] Query had 0 results, attempting atmospheric fallback...")
            fb_url = "https://api.pexels.com/videos/search?query=cinematic+dark+smoke&orientation=portrait&per_page=3"
            res = requests.get(fb_url, headers=headers, timeout=15).json()
            videos = res.get("videos", [])

        if videos:
            files = videos[0].get("video_files", [])
            # Prioritize 1080x1920 or highest vertical HD
            hd_files = [f for f in files if f.get("width") == 1080 and f.get("height") == 1920]
            if hd_files:
                video_link = hd_files[0]["link"]
            else:
                # Find best portrait file
                portrait_files = [f for f in files if (f.get("height", 0) or 0) >= (f.get("width", 0) or 0)]
                if portrait_files:
                    best = max(portrait_files, key=lambda f: f.get("height", 0) or 0)
                    video_link = best.get("link")
                elif files:
                    video_link = files[0].get("link")

    except Exception as e:
        print(f"[Pexels Error] API request failed: {e}")

    if not video_link:
        print(f"⚠️ [Fallback] Pexels B-roll unavailable for '{query}'. Generating studio-grade Flux.1 base frame with Higgsfield camera motion...")
        try:
            from video_engine import _generate_pollinations_frame, _make_higgsfield_camera_clip
            temp_img = BASE_DIR / "temp_flux_base.jpg"
            prompt = f"{query}, shot on 35mm anamorphic lens, Arri Alexa 65, volumetric lighting, moody chiaroscuro, photorealistic 8k"
            success = _generate_pollinations_frame(prompt, scene_seed=int(time.time()), out_path=temp_img)
            if success and temp_img.exists():
                h_clip = _make_higgsfield_camera_clip(temp_img, duration=8.0, scene_idx=0)
                h_clip.write_videofile(str(output_path), fps=24, codec="libx264", logger=None)
                h_clip.close()
                temp_img.unlink(missing_ok=True)
                print(f"✅ Generated Higgsfield cinematic video from Flux.1 base frame -> {output_path}")
                return str(output_path)
        except Exception as gen_err:
            print(f"[Fallback Error] Flux generation fallback failed: {gen_err}")
        raise RuntimeError(f"Could not retrieve B-roll video from Pexels or Flux.1 for query: {query}")

    print("📥 Downloading B-roll video stream...")
    vid_data = requests.get(video_link, timeout=30).content
    with open(output_path, "wb") as f:
        f.write(vid_data)
    print(f"✅ B-roll downloaded ({len(vid_data) / 1024 / 1024:.1f} MB) to {output_path}")
    return str(output_path)


# =====================================================================
# 8. Video Assembly & Rendering (MoviePy 1080x1920 at 24fps)
# =====================================================================
def assemble_video(pexels_file=OUTPUT_BROLL, audio_file=OUTPUT_VOICE, output_file=OUTPUT_VIDEO):
    """
    Stitches audio and video clips, cropping/resizing to 1080x1920 (9:16) at 24fps.
    Integrates personal assets for opening hook if available.
    """
    print("🎞️ Assembling final 9:16 YouTube Short...")
    audio = AudioFileClip(str(audio_file))
    total_dur = audio.duration
    print(f"   Audio duration: {total_dur:.2f}s")

    personal_clip = get_personal_asset(target_duration=3.5)
    raw_pexels = VideoFileClip(str(pexels_file))

    # Resize and center crop Pexels video to 1080x1920
    pexels_resized = resize_clip(raw_pexels, height=1920)
    pexels_clip = crop_clip(pexels_resized, x_center=pexels_resized.w / 2, width=1080)

    if personal_clip:
        print("   Composing hybrid Short: Personal Hook + Pexels B-Roll")
        rem_dur = max(0.5, total_dur - personal_clip.duration)
        if pexels_clip.duration < rem_dur:
            bg_clip = loop_clip(pexels_clip, duration=rem_dur)
        else:
            bg_clip = subclip_clip(pexels_clip, 0, rem_dur)
        final_video = concatenate_videoclips([personal_clip, bg_clip], method="compose")
    else:
        print("   Using full Pexels B-roll background")
        if pexels_clip.duration < total_dur:
            final_video = loop_clip(pexels_clip, duration=total_dur)
        else:
            final_video = subclip_clip(pexels_clip, 0, total_dur)

    # Attach voiceover
    final_cut = set_audio_clip(final_video, audio)

    print(f"🎬 Rendering 1080x1920 @ 24fps to: {output_file}...")
    final_cut.write_videofile(
        str(output_file),
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None,
        ffmpeg_params=["-shortest", "-pix_fmt", "yuv420p"]
    )

    # Clean up MoviePy handles
    final_cut.close()
    audio.close()
    raw_pexels.close()
    if personal_clip:
        personal_clip.close()

    # Apply studio-grade photographic clarity, micro-contrast, and 35mm film grain grade
    try:
        from video_engine import apply_photographic_clarity_grade
        apply_photographic_clarity_grade(Path(output_file))
    except Exception:
        pass

    print(f"✅ Video render complete: {output_file}")
    return str(output_file)


# =====================================================================
# 9. YouTube Publishing & Channel Optimization
# =====================================================================
def upload_to_youtube(youtube, metadata, video_file=OUTPUT_VIDEO):
    """
    Publishes the rendered Short to YouTube as a Public Short with optimized title,
    description, and tags. Falls back to simulated upload if credentials are placeholder.
    """
    title = metadata.get("title", "Mysteries of the Universe #Shorts")
    description = metadata.get("description", "Daily mysteries and psychological insights. #shorts #viral")
    tags = metadata.get("tags", ["shorts", "mystery", "viral"])

    if not youtube:
        simulated_id = f"SIM_{int(time.time())}"
        print("\n" + "=" * 60)
        print("📢 [SIMULATED DISTRIBUTION] YouTube Client is in Local Demo Mode")
        print(f"Title:       {title}")
        print(f"Description: {description}")
        print(f"Tags:        {', '.join(tags)}")
        print(f"Video File:  {video_file}")
        print(f"Simulated ID: {simulated_id}")
        print("To publish live, replace client_secrets.json with your Google Cloud OAuth credentials.")
        print("=" * 60)
        return simulated_id

    print(f"🚀 Uploading Short to YouTube: '{title}'...")
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": "27"  # Education category
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(str(video_file), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"   Upload progress: {int(status.progress() * 100)}%")

    vid_id = response.get("id")
    print(f"\n🎉 Successfully Published to YouTube Shorts!")
    print(f"🔗 URL: https://youtube.com/shorts/{vid_id}")
    return vid_id

def optimize_profile(niche="Psychology facts, mindset shifts, and curiosity mysteries"):
    """
    Uses Gemini to rewrite channel branding (bio and SEO tags) and updates YouTube.
    """
    print(f"\n🎨 Optimizing Channel Profile for Niche: '{niche}'...")
    prompt = f"""
    Act as a World-Class YouTube Algorithm & Channel Branding Strategist.
    Write an optimized About bio and algorithmic channel keywords for a YouTube Shorts channel focused on: "{niche}".

    Rules:
    1. Bio: 2-3 short, ultra-engaging paragraphs with strong keywords and call-to-action to subscribe.
    2. Keywords: High-volume, comma/space-separated keyword phrases with quotation marks for multi-word tags.

    OUTPUT ONLY RAW VALID JSON MATCHING THIS SCHEMA:
    {{
      "description": "Engaging channel description here...",
      "keywords": "psychology \\"mindset shifts\\" mysteries facts \\"dark psychology\\""
    }}
    """

    data = None
    for model_name in GEMINI_MODELS:
        try:
            res = ai_client.models.generate_content(model=model_name, contents=prompt)
            cleaned = res.text.replace("```json", "").replace("```", "").strip()
            start_idx = cleaned.find("{")
            end_idx = cleaned.rfind("}")
            if start_idx != -1 and end_idx != -1:
                cleaned = cleaned[start_idx:end_idx + 1]
            data = json.loads(cleaned)
            break
        except Exception:
            continue

    if not data:
        print("[Error] Failed to generate branding optimization with Gemini.")
        return

    print("\n" + "=" * 55)
    print("✨ GENERATED CHANNEL BRANDING & SEO:")
    print("Description:\n", data.get("description"))
    print("\nKeywords:\n", data.get("keywords"))
    print("=" * 55)

    yt = get_youtube_service()
    if not yt:
        print("[Note] Ready to push to YouTube once client_secrets.json is authorized.")
        return

    try:
        channels = yt.channels().list(mine=True, part="id,brandingSettings").execute()
        items = channels.get("items", [])
        if not items:
            print("[Warning] No channel found associated with this Google Account.")
            return

        channel_id = items[0]["id"]
        body = {
            "id": channel_id,
            "brandingSettings": {
                "channel": {
                    "description": data["description"],
                    "keywords": data["keywords"],
                    "defaultLanguage": "en"
                }
            }
        }
        yt.channels().update(part="brandingSettings", body=body).execute()
        print(f"✅ Successfully updated channel profile for channel ID: {channel_id}")
    except Exception as e:
        print(f"[Error] Failed to push channel updates to YouTube API: {e}")

# Alias for backward compatibility
optimize_channel_profile = optimize_profile


# =====================================================================
# 10. Core Closed-Loop Pipeline Execution
# =====================================================================
def execute_pipeline(directive=None):
    """
    Executes the full end-to-end production cycle:
    Audit -> Trend Scraping -> Gemini Script -> Edge-TTS -> Asset Sourcing -> MoviePy Rendering -> YouTube Publish
    """
    start_time = time.time()
    print("\n" + "=" * 65)
    print(f"🚀 INITIATING AUTONOMOUS YOUTUBE SHORTS PIPELINE [{datetime.now().strftime('%H:%M:%S')}]")
    if directive:
        print(f"🎯 Directive: '{directive}'")
    else:
        print("🤖 Mode: Fully Autonomous Trend Synthesis")
    print("=" * 65)

    # Step 1: Authentication & History
    yt = get_youtube_service()
    history = load_history()
    last_id = history.get("last_video_id")

    # Step 2: Analytics Audit
    print("\n[Step 1/6] 📊 Auditing Previous Video Performance...")
    perf = audit_previous_performance(yt, last_id)
    print(f"   Audit Insight: {perf}")

    # Step 3: Trend Scraping
    print("\n[Step 2/6] 📈 Scraping Trending YouTube Patterns...")
    trends = get_current_trends(yt)
    for i, t in enumerate(trends[:3], 1):
        print(f"   {i}. {t}")

    # Step 4: Gemini Scriptwriting
    print("\n[Step 3/6] 🧠 Synthesizing Retention-Optimized Script with Gemini...")
    content = generate_optimized_content(perf, trends, user_directive=directive)
    print(f"   Topic:            {content.get('topic_used')}")
    print(f"   Hook Critique:    {content.get('critique_of_yesterday')}")
    print(f"   Title:            {content.get('title')}")
    print(f"   Pexels Query:     {content.get('search_query')}")
    print(f"   Script Spoken:    \"{content.get('script')}\"")

    # Step 5: Voiceover & B-roll
    print("\n[Step 4/6] 🎙️ Synthesizing Voiceover & Sourcing Visual Assets...")
    asyncio.run(create_voiceover(content["script"], output_path=OUTPUT_VOICE))
    download_pexels_broll(content["search_query"], output_path=OUTPUT_BROLL)

    # Step 6: Rendering
    print("\n[Step 5/6] 🎬 Rendering 1080x1920 Short via MoviePy...")
    assemble_video(pexels_file=OUTPUT_BROLL, audio_file=OUTPUT_VOICE, output_file=OUTPUT_VIDEO)

    # Step 7: Publishing & History
    print("\n[Step 6/6] 📤 Distributing to YouTube...")
    vid_id = upload_to_youtube(yt, content, video_file=OUTPUT_VIDEO)
    record_upload(vid_id, content["title"], metadata=content)

    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print(f"🏁 PIPELINE RUN COMPLETED IN {elapsed:.1f}s")
    print(f"🎉 Produced Video: {OUTPUT_VIDEO.resolve()}")
    print("=" * 65 + "\n")
    return vid_id


# =====================================================================
# 11. Dual-Mode Voice & CLI Listener
# =====================================================================
def check_microphone_available():
    """Checks if speech_recognition and working microphone hardware are present."""
    try:
        import speech_recognition as sr
        with sr.Microphone() as source:
            return True
    except (ImportError, AttributeError, OSError, Exception):
        return False


def run_scheduler(interval_hours=24):
    """Runs autonomous production loop on a recurring schedule."""
    print(f"\n⏰ Starting scheduled autonomous YouTube agent loop (every {interval_hours} hours)...")
    print("   Press Ctrl+C to cancel schedule.\n")
    schedule.every(interval_hours).hours.do(execute_pipeline)
    # Execute immediately on start
    try:
        execute_pipeline()
    except Exception as e:
        print(f"[Scheduled Run Error] {e}")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n🛑 Schedule loop stopped by user.")


def run_cli_listener():
    """
    Dual-mode trigger loop:
    - 'start': Completely autonomous trend-and-audit driven video generation.
    - 'start with [topic]': Prioritizes user's custom directive.
    - 'optimize [niche]': Optimize channel branding.
    - 'schedule' / 'loop': Run recurring autonomous loop.
    - 'exit': Terminate agent.
    - Seamless keyboard input fallback if no microphone is detected.
    """
    has_mic = check_microphone_available()
    recognizer = None
    if has_mic:
        import speech_recognition as sr
        recognizer = sr.Recognizer()

    print("\n" + "=" * 65)
    print("  🤖 AUTONOMOUS YOUTUBE SHORTS PRODUCTION AGENT")
    print("=" * 65)
    if has_mic:
        print("🎙️ Audio Mode: Microphone active.")
        print("   Say: 'START' or 'START WITH [topic]' (or Ctrl+C to type)")
    else:
        print("⌨️ Keyboard Mode: Microphone not detected. CLI prompt active.")
    print("\nAvailable Commands:")
    print("  • start                  -> Fully autonomous trend & audit production")
    print("  • start with <topic>     -> Generate video for custom topic")
    print("  • optimize [niche]       -> AI Channel branding optimization")
    print("  • schedule / loop        -> Run recurring automated production")
    print("  • exit / quit            -> Terminate agent")
    print("=" * 65 + "\n")

    while True:
        command = None
        if has_mic and recognizer:
            try:
                import speech_recognition as sr
                with sr.Microphone() as source:
                    print("\n🎤 Listening for voice command... (Press Ctrl+C to switch to typing)")
                    recognizer.adjust_for_ambient_noise(source, duration=0.6)
                    audio = recognizer.listen(source, phrase_time_limit=6)
                    command = recognizer.recognize_google(audio).strip().lower()
                    print(f"   Heard: '{command}'")
            except (sr.UnknownValueError, sr.WaitTimeoutError):
                continue
            except (OSError, KeyboardInterrupt):
                print("\n[Switching to terminal input mode]")
                has_mic = False

        if not command:
            try:
                command = input("\nAgent Command > ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print("\nShutting down Agent.")
                break

        if not command:
            continue

        if command in ("exit", "quit", "q"):
            print("👋 Exiting Autonomous YouTube Agent.")
            break
        elif command in ("help", "?"):
            print("\nAvailable Agent Commands:")
            print("  • start                  -> Fully autonomous trend & audit production")
            print("  • start with <topic>     -> Generate video for custom topic (e.g. 'start with Bermuda Triangle')")
            print("  • optimize [niche]       -> AI Channel branding optimization")
            print("  • schedule / loop        -> Start recurring autonomous schedule (daily)")
            print("  • exit / quit            -> Terminate agent")
        elif command in ("schedule", "loop"):
            run_scheduler(interval_hours=24)
        elif command.startswith("optimize"):
            niche = command.replace("optimize", "").replace("channel", "").replace("profile", "").strip()
            optimize_profile(niche if niche else "Psychology facts, mindset shifts, and curiosity mysteries")
        elif command.startswith("start with"):
            directive = command[len("start with"):].strip()
            try:
                execute_pipeline(directive=directive if directive else None)
            except Exception as e:
                print(f"[Error in pipeline] {e}")
        elif command == "start":
            try:
                execute_pipeline(directive=None)
            except Exception as e:
                print(f"[Error in pipeline] {e}")
        elif command.startswith("start"):
            directive = command.replace("start", "").strip()
            try:
                execute_pipeline(directive=directive if directive else None)
            except Exception as e:
                print(f"[Error in pipeline] {e}")
        else:
            print(f"Unknown command: '{command}'. Try 'start', 'start with [topic]', 'optimize', or 'exit'.")


if __name__ == "__main__":
    # Check if a command argument was passed directly (e.g. python autonomous_youtube_agent.py "start with Mars")
    if len(sys.argv) > 1:
        arg_cmd = " ".join(sys.argv[1:]).strip()
        if arg_cmd in ("--schedule", "-s", "schedule", "loop"):
            run_scheduler(interval_hours=24)
        elif arg_cmd.startswith("start with"):
            execute_pipeline(directive=arg_cmd[len("start with"):].strip())
        elif arg_cmd == "start":
            execute_pipeline(directive=None)
        elif arg_cmd.startswith("optimize"):
            niche = arg_cmd.replace("optimize", "").replace("profile", "").replace("channel", "").strip()
            optimize_profile(niche if niche else "Psychology facts, mindset shifts, and curiosity mysteries")
        else:
            run_cli_listener()
    else:
        run_cli_listener()
