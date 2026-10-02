"""
video_engine.py - Elite Multi-Scene Thriller & Character Visuals Engine for YouTube Shorts
===========================================================================================
Engine Features (Inspired by Zack D. Films, MagnatesMedia, Ridddle, Aperture, Thoughty2):
1. 10 Viral Categories Master Matrix (Medical anomalies, Dark psychology, Mechanical secrets, etc.)
2. Character-Driven & Visceral Scene Storyboards with dramatic action queries.
3. Continuous Zero-Wait Voiceover Synthesis (+11% speed, 0.0s gap between sentences).
4. Procedural Thriller Sound Design: Low-frequency ambient tension drone layered beneath speech.
5. Cinematic Vignette & Full-Bleed 1080x1920 Framing (Zero black bars).
6. Alex Hormozi / MrBeast Style Dynamic Captions with electric yellow keyword highlights.
7. Infinite Algorithmic Retention Loop connecting the final punchline right back into Scene 1.
8. Pollinations AI image generation as primary visual source (guaranteed rich cinematic frames).
"""

import os
import sys
import json
import time
import math
import wave
import re
import struct
import string
import random
import asyncio
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Tuple

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from dotenv import load_dotenv

# Safe UTF-8 configuration
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

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
SCENES_CACHE_DIR = ASSETS_DIR / "scenes_cache"
FRAMES_DIR = ASSETS_DIR / "engine_frames"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
SCENES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

# API Keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

# Gemini Setup
from google import genai
ai_client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODELS_POOL = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
    "gemini-pro-latest"
]

# Edge TTS
import edge_tts

# MoviePy universal imports
try:
    from moviepy import (
        VideoFileClip,
        AudioFileClip,
        ImageClip,
        concatenate_videoclips,
        CompositeAudioClip,
        CompositeVideoClip
    )
    import moviepy.video.fx as vfx
    MOVIEPY_V2 = True
except ImportError:
    from moviepy.editor import (
        VideoFileClip,
        AudioFileClip,
        ImageClip,
        concatenate_videoclips,
        CompositeAudioClip,
        CompositeVideoClip
    )
    import moviepy.video.fx.all as vfx
    MOVIEPY_V2 = False


# ---------------------------------------------------------------------
# 1. 10 Viral Categories Master Matrix
# ---------------------------------------------------------------------
VIRAL_CATEGORIES = {
    "medical_biology_anomalies": {
        "name": "3D Medical & Body Anomalies (Zack D. Films Style)",
        "description": "Visceral physical explainers: swallowing dangerous objects, venom reactions, organ glitches, surgical anomalies.",
        "sample_topics": [
            "What happens if you accidentally swallow a live wasp",
            "Why you should never pop a pimple in the triangle of death",
            "What happens if dry ice touches your tongue",
            "The fatal genetic insomnia that prevents you from ever sleeping again"
        ],
        "visual_style": "3d anatomical x-ray, human body cross-section, terrified character close-up, microscopic cell attacks"
    },
    "thriller_dark_psychology": {
        "name": "Thriller & Dark Psychology (Aperture / MagnatesMedia Style)",
        "description": "Unsettling mental phenomena, psychological manipulation, bizarre psychiatric syndromes, eerie human experiments.",
        "sample_topics": [
            "The Cotard Delusion: People who believe they are walking corpses",
            "The Bystander Paralysis: Why crowd screams cause people to freeze",
            "The Dark Triad: How to spot psychological gaslighting in seconds",
            "The Lucifer Effect: How ordinary minds become cruel in 6 days"
        ],
        "visual_style": "shadowy silhouette, psychological thriller lighting, moody character staring into void, intense eye pupil dilation"
    },
    "how_it_actually_works": {
        "name": "How It Actually Works (Everyday & Industrial Mechanics)",
        "description": "Counter-intuitive engineering secrets behind machines, infrastructure, and everyday objects.",
        "sample_topics": [
            "Why massive ship anchors don't hold the sea floor",
            "Why airplane passenger windows have a tiny mystery hole",
            "How modern elevators are physically impossible to freefall",
            "Why bank vault doors are round instead of square"
        ],
        "visual_style": "macro engineering schematics, industrial machinery in motion, cutaway blueprint animations, high-tech components"
    },
    "unexplained_real_mysteries": {
        "name": "Unexplained Real Mysteries & Classified Files (Thoughty2 Style)",
        "description": "Bizarre true historical incidents, unexplained medical outbreaks, declassified government anomalies.",
        "sample_topics": [
            "The 1994 Toxic Lady incident that knocked out an entire hospital ER",
            "The 1518 Dancing Plague that forced people to dance to death",
            "The Wow! Signal: The 72-second radio burst that never returned",
            "Project Stargate: When military intelligence investigated psychic espionage"
        ],
        "visual_style": "vintage declassified file stamps, mysterious archival portraits, eerie fog environments, flashing radar screens"
    },
    "reality_simulation_paradoxes": {
        "name": "Reality Glitches & Scientific Paradoxes",
        "description": "Mind-bending physics paradoxes questioning perception, time, and the fabric of reality.",
        "sample_topics": [
            "The Quantum Zeno Effect: A particle cannot decay as long as you look at it",
            "The Boltzmann Brain: You are more likely a floating disembodied consciousness",
            "The Grandfather Paradox solved by parallel branching realities",
            "The Fermi Paradox: The Great Filter that extinguishes cosmic civilizations"
        ],
        "visual_style": "matrix digital code rain, endless mirror labyrinth, quantum particle collisions, holographic reality glitch"
    },
    "extreme_physics_space_terrors": {
        "name": "Cosmic Terrors & Extreme Physics (Ridddle / Kurzgesagt Style)",
        "description": "Existential cosmological threats: vacuum decay, rogue planets, strange quarks, spaghettification.",
        "sample_topics": [
            "Vacuum Decay: Why the entire universe could vanish at the speed of light",
            "Strange Matter: The subatomic drop that converts everything it touches",
            "The Boötes Void: Why a 330-million-light-year hole in space is completely empty",
            "Rogue Planets: Giant worlds roaming pitch black interstellar space"
        ],
        "visual_style": "black hole event horizon, deep space stellar explosions, microscopic strangelet collision, glowing cosmic void"
    },
    "survival_emergency_anatomy": {
        "name": "Survival Dilemmas & Extreme Anatomy",
        "description": "What happens to the human body in extreme environments: freefall, deep-sea pressure, quicksand, freezing.",
        "sample_topics": [
            "What happens to human lungs during sudden deep-sea implosion",
            "How to survive if your elevator cable snaps (the floor lie)",
            "The 10-second rule for surviving extreme arctic hypothermia",
            "Why struggling in quicksand only speeds up the sinking process"
        ],
        "visual_style": "underwater high pressure darkness, character gasping for oxygen, falling character POV, cardiac monitor pulse"
    },
    "bizarre_nature_monsters": {
        "name": "Bizarre Biology & Nature's Deadliest Weapons",
        "description": "Creepy parasites, biological immortality, lethal adaptations in the animal kingdom.",
        "sample_topics": [
            "The Cordyceps Zombie Fungus: Hijacking ant brains with fungal puppet strings",
            "The Immortal Jellyfish: How it chemically resets its age back to infancy",
            "The Mantis Shrimp Punch: Accelerating faster than a bullet to boil water",
            "The Jewel Wasp: Brain-washing cockroaches into docile living incubators"
        ],
        "visual_style": "macro insect predator eyes, glowing parasitic spores, underwater shockwave bubble, bioluminescent deep creature"
    },
    "perception_sensory_traps": {
        "name": "Perception Traps & Optical Brain Glitches",
        "description": "Phenomena where your sensory organs fail and your brain actively hallucinates reality.",
        "sample_topics": [
            "The McGurk Effect: How your eyes force your ears to hear a different word",
            "The Troxler Fading Illusion: Stare at the center and your reflection disappears",
            "The Phantom Vibration Syndrome: Why your leg vibrates when no one called",
            "Chronostasis: Why the first second on an analog clock seems frozen"
        ],
        "visual_style": "optical illusion spiral vortex, split screen human face, audio waveform pulsing, hypnotic spinning disc"
    },
    "high_stakes_heists_scandals": {
        "name": "High-Stakes Heists & Financial Scandals (MagnatesMedia Style)",
        "description": "Incredible economic glitches, rogue traders, impenetrable vault heists, billionaire scandals.",
        "sample_topics": [
            "The 1995 Rogue Trader who brought down a 233-year-old bank in 24 hours",
            "The Antwerp Diamond Center Heist: Cracking an impenetrable vault with tape",
            "The Trillion Dollar Coin Loophole: How governments can legally erase debt",
            "The Central Bank of Iraq Heist: Siphoning one billion dollars in cash at dawn"
        ],
        "visual_style": "heavy bank vault steel gear doors, stacks of cold hard cash, dark surveillance camera footage, stock market crash ticker"
    }
}


# ---------------------------------------------------------------------
# 2. Procedural Asset Generators (Vignette & Thriller Drone)
# ---------------------------------------------------------------------
def ensure_cinematic_assets():
    """Ensures assets/thriller_drone.wav and assets/cinematic_vignette.png exist."""
    drone_path = ASSETS_DIR / "thriller_drone.wav"
    vignette_path = ASSETS_DIR / "cinematic_vignette.png"

    # 1. Procedural Thriller Drone
    if not drone_path.exists():
        sample_rate = 44100
        duration = 25.0
        n_samples = int(sample_rate * duration)
        with wave.open(str(drone_path), "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            frames = bytearray()
            for i in range(n_samples):
                t = i / sample_rate
                lfo = 0.7 + 0.3 * math.sin(2 * math.pi * 0.25 * t)
                s = (
                    0.45 * math.sin(2 * math.pi * 55.0 * t) +
                    0.30 * math.sin(2 * math.pi * 82.4 * t) +
                    0.15 * math.sin(2 * math.pi * 110.0 * t) +
                    0.10 * math.sin(2 * math.pi * 27.5 * t)
                ) * lfo
                env = min(1.0, t / 1.5) * min(1.0, (duration - t) / 1.5)
                val = int(s * env * 0.12 * 32767)
                frames.extend(struct.pack("<h", max(-32767, min(32767, val))))
            wav.writeframes(frames)

    # 2. Cinematic Vignette (1080x1920)
    if not vignette_path.exists():
        w, h = 1080, 1920
        y, x = np.ogrid[:h, :w]
        cx, cy = w / 2, h / 2
        nx = (x - cx) / (w / 2)
        ny = (y - cy) / (h / 2)
        dist = np.sqrt(nx**2 + ny**2)
        vignette = np.clip((dist - 0.55) / 0.65, 0, 1)
        alpha = (vignette**1.8 * 145).astype(np.uint8)
        overlay = np.zeros((h, w, 4), dtype=np.uint8)
        overlay[..., :3] = 0
        overlay[..., 3] = alpha
        img = Image.fromarray(overlay)
        img.save(str(vignette_path))

ensure_cinematic_assets()


# ---------------------------------------------------------------------
# 3. Voiceover Sanitizer (strips visual cues, prompt leakage, camera directions)
# ---------------------------------------------------------------------
def _sanitize_voiceover(text: str) -> str:
    """
    Strips ALL non-spoken content from voiceover text before sending to TTS.
    Removes: visual cues, camera directions, bracketed tags, emoji indicators,
    English metadata bleed, image prompt artifacts, and direction markers.
    """
    if not text or not text.strip():
        return text

    # Remove bracketed directions: [Cut to 3D], [Scene 2], [HOOK], etc.
    text = re.sub(r'\[.*?\]', '', text)
    # Remove parenthesized directions: (close-up), (dramatic zoom), etc.
    text = re.sub(r'\((?:close[- ]?up|zoom|pan|cut|fade|transition|overlay|b-roll|visual|camera|angle|shot|scene|wide|medium|insert|montage|slow[- ]?mo).*?\)', '', text, flags=re.IGNORECASE)
    # Remove visual cue phrases leaked from prompts
    visual_cue_patterns = [
        r'(?:bada|badi|chota|chhota)?\s*check\s*mark',
        r'(?:teen\s*)?[23]\s*[dD]\s*(?:cut\s*away|cutaway|animation|render|cross[- ]?section|model)',
        r'cut\s*(?:to|away)\s+(?:dekho|dikhao|dekhiye|dekhein)',
        r'(?:red|green|bold)\s*(?:❌|✔️|✕|✓|X|cross|checkmark)',
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
    for pattern in visual_cue_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # Remove emoji characters that TTS can't handle
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    text = re.sub(r'[✕✔️❌✓✗⚠️🔥💀😱🙏💡🎯📌🔴🟢]', '', text)
    # Remove markdown formatting
    text = re.sub(r'[*_~`#>]', '', text)
    # Remove excess whitespace, dots, dashes
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'-{2,}', '—', text)
    return text.strip()


# ---------------------------------------------------------------------
# 3b. Modern Open-Caption Subtitle Renderer (MrBeast / Hormozi Style)
# ---------------------------------------------------------------------
def render_subtitle_badge(text: str, highlight_words: List[str] = None, is_hindi: bool = False) -> Image.Image:
    """
    Renders bold, high-contrast, open-style MrBeast/Hormozi captions.
    - NO dark pill/box background — text floats directly over video
    - Large 64pt bold font with thick 5px black stroke outline
    - Glowing white text with keyword highlights in electric yellow
    - 2-4 words per line for instant readability on mobile
    - Heavy drop shadow + stroke for legibility over any background
    """
    if highlight_words is None:
        highlight_words = []

    # Try to load a bold, impactful font at large size
    font_size = 64
    font_paths = [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arial.ttf"
    ]
    font = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue
    if not font:
        font = ImageFont.load_default()

    words = text.strip().upper().split()  # MrBeast style = ALL CAPS
    if not words:
        return Image.new("RGBA", (100, 50), (0, 0, 0, 0))

    # Split into lines of 2-3 words max for mobile readability
    lines = []
    curr_line = []
    for w in words:
        curr_line.append(w)
        if len(curr_line) >= 3:
            lines.append(curr_line)
            curr_line = []
    if curr_line:
        lines.append(curr_line)

    dummy = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(dummy)
    space_w = d.textbbox((0, 0), " ", font=font)[2]

    line_metrics = []
    max_w = 0
    line_h = 78  # Larger line height for readability
    for line in lines:
        line_w = 0
        w_widths = []
        for word in line:
            bb = d.textbbox((0, 0), word, font=font)
            w = bb[2] - bb[0]
            w_widths.append(w)
            line_w += w
        line_w += space_w * (len(line) - 1)
        max_w = max(max_w, line_w)
        line_metrics.append((line, w_widths, line_w))

    pad_x = 30
    pad_y = 20
    canvas_w = int(min(1020, max_w + pad_x * 2))
    canvas_h = int(line_h * len(lines) + pad_y * 2)

    # Transparent canvas — NO pill/box background
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    clean_highlights = [hw.lower().strip(string.punctuation) for hw in highlight_words]
    stroke_width = 5  # Thick outline for readability over any background

    for i, (line, w_widths, line_w) in enumerate(line_metrics):
        start_x = (canvas_w - line_w) / 2
        curr_x = start_x
        curr_y = pad_y + i * line_h

        for word, w in zip(line, w_widths):
            clean_w = word.lower().strip(string.punctuation)
            is_hl = any(hw in clean_w for hw in clean_highlights) if clean_highlights else False
            # Highlighted words = electric yellow, normal = bright white
            text_color = (255, 235, 30, 255) if is_hl else (255, 255, 255, 255)

            # Layer 1: Soft glow shadow (offset + blur simulated by multi-draw)
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    draw.text((curr_x + dx + 4, curr_y + dy + 4), word,
                              font=font, fill=(0, 0, 0, 100))

            # Layer 2: Thick black stroke outline
            draw.text((curr_x, curr_y), word, font=font,
                       fill=text_color, stroke_width=stroke_width,
                       stroke_fill=(0, 0, 0, 255))

            curr_x += w + space_w

    return img


# ---------------------------------------------------------------------
# 4. Gemini Thriller Storyboard Director (10-Category Aware)
# ---------------------------------------------------------------------
def generate_multi_scene_script(
    topic_directive: str = "",
    category: str = "auto",
    language: str = "auto"
) -> Dict[str, Any]:
    """
    Directs Gemini to architect a 4-scene thriller storyboard matching the style of
    Zack D. Films, MagnatesMedia, and Thoughty2.
    """
    low_dir = topic_directive.lower() if topic_directive else ""
    is_hindi = (language == "hi" or "hindi" in low_dir or "हिंदी" in low_dir or any('\u0900' <= c <= '\u097f' for c in topic_directive))

    # Select Category
    chosen_cat_key = category if category in VIRAL_CATEGORIES else random.choice(list(VIRAL_CATEGORIES.keys()))
    cat_info = VIRAL_CATEGORIES[chosen_cat_key]

    if topic_directive and topic_directive.strip():
        directive_prompt = f'User Topic Directives: "{topic_directive}". Fit this into the high-retention thrill style of: {cat_info["name"]}.'
    else:
        sample_pick = random.choice(cat_info["sample_topics"])
        directive_prompt = f'Category: {cat_info["name"]}. Selected Viral Hook: "{sample_pick}". Focus on: {cat_info["description"]}.'

    lang_rules = """
    CRITICAL LANGUAGE RULE — HINDI ONLY:
    - "voiceover": MUST be written in Hindi Devanagari script. NEVER write English in voiceover.
      This field contains ONLY the exact words the narrator speaks aloud. NOTHING ELSE.
      ABSOLUTELY FORBIDDEN in voiceover: camera directions, visual cues, bracketed tags,
      checkmark references, "cutaway dekho", "3D animation", scene descriptions, or any
      text meant for image/video generation. Those belong ONLY in "visual_query" / "pollinations_prompt".
      Good example: "क्या आप जानते हैं कि अगर ततैया आपके गले में जाए तो क्या होता है?"
      Bad example: "Do you know what happens [Cut to 3D model] check mark" ← STRICTLY FORBIDDEN
    - "subtitle_display": Write punchy Hinglish captions (mix of Hindi + English keywords).
      Example: "Gale mein jaate hi ATTACK shuru! INSAAN ko 30 SECOND mein dard!"
    - "title": Catchy Hindi title in Devanagari OR Hinglish (e.g. "अगर ततैया गले में जाए... 😱 #Shorts")
    - "description": Write in Hindi/Hinglish with hashtags: #shorts #viral #hindi #thrillerfacts
    - "tags": Must include: ["hindi shorts", "hindi facts", "viral hindi", "thrill hindi"]
    - "visual_query": ENGLISH ONLY — used for Pexels stock video search.
      Every scene visual_query MUST specify character reaction, anatomical view, or visceral action.
    - "pollinations_prompt": ENGLISH ONLY — used for AI image generation.
      NEVER leak this into voiceover. This is a completely separate rendering pipeline.
    """ if is_hindi else """
    LANGUAGE: ENGLISH
    - voiceover: Rapid, breathless, thriller narration (<14 words per scene). Pure English.
      ONLY spoken dialogue. Zero visual directions, zero camera cues, zero prompt text.
    - subtitle_display: Capitalized punchy keywords for instant viewer engagement.
    - visual_query: Dedicated English keyword for vertical 9:16 footage. MUST specify character reactions, anatomical cross-sections, or visceral actions!
    """

    # Pre-compute template examples so they can be used in the plain string below
    title_example  = "अगर ततैया गले में जाए... 😱 #Shorts" if is_hindi else "Shocking Truth About Wasps #Shorts"
    desc_example   = "रोज़ नई रोमांचक जानकारी! #shorts #viral #hindi #thrillerfacts" if is_hindi else "Daily science and psychology facts. #shorts #thriller #viral"
    tags_example   = '["hindi shorts", "hindi facts", "viral hindi", "thrill hindi", "shorts"]' if is_hindi else '["shorts", "mystery", "thriller", "science", "viral"]'
    vo1_example    = "क्या आपको पता है कि अगर ततैया ज़िंदा आपके गले में जाए, तो सिर्फ 30 सेकंड में क्या होगा?" if is_hindi else "What actually happens if you swallow a live wasp?"
    sub1_example   = "Agar tatai ZINDA gale mein jaaye... 30 SECOND mein KHATARNAK reaction!" if is_hindi else "What if you swallow a LIVE WASP?"
    vo2_example    = "ततैया का डंक आपकी श्वासनली को तुरंत सूजा देता है, जिससे ऑक्सीजन रुक जाती है।" if is_hindi else "The venom causes immediate anaphylactic shock, blocking your airway."
    sub2_example   = "Swashnali BAND ho jaati hai. Oxygen KHATAM. Anaphylactic SHOCK!" if is_hindi else "VENOM attacks your AIRWAY in seconds!"
    vo3_example    = "अगर 5 मिनट में एपिनेफ्रिन इंजेक्शन नहीं मिला, तो दिल बंद हो सकता है।" if is_hindi else "Without epinephrine in 5 minutes, cardiac arrest follows."
    sub3_example   = "5 MINUTE mein Epinephrine nahi? DIL BAND! 💀" if is_hindi else "5 minutes without help = CARDIAC ARREST!"
    vo4_example    = "इसीलिए अगली बार जब आप किसी ततैया को देखें, तो याद रखें—" if is_hindi else "Which is why you should NEVER underestimate a wasp—"
    sub4_example   = "Agle baar tatai dikhe toh BHAGO! Warna..." if is_hindi else "Never ignore a wasp. EVER."

    system_prompt = f"""
    You are an elite short-form thriller director engineering viral YouTube Shorts with 100%+ Average Percentage Viewed (APV).
    Style: Visceral, high-velocity character explainers (Zack D. Films, MagnatesMedia, Thoughty2, Ridddle).

    {directive_prompt}
    Visual Aesthetic: {cat_info["visual_style"]}
    {lang_rules}

    VIRAL RETENTION FORMULA:
    - Scene 1 (Hook, 0-3.5s): Shocking crisis, visceral question, or physical anomaly. Zero greeting.
    - Scene 2 (Mechanism/Anatomy, 3.5-7s): The biological attack, mechanical glitch, or hidden rule.
    - Scene 3 (Twist/Consequence, 7-11s): The terrifying implication or sudden escalation.
    - Scene 4 (Infinite Loop Hook, 11-15s): A punchline that syntactically and grammatically links right back into the opening words of Scene 1, triggering automatic re-watches.

    CHARACTER & VISUAL DIRECTIVE (ZACK D. FILMS PICTORIAL STANDARD):
    - Every scene's "visual_query" MUST describe the exact physical action, 3D anatomical cross-section, mechanical cutaway, or instructional demonstration.
    - NEVER request generic human portraits or scared faces (e.g. 'person shocked scared reaction' is BANNED).
    - If the voiceover explains an action, the visual query must describe that specific action (e.g. 'person lying flat on floor cushioning head 3d simulation', 'elevator cable snapping sparks slow motion', 'human spine impact force distribution 3d animation').

    OUTPUT ONLY RAW VALID JSON (no markdown, no explanation, just the JSON object):
    {{
      "category": "{chosen_cat_key}",
      "topic_used": "Concept name",
      "title": "{title_example}",
      "description": "{desc_example}",
      "tags": {tags_example},
      "is_hindi": {str(is_hindi).lower()},
      "scenes": [
        {{
          "scene_id": 1,
          "type": "hook",
          "voiceover": "{vo1_example}",
          "subtitle_display": "{sub1_example}",
          "highlight_words": ["HOOK_KEYWORD"],
          "visual_query": "high tension cable snap sparks slow motion industrial crisis"
        }},
        {{
          "scene_id": 2,
          "type": "mechanism",
          "voiceover": "{vo2_example}",
          "subtitle_display": "{sub2_example}",
          "highlight_words": ["MECHANISM_KEYWORD"],
          "visual_query": "medical anatomy 3d animation body internal attack x-ray"
        }},
        {{
          "scene_id": 3,
          "type": "consequence",
          "voiceover": "{vo3_example}",
          "subtitle_display": "{sub3_example}",
          "highlight_words": ["DANGER_KEYWORD"],
          "visual_query": "person physical survival posture demonstration 3d simulation cutaway"
        }},
        {{
          "scene_id": 4,
          "type": "loop_hook",
          "voiceover": "{vo4_example}",
          "subtitle_display": "{sub4_example}",
          "highlight_words": ["LOOP_KEYWORD"],
          "visual_query": "internal force impact dissipation physics simulation 3d"
        }}
      ]
    }}
    """

    print(f"🧠 [Gemini Director] Synthesizing thriller storyboard ({chosen_cat_key})...")
    script_data = None
    for model_name in GEMINI_MODELS_POOL:
        try:
            resp = ai_client.models.generate_content(
                model=model_name,
                contents=system_prompt
            )
            raw = resp.text.strip().replace("```json", "").replace("```", "").strip()
            s = raw.find("{")
            e = raw.rfind("}")
            if s != -1 and e != -1:
                raw = raw[s:e + 1]
            script_data = json.loads(raw)
            if "scenes" in script_data and len(script_data["scenes"]) >= 3:
                # Ensure exactly 4 scenes with required fields
                script_data["scenes"] = _normalize_scenes(
                    script_data["scenes"], topic_directive, chosen_cat_key, is_hindi
                )
                print(f"   [AI Director] Storyboard created using {model_name} ({len(script_data['scenes'])} scenes)")
                break
            else:
                script_data = None
        except Exception as ex:
            print(f"   [AI Director] {model_name} failed: {ex}")
            time.sleep(1.0)
            continue

    if not script_data or "scenes" not in script_data:
        print(f"   [AI Director] All models failed — using dynamic topic-aware fallback storyboard")
        script_data = _build_fallback_storyboard(topic_directive, chosen_cat_key, is_hindi)

    return script_data


def _normalize_scenes(
    scenes: List[Dict],
    topic: str,
    cat_key: str,
    is_hindi: bool
) -> List[Dict]:
    """Ensure all scenes have required fields and pad/trim to exactly 4 scenes."""
    scene_types = ["hook", "mechanism", "consequence", "loop_hook"]
    cat_info = VIRAL_CATEGORIES.get(cat_key, {})
    visual_style = cat_info.get("visual_style", "cinematic dramatic thriller scene")

    normalized = []
    for i, scene in enumerate(scenes[:4]):
        sc = dict(scene)
        sc.setdefault("scene_id", i + 1)
        sc.setdefault("type", scene_types[i % len(scene_types)])
        # Ensure voiceover is present and non-empty
        if not sc.get("voiceover", "").strip():
            sc["voiceover"] = f"{topic}. Scene {i+1}."
        # Ensure subtitle_display
        if not sc.get("subtitle_display", "").strip():
            sc["subtitle_display"] = sc["voiceover"][:60]
        # Ensure highlight_words
        if not sc.get("highlight_words"):
            words = sc["voiceover"].split()
            sc["highlight_words"] = [w for w in words if len(w) > 5][:2] or [words[0]]
        # Ensure visual_query (used for Pexels/Pollinations)
        if not sc.get("visual_query", "").strip() or sc.get("visual_query") == "visual_query":
            sc["visual_query"] = f"{visual_style}, scene {i+1} {topic[:30]}"
        # Build pollinations_prompt from visual_query
        if not sc.get("pollinations_prompt", "").strip():
            sc["pollinations_prompt"] = (
                f"Cinematic thriller YouTube Shorts vertical 9:16, "
                f"{sc['visual_query']}, "
                f"dramatic lighting, high detail 3D render, ultra-sharp focus, "
                f"dark atmospheric background, vivid colors, professional cinematography"
            )
        normalized.append(sc)

    # Pad with generated scenes if fewer than 4
    while len(normalized) < 4:
        i = len(normalized)
        sc_type = scene_types[i % len(scene_types)]
        fb = _fallback_scene(i, topic, cat_key, is_hindi)
        normalized.append(fb)

    return normalized[:4]


def _fallback_scene(idx: int, topic: str, cat_key: str, is_hindi: bool) -> Dict:
    """Generate a single complete fallback scene."""
    cat_info = VIRAL_CATEGORIES.get(cat_key, {})
    visual_style = cat_info.get("visual_style", "cinematic thriller dramatic scene")
    scene_types = ["hook", "mechanism", "consequence", "loop_hook"]
    sc_type = scene_types[idx % len(scene_types)]

    if is_hindi:
        voiceovers = [
            f"क्या आप जानते हैं कि {topic[:40]} का सच इतना खतरनाक है?",
            f"वैज्ञानिकों ने पाया कि इसके पीछे का असली कारण चौंकाने वाला है।",
            f"जब यह होता है तो शरीर के अंदर एक भयानक प्रतिक्रिया शुरू हो जाती है।",
            f"इसीलिए अगली बार जब आप {topic[:20]} देखें — याद रखें यह सच!",
        ]
        subtitles = [
            "Kya aap jaante hain? DANGEROUS SACH!",
            "Andar ATTACK shuru! KHATARNAK reaction!",
            "Shareer mein TOOFAN aa gaya!",
            "Yaad rakho yeh SACH hamesha!",
        ]
    else:
        voiceovers = [
            f"What actually happens when {topic[:40]}? The truth is terrifying.",
            f"Scientists discovered the real mechanism behind this — and it's shocking.",
            f"The moment it happens, your body triggers a catastrophic chain reaction.",
            f"This is why you must never underestimate {topic[:25]} — ever.",
        ]
        subtitles = [
            "The TERRIFYING truth revealed!",
            "Your body ATTACKS itself instantly!",
            "CATASTROPHIC chain reaction starts!",
            "NEVER forget this fact!",
        ]

    vo = voiceovers[idx % len(voiceovers)]
    sub = subtitles[idx % len(subtitles)]
    words = vo.split()
    hl = [w for w in words if len(w) > 5][:2] or [words[0]]

    return {
        "scene_id": idx + 1,
        "type": sc_type,
        "voiceover": vo,
        "subtitle_display": sub,
        "highlight_words": hl,
        "visual_query": f"{visual_style}, {topic[:35]}, scene {idx+1}",
        "pollinations_prompt": (
            f"Cinematic thriller YouTube Shorts vertical 9:16, "
            f"{visual_style}, {topic[:35]}, scene {idx+1}, "
            f"dramatic atmospheric lighting, ultra-sharp 3D render, "
            f"vivid colors, professional cinematography"
        )
    }


def _build_fallback_storyboard(
    topic: str,
    cat_key: str,
    is_hindi: bool
) -> Dict[str, Any]:
    """Build a complete 4-scene storyboard when Gemini is unavailable."""
    cat_info = VIRAL_CATEGORIES.get(cat_key, {})
    if is_hindi:
        title = f"{topic[:60]} 😱 #Shorts #Hindi"
        description = f"{topic}. रोज नई रोमांचक जानकारी! #shorts #viral #hindi #thrillerfacts"
        tags = ["hindi shorts", "hindi facts", "viral hindi", "thrill hindi", "shorts"]
    else:
        title = f"{topic[:65]} #Shorts"
        description = f"{topic}. Daily science and psychology facts. #shorts #thriller #viral"
        tags = ["shorts", "mystery", "thriller", "science", "viral"]

    scenes = [_fallback_scene(i, topic, cat_key, is_hindi) for i in range(4)]
    return {
        "category": cat_key,
        "topic_used": topic,
        "title": title,
        "description": description,
        "tags": tags,
        "is_hindi": is_hindi,
        "scenes": scenes,
    }


# ---------------------------------------------------------------------
# 5. Continuous Zero-Wait Voiceover Synthesis
# ---------------------------------------------------------------------
async def _synth_continuous_voice(full_text: str, voice: str, out_path: Path) -> List[Tuple[float, float, str]]:
    """
    Synthesizes the entire script as a single continuous audio stream at +5% rate.
    Uses slower rate for more natural, expressive Hindi narration.
    Captures exact SentenceBoundary timestamps for 0.0s dead-air cut transitions.
    """
    comm = edge_tts.Communicate(full_text, voice, rate="+5%")
    boundaries = []
    with open(out_path, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                offset_s = chunk["offset"] / 1e7
                dur_s = chunk["duration"] / 1e7
                boundaries.append((offset_s, dur_s, chunk["text"]))
    return boundaries

def synthesize_continuous_voiceover(
    scenes: List[Dict[str, Any]],
    is_hindi: bool,
    out_audio_path: Path
) -> Tuple[float, List[Tuple[float, float]]]:
    """
    Executes continuous voiceover synthesis.
    Sanitizes voiceover text to remove visual cue leakage before TTS.
    Returns: (total_duration, [(scene_start_sec, scene_duration_sec), ...])
    """
    voice = "hi-IN-MadhurNeural" if is_hindi else "en-US-ChristopherNeural"
    # Sanitize each scene's voiceover to strip visual cues and prompt leakage
    cleaned_parts = []
    for s in scenes:
        raw_vo = s["voiceover"].strip()
        clean_vo = _sanitize_voiceover(raw_vo)
        if clean_vo:
            cleaned_parts.append(clean_vo)
        else:
            cleaned_parts.append(raw_vo)  # Fallback to raw if sanitizer removed everything
    full_text = " ".join(cleaned_parts)
    print(f"🎙️ [Continuous Audio] Synthesizing expressive voiceover with {voice} (+5%)...")
    print(f"   Sanitized TTS text ({len(full_text)} chars): {full_text[:120]}...")

    boundaries = asyncio.run(_synth_continuous_voice(full_text, voice, out_audio_path))

    ac = AudioFileClip(str(out_audio_path))
    total_dur = float(ac.duration)
    ac.close()

    # Map sentence boundaries to scenes with 0.0s gap
    scene_timings = []
    for i in range(len(scenes)):
        if i < len(boundaries):
            start = boundaries[i][0]
            if i + 1 < len(boundaries):
                end = boundaries[i + 1][0]
            else:
                end = total_dur
            dur = max(1.2, end - start)
        else:
            start = scene_timings[-1][0] + scene_timings[-1][1] if scene_timings else 0.0
            dur = max(1.2, total_dur - start)
        scene_timings.append((start, dur))
        print(f"   Scene {i+1} timing: [{start:.2f}s - {start+dur:.2f}s] ({dur:.2f}s) -> \"{scenes[i]['voiceover'][:35]}...\"")

    return total_dur, scene_timings


# ---------------------------------------------------------------------
# 6. Visual Engine: Pollinations AI (primary) → Pexels (secondary) → Procedural (fallback)
# ---------------------------------------------------------------------

# Cinematic visual DNA injected into every Pollinations prompt
# 5. Realism & Photographic Clarity Engine: Authentic Film Tokens & Negative Rules
_BANNED_SYNTHETIC_TERMS = [
    r'\bhyper[- ]?realistic\b',
    r'\bunreal\s*engine(?:\s*5)?\b',
    r'\boctane\s*render(?:\s*quality)?\b',
    r'\btrending\s*on\s*artstation\b',
    r'\b3[dD]\s*render(?:\s*quality)?\b',
    r'\bcgi\s*sheen\b',
    r'\bplastic\s*skin\b',
    r'\bairbrushed\b',
    r'\bsmooth\s*doll\s*skin\b',
    r'\bwax\s*figure\b',
    r'\bbeauty\s*filter\b',
]

def _clean_synthetic_keywords(prompt: str) -> str:
    """Purge synthetic/video-game keywords that trigger artificial CGI/plastic sheen."""
    for term in _BANNED_SYNTHETIC_TERMS:
        prompt = re.sub(term, '', prompt, flags=re.IGNORECASE)
    return re.sub(r'\s{2,}', ' ', prompt).strip(' ,')

# Authentic photography tokens (Kodak Portra 400 + micro skin details)
AUTHENTIC_PHOTOGRAPHY_DNA = (
    "Raw candid photograph, shot on Kodak Portra 400, 35mm film stock, Arri Alexa 65 sensor. "
    "Visible skin pores, natural blemishes, fine facial peach fuzz, subtle imperfections, "
    "natural un-airbrushed skin texture, realistic catchlights in the eyes, "
    "1/500s shutter speed, tack sharp focus, zero motion blur on subject, "
    "shallow depth of field (f/1.8), cinematic rim light, golden hour, moody chiaroscuro"
)

NEGATIVE_PROMPT_TOKENS = (
    "plastic skin, airbrushed, 3D render, smooth doll skin, wax figure, CGI sheen, "
    "oversaturated, illustration, cartoon, soft focus, beauty filter"
)

# Unified engine visual DNA
_ENGINE_VISUAL_DNA = f"{AUTHENTIC_PHOTOGRAPHY_DNA}, 9:16 vertical composition"

FALLBACK_THRILLER_QUERIES = [
    "dramatic crisis dark thriller candid photograph 35mm",
    "medical internal anatomy realistic macro biological cross section",
    "survival extreme environment raw photograph cinematic",
    "science discovery shocking reaction candid close up portra"
]


def _generate_pollinations_frame(
    poll_prompt: str,
    scene_seed: int,
    out_path: Path,
    width: int = 1080,
    height: int = 1920
) -> bool:
    """Download studio-grade raw photograph with 1.5x supersampling and Flux.1 priority."""
    if not poll_prompt.strip():
        return False

    # 1. Purge synthetic / CGI tokens
    poll_prompt = _clean_synthetic_keywords(poll_prompt)

    # 2. Inject authentic photography tokens and negative guidance
    if "kodak portra" not in poll_prompt.lower() and "35mm film" not in poll_prompt.lower():
        poll_prompt = f"{poll_prompt}, {AUTHENTIC_PHOTOGRAPHY_DNA}"

    # Append negative suppression tokens directly
    styled_prompt = f"{poll_prompt} [avoid: {NEGATIVE_PROMPT_TOKENS}]"
    encoded = urllib.parse.quote(styled_prompt)

    poll_key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    key_param = f"&key={poll_key}" if poll_key else ""

    # 1.5x Supersampling dimensions: 1620x2880 downscaled to 1080x1920 for maximum sharpness
    super_w, super_h = int(width * 1.5), int(height * 1.5)

    # Check Hugging Face serverless if HF_TOKEN is present
    hf_token = os.environ.get("HF_TOKEN", "").strip()
    if hf_token:
        try:
            hf_url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
            hf_headers = {"Authorization": f"Bearer {hf_token}"}
            hf_payload = {"inputs": poll_prompt, "parameters": {"negative_prompt": NEGATIVE_PROMPT_TOKENS}}
            hf_resp = requests.post(hf_url, headers=hf_headers, json=hf_payload, timeout=35)
            if hf_resp.status_code == 200 and len(hf_resp.content) > 5000:
                img = Image.open(__import__('io').BytesIO(hf_resp.content)).convert("RGB")
                img = img.resize((width, height), Image.LANCZOS)
                img = _apply_vignette_to_pil(img)
                img.save(str(out_path), quality=95)
                print(f"   [Flux.1 HF] Generated raw photograph via Hugging Face FLUX.1-schnell")
                return True
        except Exception as hf_err:
            print(f"   [Flux.1 HF] Fallback from HF: {hf_err}")

    # Hierarchy of endpoints prioritizing Flux.1 open-weights with supersampling
    urls_to_try = [
        f"https://image.pollinations.ai/prompt/{encoded}?width={super_w}&height={super_h}&model=flux&nologo=true&seed={scene_seed}&enhance=false&safe=false{key_param}",
        f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&model=flux&nologo=true&seed={scene_seed}&enhance=false&safe=false{key_param}",
        f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&model=turbo&nologo=true&seed={scene_seed}&safe=false{key_param}",
        f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true&seed={scene_seed}&safe=false{key_param}",
    ]
    for attempt, url in enumerate(urls_to_try):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200 and len(r.content) > 5000:
                img = Image.open(__import__('io').BytesIO(r.content)).convert("RGB")
                # Downscale 1.5x supersampled canvas to target 1080x1920 using high-precision Lanczos
                img = img.resize((width, height), Image.LANCZOS)
                img = _apply_vignette_to_pil(img)
                img.save(str(out_path), quality=95)
                return True
            elif r.status_code == 429:
                wait = 3 + attempt * 2
                print(f"   [Visual Engine] Rate-limited (429), waiting {wait}s...")
                time.sleep(wait)
            elif r.status_code == 402:
                print(f"   [Visual Engine] Pollinations tier limit (402), attempting alternative...")
            else:
                print(f"   [Visual Engine] Attempt {attempt+1} status={r.status_code}, trying alternate model...")
        except Exception as ex:
            print(f"   [Visual Engine] Attempt {attempt+1} error: {ex}")
        time.sleep(1.0)
    return False


def _apply_vignette_to_pil(img: Image.Image) -> Image.Image:
    """Apply a cinematic vignette overlay to a PIL image."""
    w, h = img.size
    arr = np.array(img).astype(np.float32)
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    nx = (x - cx) / (w / 2.0)
    ny = (y - cy) / (h / 2.0)
    dist = np.sqrt(nx**2 + ny**2)
    vignette = np.clip((dist - 0.45) / 0.70, 0, 1) ** 1.6
    # Darken edges
    for c in range(3):
        arr[:, :, c] = arr[:, :, c] * (1.0 - vignette * 0.65)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _make_procedural_frame(
    scene_idx: int,
    topic: str,
    cat_key: str,
    out_path: Path,
    width: int = 1080,
    height: int = 1920
) -> Path:
    """Generate a vibrant, colorful procedural frame as last-resort fallback.
    NEVER produces black or near-black frames — always uses bright, saturated palettes."""
    # VIBRANT color palettes per category (much brighter than before to prevent black screens)
    palettes = {
        "medical_biology_anomalies":   [(60, 10, 30), (220, 30, 80), (255, 80, 140)],
        "thriller_dark_psychology":    [(40, 20, 80), (100, 40, 180), (180, 80, 255)],
        "how_it_actually_works":       [(20, 40, 100), (40, 100, 200), (80, 180, 255)],
        "unexplained_real_mysteries":  [(60, 30, 10), (160, 80, 20), (240, 150, 40)],
        "reality_simulation_paradoxes":[(20, 50, 80), (40, 140, 200), (80, 220, 255)],
        "extreme_physics_space_terrors":[(30, 20, 80), (60, 30, 160), (140, 60, 240)],
        "survival_emergency_anatomy":  [(60, 30, 10), (180, 80, 20), (255, 140, 40)],
        "bizarre_nature_monsters":     [(10, 60, 30), (30, 140, 60), (60, 220, 100)],
        "perception_sensory_traps":    [(60, 20, 60), (160, 40, 160), (240, 80, 240)],
        "high_stakes_heists_scandals": [(50, 40, 15), (140, 120, 30), (220, 200, 60)],
    }
    colors = palettes.get(cat_key, [(40, 30, 80), (120, 60, 200), (200, 120, 255)])
    bg_col, mid_col, accent_col = colors

    img = Image.new("RGB", (width, height), bg_col)
    draw = ImageDraw.Draw(img)

    # Vibrant radial gradient rings (brighter fill)
    for rad in range(900, 0, -40):
        alpha = 1 - (rad / 900)
        r = int(bg_col[0] + (accent_col[0] - bg_col[0]) * alpha * 0.7)
        g = int(bg_col[1] + (accent_col[1] - bg_col[1]) * alpha * 0.7)
        b = int(bg_col[2] + (accent_col[2] - bg_col[2]) * alpha * 0.7)
        draw.ellipse(
            [(width//2 - rad, height//2 - rad), (width//2 + rad, height//2 + rad)],
            fill=(r, g, b)
        )

    # Decorative starburst rays for visual interest
    for ang in range(0, 360, 15):
        rad_a = math.radians(ang)
        x2 = width // 2 + int(1100 * math.cos(rad_a))
        y2 = height // 2 + int(1100 * math.sin(rad_a))
        ray_col = (min(255, accent_col[0] + 40), min(255, accent_col[1] + 40), min(255, accent_col[2] + 40))
        draw.line([(width // 2, height // 2), (x2, y2)], fill=ray_col, width=4)

    # Subtle scan lines for cinematic feel
    for y in range(0, height, 6):
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, 12), width=1)

    # Scene number indicator (center area)
    try:
        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/arial.ttf"
        ]
        font = None
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, 90)
                    break
                except Exception:
                    pass
        if not font:
            font = ImageFont.load_default()
        # Scene number with glow
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                draw.text((width // 2 + dx, height // 2 + dy), str(scene_idx + 1),
                          anchor="mm", font=font, fill=(0, 0, 0, 80))
        draw.text((width // 2, height // 2), str(scene_idx + 1),
                  anchor="mm", font=font, fill=(255, 255, 255, 200))
    except Exception:
        pass

    # Apply light vignette (less aggressive than before)
    img = _apply_vignette_to_pil(img)
    img.save(str(out_path), quality=90)
    return out_path


def fetch_scene_visuals(
    scenes: List[Dict[str, Any]],
    video_seed: int = 42
) -> List[Path]:
    """
    Acquires one visual asset per scene using a 3-tier strategy:
    1. Pollinations AI generated image (primary - always unique, rich visuals)
    2. Pexels video download (secondary)
    3. Procedurally generated cinematic frame (guaranteed fallback)

    Returns a list of Path objects — each is either an image (.jpg) or video (.mp4).
    """
    print(f"🎨 [Visual Engine] Sourcing {len(scenes)} scene visuals (Pollinations→Pexels→Procedural)...")
    asset_paths = []
    cat_key = ""

    for i, scene in enumerate(scenes):
        scene_seed = video_seed + i * 13
        out_img = FRAMES_DIR / f"engine_frame_{video_seed}_{i+1}.jpg"
        topic_hint = scene.get("visual_query", scene.get("subtitle_display", ""))[:60]
        poll_prompt = scene.get("pollinations_prompt", "")
        if not poll_prompt:
            poll_prompt = (
                f"{_ENGINE_VISUAL_DNA}, "
                f"{topic_hint}, "
                f"dramatic thriller scene, cinematic lighting"
            )

        print(f"   Scene {i+1}: Pollinations AI → '{poll_prompt[:55]}...'")
        success = _generate_pollinations_frame(poll_prompt, scene_seed, out_img)

        if success:
            print(f"   Scene {i+1}: ✓ Pollinations AI frame generated")
            asset_paths.append(out_img)
            time.sleep(0.8)  # gentle rate limit
            continue

        # Tier 2: Pexels video
        print(f"   Scene {i+1}: Pollinations failed → trying Pexels...")
        query = scene.get("visual_query") or FALLBACK_THRILLER_QUERIES[i % len(FALLBACK_THRILLER_QUERIES)]
        clean_q = query.replace("in hindi", "").replace("hindi", "").strip()
        headers = {"Authorization": PEXELS_API_KEY}
        target_file = SCENES_CACHE_DIR / f"pexels_scene_{i}_{int(time.time())}.mp4"
        download_url = None

        try:
            url = (
                f"https://api.pexels.com/videos/search"
                f"?query={requests.utils.quote(clean_q)}&orientation=portrait&per_page=5"
            )
            r = requests.get(url, headers=headers, timeout=12).json()
            videos = r.get("videos", [])
            if not videos:
                fb_q = FALLBACK_THRILLER_QUERIES[i % len(FALLBACK_THRILLER_QUERIES)]
                url2 = (
                    f"https://api.pexels.com/videos/search"
                    f"?query={requests.utils.quote(fb_q)}&orientation=portrait&per_page=4"
                )
                r = requests.get(url2, headers=headers, timeout=12).json()
                videos = r.get("videos", [])
            if videos:
                files = videos[0].get("video_files", [])
                portraits = [f for f in files if (f.get("height", 0) or 0) >= (f.get("width", 0) or 0)]
                download_url = portraits[0]["link"] if portraits else (files[0]["link"] if files else None)
        except Exception as e:
            print(f"   [Pexels] Query error: {e}")

        if download_url:
            try:
                content = requests.get(download_url, timeout=30).content
                with open(target_file, "wb") as f:
                    f.write(content)
                asset_paths.append(target_file)
                print(f"   Scene {i+1}: ✓ Pexels video ({len(content)/1024/1024:.1f} MB)")
                continue
            except Exception as e:
                print(f"   [Pexels] Download error: {e}")

        # Tier 3: Procedural cinematic frame (guaranteed)
        print(f"   Scene {i+1}: Using procedural cinematic fallback frame")
        proc_path = FRAMES_DIR / f"procedural_{video_seed}_{i+1}.jpg"
        _make_procedural_frame(i, topic_hint, cat_key, proc_path)
        asset_paths.append(proc_path)

    return asset_paths


# Keep old function name as alias for backward compatibility
def fetch_character_scene_videos(scenes: List[Dict[str, Any]]) -> List[Path]:
    """Backward-compatible alias. Delegates to fetch_scene_visuals."""
    return fetch_scene_visuals(scenes, video_seed=int(time.time()) % 10000)


# ---------------------------------------------------------------------
# 7. Higgsfield-Style 2.5D Cinematic Camera Motion Engine (Zero Cost)
# ---------------------------------------------------------------------
try:
    from moviepy import VideoClip as _VClip
except ImportError:
    from moviepy.editor import VideoClip as _VClip


def _smootherstep(t: float) -> float:
    """Perlin's smootherstep curve: 6t^5 - 15t^4 + 10t^3.
    Guarantees 1st and 2nd derivatives are 0 at boundaries, yielding zero-jerk physical camera inertia."""
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


# Studio-grade Higgsfield/Astra camera archetypes
_HIGGSFIELD_CAMERA_ARCHETYPES = [
    # (name, zoom_start, zoom_end, dx_frac, dy_frac, motion_type)
    ("cinematic_dolly_in",       1.00, 1.16,  0.000, -0.015, "dolly_in"),
    ("dolly_out_grand_reveal",   1.18, 1.02,  0.000,  0.020, "dolly_out"),
    ("pedestal_crane_rise",      1.04, 1.13,  0.010, -0.035, "pedestal_rise"),
    ("dramatic_vertigo_zoom",    1.00, 1.20,  0.000,  0.000, "vertigo"),
    ("orbital_arc_drift",        1.03, 1.14,  0.035,  0.010, "orbital_arc"),
    ("steadicam_handheld_drift", 1.02, 1.11,  0.000,  0.000, "steadicam"),
]


def _make_higgsfield_camera_clip(img_path: Path, duration: float, scene_idx: int):
    """
    Higgsfield / Astra Studio-Grade 2.5D Cinematic Camera Motion Engine:
    - Zero cost & zero heavyweight GPU dependencies (renders 30+ fps on CPU)
    - Perlin smootherstep S-curve easing (accelerates & decelerates with physical Steadicam inertia)
    - 6 distinct cinematic camera archetypes:
        1. Dolly In (slow push-in with anamorphic focal breathing)
        2. Dolly Out (grand reveal expanding environment)
        3. Pedestal Crane Rise (vertical crane travel to subject eye-line)
        4. Dramatic Vertigo Zoom (Hitchcock perspective warp)
        5. Orbital Arc Drift (curved track parallax simulation)
        6. Steadicam Handheld Drift (multi-harmonic human operator sway)
    - Anti-aliased sub-pixel cropping on oversized padded canvas
    - Subtle 35mm anamorphic edge vignette
    """
    name, z_s, z_e, dx_target, dy_target, m_type = _HIGGSFIELD_CAMERA_ARCHETYPES[
        scene_idx % len(_HIGGSFIELD_CAMERA_ARCHETYPES)
    ]
    W, H = 1080, 1920
    PAD = 160  # Padded canvas for safe edge-free camera travels

    raw_pil = Image.open(str(img_path)).convert("RGB")
    cw_target, ch_target = W + PAD * 2, H + PAD * 2
    pil = raw_pil.resize((cw_target, ch_target), Image.LANCZOS)
    cw, ch = pil.size

    dur_safe = max(duration, 0.001)

    def make_frame(t: float):
        norm_t = min(1.0, max(0.0, t / dur_safe))
        ease = _smootherstep(norm_t)

        if m_type == "dolly_in":
            # Smooth push-in with subtle anamorphic lens breathing
            breathing = 0.003 * math.sin(2.0 * math.pi * norm_t)
            zoom = z_s + (z_e - z_s) * ease + breathing
            pan_x = int(dx_target * cw * ease)
            pan_y = int(dy_target * ch * ease)
        elif m_type == "dolly_out":
            # Grand reveal pull-back
            zoom = z_s + (z_e - z_s) * ease
            pan_x = int(dx_target * cw * ease)
            pan_y = int(dy_target * ch * ease)
        elif m_type == "pedestal_rise":
            # Vertical crane ascent from lower-third to eye-level
            zoom = z_s + (z_e - z_s) * ease
            pan_x = int(dx_target * cw * ease)
            crane_y = (0.030 - 0.060 * ease) * ch
            pan_y = int(crane_y)
        elif m_type == "vertigo":
            # Hitchcock dolly zoom: exponential ease on zoom with counter-framing
            v_ease = norm_t ** 1.8
            zoom = z_s + (z_e - z_s) * v_ease
            pan_x = 0
            pan_y = int(-0.015 * ch * v_ease)
        elif m_type == "orbital_arc":
            # Curved orbital track: lateral pan peaks in middle, zoom is continuous
            zoom = z_s + (z_e - z_s) * ease
            arc_x = math.sin(math.pi * ease) * (dx_target * cw)
            pan_x = int(arc_x)
            pan_y = int(dy_target * ch * ease)
        elif m_type == "steadicam":
            # Natural human operator breathing on EasyRig (harmonic sin/cos sway)
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
    clip = _VClip(make_frame)
    if MOVIEPY_V2:
        return clip.with_duration(duration)
    else:
        return clip.set_duration(duration)


# Backward-compatible alias
_make_kenburns_clip = _make_higgsfield_camera_clip


# ---------------------------------------------------------------------
# 8. Master Video Assembler (Continuous Voice + Thriller Sound + Vignette)
# ---------------------------------------------------------------------
def assemble_thriller_short(
    storyboard: Dict[str, Any],
    voice_audio_path: Path,
    scene_timings: List[Tuple[float, float]],
    video_items: List[Path],
    output_path: Path
) -> Path:
    """
    Assembles the thriller Short with:
    - Frame-accurate scene cuts (supports both still images and video clips)
    - Ken Burns motion effect on still images for dynamic feel
    - Full-bleed 1080x1920 cover scaling (zero black bars)
    - Dynamic Alex Hormozi subtitle badges with neon yellow keywords
    - Cinematic dark vignette overlay layer
    - Continuous speech mixed with procedural low-frequency thriller drone
    """
    scenes = storyboard["scenes"]
    is_hindi = storyboard.get("is_hindi", False)
    print("\n🎞️ [Compositor] Assembling character-driven thriller Short...")

    # Force total visual duration to equal the exact voiceover duration
    voice_audio = AudioFileClip(str(voice_audio_path))
    total_voice_duration = float(voice_audio.duration)

    num_scenes = max(1, len(video_items))
    scene_duration = total_voice_duration / num_scenes
    print(f"   Audio Duration: {total_voice_duration:.2f}s | Scenes: {num_scenes} | Exact Scene Duration: {scene_duration:.2f}s")

    video_clips = []
    subtitle_overlays = []

    for i, scene in enumerate(scenes):
        start_t = i * scene_duration
        scene_dur = scene_duration
        asset_file = video_items[i]
        ext = asset_file.suffix.lower()

        print(f"   Scene {i+1}: {asset_file.name} ({ext}) @ {scene_dur:.2f}s")

        # 1a. Still image → Ken Burns animated clip
        if ext in (".jpg", ".jpeg", ".png", ".webp"):
            clip_base = _make_kenburns_clip(asset_file, scene_dur, i)
        else:
            # 1b. Video clip → trim/loop to scene duration with full-bleed cover
            raw_vc = VideoFileClip(str(asset_file))
            vc_dur = raw_vc.duration
            if vc_dur >= scene_dur:
                cut = (raw_vc.subclipped(0, scene_dur)
                       if hasattr(raw_vc, "subclipped")
                       else raw_vc.subclip(0, scene_dur))
            else:
                repeats = max(1, int(scene_dur / max(vc_dur, 0.1)) + 1)
                extended = concatenate_videoclips([raw_vc] * repeats)
                cut = (extended.subclipped(0, scene_dur)
                       if hasattr(extended, "subclipped")
                       else extended.subclip(0, scene_dur))
            # Cover-scale to 1080x1920
            w, h = cut.w, cut.h
            scale = max(1080.0 / w, 1920.0 / h)
            new_w, new_h = int(round(w * scale)), int(round(h * scale))
            if hasattr(cut, "resized"):
                resized = cut.resized((new_w, new_h))
            else:
                resized = cut.resize((new_w, new_h))
            if hasattr(resized, "cropped"):
                clip_base = resized.cropped(
                    x_center=new_w / 2, y_center=new_h / 2, width=1080, height=1920
                )
            else:
                clip_base = resized.crop(
                    x_center=new_w / 2, y_center=new_h / 2, width=1080, height=1920
                )

        # Explicitly assign each scene clip: clip.set_duration(scene_duration)
        if hasattr(clip_base, "with_duration"):
            clip_base = clip_base.with_duration(scene_dur)
        else:
            clip_base = clip_base.set_duration(scene_dur)
        video_clips.append(clip_base)

        # 2. Modern Open Captions (MrBeast/Hormozi style — no pill box)
        sub_text = scene.get("subtitle_display") or scene.get("voiceover", "")[:80]
        hl_words = scene.get("highlight_words", [])
        badge_img = render_subtitle_badge(sub_text, highlight_words=hl_words, is_hindi=is_hindi)
        overlay_clip = ImageClip(np.array(badge_img))
        if hasattr(overlay_clip, "with_duration"):
            overlay_clip = (
                overlay_clip.with_duration(scene_dur)
                .with_position(("center", 1100))
                .with_start(start_t)
            )
        else:
            overlay_clip = (
                overlay_clip.set_duration(scene_dur)
                .set_position(("center", 1100))
                .set_start(start_t)
            )
        subtitle_overlays.append(overlay_clip)

    # Concatenate base visual cuts & explicitly enforce total_voice_duration
    base_video = concatenate_videoclips(video_clips, method="compose")
    if hasattr(base_video, "with_duration"):
        base_video = base_video.with_duration(total_voice_duration)
    else:
        base_video = base_video.set_duration(total_voice_duration)

    # 3. Cinematic Vignette Overlay Layer
    vignette_file = ASSETS_DIR / "cinematic_vignette.png"
    vignette_img = Image.open(str(vignette_file)).convert("RGBA")
    vignette_clip = ImageClip(np.array(vignette_img))
    if hasattr(vignette_clip, "with_duration"):
        vignette_clip = (
            vignette_clip.with_duration(total_voice_duration)
            .with_position((0, 0))
            .with_start(0.0)
        )
    else:
        vignette_clip = (
            vignette_clip.set_duration(total_voice_duration)
            .set_position((0, 0))
            .set_start(0.0)
        )

    # 4. Audio Design: Continuous Speech + Background Music strictly trimmed to voice_duration
    drone_file = ASSETS_DIR / "thriller_drone.wav"
    audio_tracks = [voice_audio]
    if drone_file.exists():
        drone_raw = AudioFileClip(str(drone_file))
        # Strictly trim background music to voice_duration using .subclip(0, voice_duration)
        if hasattr(drone_raw, "subclipped"):
            drone_cut = drone_raw.subclipped(0, total_voice_duration)
        else:
            drone_cut = drone_raw.subclip(0, total_voice_duration)
        if hasattr(drone_cut, "with_volume_scaled"):
            drone_cut = drone_cut.with_volume_scaled(0.12)
        elif hasattr(drone_cut, "volumex"):
            drone_cut = drone_cut.volumex(0.12)
        audio_tracks.append(drone_cut)

    composite_audio = CompositeAudioClip(audio_tracks) if len(audio_tracks) > 1 else voice_audio
    if hasattr(composite_audio, "with_duration"):
        composite_audio = composite_audio.with_duration(total_voice_duration)
    else:
        composite_audio = composite_audio.set_duration(total_voice_duration)

    if hasattr(base_video, "with_audio"):
        base_video = base_video.with_audio(composite_audio)
    else:
        base_video = base_video.set_audio(composite_audio)

    # 5. Composite Final Stack: [Base Video, Vignette, Subtitles]
    final_comp = CompositeVideoClip([base_video, vignette_clip, *subtitle_overlays])
    if hasattr(final_comp, "with_duration"):
        final_comp = final_comp.with_duration(total_voice_duration)
    else:
        final_comp = final_comp.set_duration(total_voice_duration)

    print(f"🎬 [Compositor] Rendering {final_comp.duration:.1f}s @ 24fps → {output_path.name}")
    final_comp.write_videofile(
        str(output_path),
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None,
        remove_temp=False,
        ffmpeg_params=["-shortest", "-pix_fmt", "yuv420p"]
    )

    # Close all clips
    for c in [final_comp, base_video, vignette_clip, voice_audio] + video_clips + subtitle_overlays:
        try:
            c.close()
        except Exception:
            pass
    for tmp_file in BASE_DIR.glob("*TEMP_MPY*"):
        try:
            tmp_file.unlink()
        except Exception:
            pass

    print(f"✅ [Compositor] Done: {output_path} ({os.path.getsize(output_path)/1024/1024:.2f} MB)")
    # Apply studio-grade photographic clarity, micro-contrast, and 35mm film grain grade
    apply_photographic_clarity_grade(output_path)
    return output_path


# ---------------------------------------------------------------------
# 8. Post-Processing Sharpening & Micro-Contrast Grade (FFmpeg)
# ---------------------------------------------------------------------
def apply_photographic_clarity_grade(video_path: Path) -> Path:
    """
    Applies studio-grade Photographic Clarity & Film Grade pass via FFmpeg:
    1. Contrast Adaptive Sharpening (unsharp=5:5:0.8:5:5:0.0) for crisp micro-textures
    2. Dynamic Range & Micro-Contrast: eq=contrast=1.05:brightness=0.01:saturation=1.02
    3. Organic 35mm monochrome micro-grain: noise=alls=4:allf=t+u
    """
    if not video_path.exists():
        return video_path

    temp_graded = video_path.with_name(f"{video_path.stem}_graded{video_path.suffix}")
    try:
        import subprocess, imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        vf_filter = "unsharp=5:5:0.8:5:5:0.0,eq=contrast=1.05:brightness=0.01:saturation=1.02,noise=alls=4:allf=t+u"
        cmd = [
            ffmpeg_exe, "-y",
            "-i", str(video_path),
            "-vf", vf_filter,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-c:a", "copy",
            "-shortest",
            str(temp_graded)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and temp_graded.exists() and temp_graded.stat().st_size > 10000:
            temp_graded.replace(video_path)
            print(f"✨ [Clarity Engine] Applied 35mm unsharp mask, micro-contrast & organic film grain to {video_path.name}")
        else:
            if temp_graded.exists():
                temp_graded.unlink(missing_ok=True)
    except Exception as ex:
        print(f"⚠️ [Clarity Engine] Post-processing grade notice: {ex}")
        if temp_graded.exists():
            temp_graded.unlink(missing_ok=True)

    return video_path


# ---------------------------------------------------------------------
# 8. Master Production Pipeline Entrypoint
# ---------------------------------------------------------------------
def produce_cinematic_short(
    topic_directive: str = "",
    category: str = "auto",
    language: str = "auto",
    output_path: Path = None
) -> Dict[str, Any]:
    """
    Orchestrates the complete character-driven thriller Short production:
    1. Gemini Storyboard Director (10-category matrix, always 4 complete scenes)
    2. Continuous Voiceover Synthesis (zero pause, +11% speed, exact sentence timestamps)
    3. Pollinations AI frame generation → Pexels video → Procedural fallback visuals
    4. MoviePy & Pillow Compositor (Ken Burns motion, Hormozi captions, vignette, drone sound)
    """
    if output_path is None:
        output_path = BASE_DIR / "final_short.mp4"

    video_seed = int(time.time()) % 100000
    start_time = time.time()
    print("\n" + "=" * 65)
    print("🚀 [THRILLER SHORT ENGINE] Starting Character-Driven Production")
    print("=" * 65)

    # Step 1: Scripting with Gemini (always returns complete 4-scene storyboard)
    storyboard = generate_multi_scene_script(
        topic_directive=topic_directive,
        category=category,
        language=language
    )
    scenes = storyboard["scenes"]
    is_hindi = storyboard.get("is_hindi", False)
    cat_key = storyboard.get("category", "curiosity")

    print(f"\n📋 Thriller Storyboard Plan:")
    print(f"• Category: {cat_key}")
    print(f"• Topic:    {storyboard.get('topic_used')}")
    print(f"• Title:    {storyboard.get('title')}")
    print(f"• Scenes:   {len(scenes)}")
    for sc in scenes:
        print(f"  [Scene {sc.get('scene_id')}] {sc.get('type','?')} | Subtitle: '{sc.get('subtitle_display','')[:50]}'")
        print(f"             Voiceover: '{sc.get('voiceover','')[:60]}...'")

    # Step 2: Continuous Voiceover Synthesis (0.0s gap)
    temp_voice = SCENES_CACHE_DIR / f"continuous_voice_{int(time.time())}.mp3"
    total_dur, scene_timings = synthesize_continuous_voiceover(
        scenes, is_hindi=is_hindi, out_audio_path=temp_voice
    )

    # Step 3: Visual assets — Pollinations AI → Pexels → Procedural (guaranteed visuals)
    video_items = fetch_scene_visuals(scenes, video_seed=video_seed)

    # Step 4: Final Assembly & Rendering
    rendered_file = assemble_thriller_short(storyboard, temp_voice, scene_timings, video_items, output_path)

    # Cleanup temp voice
    try:
        temp_voice.unlink(missing_ok=True)
    except Exception:
        pass

    elapsed = time.time() - start_time

    result = {
        "title": storyboard.get("title"),
        "description": storyboard.get("description"),
        "tags": storyboard.get("tags", []),
        "topic_used": storyboard.get("topic_used"),
        "category": cat_key,
        "is_hindi": is_hindi,
        "scenes_count": len(scenes),
        "total_duration": round(total_dur, 2),
        "render_time": round(elapsed, 1),
        "file_path": str(rendered_file),
        "file_size_mb": round(os.path.getsize(rendered_file) / 1024 / 1024, 2)
    }
    print(f"\n🎉 Thriller Production Succeeded in {elapsed:.1f}s!")
    print(f"• File: {result['file_path']} ({result['file_size_mb']} MB, {result['total_duration']}s)")
    return result


if __name__ == "__main__":
    directive = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else ""
    res = produce_cinematic_short(topic_directive=directive)
    print("\nResult:")
    print(json.dumps(res, indent=2))
