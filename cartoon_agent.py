import os, sys, json, time, math, struct, wave, string, asyncio, argparse, urllib.parse, random
from pathlib import Path
from typing import List, Tuple, Dict, Any
from datetime import datetime

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

from dotenv import load_dotenv
load_dotenv()

BASE_DIR   = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
FRAMES_DIR = ASSETS_DIR / "cartoon_frames"
ASSETS_DIR.mkdir(exist_ok=True)
FRAMES_DIR.mkdir(exist_ok=True)

try:
    import imageio_ffmpeg
    _fe = imageio_ffmpeg.get_ffmpeg_exe()
    if os.path.exists(_fe):
        os.environ["IMAGEIO_FFMPEG_EXE"] = _fe
        _fd = str(Path(_fe).parent)
        if _fd not in os.environ.get("PATH", ""):
            os.environ["PATH"] = _fd + os.pathsep + os.environ.get("PATH", "")
except Exception:
    pass

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from google import genai
from google.genai import types
import edge_tts

try:
    from moviepy import (VideoClip, ImageClip, AudioFileClip, VideoFileClip, concatenate_videoclips,
                         CompositeVideoClip, CompositeAudioClip)
    import moviepy.video.fx as vfx
    MOVIEPY_V2 = True
except ImportError:
    from moviepy.editor import (VideoClip, ImageClip, AudioFileClip, VideoFileClip, concatenate_videoclips,
                                CompositeVideoClip, CompositeAudioClip)
    import moviepy.video.fx.all as vfx
    MOVIEPY_V2 = False

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ai_client      = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(
        timeout=20000,
        retry_options=types.HttpRetryOptions(attempts=1)
    )
)
GEMINI_MODELS  = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
HISTORY_FILE   = BASE_DIR / "history.json"
AVATAR_PATH    = ASSETS_DIR / "max_avatar.jpg"
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
import io as _io
import re as _re

# LOCKED CHARACTER DNA - inject into EVERY Pollinations prompt
CHARACTER_DNA = (
    "3D stylized cartoon character Max, bright neon-yellow hoodie, "
    "messy dark brown spiky hair, huge expressive Pixar-style animated eyes, "
    "round cute face, clean 3D octane render, vibrant cinematic studio lighting, "
    "vertical 9:16 framed shot, sharp focus, high detail"
)
CHARACTER_SEED = 12345

CARTOON_PILLARS_HI = [
    ("medical_biology_anomalies",
     "agar tum dry ice kha lo toh aapke andar kya hoga - Max ka hairan karne wala experiment"),
    ("survival_emergency_anatomy",
     "100 ghante jaagna - Max ke dimag aur aankhon mein kya hota hai jab neend nahi aati"),
    ("how_it_actually_works",
     "girte hue lift mein agar tum uchhal do toh kya bach sakte ho - Max ka darr"),
    ("extreme_physics_space_terrors",
     "quicksand mein Max phans gaya - nikalne ki koshish se aur gehra kyun dhasta hai"),
    ("medical_biology_anomalies",
     "brain freeze kyun hota hai - Max ne ice cream khayi aur dimag mein kya toofan aaya"),
    ("survival_emergency_anatomy",
     "samudra ka paani pina - Max kya soch raha tha aur uske sharir ne kya kiya"),
    ("bizarre_nature_monsters",
     "zeher wale keedey ne Max ki ungli kaati - andar kya ho raha hai ek second mein"),
    ("thriller_dark_psychology",
     "bleach aur cleaner mila diya Max ne band bathroom mein - 60 second mein kya hua"),
    ("extreme_physics_space_terrors",
     "nuclear flash seedha aankhon mein - Max ko 3 second mein kya hua"),
    ("medical_biology_anomalies",
     "danger zone mein pimple toda Max ne - triangle of death ka darr wala sach"),
]

CARTOON_PILLARS_EN = [
    ("medical_biology_anomalies",   "What actually happens inside your body if you swallow dry ice"),
    ("survival_emergency_anatomy",  "What happens to your brain if you stay awake for 100 hours"),
    ("how_it_actually_works",       "Why jumping inside a falling elevator will not save your life"),
    ("extreme_physics_space_terrors","The horrifying physics of what happens if you get trapped in quicksand"),
    ("medical_biology_anomalies",   "Why you get an instant brain freeze and the dangerous reflex behind it"),
    ("survival_emergency_anatomy",  "What happens if you drink sea water when stranded on an island"),
    ("bizarre_nature_monsters",     "What happens when a venomous centipede bites your thumb"),
    ("thriller_dark_psychology",    "The lethal mistake of mixing bleach and glass cleaner in a closed bathroom"),
    ("extreme_physics_space_terrors","What happens to your eyes if you stare directly at a nuclear flash"),
    ("medical_biology_anomalies",   "Why you should never pop a pimple inside the dangerous facial triangle"),
]


def build_avatar_watermark(size: int = 170) -> Image.Image:
    if not AVATAR_PATH.exists():
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([(0, 0), (size-1, size-1)], fill=(255, 230, 0, 220))
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size // 4)
        except Exception:
            font = ImageFont.load_default()
        draw.text((size//2, size//2), "MAX", anchor="mm", font=font, fill=(20, 20, 20, 255))
        return img
    avatar_raw = Image.open(str(AVATAR_PATH)).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([(0, 0), (size-1, size-1)], fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(avatar_raw, (0, 0), mask)
    bw = max(5, size // 32)
    ImageDraw.Draw(result).ellipse(
        [(bw//2, bw//2), (size-1-bw//2, size-1-bw//2)],
        outline=(255, 230, 0, 255), width=bw
    )
    pad = 16
    glow = Image.new("RGBA", (size + pad*2, size + pad*2), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        [(pad//2, pad//2), (size+pad*2-pad//2-1, size+pad*2-pad//2-1)],
        outline=(255, 230, 0, 90), width=10
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=5))
    final = Image.new("RGBA", (size + pad*2, size + pad*2), (0, 0, 0, 0))
    final.paste(glow, (0, 0), glow)
    final.paste(result, (pad, pad), result)
    return final


_AVATAR_WATERMARK = build_avatar_watermark(size=170)


def stamp_avatar(frame_img: Image.Image) -> Image.Image:
    fw, fh = frame_img.size
    aw, ah = _AVATAR_WATERMARK.size
    margin = 20
    x, y = fw - aw - margin, fh - ah - margin
    out = frame_img.convert("RGBA").copy()
    out.paste(_AVATAR_WATERMARK, (x, y), _AVATAR_WATERMARK)
    return out.convert("RGB")


def render_subtitle_badge(text: str, highlight_words: list, canvas_w: int = 1080) -> Image.Image:
    """Bold, high-contrast open MrBeast/Hormozi style captions.
    NO dark pill/box — text floats directly with thick stroke outline."""
    font_paths = ["C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arialbd.ttf",
                  "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arial.ttf"]
    font = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 64)
                break
            except Exception:
                continue
    if not font:
        font = ImageFont.load_default()
    words = text.strip().upper().split()  # ALL CAPS for impact
    lines, curr = [], []
    for w in words:
        curr.append(w)
        if len(curr) >= 3:  # 2-3 words per line for mobile readability
            lines.append(curr)
            curr = []
    if curr:
        lines.append(curr)
    dummy = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(dummy)
    space_w = d.textbbox((0, 0), " ", font=font)[2]
    line_h, pad_x, pad_y = 78, 30, 20
    line_mets = []
    max_w = 0
    for line in lines:
        lw = sum(d.textbbox((0,0),w,font=font)[2]-d.textbbox((0,0),w,font=font)[0] for w in line)
        lw += space_w * (len(line) - 1)
        max_w = max(max_w, lw)
        line_mets.append((line, lw))
    canvas_w_actual = int(min(canvas_w - 40, max_w + pad_x * 2))
    canvas_h = int(line_h * len(lines) + pad_y * 2)
    # Transparent canvas — NO pill/box background
    img = Image.new("RGBA", (canvas_w_actual, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    hl_clean = [h.lower().strip(string.punctuation) for h in highlight_words]
    stroke_width = 5
    for i, (line, lw) in enumerate(line_mets):
        cx = (canvas_w_actual - lw) / 2
        cy = pad_y + i * line_h
        for w in line:
            bb = d.textbbox((0, 0), w, font=font)
            ww = bb[2] - bb[0]
            is_hl = any(h in w.lower().strip(string.punctuation) for h in hl_clean) if hl_clean else False
            col = (255, 235, 30, 255) if is_hl else (255, 255, 255, 255)
            # Glow shadow layer
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    draw.text((cx + dx + 4, cy + dy + 4), w, font=font, fill=(0, 0, 0, 100))
            # Bold text with thick stroke
            draw.text((cx, cy), w, font=font, fill=col,
                      stroke_width=stroke_width, stroke_fill=(0, 0, 0, 255))
            cx += ww + space_w
    return img


def generate_cartoon_storyboard(topic: str, is_hindi: bool, cat_key: str) -> Dict[str, Any]:
    if is_hindi:
        lang_block = (
            "LANGUAGE HINDI ONLY:\n"
            "- voiceover: Pure Hindi Devanagari ONLY. Zero English.\n"
            "- subtitle_display: Punchy Hinglish (e.g. Andar ATTACK shuru 30 SECOND mein KHATARNAK)\n"
            "- title: Hindi under 50 chars\n"
            "- description: Hindi with hashtags shorts hindi viral animation\n"
            "- pollinations_prompt: ENGLISH ONLY for the image AI\n"
        )
        vo_ex = "Max ne jab dry ice khaaya, tab uske andar kya toofan aaya?"
        sub_ex = "Max ne DRY ICE khaaya - 30 SECOND mein KHATARNAK!"
    else:
        lang_block = "LANGUAGE ENGLISH: fast breathless thriller, max 12 words per scene."
        vo_ex = "Max just swallowed dry ice. Watch what happens next."
        sub_ex = "DRY ICE inside Max... INSTANT DANGER!"

    prompt = (
        "You are the Lead Creative Director of top-tier 3D viral animation channels like Zack D. Films.\n"
        f"CHARACTER BIBLE: {CHARACTER_DNA!r}\n"
        f"TOPIC: {topic!r}\nCATEGORY: {cat_key}\n\n"
        f"{lang_block}\n\n"
        "ABSOLUTE RULE - VOICEOVER FIELD PURITY (CRITICAL):\n"
        "The 'voiceover' field contains ONLY the exact words the narrator speaks aloud to the audience.\n"
        "ABSOLUTELY FORBIDDEN in 'voiceover': visual cues, camera directions, bracketed tags like [Cut to],\n"
        "checkmark text like 'bada check mark', cutaway references like 'teen D cutaway dekho',\n"
        "3D/animation references, scene descriptions, infographic labels, overlay instructions,\n"
        "pollinations prompts, or ANY text intended for the image/video generator pipeline.\n"
        "All visual directions go EXCLUSIVELY into 'pollinations_prompt'. These are two SEPARATE pipelines.\n\n"
        "STRICT ZACK D. FILMS PICTORIAL DIRECTIVE (MANDATORY):\n"
        "Every single scene MUST be a LITERAL PICTORIAL AND INSTRUCTIONAL DEMONSTRATION of the action being described.\n"
        "- NEVER create generic scenes like 'Max looking terrified', 'Max shocked', or plain face close-ups. This is STRICTLY FORBIDDEN.\n"
        "- 1:1 VISUAL-VERBAL MIRRORING: If the voiceover says 'lie flat on the floor', the visual MUST show Max lying completely flat on his back on the floor, hands behind head, side cutaway view.\n"
        "- MISTAKE VS SOLUTION INFOGRAPHICS: If the scene explains a dangerous mistake (e.g. jumping in a falling elevator), show the character in mid-jump with a bold red ❌ indicator and skeletal stress fractures. If it explains the solution, show the exact correct posture with a glowing green ✔️ checkmark.\n"
        "- 3D ANATOMICAL & PHYSICAL CUTAWAYS: Show semi-transparent internal anatomy, glowing force arrows showing impact dissipation, expanding gases, or internal organ reactions in full 3D octane render.\n"
        "- Clear camera angles: isometric cutaways, side-profile mechanical cross-sections, or macro action framing.\n\n"
        "Write a 5-scene viral storyboard for Max:\n"
        "Scene 1: The Sudden Crisis - Max inside the exact environment mid-crisis (e.g. elevator cable fraying and snapping with high-tension sparks).\n"
        "Scene 2: The Fatal Mistake - What most people do wrong, visual red ❌ graphic showing catastrophic bone/muscle stress or immediate failure.\n"
        "Scene 3: The True Action / Technique - Literal step-by-step physical demonstration of the exact survival or correct posture with green ✔️ checkmark.\n"
        "Scene 4: The Internal Science/Mechanism - 3D anatomical cutaway showing force distribution, organ defense, or biological reaction.\n"
        "Scene 5: The Loop Reveal - Final essential safety rule or shocking fact connecting seamlessly back to Scene 1.\n\n"
        "Every 'pollinations_prompt' MUST begin with the full CHARACTER_DNA, followed by the EXACT PHYSICAL ACTION, environment cutaway, anatomical details, and visual indicators.\n\n"
        'OUTPUT ONLY RAW JSON with fields: title, description, tags (list), is_hindi (bool), '
        'scenes (list of 5 objects each with: scene_id, voiceover, subtitle_display, highlight_words, pollinations_prompt)'
    )

    for model in GEMINI_MODELS:
        try:
            resp = ai_client.models.generate_content(model=model, contents=prompt)
            raw = resp.text.strip().replace("```json", "").replace("```", "").strip()
            s, e = raw.find("{"), raw.rfind("}")
            if s != -1 and e != -1:
                data = json.loads(raw[s:e+1])
                if "scenes" in data and len(data["scenes"]) >= 4:
                    # Normalize: ensure every scene has all required fields
                    data["scenes"] = _normalize_cartoon_scenes(
                        data["scenes"], topic, cat_key, is_hindi
                    )
                    print(f"   [Storyboard] {model} -> {len(data['scenes'])} scenes OK")
                    return data
        except Exception as ex:
            print(f"   [Storyboard] {model} failed: {ex}")
            time.sleep(1)

    print(f"   [Storyboard] Using dynamic high-retention fallback storyboard for: {topic[:40]}...")
    return _build_cartoon_fallback(topic, cat_key, is_hindi)


def _normalize_cartoon_scenes(
    scenes: List[Dict],
    topic: str,
    cat_key: str,
    is_hindi: bool
) -> List[Dict]:
    """Ensure every cartoon scene has all required fields, pad to 5 scenes."""
    result = []
    for i, scene in enumerate(scenes[:5]):
        sc = dict(scene)
        sc.setdefault("scene_id", i + 1)
        if not sc.get("voiceover", "").strip():
            sc["voiceover"] = f"Scene {i+1}: {topic[:50]}"
        if not sc.get("subtitle_display", "").strip():
            sc["subtitle_display"] = sc["voiceover"][:60]
        if not sc.get("highlight_words"):
            words = sc["voiceover"].split()
            sc["highlight_words"] = [w for w in words if len(w) > 5][:2] or [words[0]]
        if not sc.get("pollinations_prompt", "").strip():
            sc["pollinations_prompt"] = (
                f"{CHARACTER_DNA}, Max in dramatic action scene {i+1} for topic: {topic[:40]}, "
                f"3D Pixar style, vibrant cinematic lighting, vertical 9:16"
            )
        result.append(sc)
    # Pad to 5 scenes if needed
    fallback = _build_cartoon_fallback(topic, cat_key, is_hindi)
    while len(result) < 5:
        result.append(fallback["scenes"][len(result)])
    return result[:5]


def _build_cartoon_fallback(topic: str, cat_key: str, is_hindi: bool) -> Dict[str, Any]:
    """Build a complete 5-scene storyboard fallback with topic-specific content."""
    title = f"{topic[:65]} 😱 #Shorts"
    if is_hindi:
        desc = f"{topic}. Max ke saath dekhiye! #shorts #viral #hindi"
        tags = ["shorts", "viral", "hindi", "facts", "max cartoon", "thriller"]
        scenes_data = [
            {
                "scene_id": 1,
                "voiceover": f"क्या आप जानते हैं कि {topic[:40]} का सच इतना खतरनाक है?",
                "subtitle_display": "Kya aap jaante hain? KHATARNAK SACH!",
                "highlight_words": ["KHATARNAK", "SACH"],
                "pollinations_prompt": f"{CHARACTER_DNA}, Max shocked mid-crisis facing dangerous situation: {topic[:35]}, dramatic red lighting, 3D Pixar octane render, vertical 9:16"
            },
            {
                "scene_id": 2,
                "voiceover": f"अक्सर लोग गलती करते हैं - Max भी यही गलती करने वाला था! ✕",
                "subtitle_display": "Galat kaam! RED ❌ WARNING!",
                "highlight_words": ["Galat", "WARNING"],
                "pollinations_prompt": f"{CHARACTER_DNA}, Max doing the WRONG action with bold red ❌ overlay, skeleton stress fracture lines visible, 3D anatomical infographic, dark dramatic lighting, vertical 9:16"
            },
            {
                "scene_id": 3,
                "voiceover": f"सही तरीका है: Max ने सही पोज़चर लिया और नतीजा चौंकाने वाला रहा! ✔️",
                "subtitle_display": "Sahi tarika! GREEN ✔️ SAFE!",
                "highlight_words": ["Sahi", "SAFE"],
                "pollinations_prompt": f"{CHARACTER_DNA}, Max in CORRECT survival posture with glowing green ✔️ checkmark, step-by-step action demonstration infographic, 3D Pixar render, bright hopeful lighting, vertical 9:16"
            },
            {
                "scene_id": 4,
                "voiceover": f"शरीर के अंदर क्या हो रहा है - 3D कटअवे देखो!",
                "subtitle_display": "Andar kya hua? 3D CUTAWAY!",
                "highlight_words": ["Andar", "CUTAWAY"],
                "pollinations_prompt": f"{CHARACTER_DNA}, 3D anatomical semi-transparent cutaway of human body showing internal reaction for {topic[:30]}, glowing organs, force distribution arrows, octane render, vertical 9:16"
            },
            {
                "scene_id": 5,
                "voiceover": f"इसिलिए हमेशा याद रखो - {topic[:30]}. Comment में बताओ!",
                "subtitle_display": "Yaad rakho! Like aur Subscribe!",
                "highlight_words": ["Yaad", "Subscribe"],
                "pollinations_prompt": f"{CHARACTER_DNA}, Max pointing at viewer with confident smile, neon-glow subscribe button visual, dramatic reveal lighting, 3D Pixar style, vertical 9:16"
            },
        ]
    else:
        desc = f"{topic}. Watch what happens next! #shorts #viral #science"
        tags = ["shorts", "viral", "science", "facts", "max cartoon", "thriller"]
        scenes_data = [
            {
                "scene_id": 1,
                "voiceover": f"What actually happens when {topic[:40]}? The truth is terrifying.",
                "subtitle_display": "The TERRIFYING truth!",
                "highlight_words": ["TERRIFYING", "truth"],
                "pollinations_prompt": f"{CHARACTER_DNA}, Max shocked mid-crisis facing dangerous situation: {topic[:35]}, dramatic red lighting, 3D Pixar octane render, vertical 9:16"
            },
            {
                "scene_id": 2,
                "voiceover": f"Most people make this fatal mistake - Max almost did too! ❌",
                "subtitle_display": "FATAL mistake! RED ❌ WARNING!",
                "highlight_words": ["FATAL", "WARNING"],
                "pollinations_prompt": f"{CHARACTER_DNA}, Max doing the WRONG action with bold red ❌ overlay, skeleton stress fracture lines visible, 3D anatomical infographic, dark dramatic lighting, vertical 9:16"
            },
            {
                "scene_id": 3,
                "voiceover": f"Here's the correct technique: Max showed us the right way! ✔️",
                "subtitle_display": "Correct technique! GREEN ✔️",
                "highlight_words": ["correct", "technique"],
                "pollinations_prompt": f"{CHARACTER_DNA}, Max in CORRECT survival posture with glowing green ✔️ checkmark, step-by-step action demonstration infographic, 3D Pixar render, bright hopeful lighting, vertical 9:16"
            },
            {
                "scene_id": 4,
                "voiceover": f"Inside your body, a catastrophic chain reaction begins - see the 3D cutaway!",
                "subtitle_display": "Inside body CHAIN REACTION!",
                "highlight_words": ["CHAIN", "REACTION"],
                "pollinations_prompt": f"{CHARACTER_DNA}, 3D anatomical semi-transparent cutaway of human body showing internal reaction for {topic[:30]}, glowing organs, force distribution arrows, octane render, vertical 9:16"
            },
            {
                "scene_id": 5,
                "voiceover": f"Remember this fact always. Now you know the truth about {topic[:25]}!",
                "subtitle_display": "Remember this ALWAYS!",
                "highlight_words": ["Remember", "ALWAYS"],
                "pollinations_prompt": f"{CHARACTER_DNA}, Max pointing at viewer with confident smile, neon-glow subscribe button visual, dramatic reveal lighting, 3D Pixar style, vertical 9:16"
            },
        ]
    return {
        "title": title,
        "description": desc,
        "tags": tags,
        "is_hindi": is_hindi,
        "scenes": scenes_data,
    }


# Per-scene Pexels search queries for visually-rich video and photography fallback imagery
_PEXELS_CARTOON_QUERIES = [
    "dramatic lightning face closeup dark cinematic portrait",
    "danger warning sign red glow dark dramatic",
    "correct solution green checkmark bright hopeful",
    "body anatomy 3d medical science glowing xray",
    "sunrise golden silhouette mountain dramatic cinematic",
]

_PEXELS_VIDEO_QUERIES = [
    "dramatic lightning storm dark portrait cinematic",
    "warning danger crimson dark portrait",
    "success green light explosion hopeful portrait",
    "futuristic 3d medical science glowing xray portrait",
    "golden sunset mountain dramatic portrait cinematic",
]

# Per-scene color palettes for Tier 4 procedural fallback (vibrant, never black)
_SCENE_PALETTES = [
    ((60, 10, 10), (255, 50, 30)),       # Scene 1: Fiery Crimson (Hook/Crisis)
    ((50, 15, 5),  (255, 130, 15)),       # Scene 2: Warning Amber (Mistake)
    ((5, 40, 20),  (30, 220, 80)),        # Scene 3: Success Green (Solution)
    ((15, 5, 50),  (120, 50, 240)),       # Scene 4: Cosmic Purple (Internal)
    ((50, 40, 5),  (255, 215, 30)),       # Scene 5: Golden Reveal (Climax)
]


def generate_cartoon_frames(scenes: List[Dict], video_seed: int) -> List[Path]:
    print(f"\n Generating {len(scenes)} media assets (Pollinations AI -> Pexels Video -> Pexels 4K Photo -> Procedural)...")
    frame_paths = []
    pollinations_exhausted = False  # Once rate-limited, skip Pollinations for remaining scenes

    for i, scene in enumerate(scenes):
        poll_prompt = scene.get("pollinations_prompt", "")
        if not poll_prompt or CHARACTER_DNA[:20] not in poll_prompt:
            poll_prompt = f"{CHARACTER_DNA}, Max emotional expression for scene {i+1}, 3D Pixar style"
        encoded = urllib.parse.quote(poll_prompt)
        scene_seed = video_seed + i * 7
        out_jpg = FRAMES_DIR / f"frame_{video_seed}_{i+1}.jpg"
        out_mp4 = FRAMES_DIR / f"frame_{video_seed}_{i+1}.mp4"
        print(f"   Scene {i+1}: seed={scene_seed} '{poll_prompt[:55]}...'")
        downloaded = False

        # ── Tier 1: Pollinations AI Image (skip if already rate-limited) ──
        if not pollinations_exhausted:
            urls_to_try = [
                f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&model=turbo&nologo=true&seed={scene_seed}",
                f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&model=flux&nologo=true&seed={scene_seed}&enhance=true",
                f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={scene_seed}",
            ]
            for attempt, url in enumerate(urls_to_try):
                try:
                    r = requests.get(url, timeout=40)
                    if r.status_code == 200 and len(r.content) > 4000:
                        pil = Image.open(_io.BytesIO(r.content)).convert("RGB").resize((1080, 1920), Image.LANCZOS)
                        stamped = stamp_avatar(pil)
                        stamped.save(str(out_jpg), quality=92)
                        frame_paths.append(out_jpg)
                        print(f"   Media {i+1} OK via Pollinations AI Image ({len(r.content)//1024}KB)")
                        downloaded = True
                        time.sleep(4)  # Respect rate limit between successful requests
                        break
                    elif r.status_code in (402, 429):
                        print(f"   Pollinations rate-limited ({r.status_code}), switching to Pexels HD Video & 4K Photo for remaining scenes")
                        pollinations_exhausted = True
                        break  # Don't retry other Pollinations URLs
                    else:
                        print(f"   Pollinations attempt {attempt+1} status={r.status_code}")
                        time.sleep(2)
                except Exception as ex:
                    print(f"   Pollinations attempt {attempt+1}: {ex}")
                    time.sleep(2)

        # ── Tier 2: Free Pexels HD Motion Video Clips ──
        if not downloaded and PEXELS_API_KEY:
            try:
                vq = _PEXELS_VIDEO_QUERIES[i % len(_PEXELS_VIDEO_QUERIES)]
                v_api = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(vq)}&orientation=portrait&per_page=3"
                vr = requests.get(v_api, headers={"Authorization": PEXELS_API_KEY}, timeout=10).json()
                videos = vr.get("videos", [])
                if videos:
                    target_vid = videos[i % len(videos)]
                    video_files = target_vid.get("video_files", [])
                    matched_link = None
                    for vf in video_files:
                        if vf.get("width") and vf.get("height") and vf.get("height") >= vf.get("width"):
                            matched_link = vf.get("link")
                            break
                    if not matched_link and video_files:
                        matched_link = video_files[0].get("link")
                    if matched_link:
                        v_resp = requests.get(matched_link, stream=True, timeout=20)
                        if v_resp.status_code == 200:
                            with open(out_mp4, "wb") as f_out:
                                for chunk in v_resp.iter_content(chunk_size=128*1024):
                                    f_out.write(chunk)
                            frame_paths.append(out_mp4)
                            print(f"   Media {i+1} OK via Pexels Free HD Video ({os.path.getsize(out_mp4)//1024}KB MP4)")
                            downloaded = True
            except Exception as ex:
                print(f"   Pexels video fallback error: {ex}")

        # ── Tier 3: Pexels 4K Cinematic Photography ──
        if not downloaded and PEXELS_API_KEY:
            try:
                q = _PEXELS_CARTOON_QUERIES[i % len(_PEXELS_CARTOON_QUERIES)]
                p_url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(q)}&orientation=portrait&per_page=3"
                pr = requests.get(p_url, headers={"Authorization": PEXELS_API_KEY}, timeout=10).json()
                photos = pr.get("photos", [])
                if photos:
                    photo_idx = i % len(photos)
                    p_img_url = photos[photo_idx]["src"].get("large2x") or photos[photo_idx]["src"].get("original")
                    content = requests.get(p_img_url, timeout=15).content
                    pil = Image.open(_io.BytesIO(content)).convert("RGB").resize((1080, 1920), Image.LANCZOS)
                    c_bg, c_fg = _SCENE_PALETTES[i % len(_SCENE_PALETTES)]
                    overlay = Image.new("RGB", (1080, 1920), c_fg)
                    pil = Image.blend(pil, overlay, alpha=0.15)
                    stamped = stamp_avatar(pil)
                    stamped.save(str(out_jpg), quality=92)
                    frame_paths.append(out_jpg)
                    print(f"   Media {i+1} OK via Pexels 4K Photo ({len(content)//1024}KB)")
                    downloaded = True
            except Exception as ex:
                print(f"   Pexels photo fallback error: {ex}")

        # ── Tier 4: Vibrant Procedural Art (NEVER black — bright colorful radial burst) ──
        if not downloaded:
            c_bg, c_fg = _SCENE_PALETTES[i % len(_SCENE_PALETTES)]
            fb = Image.new("RGB", (1080, 1920), c_bg)
            draw_fb = ImageDraw.Draw(fb)
            cx, cy = 540, 960
            # Starburst rays
            for ang in range(0, 360, 12):
                rad_a = math.radians(ang)
                x2 = cx + int(1200 * math.cos(rad_a))
                y2 = cy + int(1200 * math.sin(rad_a))
                ray_col = (min(255, c_fg[0] + 30), min(255, c_fg[1] + 30), min(255, c_fg[2] + 30))
                draw_fb.line([(cx, cy), (x2, y2)], fill=ray_col, width=10)
            # Bright radial gradient
            for r in range(500, 0, -20):
                alpha = 1.0 - (r / 500)
                col = (
                    int(c_bg[0] + (c_fg[0] - c_bg[0]) * alpha),
                    int(c_bg[1] + (c_fg[1] - c_bg[1]) * alpha),
                    int(c_bg[2] + (c_fg[2] - c_bg[2]) * alpha),
                )
                draw_fb.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=col)
            stamped = stamp_avatar(fb)
            stamped.save(str(out_jpg), quality=92)
            frame_paths.append(out_jpg)
            print(f"   Media {i+1} OK via vibrant procedural art (Scene {i+1} palette)")
    return frame_paths


async def _synth_voice_async(text: str, voice: str, out: Path) -> list:
    comm = edge_tts.Communicate(text, voice, rate="+5%")
    boundaries = []
    with open(out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                boundaries.append((chunk["offset"] / 1e7, chunk["duration"] / 1e7, chunk["text"]))
    return boundaries


def _clean_voiceover_text(text: str, is_hindi: bool) -> str:
    """Comprehensive voiceover sanitizer: strips ALL non-spoken content.
    Removes: visual cues, camera directions, bracketed tags, emoji indicators,
    English metadata bleed, image prompt artifacts, checkmark references."""
    # Remove bracketed directions: [Cut to 3D], [Scene 2], [HOOK], etc.
    text = _re.sub(r'\[.*?\]', '', text)
    # Remove parenthesized visual directions
    text = _re.sub(r'\((?:close[- ]?up|zoom|pan|cut|fade|transition|overlay|b-roll|visual|camera|angle|shot|scene|wide|medium|insert|montage|slow[- ]?mo).*?\)', '', text, flags=_re.IGNORECASE)
    # Remove visual cue phrases leaked from prompts
    _vo_cue_patterns = [
        r'(?:bada|badi|chota|chhota)?\s*check\s*mark',
        r'(?:teen\s*)?[23]\s*[dD]\s*(?:cut\s*away|cutaway|animation|render|cross[- ]?section|model)',
        r'cut\s*(?:to|away)\s+(?:dekho|dikhao|dekhiye|dekhein)',
        r'(?:Visual|Camera|Shot|Scene)\s*(?:style|direction|description|note|cue)\s*:.*?(?=\.|$)',
        r'(?:FIX|HOOK|IMPROVEMENT|STRATEGY|VISUAL DNA|USE THIS)\s*:.*?(?=\.|$)',
        r'Hook\s*:.*?(?=\.|$)',
        r'Script\s*tone\s*:.*?(?=\.|$)',
        r'pollinations.*?(?:prompt|image)',
        r'infographic\s*(?:style|cue|overlay)',
        r'overlay\s+(?:text|graphic|badge)',
        r'subtitle[_ ]?display',
        r'visual[_ ]?query',
        r'scene[_ ]?(?:description|direction)',
    ]
    for pattern in _vo_cue_patterns:
        text = _re.sub(pattern, '', text, flags=_re.IGNORECASE)
    # Remove injected English metadata
    text = _re.sub(r'Visual style:.*?(?=\.|$)', '', text)
    # Remove emoji characters that TTS can't handle
    text = _re.sub(r'[\U00010000-\U0010ffff]', '', text)
    text = _re.sub(r'[\u2715\u2714\ufe0f\u274c\u2713\u2717\u26a0\ufe0f]', '', text)
    # Remove markdown formatting
    text = _re.sub(r'[*_~`#>]', '', text)
    # Remove excess whitespace and dots
    text = _re.sub(r'\s{2,}', ' ', text)
    text = _re.sub(r'\.{2,}', '.', text)
    text = _re.sub(r'-{2,}', '\u2014', text)
    return text.strip()


def synthesize_voiceover(scenes: List[Dict], is_hindi: bool, out_path: Path):
    voice = "hi-IN-MadhurNeural" if is_hindi else "en-US-ChristopherNeural"
    # Clean each scene's voiceover before concatenating
    cleaned_parts = []
    for s in scenes:
        raw = s["voiceover"].strip()
        cleaned = _clean_voiceover_text(raw, is_hindi)
        if cleaned:
            cleaned_parts.append(cleaned)
    full_text = " ".join(cleaned_parts)
    print(f"\n [Voice] {voice} +5% speed (natural expressive pacing)...")
    print(f"   TTS text ({len(full_text)} chars): {full_text[:120]}...")
    boundaries = asyncio.run(_synth_voice_async(full_text, voice, out_path))
    ac = AudioFileClip(str(out_path))
    total = float(ac.duration)
    ac.close()
    timings = []
    for i in range(len(scenes)):
        if i < len(boundaries):
            start = boundaries[i][0]
            end = boundaries[i + 1][0] if i + 1 < len(boundaries) else total
        else:
            prev = timings[-1] if timings else (0, 0)
            start = prev[0] + prev[1]
            end = total
        dur = max(1.5, end - start)
        timings.append((start, dur))
        print(f"   Scene {i+1}: [{start:.2f}s-{start+dur:.2f}s]")
    return total, timings


def _smootherstep(t: float) -> float:
    """Perlin's smootherstep curve: 6t^5 - 15t^4 + 10t^3. Zero-jerk physical camera inertia."""
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


# Studio-grade Higgsfield/Astra camera archetypes
_HIGGSFIELD_CARTOON_MOTIONS = [
    ("cinematic_dolly_in",       1.00, 1.15,  0.000, -0.015, "dolly_in"),
    ("dolly_out_grand_reveal",   1.16, 1.02,  0.000,  0.020, "dolly_out"),
    ("pedestal_crane_rise",      1.03, 1.12,  0.010, -0.035, "pedestal_rise"),
    ("dramatic_vertigo_zoom",    1.00, 1.18,  0.000,  0.000, "vertigo"),
    ("orbital_arc_drift",        1.03, 1.14,  0.035,  0.010, "orbital_arc"),
    ("steadicam_handheld_drift", 1.02, 1.11,  0.000,  0.000, "steadicam"),
]


def make_kinetic_clip(frame_path: Path, duration: float, scene_idx: int):
    """
    Higgsfield / Astra Studio-Grade 2.5D Cinematic Camera Motion Engine for cartoon frames.
    Uses Perlin smootherstep S-curve easing with 6 distinct camera motion archetypes.
    """
    name, z_s, z_e, dx_target, dy_target, m_type = _HIGGSFIELD_CARTOON_MOTIONS[
        scene_idx % len(_HIGGSFIELD_CARTOON_MOTIONS)
    ]
    W, H = 1080, 1920
    PAD = 160
    pil = Image.open(str(frame_path)).convert("RGB").resize((W + PAD * 2, H + PAD * 2), Image.LANCZOS)
    cw, ch = pil.size

    dur_safe = max(duration, 0.001)

    def make_frame(t: float):
        norm_t = min(1.0, max(0.0, t / dur_safe))
        ease = _smootherstep(norm_t)

        if m_type == "dolly_in":
            breathing = 0.003 * math.sin(2.0 * math.pi * norm_t)
            zoom = z_s + (z_e - z_s) * ease + breathing
            pan_x = int(dx_target * cw * ease)
            pan_y = int(dy_target * ch * ease)
        elif m_type == "dolly_out":
            zoom = z_s + (z_e - z_s) * ease
            pan_x = int(dx_target * cw * ease)
            pan_y = int(dy_target * ch * ease)
        elif m_type == "pedestal_rise":
            zoom = z_s + (z_e - z_s) * ease
            pan_x = int(dx_target * cw * ease)
            crane_y = (0.030 - 0.060 * ease) * ch
            pan_y = int(crane_y)
        elif m_type == "vertigo":
            v_ease = norm_t ** 1.8
            zoom = z_s + (z_e - z_s) * v_ease
            pan_x = 0
            pan_y = int(-0.015 * ch * v_ease)
        elif m_type == "orbital_arc":
            zoom = z_s + (z_e - z_s) * ease
            arc_x = math.sin(math.pi * ease) * (dx_target * cw)
            pan_x = int(arc_x)
            pan_y = int(dy_target * ch * ease)
        elif m_type == "steadicam":
            zoom = z_s + (z_e - z_s) * ease
            sway_x = (math.sin(t * 2.1) * 0.004 + math.sin(t * 4.3) * 0.002) * W
            sway_y = (math.cos(t * 1.8) * 0.003 + math.cos(t * 3.7) * 0.0015) * H
            pan_x = int(sway_x)
            pan_y = int(sway_y)
        else:
            zoom = z_s + (z_e - z_s) * ease
            pan_x = int(dx_target * cw * ease)
            pan_y = int(dy_target * ch * ease)

        zoom = max(1.00, zoom)
        rw, rh = int(W / zoom), int(H / zoom)
        cx = cw // 2 + pan_x
        cy = ch // 2 + pan_y

        x1 = max(0, cx - rw // 2)
        y1 = max(0, cy - rh // 2)
        x2 = min(cw, x1 + rw)
        y2 = min(ch, y1 + rh)
        if x2 - x1 < rw:
            x1 = max(0, x2 - rw)
        if y2 - y1 < rh:
            y1 = max(0, y2 - rh)
        crop = pil.crop((x1, y1, x1 + rw, y1 + rh))
        return np.array(crop.resize((W, H), Image.BILINEAR))

    print(f"   Higgsfield Motion [{scene_idx+1}]: {name} (zoom {z_s:.2f}->{z_e:.2f}, ease=smootherstep)")
    clip = VideoClip(make_frame)
    if MOVIEPY_V2:
        return clip.with_duration(duration)
    else:
        return clip.set_duration(duration)


def make_video_media_clip(mp4_path: Path, duration: float, scene_idx: int):
    """Load real HD vertical MP4 video clip, center crop to 1080x1920, loop or slice to match duration."""
    clip = VideoFileClip(str(mp4_path))
    w, h = clip.size
    target_w, target_h = 1080, 1920
    scale = max(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    x1 = (new_w - target_w) // 2
    y1 = (new_h - target_h) // 2
    print(f"   Video Clip [{scene_idx+1}]: {mp4_path.name} ({clip.duration:.1f}s -> {duration:.1f}s)")
    if MOVIEPY_V2:
        resized = clip.resized((new_w, new_h)).cropped(x1=x1, y1=y1, width=target_w, height=target_h)
        if resized.duration < duration:
            return resized.with_effects([vfx.Loop(duration=duration)])
        return resized.subclipped(0, duration)
    else:
        resized = clip.resize((new_w, new_h)).crop(x1=x1, y1=y1, width=target_w, height=target_h)
        if resized.duration < duration:
            return vfx.loop(resized, duration=duration)
        return resized.subclip(0, duration)


def _ensure_drone() -> Path:
    drone = ASSETS_DIR / "thriller_drone.wav"
    if not drone.exists():
        sr, dur = 44100, 20.0
        n = int(sr * dur)
        with wave.open(str(drone), "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sr)
            buf = bytearray()
            for i in range(n):
                t = i / sr
                lfo = 0.7 + 0.3 * math.sin(2 * math.pi * 0.25 * t)
                s = (0.45 * math.sin(2 * math.pi * 55 * t) +
                     0.25 * math.sin(2 * math.pi * 82.4 * t)) * lfo
                env = min(1.0, t / 1.5) * min(1.0, (dur - t) / 1.5)
                val = int(s * env * 0.10 * 32767)
                buf.extend(struct.pack("<h", max(-32767, min(32767, val))))
            wav.writeframes(buf)
    return drone


def assemble_cartoon_short(storyboard, frame_paths, voice_path, timings, out_path):
    scenes = storyboard["scenes"]
    is_hindi = storyboard.get("is_hindi", False)
    voice = AudioFileClip(str(voice_path))
    total_voice_duration = float(voice.duration)
    num_scenes = max(1, len(frame_paths))
    scene_duration = total_voice_duration / num_scenes
    print(f"\n [Assembler] {num_scenes} scenes -> {out_path.name} | Voice: {total_voice_duration:.2f}s | Scene: {scene_duration:.2f}s")

    video_clips, sub_clips = [], []
    for i, (scene, fp) in enumerate(zip(scenes, frame_paths)):
        start_t = i * scene_duration
        dur = scene_duration
        if fp.suffix.lower() == ".mp4":
            kc = make_video_media_clip(fp, dur, i)
        else:
            kc = make_kinetic_clip(fp, dur, i)
        sub_txt = scene.get("subtitle_display") or scene["voiceover"]
        hl = scene.get("highlight_words", [])
        badge = render_subtitle_badge(sub_txt, hl)
        badge_arr = np.array(badge)
        if MOVIEPY_V2:
            kc2 = kc.with_duration(dur)
            sc = (ImageClip(badge_arr).with_duration(dur)
                  .with_position(("center", 1100)).with_start(start_t))
        else:
            kc2 = kc.set_duration(dur)
            sc = (ImageClip(badge_arr).set_duration(dur)
                  .set_position(("center", 1100)).set_start(start_t))
        video_clips.append(kc2)
        sub_clips.append(sc)

    base = concatenate_videoclips(video_clips, method="compose")
    if MOVIEPY_V2:
        base = base.with_duration(total_voice_duration)
    else:
        base = base.set_duration(total_voice_duration)

    drone = AudioFileClip(str(_ensure_drone()))
    if MOVIEPY_V2:
        drone_cut = drone.subclipped(0, total_voice_duration)
        mix = CompositeAudioClip([voice, drone_cut]).with_duration(total_voice_duration)
        final = CompositeVideoClip([base.with_audio(mix), *sub_clips]).with_duration(total_voice_duration)
    else:
        drone_cut = drone.subclip(0, total_voice_duration)
        mix = CompositeAudioClip([voice, drone_cut]).set_duration(total_voice_duration)
        final = CompositeVideoClip([base.set_audio(mix), *sub_clips]).set_duration(total_voice_duration)
    print(f"   Rendering {final.duration:.1f}s @ 24fps...")
    final.write_videofile(str(out_path), fps=24, codec="libx264",
                          audio_codec="aac", logger=None, remove_temp=False,
                          ffmpeg_params=["-shortest", "-pix_fmt", "yuv420p"])
    sz = os.path.getsize(out_path) // 1024 // 1024
    print(f"   Done: {out_path.name} ({sz} MB)")
    for c in [final, base, voice, drone, drone_cut] + video_clips + sub_clips:
        try:
            c.close()
        except Exception:
            pass
    for tmp_file in BASE_DIR.glob("*TEMP_MPY*"):
        try:
            tmp_file.unlink()
        except Exception:
            pass

    # Apply studio-grade photographic clarity, micro-contrast, and 35mm film grain grade
    try:
        from video_engine import apply_photographic_clarity_grade
        apply_photographic_clarity_grade(out_path)
    except Exception:
        pass

    return out_path


def upload_cartoon(video_path, title, description, tags, is_hindi=True):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    TOKEN = BASE_DIR / "token.json"
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
              "https://www.googleapis.com/auth/youtube.readonly",
              "https://www.googleapis.com/auth/youtube.force-ssl"]
    if not TOKEN.exists():
        return f"LOCAL_{int(time.time())}"
    creds = None
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    except Exception:
        pass
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                TOKEN.write_text(creds.to_json(), encoding="utf-8")
            except Exception:
                return f"LOCAL_{int(time.time())}"
    try:
        yt = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": title[:100], "description": description, "tags": tags,
                "categoryId": "27",
                "defaultLanguage": "hi" if is_hindi else "en",
                "defaultAudioLanguage": "hi" if is_hindi else "en",
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            st, resp = req.next_chunk()
            if st:
                print(f"   Upload {int(st.progress()*100)}%", end="\r")
        print()
        vid_id = resp.get("id", "unknown")
        print(f"   Live: https://youtube.com/shorts/{vid_id}")
        return vid_id
    except Exception as e:
        err_msg = str(e)
        if "uploadLimitExceeded" in err_msg:
            print(f"   [QUOTA] YouTube daily upload limit reached! Video saved locally: {video_path.name}")
            return f"SAVED_LOCAL_{int(time.time())}"
        print(f"   Upload error: {e}")
        return f"ERR_{int(time.time())}"


def produce_cartoon_short(topic, cat_key, lang="hi", output_path=None,
                          dry_run=False, video_num=1):
    is_hindi = lang == "hi"
    if output_path is None:
        output_path = BASE_DIR / f"cartoon_short_{video_num:02d}.mp4"
    video_seed = CHARACTER_SEED + video_num * 100 + (hash(topic) % 500)
    print(f"\n{'='*65}")
    print(f"  CARTOON ENGINE [{video_num}]  {topic[:50]}")
    print(f"  Max | {'Hindi' if is_hindi else 'English'} | Seed {video_seed}")
    print(f"{'='*65}")
    t0 = time.time()
    storyboard = generate_cartoon_storyboard(topic, is_hindi, cat_key)
    title = storyboard.get("title", f"Max Cartoon {video_num} #Shorts")
    description = storyboard.get("description", "Daily cartoon facts! #shorts #viral #hindi")
    tags = list(dict.fromkeys(
        storyboard.get("tags", []) + ["max cartoon", "hindi animation", "cartoon shorts", "shorts"]
    ))
    frames = generate_cartoon_frames(storyboard["scenes"], video_seed)
    voice_path = ASSETS_DIR / f"cartoon_voice_{video_num:02d}.mp3"
    total_dur, timings = synthesize_voiceover(storyboard["scenes"], is_hindi, voice_path)
    rendered = assemble_cartoon_short(storyboard, frames, voice_path, timings, output_path)
    vid_id = f"DRYRUN_{int(time.time())}"
    if not dry_run:
        vid_id = upload_cartoon(rendered, title, description, tags, is_hindi)
    hist = {}
    if HISTORY_FILE.exists():
        try:
            hist = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    hist.setdefault("videos", []).append({
        "id": vid_id, "title": title,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "topic": topic, "category": cat_key,
        "type": "cartoon", "character": "Max", "language": lang,
    })
    hist["last_video_id"] = vid_id
    HISTORY_FILE.write_text(json.dumps(hist, indent=2, ensure_ascii=False), encoding="utf-8")

    # Record to Variety Store
    try:
        from yt_variety import variety_engine
        v_bundle = variety_engine.pick_production_bundle(lang_preference=lang)
        variety_engine.record_production(
            topic=topic,
            title=title,
            bundle=v_bundle,
            image_prompts=[sc.get("action", "") for sc in storyboard.get("scenes", [])],
            video_id=vid_id
        )
    except Exception as v_err:
        print(f"   [Variety Store Notice] {v_err}")

    elapsed = time.time() - t0
    return {"title": title, "video_id": vid_id, "category": cat_key, "topic": topic,
            "duration": round(total_dur, 1), "render_time": round(elapsed, 1),
            "file": str(rendered), "status": "OK"}


def run_batch_cartoon(count=10, lang="hi", dry_run=False):
    pillars = CARTOON_PILLARS_HI if lang == "hi" else CARTOON_PILLARS_EN
    count = min(count, len(pillars))
    results = []
    print(f"\n{'='*65}")
    print(f"  CARTOON BATCH | {count} videos | {'Hindi' if lang=='hi' else 'English'}")
    print(f"  Max watermark: bottom-right | Motion: Ken Burns | Voice: MadhurNeural")
    print(f"{'='*65}")
    for idx in range(count):
        cat_key, topic = pillars[idx % len(pillars)]
        out_path = BASE_DIR / f"cartoon_short_{idx+1:02d}.mp4"
        try:
            res = produce_cartoon_short(topic, cat_key, lang, out_path, dry_run, idx + 1)
            results.append(res)
            print(f"  [{idx+1}/{count}] OK: {res['title'][:55]} -> {res['video_id']}")
        except Exception as e:
            print(f"  [{idx+1}/{count}] FAILED: {e}")
            results.append({"status": "FAILED", "error": str(e), "num": idx + 1})
        if idx + 1 < count:
            time.sleep(5)
    ok = sum(1 for r in results if r.get("status") == "OK")
    print(f"\n  BATCH DONE: {ok}/{count} cartoons produced")
    return results




# =============================================================================
# KIDS LONG CARTOON - Children's dancing/learning style (3-5 min)
# =============================================================================

KIDS_CARTOON_TOPICS = [
    "Max teaches kids the Hindi alphabet - A for Anar, B for Baar - singing and dancing",
    "Max and the magical numbers 1 to 10 - a dancing counting adventure for kids",
    "Max explains why the sky is blue - a colorful animated science adventure for kids",
    "Max teaches kids about animals of the jungle - lion, elephant, monkey dancing together",
    "Max and the rainbow - a singing color-learning adventure with dancing cartoon characters",
    "Max teaches kids about the solar system - planets dancing around the sun cartoon",
    "Max explains how plants grow - seeds to flowers - a fun dancing nature lesson for kids",
    "Max and the ocean - fish, whales and dolphins - a singing underwater adventure for kids",
    "Max teaches kids healthy habits - brush teeth, eat vegetables - a fun singing lesson",
    "Max and the weather - rain, sun, snow - a colorful dancing cartoon for young learners",
]

KIDS_CHARACTER_DNA = (
    "3D stylized friendly cartoon character Max, bright neon-yellow hoodie, "
    "messy dark brown spiky hair, huge happy smiling Pixar-style eyes, "
    "round cute friendly face, warm colorful background, "
    "children educational cartoon style, vibrant rainbow colors, "
    "clean 3D octane render, cinematic studio lighting, vertical 9:16"
)


def generate_kids_storyboard(topic: str, is_hindi: bool = True) -> Dict[str, Any]:
    """Gemini-powered 8-scene kids educational cartoon storyboard."""
    lang = "Hindi Devanagari" if is_hindi else "English"
    prompt = (
        "You are the creative director of the world top children education cartoon channel "
        "(think Cocomelon, ChuChu TV, Little Baby Bum style but with character Max).\n\n"
        f"TOPIC: {topic!r}\n"
        f"CHARACTER: {KIDS_CHARACTER_DNA!r}\n\n"
        f"Create a cheerful, educational, song-and-dance style 8-scene cartoon script.\n"
        f"Language: {lang} voiceover. Fun, repetitive, catchy learning phrases.\n"
        f"Each scene = 20-25 seconds. Total = 3-4 minutes.\n\n"
        "Rules:\n"
        "- Scene 1: Intro song with Max dancing and welcoming kids\n"
        "- Scenes 2-7: Each teaches one fun fact/element with a song line\n"
        "- Scene 8: Outro - Max waves goodbye with a catchy summary rhyme\n"
        "- voiceover: Singable, rhythmic, educational (like a nursery rhyme)\n"
        "- subtitle_display: Simple words kids can read (max 4 words per line)\n"
        "- pollinations_prompt: ENGLISH, describe Max in colorful happy scene\n\n"
        "OUTPUT ONLY RAW JSON with: title, description, tags (list), is_hindi (bool), "
        "scenes (8 objects: scene_id, voiceover, subtitle_display, highlight_words, pollinations_prompt)"
    )
    for model in GEMINI_MODELS:
        try:
            resp = ai_client.models.generate_content(model=model, contents=prompt)
            raw = resp.text.strip().replace("```json", "").replace("```", "").strip()
            s, e = raw.find("{"), raw.rfind("}")
            if s != -1 and e != -1:
                data = json.loads(raw[s:e+1])
                if "scenes" in data and len(data["scenes"]) >= 6:
                    print(f"   [Kids Storyboard] {model} -> {len(data['scenes'])} scenes OK")
                    return data
        except Exception as ex:
            print(f"   [Kids Storyboard] {model} failed: {ex}")
            time.sleep(1)

    print(f"   [Kids Storyboard] Using dynamic educational fallback storyboard for: {topic[:40]}...")
    title = "Max Sikhata Hai #KidsCartoon #Learning"
    desc = f"Max ke saath masti aur padhai! {topic} #kids #cartoon #hindi"
    tags = ["kids cartoon", "children learning", "hindi kids", "educational cartoon", "max cartoon"]
    kids_scenes = [
        {
            "scene_id": 1,
            "voiceover": "Aao bacho Max ke saath nacho aur nayi cheezein seekho!",
            "subtitle_display": "Aao nacho aur seekho!",
            "highlight_words": ["nacho", "seekho"],
            "pollinations_prompt": f"{KIDS_CHARACTER_DNA}, Max dancing happily, bright rainbow background"
        },
        {
            "scene_id": 2,
            "voiceover": "Kya aap jaante ho hamari duniya kitni sundar aur pyari hai?",
            "subtitle_display": "Duniya kitni pyari hai!",
            "highlight_words": ["sundar", "pyari"],
            "pollinations_prompt": f"{KIDS_CHARACTER_DNA}, Max exploring nature with flowers and butterflies"
        },
        {
            "scene_id": 3,
            "voiceover": "Suraj chamke asmaan mein aur chanda mama muskuraye raat mein.",
            "subtitle_display": "Suraj chamke asmaan mein!",
            "highlight_words": ["Suraj", "chanda"],
            "pollinations_prompt": f"{KIDS_CHARACTER_DNA}, bright smiling cartoon sun and stars dancing"
        },
        {
            "scene_id": 4,
            "voiceover": "Chalo milkar ginte hain ek do teen chaar paanch!",
            "subtitle_display": "Ek Do Teen Chaar!",
            "highlight_words": ["Ek", "Do", "Teen"],
            "pollinations_prompt": f"{KIDS_CHARACTER_DNA}, giant colorful floating 3D numbers 1 2 3"
        },
        {
            "scene_id": 5,
            "voiceover": "Roj padhai aur achhi aadat se bante hain hum sabse smart bache.",
            "subtitle_display": "Hum sabse smart bache!",
            "highlight_words": ["smart", "bache"],
            "pollinations_prompt": f"{KIDS_CHARACTER_DNA}, Max with books and superhero cape smiling"
        },
        {
            "scene_id": 6,
            "voiceover": "Video achha laga toh like karo aur Max ke agle gaane ke liye subscribe karo!",
            "subtitle_display": "Like aur Subscribe karo!",
            "highlight_words": ["Like", "Subscribe"],
            "pollinations_prompt": f"{KIDS_CHARACTER_DNA}, Max waving cheerful goodbye with heart balloons"
        }
    ]
    return {
        "title": title,
        "description": desc,
        "tags": tags,
        "is_hindi": is_hindi,
        "scenes": kids_scenes
    }


def produce_kids_long_cartoon(
    topic: str = None,
    output_path: Path = None,
    dry_run: bool = False,
    lang: str = "hi",
) -> Dict[str, Any]:
    """
    Produces a 3-5 minute children educational cartoon with Max.
    Colorful, dancing, learning style (Cocomelon/ChuChu TV inspired).
    Each scene uses upbeat voice and happy character expressions.
    """
    is_hindi = lang == "hi"
    if topic is None:
        import random
        topic = random.choice(KIDS_CARTOON_TOPICS)
    if output_path is None:
        output_path = BASE_DIR / "kids_long_cartoon.mp4"

    video_seed = CHARACTER_SEED + 9999 + (hash(topic) % 300)
    print(f"\n{'='*65}")
    print(f"  KIDS CARTOON ENGINE  |  {topic[:55]}")
    print(f"  Style: Colorful/Educational/Dancing | Seed: {video_seed}")
    print(f"{'='*65}")

    t0 = time.time()

    # Use kids-specific storyboard
    storyboard = generate_kids_storyboard(topic, is_hindi)
    title = storyboard.get("title", "Max Sikhata Hai #KidsCartoon")
    description = storyboard.get(
        "description",
        "Max ke saath seekho aur nacho! #kids #cartoon #learning #hindi #educational"
    )
    tags = list(dict.fromkeys(
        storyboard.get("tags", []) +
        ["kids cartoon", "children learning", "hindi kids", "educational cartoon",
         "cocomelon hindi", "cartoon for kids", "max cartoon"]
    ))

    # Use KIDS_CHARACTER_DNA for frames (happier, more colorful)
    scenes = storyboard["scenes"]
    for s in scenes:
        pp = s.get("pollinations_prompt", "")
        if KIDS_CHARACTER_DNA[:20] not in pp and CHARACTER_DNA[:20] not in pp:
            s["pollinations_prompt"] = (
                f"{KIDS_CHARACTER_DNA}, {s.get('expression', 'happy dancing')}, "
                f"colorful children educational scene, bright rainbow background"
            )

    # Generate frames with kids DNA
    old_dna = CHARACTER_DNA
    frames = []
    print(f"\n Generating {len(scenes)} colorful kids frames...")
    for i, scene in enumerate(scenes):
        poll_prompt = scene.get("pollinations_prompt", "")
        if not poll_prompt:
            poll_prompt = (
                f"{KIDS_CHARACTER_DNA}, Max dancing happily scene {i+1}, "
                f"colorful educational cartoon, bright cheerful background"
            )
        encoded = urllib.parse.quote(poll_prompt)
        scene_seed = video_seed + i * 11
        urls_to_try = [
            f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&model=flux&nologo=true&seed={scene_seed}&enhance=true",
            f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&model=turbo&nologo=true&seed={scene_seed}",
            f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={scene_seed}",
            f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={scene_seed+1}",
        ]
        out_path = FRAMES_DIR / f"kids_frame_{video_seed}_{i+1}.jpg"
        downloaded = False
        for attempt, url in enumerate(urls_to_try):
            try:
                r = requests.get(url, timeout=35)
                if r.status_code == 200 and len(r.content) > 4000:
                    with open(out_path, "wb") as f:
                        f.write(r.content)
                    pil = Image.open(str(out_path)).convert("RGB").resize((1080, 1920), Image.LANCZOS)
                    stamped = stamp_avatar(pil)
                    stamped.save(str(out_path), quality=92)
                    frames.append(out_path)
                    print(f"   Kids frame {i+1} OK ({len(r.content)//1024}KB)")
                    downloaded = True
                    break
                elif r.status_code == 429:
                    wait = 4 + attempt * 3
                    print(f"   Pollinations rate-limited (429), waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"   Retry {attempt+1} status={r.status_code}, trying alternate model...")
            except Exception as ex:
                print(f"   Retry {attempt+1}: {ex}")
            time.sleep(1)
        if not downloaded:
            fb = Image.new("RGB", (1080, 1920), (30, 20, 60))
            draw = ImageDraw.Draw(fb)
            for rad in range(700, 0, -35):
                alpha = int(45 * (1 - rad / 700))
                draw.ellipse([(540 - rad, 960 - rad), (540 + rad, 960 + rad)], fill=(120 + alpha, 80 + alpha, 220 + alpha))
            stamped = stamp_avatar(fb)
            stamped.save(str(out_path), quality=92)
            frames.append(out_path)

    # Kids voice: upbeat, female, for children
    voice = "hi-IN-SwaraNeural" if is_hindi else "en-US-AnaNeural"
    full_text = " ".join(s["voiceover"].strip() for s in scenes)
    voice_path = ASSETS_DIR / "kids_voice.mp3"
    print(f"\n [Kids Voice] {voice} +5% speed (slower for kids)...")
    boundaries = asyncio.run(_synth_voice_async(full_text, voice, voice_path))
    ac = AudioFileClip(str(voice_path))
    total_dur = float(ac.duration)
    ac.close()

    # Build timings for kids (longer per scene = more learning time)
    timings = []
    for i in range(len(scenes)):
        if i < len(boundaries):
            start = boundaries[i][0]
            end = boundaries[i + 1][0] if i + 1 < len(boundaries) else total_dur
        else:
            prev = timings[-1] if timings else (0, 0)
            start = prev[0] + prev[1]
            end = total_dur
        dur = max(3.0, end - start)  # Kids scenes = at least 3 seconds
        timings.append((start, dur))

    num_scenes = max(1, len(frames))
    scene_duration = total_dur / num_scenes

    # Assemble with slower, gentler zoom (kids = smooth, not shake)
    print(f"\n [Kids Assembler] {num_scenes} scenes -> {output_path.name} | Voice: {total_dur:.2f}s | Scene: {scene_duration:.2f}s")
    video_clips, sub_clips = [], []
    for i, (scene, fp) in enumerate(zip(scenes, frames)):
        start_t = i * scene_duration
        dur = scene_duration
        # Gentle push-in only for kids
        W, H = 1080, 1920
        PAD = 100
        pil = Image.open(str(fp)).convert("RGB").resize((W + PAD*2, H + PAD*2), Image.LANCZOS)
        cw, ch = pil.size
        z_start, z_end = 1.00, 1.06  # Very gentle zoom for kids

        def make_frame_kids(t, pil=pil, cw=cw, ch=ch, z_s=z_start, z_e=z_end, dur=dur):
            progress = min(1.0, t / max(dur, 0.001))
            zoom = z_s + (z_e - z_s) * progress
            rw, rh = int(W / zoom), int(H / zoom)
            x1 = max(0, cw//2 - rw//2)
            y1 = max(0, ch//2 - rh//2)
            crop = pil.crop((x1, y1, x1 + rw, y1 + rh))
            return np.array(crop.resize((W, H), Image.LANCZOS))

        clip_k = VideoClip(make_frame_kids)
        kc = clip_k.with_duration(dur) if MOVIEPY_V2 else clip_k.set_duration(dur)
        sub_txt = scene.get("subtitle_display") or scene["voiceover"][:30]
        hl = scene.get("highlight_words", [])
        badge = render_subtitle_badge(sub_txt, hl)
        badge_arr = np.array(badge)

        if MOVIEPY_V2:
            kc2 = kc.with_duration(dur)
            sc = (ImageClip(badge_arr).with_duration(dur)
                  .with_position(("center", 1100)).with_start(start_t))
        else:
            kc2 = kc.set_duration(dur)
            sc = (ImageClip(badge_arr).set_duration(dur)
                  .set_position(("center", 1100)).set_start(start_t))
        video_clips.append(kc2)
        sub_clips.append(sc)

    base = concatenate_videoclips(video_clips, method="compose")
    voice_ac = AudioFileClip(str(voice_path))

    if MOVIEPY_V2:
        base = base.with_duration(total_dur)
        final = CompositeVideoClip([base.with_audio(voice_ac), *sub_clips]).with_duration(total_dur)
    else:
        base = base.set_duration(total_dur)
        final = CompositeVideoClip([base.set_audio(voice_ac), *sub_clips]).set_duration(total_dur)

    final.write_videofile(str(output_path), fps=24, codec="libx264",
                          audio_codec="aac", logger=None, remove_temp=False,
                          ffmpeg_params=["-shortest", "-pix_fmt", "yuv420p"])
    sz = os.path.getsize(output_path) // 1024 // 1024
    print(f"   Kids cartoon done: {output_path.name} ({sz} MB, {total_dur:.0f}s)")

    for c in [final, base, voice_ac] + video_clips + sub_clips:
        try:
            c.close()
        except Exception:
            pass
    for tmp_file in BASE_DIR.glob("*TEMP_MPY*"):
        try:
            tmp_file.unlink()
        except Exception:
            pass

    # Apply studio-grade photographic clarity, micro-contrast, and 35mm film grain grade
    try:
        from video_engine import apply_photographic_clarity_grade
        apply_photographic_clarity_grade(output_path)
    except Exception:
        pass

    # Upload
    vid_id = f"DRYRUN_{int(time.time())}"
    if not dry_run:
        vid_id = upload_cartoon(output_path, title, description, tags, is_hindi)

    # Record
    hist = {}
    if HISTORY_FILE.exists():
        try:
            hist = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    hist.setdefault("videos", []).append({
        "id": vid_id, "title": title,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "topic": topic, "type": "kids_cartoon",
        "character": "Max", "language": lang, "duration_s": round(total_dur),
    })
    hist["last_video_id"] = vid_id
    HISTORY_FILE.write_text(json.dumps(hist, indent=2, ensure_ascii=False), encoding="utf-8")

    elapsed = time.time() - t0
    return {
        "title": title, "video_id": vid_id,
        "topic": topic, "type": "kids_cartoon",
        "duration": round(total_dur, 1),
        "render_time": round(elapsed, 1),
        "file": str(output_path), "status": "OK",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Max Cartoon YouTube Agent")
    parser.add_argument("--batch",   type=int,   default=1,    help="Number of Shorts (max 10)")
    parser.add_argument("--topic",   type=str,   default="",   help="Custom topic override")
    parser.add_argument("--lang",    type=str,   default="hi", choices=["hi", "en"])
    parser.add_argument("--dry-run", action="store_true",      help="No YouTube upload")
    args = parser.parse_args()
    if args.batch > 1:
        run_batch_cartoon(count=args.batch, lang=args.lang, dry_run=args.dry_run)
    else:
        pillars = CARTOON_PILLARS_HI if args.lang == "hi" else CARTOON_PILLARS_EN
        cat_key, topic = pillars[0]
        if args.topic:
            topic = args.topic
        produce_cartoon_short(topic, cat_key, args.lang, dry_run=args.dry_run)
