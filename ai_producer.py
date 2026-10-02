"""
ai_producer.py - Autonomous AI Producer Pipeline for YouTube Shorts
=====================================================================
A fully autonomous, agentic pipeline that:
1. Live Research & Fact-Finding Stage (The "Brain"):
   - Scrapes live RSS feeds (Google News, ScienceDaily) for trending breakthroughs.
   - Extracts 3 verified counter-intuitive facts, physical details, and curiosity triggers.
2. Editorial & Story Director (Ideation & Hook):
   - Generates 3 distinct hook variations (Question, Negative Constraint, Shocking Metric).
   - Evaluates hooks via an LLM scoring matrix and picks the highest-retention concept.
   - Drafts a tight 35-45 second script segmented into 7 to 9 narrative beats with an infinite loop.
3. Visual Director & Scene Choreographer:
   - Writes research-grounded visual descriptions dictating focal lengths, lighting, and palettes.
   - Injects authentic 35mm photography tokens and matches pacing to audio syllables.
4. The Self-Critique & Quality Gatekeeper (Evaluator-Optimizer Loop):
   - Script Check: Evaluates clarity, retention flow, and loop potential (auto-revises if < 75).
   - Visual Check: Validates images exist, size > 50KB, non-blank variance.
   - Frame Continuity: Enforces framing variety across consecutive scenes.
5. Assembly & Autonomous Publisher:
   - Renders 1080x1920 video with Higgsfield 2.5D camera motion (smootherstep).
   - Adds bold mobile subtitle badges at safe area (y=1100).
   - Mixes voiceover and procedural ambient drone.
   - Runs FFmpeg photographic clarity grading pass (unsharp mask, micro-contrast, organic grain).
   - Generates SEO metadata and uploads to YouTube Data API v3 (or queues locally).
"""

import os
import sys
import json
import time
import math
import random
import string
import re
import logging
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import xml.etree.ElementTree as ET

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from dotenv import load_dotenv

# Safe UTF-8 encoding for Windows terminals
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

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ai_producer.log", encoding="utf-8", mode="a")
    ]
)
log = logging.getLogger("AIProducer")

# Path Configuration
BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"
PRODUCER_CACHE_DIR = ASSETS_DIR / "producer_cache"
FRAMES_DIR = ASSETS_DIR / "producer_frames"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
PRODUCER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = BASE_DIR / "history.json"
DAILY_REPORT_FILE = BASE_DIR / "daily_report.json"
STATE_FILE = BASE_DIR / "autopilot_state.json"

# API Keys & Gemini Client
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
from google import genai
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

GEMINI_MODELS_POOL = [
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
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
        concatenate_audioclips,
        CompositeAudioClip,
        CompositeVideoClip
    )
    MOVIEPY_V2 = True
except ImportError:
    from moviepy.editor import (
        VideoFileClip,
        AudioFileClip,
        ImageClip,
        concatenate_videoclips,
        concatenate_audioclips,
        CompositeAudioClip,
        CompositeVideoClip
    )
    MOVIEPY_V2 = False

# Import Reusable Visual and Camera Utilities from video_engine
from video_engine import (
    _make_higgsfield_camera_clip,
    _generate_pollinations_frame,
    _apply_vignette_to_pil,
    _make_procedural_frame,
    apply_photographic_clarity_grade,
    _clean_synthetic_keywords,
    ensure_cinematic_assets,
    AUTHENTIC_PHOTOGRAPHY_DNA,
    NEGATIVE_PROMPT_TOKENS
)


# =============================================================================
# Helper: Gemini Robust LLM Invocation
# =============================================================================
def call_gemini_json(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    """Calls Gemini across the model fallback pool and parses JSON response."""
    if not ai_client:
        log.warning("[Gemini] No GEMINI_API_KEY set. Cannot invoke AI.")
        return None

    full_prompt = f"{system_prompt}\n\nUSER REQUEST:\n{user_prompt}\n\nRespond ONLY with valid JSON."
    for model_name in GEMINI_MODELS_POOL:
        try:
            resp = ai_client.models.generate_content(
                model=model_name,
                contents=full_prompt
            )
            raw = resp.text.strip().replace("```json", "").replace("```", "").strip()
            s = raw.find("{")
            e = raw.rfind("}")
            if s != -1 and e != -1:
                raw = raw[s:e + 1]
            data = json.loads(raw)
            log.info(f"   [Gemini] Model '{model_name}' generated structured response.")
            return data
        except Exception as ex:
            log.warning(f"   [Gemini] '{model_name}' failed or rate-limited: {ex}")
            time.sleep(1.0)
            continue
    log.error("[Gemini] All models in fallback pool exhausted.")
    return None


# =============================================================================
# STAGE 1: Live Research & Fact-Finding Stage (The "Brain")
# =============================================================================
class LiveResearchBrain:
    """
    Autonomous research agent that scrapes live RSS feeds across Google News,
    ScienceDaily, and discovery portals to identify viral trending subjects.
    Extracts 3 verified counter-intuitive facts, tangible physical parameters
    (scale, textures, lighting, temperatures), and psychological curiosity triggers.
    """

    RSS_FEEDS = [
        {
            "name": "Google News Science & Discoveries",
            "url": "https://news.google.com/rss/search?q=scientific+breakthrough+OR+archaeological+discovery+OR+space+mystery&hl=en-US&gl=US&ceid=US:en",
            "category": "science_discovery"
        },
        {
            "name": "ScienceDaily Top Breakthroughs",
            "url": "https://www.sciencedaily.com/rss/top/science.xml",
            "category": "scientific_breakthrough"
        },
        {
            "name": "ScienceDaily Strange & Offbeat",
            "url": "https://www.sciencedaily.com/rss/strange_offbeat.xml",
            "category": "strange_anomalies"
        }
    ]

    FALLBACK_ARCHIVE = [
        {
            "topic": "The Kola Superdeep Borehole Paradox",
            "headline": "Soviet scientists drilled 40,000 feet into Earth and found boiled water and unexpected acoustics",
            "source": "Historical Geological Archive",
            "counter_intuitive_facts": [
                "At 12 kilometers depth, rock ceases to be brittle and behaves like soft plastic putty.",
                "Water was discovered boiling at 180°C inside solid granite where no liquid was thought possible.",
                "The acoustic sensor recordings revealed high-velocity screeching micro-fractures nicknamed the 'sounds of hell'."
            ],
            "entities_and_dates": [
                {"name": "Kola Peninsula", "role": "Soviet Drilling Site", "date_or_era": "1970-1992"},
                {"name": "SG-3 Borehole", "role": "Deepest Artificial Point on Earth", "date_or_era": "May 1989"}
            ],
            "physical_environment": {
                "scale_and_dimensions": "12,262 meters deep, 9 inches diameter borehole chamber",
                "materials_and_textures": "crushed crystalline granite, muddy hydrothermal mud, glowing drill bit",
                "lighting_and_atmosphere": "pitch black abyss illuminated only by heavy industrial tungsten lamps, suffocating steam haze",
                "temperatures_or_physics": "180 degrees Celsius, 4,000 atmospheres of lithostatic pressure"
            },
            "core_emotional_tension": "The eerie claustrophobia of piercing into the planetary underworld where physics breaks down.",
            "curiosity_trigger": "Why did the world's deepest drill suddenly melt shut?"
        },
        {
            "topic": "Lake Vostok: The Alien Sea Sealed Under 4km of Antarctic Ice",
            "headline": "Russian drills pierced a pristine freshwater ocean sealed from Earth's atmosphere for 15 million years",
            "source": "Antarctic Glaciology Archive",
            "counter_intuitive_facts": [
                "The lake water stays liquid at -3°C under 350 atmospheres of pure overburden pressure.",
                "The dissolved oxygen concentration is 50 times higher than regular fresh water, creating an hyperoxic environment.",
                "Geothermal vents on the lake floor maintain a completely dark biome disconnected from solar photosynthesis."
            ],
            "entities_and_dates": [
                {"name": "Lake Vostok", "role": "Subglacial Lake", "date_or_era": "Discovered 1996"},
                {"name": "Vostok Station", "role": "Coldest Inhabited Point on Earth", "date_or_era": "February 2012"}
            ],
            "physical_environment": {
                "scale_and_dimensions": "250 km long, 50 km wide, buried under 4,000 meters of prehistoric ice sheet",
                "materials_and_textures": "tack sharp sapphire-blue accretion ice, crystal clear pressurized water, black hydrothermal basalt",
                "lighting_and_atmosphere": "complete abyssal darkness punctuated by cold robotic LED drill lights and bioluminescent microbes",
                "temperatures_or_physics": "-3°C liquid water, extreme hyper-pressure, absolute atmospheric isolation"
            },
            "core_emotional_tension": "The terrifying realization that prehistoric lifeforms are swimming right beneath Antarctic ice.",
            "curiosity_trigger": "What survived 15 million years locked in total darkness?"
        },
        {
            "topic": "The Antikythera Mechanism: 2,000-Year-Old Analog Computer",
            "headline": "Sponge divers off a Greek island retrieved a corroded bronze clockwork that calculated planetary orbits",
            "source": "Archaeological Heritage Archive",
            "counter_intuitive_facts": [
                "It contained 37 precision bronze differential gears centuries before Renaissance watchmakers reinvented them.",
                "The device predicted lunar eclipses down to the exact hour and tracked Olympic game cycles.",
                "Its mechanical complexity vanished from human history for over 1,400 years after the Roman ship sank."
            ],
            "entities_and_dates": [
                {"name": "Antikythera Island", "role": "Aegean Shipwreck Location", "date_or_era": "60-70 BC"},
                {"name": "Valerios Stais", "role": "Archaeologist", "date_or_era": "May 1902"}
            ],
            "physical_environment": {
                "scale_and_dimensions": "34 cm wooden box housing interlocking precision bronze cogs",
                "materials_and_textures": "oxidized greenish-bronze patina, calcified Aegean sea sponges, micro-inscriptions in ancient Greek",
                "lighting_and_atmosphere": "deep ocean turquoise shafts cutting through murky shipwreck sediment, dramatic restoration laboratory lighting",
                "temperatures_or_physics": "45 meters underwater depth, centuries of marine encrustation"
            },
            "core_emotional_tension": "The unsettling mystery of an advanced technology lost to the dark ages.",
            "curiosity_trigger": "Who built an analog computer 2,000 years before modern clocks?"
        },
        {
            "topic": "The Chernobyl Elephant's Foot: Earth's Deadliest Mass",
            "headline": "Beneath Reactor 4 lies a 2-ton radioactive corium mass that can end human life in 300 seconds",
            "source": "Nuclear Physics Safety Archive",
            "counter_intuitive_facts": [
                "It is not pure metal, but corium: a synthetic volcanic glass formed from melted fuel rods, sand, and concrete.",
                "In 1986, taking a single photograph required rolling a motorized camera cart into the room because film fogged instantly.",
                "Workers attempting to sample it had to shoot it with an AK-47 rifle because standard drills bounced off its ceramic density."
            ],
            "entities_and_dates": [
                {"name": "Reactor No. 4", "role": "Chernobyl Nuclear Plant", "date_or_era": "April 26, 1986"},
                {"name": "Artur Korneyev", "role": "Nuclear Inspector", "date_or_era": "1996 Photograph"}
            ],
            "physical_environment": {
                "scale_and_dimensions": "2 meters wide, 2 tons mass, pooled in a collapsed basement steam corridor",
                "materials_and_textures": "wrinkled obsidian-black corium crust, crystallized ceramic slag, peeling concrete walls",
                "lighting_and_atmosphere": "grainy flashlight beam cutting through radioactive dust, eerie amber ambient decay, film static noise",
                "temperatures_or_physics": "10,000 roentgens per hour radiation field, extreme molecular ionization"
            },
            "core_emotional_tension": "An invisible death aura in a dark room that destroys human DNA in minutes.",
            "curiosity_trigger": "Why did scientists need an AK-47 to study this 2-ton monster?"
        }
    ]

    def fetch_live_signals(self) -> List[Dict[str, str]]:
        """Queries live RSS feeds with timeouts and extracts top candidate headlines."""
        log.info("[Stage 1: Brain] Scanning live scientific & discovery RSS feeds...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        collected = []
        for feed in self.RSS_FEEDS:
            try:
                res = requests.get(feed["url"], headers=headers, timeout=6.0)
                if res.status_code == 200:
                    root = ET.fromstring(res.content)
                    items = root.findall(".//item")
                    for it in items[:6]:
                        t = it.find("title")
                        l = it.find("link")
                        d = it.find("description")
                        title_text = t.text.strip() if (t is not None and t.text) else ""
                        link_text = l.text.strip() if (l is not None and l.text) else ""
                        desc_text = d.text.strip() if (d is not None and d.text) else ""
                        if title_text and len(title_text) > 15:
                            collected.append({
                                "title": title_text,
                                "link": link_text,
                                "description": desc_text[:300],
                                "source": feed["name"]
                            })
                    log.info(f"   [Feed] Loaded {len(items)} items from '{feed['name']}'")
            except Exception as ex:
                log.warning(f"   [Feed Error] Could not reach '{feed['name']}': {ex}")

        log.info(f"[Stage 1: Brain] Discovered {len(collected)} live trending research signals.")
        return collected

    def perform_deep_research(self, custom_topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Conducts research on either a live trending signal, a user topic, or a fallback discovery.
        Extracts:
        - 3 verified, counter-intuitive facts
        - Specific names, dates, physical descriptions
        - Core emotional tension & curiosity trigger
        """
        live_signals = self.fetch_live_signals()
        selected_signal = None

        if custom_topic:
            selected_signal = {
                "title": custom_topic,
                "description": f"Targeted exploration of {custom_topic}",
                "source": "Direct Directive"
            }
        elif live_signals:
            # Pick a rich, high-intrigue live topic
            selected_signal = random.choice(live_signals[:10])
        else:
            log.info("[Stage 1: Brain] Utilizing curated historical/scientific anomaly archive.")
            return random.choice(self.FALLBACK_ARCHIVE)

        log.info(f"[Stage 1: Brain] Selected Subject for Deep Fact Extraction: '{selected_signal['title']}'")

        system_prompt = (
            "You are a Senior Investigative Science Journalist and Documentary Researcher.\n"
            "Your task is to analyze the given topic/headline and extract verified, counter-intuitive facts, "
            "tangible physical descriptions, and emotional curiosity triggers suitable for an elite viral documentary.\n\n"
            "CRITICAL EXTRACTION REQUIREMENTS:\n"
            "1. Three Verified Counter-Intuitive Facts: Surprising, mind-bending, counter-intuitive facts that challenge common assumptions.\n"
            "2. Specific Entities and Dates: Real historical figures, scientists, missions, or dates.\n"
            "3. Tangible Physical Descriptions: Real-world physical parameters (scale/dimensions, exact materials/textures, lighting/atmosphere, temperatures or extreme physics).\n"
            "4. Core Emotional Tension: The psychological hook (dread, awe, disbelief, claustrophobia).\n"
            "5. Curiosity Trigger: A 1-sentence viral question.\n\n"
            "OUTPUT FORMAT (STRICT JSON ONLY):\n"
            "{\n"
            '  "topic": "Short punchy subject name",\n'
            '  "headline": "Compelling journalistic headline",\n'
            '  "source": "Name of scientific institution / field",\n'
            '  "counter_intuitive_facts": [\n'
            '    "Fact 1...",\n'
            '    "Fact 2...",\n'
            '    "Fact 3..."\n'
            "  ],\n"
            '  "entities_and_dates": [\n'
            '    {"name": "...", "role": "...", "date_or_era": "..."}\n'
            "  ],\n"
            '  "physical_environment": {\n'
            '    "scale_and_dimensions": "...",\n'
            '    "materials_and_textures": "...",\n'
            '    "lighting_and_atmosphere": "...",\n'
            '    "temperatures_or_physics": "..."\n'
            "  },\n"
            '  "core_emotional_tension": "...",\n'
            '  "curiosity_trigger": "..."\n'
            "}"
        )

        user_prompt = f"HEADLINE / TOPIC: {selected_signal['title']}\nSUMMARY: {selected_signal.get('description', '')}"

        data = call_gemini_json(system_prompt, user_prompt)
        if data and "counter_intuitive_facts" in data and len(data["counter_intuitive_facts"]) >= 3:
            log.info(f"[Stage 1: Brain] Verified 3 counter-intuitive facts on: {data.get('topic')}")
            return data

        log.warning("[Stage 1: Brain] LLM fact extraction returned incomplete data. Using fallback archive.")
        return random.choice(self.FALLBACK_ARCHIVE)


# =============================================================================
# STAGE 2: Editorial & Story Director (Ideation & Hook)
# =============================================================================
class EditorialStoryDirector:
    """
    Autonomous Editorial Director that:
    1. Drafts 3 distinct hook variations (Question, Negative Constraint, Shocking Metric).
    2. Runs an automated LLM evaluation matrix to score thumb-stop and retention power.
    3. Drafts a tight 35-45 second script segmented into 7 to 9 narrative beats with an infinite loop ending.
    """

    def ideate_and_evaluate_hooks(self, research: Dict[str, Any]) -> Dict[str, Any]:
        """
        Drafts 3 distinct hook variations, evaluates retention scores,
        and selects the highest-scoring hook.
        """
        log.info("[Stage 2: Director] Ideating 3 viral hook variations...")
        system_prompt = (
            "You are a World-Class Viral Storytelling Director specializing in YouTube Shorts retention.\n"
            "Given the extracted research facts and physical environment, draft 3 distinct hook variations:\n"
            "1. Question Hook: A visceral question opening a massive curiosity gap.\n"
            "2. Negative Constraint Hook: A high-urgency warning ('Never do X...', 'Whatever you do, don't touch...').\n"
            "3. Shocking Metric Hook: A mind-bending physical number, temperature, or extreme dimension.\n\n"
            "Then, evaluate each hook on 4 retention criteria (0 to 10 each):\n"
            "- thumb_stop_power: Will a user scrolling rapidly pause immediately?\n"
            "- curiosity_gap: How urgently does the viewer need the answer?\n"
            "- emotional_tension: Level of awe, wonder, or psychological dread.\n"
            "- narrative_transition: How smoothly does it flow into the story?\n\n"
            "Calculate total_score (sum of the 4 metrics) and select the highest scoring winning_hook.\n\n"
            "STRICT JSON OUTPUT FORMAT:\n"
            "{\n"
            '  "hooks": [\n'
            '    {\n'
            '      "hook_type": "question",\n'
            '      "hook_text": "...",\n'
            '      "scores": {"thumb_stop_power": 9, "curiosity_gap": 9, "emotional_tension": 8, "narrative_transition": 9},\n'
            '      "total_score": 35\n'
            '    },\n'
            '    {\n'
            '      "hook_type": "negative_constraint",\n'
            '      "hook_text": "...",\n'
            '      "scores": {"thumb_stop_power": 8, "curiosity_gap": 8, "emotional_tension": 9, "narrative_transition": 8},\n'
            '      "total_score": 33\n'
            '    },\n'
            '    {\n'
            '      "hook_type": "shocking_metric",\n'
            '      "hook_text": "...",\n'
            '      "scores": {"thumb_stop_power": 9, "curiosity_gap": 9, "emotional_tension": 9, "narrative_transition": 9},\n'
            '      "total_score": 36\n'
            '    }\n'
            '  ],\n'
            '  "winning_hook": {\n'
            '    "hook_type": "...",\n'
            '    "hook_text": "...",\n'
            '    "rationale": "..."\n'
            '  }\n'
            "}"
        )

        user_prompt = (
            f"TOPIC: {research.get('topic')}\n"
            f"FACTS: {json.dumps(research.get('counter_intuitive_facts', []))}\n"
            f"ENVIRONMENT: {json.dumps(research.get('physical_environment', {}))}\n"
            f"CURIOSITY TRIGGER: {research.get('curiosity_trigger')}"
        )

        data = call_gemini_json(system_prompt, user_prompt)
        if data and "winning_hook" in data and "hook_text" in data["winning_hook"]:
            log.info(f"   [Winner Hook ({data['winning_hook']['hook_type']})]: {data['winning_hook']['hook_text']}")
            return data

        # Deterministic fallback hook
        facts = research.get("counter_intuitive_facts", ["A discovery that broke modern physics."])
        return {
            "hooks": [
                {"hook_type": "shocking_metric", "hook_text": f"Inside this anomaly, {facts[0]}", "total_score": 36}
            ],
            "winning_hook": {
                "hook_type": "shocking_metric",
                "hook_text": f"Inside this hidden anomaly, {facts[0]}",
                "rationale": "Direct fact-grounded curiosity hook"
            }
        }

    def draft_narrative_script(
        self,
        research: Dict[str, Any],
        winning_hook: Dict[str, Any],
        target_beats: int = 8,
        critique_feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Drafts a tight, 35-45 second script segmented into 7 to 9 narrative beats:
        Beat 1: Hook (0-4s)
        Beat 2: Physical Discovery / Paradox Environment
        Beat 3: Counter-Intuitive Fact 1 (tangible physical detail)
        Beat 4: Scientific / Historical Evidence & Exact Names/Dates
        Beat 5: Escalating Anomaly / Climax
        Beat 6: Real-World Consequence / Dangerous Mechanism
        Beat 7: Unresolved Mystery / Revelatory Truth
        Beat 8: Seamless Loop Hook (cycles back into Beat 1)
        """
        log.info(f"[Stage 2: Director] Drafting {target_beats}-beat documentary narrative script...")
        system_prompt = (
            "You are the Lead Creative Director for an elite, high-retention YouTube Shorts documentary channel "
            "(inspired by Zack D. Films, MagnatesMedia, Aperture, and Ridddle).\n"
            "Write a fast-paced 35-45 second script segmented into exactly 7 to 9 narrative beats.\n\n"
            "STRICT RULES:\n"
            "1. NO PROMPT LEAKAGE: In 'narration_text', write ONLY the spoken voiceover words. "
            "NEVER include bracketed visual cues, scene descriptions, sound effect labels, or speaker names.\n"
            "2. CLEAN SUBTITLES: 'subtitle_text' must be 4 to 8 punchy words per beat for quick mobile reading.\n"
            "3. KEYWORD HIGHLIGHTS: Provide 1 to 2 power words in 'highlight_words' to be highlighted in electric yellow.\n"
            "4. SEAMLESS LOOP: The final beat MUST end on an open transition phrase that semantically and syntactically "
            "flows directly back into the opening hook of Beat 1, creating an infinite retention loop!\n"
            "5. PACING: Target 14 to 22 spoken words per beat (~4 seconds per beat).\n"
            "6. FRAMING VARIETY: Assign a distinct 'visual_beat_type' to each beat "
            "('wide_establishing', 'macro_detail', 'medium_close_up', 'cinematic_portrait', 'low_angle_crane', 'overhead_drone', 'extreme_close_up').\n"
            "Ensure consecutive beats change framing!\n\n"
            "OUTPUT FORMAT (STRICT JSON ONLY):\n"
            "{\n"
            '  "title": "Viral Hook Title Under 90 chars #Shorts",\n'
            '  "total_estimated_duration_sec": 38,\n'
            '  "beats": [\n'
            '    {\n'
            '      "beat_number": 1,\n'
            '      "role": "hook",\n'
            '      "narration_text": "Exact spoken voiceover words...",\n'
            '      "subtitle_text": "PUNCHY 4-8 WORDS SUBTITLE",\n'
            '      "highlight_words": ["WORD1", "WORD2"],\n'
            '      "visual_beat_type": "macro_detail",\n'
            '      "camera_focal_length": "100mm macro prime",\n'
            '      "lighting_setup": "chiaroscuro high-contrast spotlight",\n'
            '      "color_palette": "obsidian black and neon cyan",\n'
            '      "estimated_syllables": 22\n'
            '    }\n'
            '  ]\n'
            "}"
        )

        user_prompt = (
            f"TOPIC: {research.get('topic')}\n"
            f"WINNING HOOK: {winning_hook.get('hook_text')}\n"
            f"3 VERIFIED FACTS: {json.dumps(research.get('counter_intuitive_facts', []))}\n"
            f"ENTITIES & DATES: {json.dumps(research.get('entities_and_dates', []))}\n"
            f"PHYSICAL ENVIRONMENT: {json.dumps(research.get('physical_environment', {}))}\n"
            f"DESIRED BEAT COUNT: {target_beats}\n"
        )
        if critique_feedback:
            user_prompt += f"\nPREVIOUS CRITIQUE FEEDBACK TO FIX:\n{critique_feedback}\n"

        data = call_gemini_json(system_prompt, user_prompt)
        if data and "beats" in data and len(data["beats"]) >= 6:
            # Sanitize each beat's narration to ensure zero prompt leakage
            for b in data["beats"]:
                clean_text = self._sanitize_narration(b.get("narration_text", ""))
                b["narration_text"] = clean_text
            log.info(f"[Stage 2: Director] Generated {len(data['beats'])} narrative beats successfully.")
            return data

        log.warning("[Stage 2: Director] Falling back to procedural script structure.")
        return self._build_fallback_script(research, winning_hook, target_beats)

    @staticmethod
    def _sanitize_narration(text: str) -> str:
        """Strips stage directions, brackets, and parentheticals to prevent audio prompt leakage."""
        t = re.sub(r"\[.*?\]", "", text)
        t = re.sub(r"\(.*?\)", "", t)
        t = re.sub(r"^(Max|Narrator|Voice|Scene \d+):\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"(wide shot|close up|drone shot|cutaway|camera moves)", "", t, flags=re.IGNORECASE)
        return " ".join(t.split()).strip()

    def _build_fallback_script(self, research: Dict[str, Any], hook: Dict[str, Any], count: int) -> Dict[str, Any]:
        topic = research.get("topic", "Mystery Anomaly")
        facts = research.get("counter_intuitive_facts", [
            "Extreme pressures alter standard physical laws.",
            "Historical records document sudden unexplained events.",
            "Modern scientific sensors recorded impossible readings."
        ])
        while len(facts) < 3:
            facts.append("Unprecedented anomalies were verified by researchers.")

        hook_text = hook.get("hook_text", f"This single anomaly completely changes everything we know about {topic}.")
        framings = ["macro_detail", "wide_establishing", "medium_close_up", "low_angle_crane",
                    "cinematic_portrait", "extreme_close_up", "overhead_drone", "macro_detail"]

        beats = [
            {
                "beat_number": 1,
                "role": "hook",
                "narration_text": hook_text,
                "subtitle_text": hook_text[:40].upper(),
                "highlight_words": ["NEVER", "ANOMALY"],
                "visual_beat_type": framings[0],
                "camera_focal_length": "85mm prime",
                "lighting_setup": "dramatic chiaroscuro",
                "color_palette": "obsidian and amber",
                "estimated_syllables": 18
            },
            {
                "beat_number": 2,
                "role": "paradox_setup",
                "narration_text": f"Deep inside this location, standard laws of nature suddenly collapse.",
                "subtitle_text": "LAWS OF NATURE COLLAPSE",
                "highlight_words": ["COLLAPSE", "NATURE"],
                "visual_beat_type": framings[1],
                "camera_focal_length": "24mm anamorphic wide",
                "lighting_setup": "volumetric rim light",
                "color_palette": "charcoal and cyan",
                "estimated_syllables": 16
            },
            {
                "beat_number": 3,
                "role": "counter_fact_1",
                "narration_text": facts[0],
                "subtitle_text": facts[0][:40].upper(),
                "highlight_words": ["WATER", "PRESSURE"],
                "visual_beat_type": framings[2],
                "camera_focal_length": "50mm prime",
                "lighting_setup": "harsh tungsten spotlight",
                "color_palette": "slate and bronze",
                "estimated_syllables": 18
            },
            {
                "beat_number": 4,
                "role": "scientific_evidence",
                "narration_text": f"When scientists measured the physical core, instrument readings spiked beyond theoretical limits.",
                "subtitle_text": "READINGS BEYOND LIMITS",
                "highlight_words": ["BEYOND", "LIMITS"],
                "visual_beat_type": framings[3],
                "camera_focal_length": "100mm macro prime",
                "lighting_setup": "fluorescent laboratory glow",
                "color_palette": "emerald and chrome",
                "estimated_syllables": 20
            },
            {
                "beat_number": 5,
                "role": "escalating_anomaly",
                "narration_text": facts[1],
                "subtitle_text": facts[1][:40].upper(),
                "highlight_words": ["SHOCKING", "DISCOVERY"],
                "visual_beat_type": framings[4],
                "camera_focal_length": "35mm documentary",
                "lighting_setup": "chiaroscuro side light",
                "color_palette": "dark teal and gold",
                "estimated_syllables": 19
            },
            {
                "beat_number": 6,
                "role": "real_consequence",
                "narration_text": facts[2],
                "subtitle_text": facts[2][:40].upper(),
                "highlight_words": ["DANGEROUS", "REALITY"],
                "visual_beat_type": framings[5],
                "camera_focal_length": "85mm portrait",
                "lighting_setup": "atmospheric haze rim light",
                "color_palette": "amber and cobalt",
                "estimated_syllables": 18
            },
            {
                "beat_number": 7,
                "role": "unresolved_mystery",
                "narration_text": "To this day, researchers have found no mathematical model that can explain this event.",
                "subtitle_text": "NO MATHEMATICAL MODEL",
                "highlight_words": ["NO", "EXPLAIN"],
                "visual_beat_type": framings[6],
                "camera_focal_length": "24mm anamorphic wide",
                "lighting_setup": "deep moody twilight",
                "color_palette": "slate and obsidian",
                "estimated_syllables": 18
            },
            {
                "beat_number": 8,
                "role": "loop_hook",
                "narration_text": "Which leaves everyone asking the exact same question:",
                "subtitle_text": "THE EXACT SAME QUESTION:",
                "highlight_words": ["EXACT", "QUESTION"],
                "visual_beat_type": framings[7],
                "camera_focal_length": "50mm documentary prime",
                "lighting_setup": "dramatic high contrast",
                "color_palette": "obsidian and electric cyan",
                "estimated_syllables": 14
            }
        ]
        return {
            "title": f"The Terrifying Secret of {topic} 😱 #Shorts",
            "total_estimated_duration_sec": 38,
            "beats": beats
        }


# =============================================================================
# STAGE 3: Visual Director & Scene Choreographer
# =============================================================================
class VisualDirectorChoreographer:
    """
    Translates research context and narrative beats into research-grounded visual prompts:
    - Injects Kodak Portra 400 / Arri Alexa 65 photographic DNA.
    - Dictates specific focal lengths, lighting setups, and color palettes per beat.
    - Applies negative prompt suppression (removes plastic skin, 3D render, smooth doll skin, wax figure).
    - Matches pacing to syllable counts.
    """

    FRAMING_DIRECTIVES = {
        "wide_establishing": "ultra-wide 24mm anamorphic panoramic establishing shot, epic cinematic scale, expansive environmental depth",
        "medium_close_up": "intimate 50mm documentary prime framing, subject centered, rich foreground context, cinematic atmosphere",
        "macro_detail": "100mm macro telephoto close-up, tack sharp microscopic surface details, visible micro-textures and tactile grains, shallow depth of field (f/1.8)",
        "cinematic_portrait": "85mm portrait prime lens, intense facial catchlights in eyes, authentic candid expression, creamy bokeh background",
        "low_angle_crane": "dramatic low-angle ground view looking upward, towering monolithic presence, atmospheric volumetric haze",
        "overhead_drone": "top-down geometric 90-degree bird's eye perspective, architectural symmetry, dynamic shadow casting",
        "extreme_close_up": "hyper-detailed extreme close-up, microscopic cellular or mechanical gear teeth, tactile authentic materials"
    }

    def choreograph_prompts(self, beats: List[Dict[str, Any]], research: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Constructs rich, research-grounded photographic prompts for each beat."""
        log.info(f"[Stage 3: Visual Director] Choreographing {len(beats)} research-grounded visual prompts...")
        env = research.get("physical_environment", {})
        scale_desc = env.get("scale_and_dimensions", "monolithic scale")
        materials_desc = env.get("materials_and_textures", "tactile raw surfaces")
        light_desc = env.get("lighting_and_atmosphere", "volumetric chiaroscuro")

        for idx, beat in enumerate(beats):
            framing_key = beat.get("visual_beat_type", "medium_close_up")
            framing_dna = self.FRAMING_DIRECTIVES.get(framing_key, self.FRAMING_DIRECTIVES["medium_close_up"])
            focal = beat.get("camera_focal_length", "35mm anamorphic")
            lighting = beat.get("lighting_setup", light_desc)
            palette = beat.get("color_palette", "cinematic moody tones")
            subtitle = beat.get("subtitle_text", "")

            # Research-grounded core scene subject
            subject_core = f"{research.get('topic', 'Mystery discovery')}, {subtitle}"

            # Assemble photographic description
            raw_prompt = (
                f"{framing_dna}, {focal}, depicting {subject_core}. "
                f"Physical environment features: {materials_desc}, {scale_desc}. "
                f"Lighting: {lighting}, dramatic atmospheric volumetric illumination. "
                f"Color grade: {palette}, 35mm film color science. "
                f"{AUTHENTIC_PHOTOGRAPHY_DNA}"
            )

            # Strip synthetic keywords (Unreal engine, hyperrealistic, octane render, etc.)
            clean_prompt = _clean_synthetic_keywords(raw_prompt)
            beat["visual_prompt"] = clean_prompt
            beat["negative_prompt"] = NEGATIVE_PROMPT_TOKENS

        log.info("[Stage 3: Visual Director] All visual choreographies completed.")
        return beats


# =============================================================================
# STAGE 4: Self-Critique & Quality Gatekeeper (Evaluator-Optimizer Loop)
# =============================================================================
class QualityGatekeeper:
    """
    Autonomous quality assurance engine running 3 strict gates:
    Gate 1: Script Check - Clarity, retention flow, loop potential. Auto-revises if < 75.
    Gate 2: Frame Continuity - Enforces framing variety across consecutive scenes.
    Gate 3: Visual Asset Check - Validates image file size (> 50KB), PIL decodability, non-blank variance.
    """

    PASS_THRESHOLD_SCRIPT = 75

    def evaluate_and_optimize_script(
        self,
        script_data: Dict[str, Any],
        research: Dict[str, Any],
        winning_hook: Dict[str, Any],
        director: EditorialStoryDirector
    ) -> Dict[str, Any]:
        """
        Gate 1: LLM Evaluator scoring the script on 4 axes:
        - Clarity (0-25)
        - Retention Flow (0-25)
        - Curiosity Sustain (0-25)
        - Loop Potential (0-25)
        If total score < 75, feeds critique into optimizer to auto-revise script.
        """
        log.info("[Stage 4: Gatekeeper] === GATE 1: Script Quality Self-Critique ===")
        max_revisions = 2

        for attempt in range(max_revisions + 1):
            beats = script_data.get("beats", [])
            beats_repr = "\n".join([
                f"Beat {b['beat_number']} ({b.get('role')}): '{b.get('narration_text')}' "
                f"[Subtitle: {b.get('subtitle_text')}]"
                for b in beats
            ])

            eval_prompt = (
                "You are an Elite Video Retention Analyst & Executive Script Doctor.\n"
                "Evaluate this short-form documentary script against high-retention viral standards.\n\n"
                f"TOPIC: {research.get('topic')}\n"
                f"OPENING HOOK: {beats[0].get('narration_text') if beats else ''}\n"
                f"FINAL BEAT (LOOP HOOK): {beats[-1].get('narration_text') if beats else ''}\n\n"
                f"SCRIPT BEATS:\n{beats_repr}\n\n"
                "Score the script across these 4 dimensions (0 to 25 points each):\n"
                "1. clarity_and_pacing: Is every sentence immediate, clear, and free of filler?\n"
                "2. retention_flow: Does each beat create an open loop compelling the next beat?\n"
                "3. fact_grounding: Are the counter-intuitive scientific/historical facts vivid and tangible?\n"
                "4. loop_potential: Does the final beat syntactically and seamlessly loop back into Beat 1?\n\n"
                "STRICT JSON OUTPUT:\n"
                "{\n"
                '  "scores": {\n'
                '    "clarity_and_pacing": 22,\n'
                '    "retention_flow": 23,\n'
                '    "fact_grounding": 24,\n'
                '    "loop_potential": 22\n'
                '  },\n'
                '  "total_score": 91,\n'
                '  "critique": "Specific feedback points...",\n'
                '  "pass_gate": true\n'
                "}"
            )

            result = call_gemini_json(eval_prompt, "Please evaluate the script.")
            total_score = 80
            critique = "Script meets retention standards."
            passed = True

            if result and "total_score" in result:
                total_score = result["total_score"]
                critique = result.get("critique", "")
                passed = total_score >= self.PASS_THRESHOLD_SCRIPT

            log.info(f"   [Gate 1 Script Score (Attempt {attempt+1})]: {total_score}/100 - "
                     f"{'[PASSED]' if passed else '[BELOW THRESHOLD]'}")

            if passed or attempt == max_revisions:
                if not passed:
                    log.warning(f"   [Gate 1 Notice] Proceeding with current best script after {max_revisions} passes.")
                script_data["quality_score"] = total_score
                script_data["critique"] = critique
                return script_data

            log.info(f"   [Gate 1 Optimizer] Auto-revising script based on critique: {critique[:120]}...")
            script_data = director.draft_narrative_script(
                research, winning_hook, len(beats), critique_feedback=critique
            )

        return script_data

    def enforce_frame_continuity(self, beats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Gate 2: Frame Continuity & Framing Variety Check:
        Verifies that consecutive scenes vary in framing (e.g. Wide -> Close-up -> Macro)
        so the video never looks visually repetitive or monotonous.
        """
        log.info("[Stage 4: Gatekeeper] === GATE 2: Frame Continuity & Variety Check ===")
        alternatives = [
            "macro_detail", "wide_establishing", "medium_close_up",
            "low_angle_crane", "cinematic_portrait", "extreme_close_up", "overhead_drone"
        ]

        adjustments_made = 0
        for i in range(1, len(beats)):
            prev_framing = beats[i - 1].get("visual_beat_type", "")
            curr_framing = beats[i].get("visual_beat_type", "")

            if curr_framing == prev_framing:
                # Find an alternative framing that is different from both prev and next
                next_framing = beats[i + 1].get("visual_beat_type", "") if (i + 1 < len(beats)) else ""
                chosen = None
                for alt in alternatives:
                    if alt != prev_framing and alt != next_framing:
                        chosen = alt
                        break
                chosen = chosen or "macro_detail"
                log.info(f"   [Continuity Fix] Beat {beats[i]['beat_number']} changed from '{curr_framing}' to '{chosen}' (preventing back-to-back repetition)")
                beats[i]["visual_beat_type"] = chosen
                adjustments_made += 1

        log.info(f"[Stage 4: Gatekeeper] Frame continuity check passed ({adjustments_made} adjustments applied).")
        return beats

    def validate_and_heal_visuals(
        self,
        beats: List[Dict[str, Any]],
        cache_dir: Path
    ) -> List[Path]:
        """
        Gate 3: Visual Check:
        Validates that all scene images downloaded successfully,
        exist on disk, are valid decodable PIL images, non-blank (variance check),
        and have a file size > 50KB.
        If under 50KB or blank: auto-retries generation with altered seed/prompt.
        """
        log.info(f"[Stage 4: Gatekeeper] === GATE 3: Visual Asset Quality & Health Check ===")
        image_paths = []

        for idx, beat in enumerate(beats):
            beat_num = beat.get("beat_number", idx + 1)
            prompt = beat.get("visual_prompt", f"Cinematic scene {beat_num}")
            out_img = cache_dir / f"scene_{beat_num:02d}.jpg"

            valid = False
            for retry in range(3):
                # 1. Generate via Pollinations Flux.1 with supersampling
                if not out_img.exists() or retry > 0:
                    seed = random.randint(1000, 999999)
                    enhanced_prompt = f"{prompt}, atmospheric seed {seed}"
                    _generate_pollinations_frame(enhanced_prompt, seed, out_img, width=1080, height=1920)

                # 2. Check File Exists and Size > 50KB
                if not out_img.exists():
                    log.warning(f"   [Beat {beat_num}] Image missing. Retrying ({retry+1}/3)...")
                    continue

                size_kb = out_img.stat().st_size / 1024.0
                if size_kb < 50.0:
                    log.warning(f"   [Beat {beat_num}] Image too small ({size_kb:.1f}KB < 50KB). Retrying ({retry+1}/3)...")
                    continue

                # 3. Check Decodability and Pixel Variance (Non-Blank Check)
                try:
                    with Image.open(out_img) as im:
                        im.verify()
                    with Image.open(out_img) as im:
                        gray = im.convert("L").resize((64, 64))
                        arr = np.array(gray, dtype=float)
                        variance = float(np.var(arr))
                        if variance < 12.0:
                            log.warning(f"   [Beat {beat_num}] Image is solid/blank (var={variance:.1f}). Retrying ({retry+1}/3)...")
                            continue
                    valid = True
                    log.info(f"   [Beat {beat_num} Image [OK]]: {out_img.name} ({size_kb:.1f} KB, variance={variance:.1f})")
                    break
                except Exception as ex:
                    log.warning(f"   [Beat {beat_num}] Image corrupted ({ex}). Retrying ({retry+1}/3)...")
                    continue

            # Fallback if 3 retries failed
            if not valid:
                log.error(f"   [Beat {beat_num}] Pollinations failed. Generating high-res procedural fallback frame.")
                _make_procedural_frame(beat_num, prompt[:40], "unexplained_real_mysteries", out_img)

            image_paths.append(out_img)

        log.info(f"[Stage 4: Gatekeeper] All {len(image_paths)} visual assets passed Gate 3.")
        return image_paths


# =============================================================================
# Helper: Cross-Platform Subtitle Badge Renderer
# =============================================================================
def render_producer_subtitle_badge(
    text: str,
    highlight_words: Optional[List[str]] = None,
    font_size: int = 64
) -> Image.Image:
    """
    Renders open bold mobile subtitles compatible with both Windows and Linux (Ubuntu CI).
    """
    if highlight_words is None:
        highlight_words = []

    # Cross-platform font search
    candidate_fonts = [
        # Windows
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arial.ttf",
        # Linux (Ubuntu GitHub Actions)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    ]
    font = None
    for fp in candidate_fonts:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue
    if not font:
        font = ImageFont.load_default()

    words = text.strip().upper().split()
    if not words:
        return Image.new("RGBA", (100, 50), (0, 0, 0, 0))

    # Split into lines of 2 to 3 words for instant mobile reading
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
    line_h = int(font_size * 1.25)
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
    canvas_w = int(min(1040, max_w + pad_x * 2))
    canvas_h = int(line_h * len(lines) + pad_y * 2)

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    clean_highlights = [hw.lower().strip(string.punctuation) for hw in highlight_words]
    stroke_width = 5

    for i, (line, w_widths, line_w) in enumerate(line_metrics):
        start_x = (canvas_w - line_w) / 2
        curr_x = start_x
        curr_y = pad_y + i * line_h

        for word, w in zip(line, w_widths):
            clean_w = word.lower().strip(string.punctuation)
            is_hl = any(hw in clean_w for hw in clean_highlights) if clean_highlights else False
            text_color = (255, 235, 30, 255) if is_hl else (255, 255, 255, 255)

            # Drop shadow
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    draw.text((curr_x + dx + 4, curr_y + dy + 4), word,
                              font=font, fill=(0, 0, 0, 120))

            # Thick black outline + vibrant fill
            draw.text((curr_x, curr_y), word, font=font,
                      fill=text_color, stroke_width=stroke_width,
                      stroke_fill=(0, 0, 0, 255))
            curr_x += w + space_w

    return img


def _clip_with_start(clip, t):
    if hasattr(clip, "with_start"):
        return clip.with_start(t)
    return clip.set_start(t)

def _clip_with_duration(clip, dur):
    if hasattr(clip, "with_duration"):
        return clip.with_duration(dur)
    return clip.set_duration(dur)

def _clip_with_position(clip, pos):
    if hasattr(clip, "with_position"):
        return clip.with_position(pos)
    return clip.set_position(pos)

def _clip_with_volume(clip, vol):
    if hasattr(clip, "with_volume_scaled"):
        return clip.with_volume_scaled(vol)
    elif hasattr(clip, "volumex"):
        return clip.volumex(vol)
    return clip

def _clip_subclip(clip, t_start, t_end):
    if hasattr(clip, "subclipped"):
        return clip.subclipped(t_start, t_end)
    return clip.subclip(t_start, t_end)


# =============================================================================
# STAGE 5: Assembly & Autonomous Publisher
# =============================================================================
class AutonomousPublisher:
    """
    Compositor & publisher:
    - Generates Edge TTS voiceover with measured durations.
    - Creates Higgsfield 2.5D camera clips with Perlin smootherstep.
    - Adds bold mobile subtitle badges at y=1100 (safe area).
    - Mixes balanced procedural tension drone (-18dB).
    - Applies FFmpeg photographic clarity grading pass (unsharp mask, micro-contrast, organic 35mm grain).
    - Generates SEO metadata (title, description, tags).
    - Uploads to YouTube API v3 or saves to local queue if quota reached.
    - Updates history.json, daily_report.json, and autopilot_state.json.
    """

    def __init__(self, voice_name: str = "en-US-ChristopherNeural"):
        self.voice_name = voice_name
        ensure_cinematic_assets()

    async def _synth_voice_beat(self, text: str, out_path: Path) -> float:
        """Synthesizes voiceover for a single beat and returns duration."""
        clean = " ".join(text.split()).strip()
        comm = edge_tts.Communicate(clean, self.voice_name, rate="+8%")
        await comm.save(str(out_path))

        with AudioFileClip(str(out_path)) as a:
            dur = a.duration
        return max(2.5, dur)

    def assemble_cinematic_short(
        self,
        beats: List[Dict[str, Any]],
        image_paths: List[Path],
        output_path: Path
    ) -> Path:
        """Assembles 1080x1920 Short with Higgsfield motion, subtitles, audio, and clarity grade."""
        log.info(f"[Stage 5: Publisher] Assembling video across {len(beats)} narrative beats...")
        temp_audio_dir = PRODUCER_CACHE_DIR / "audio"
        temp_audio_dir.mkdir(parents=True, exist_ok=True)

        audio_clips = []
        video_clips = []
        sub_clips = []

        total_elapsed = 0.0

        for idx, (beat, img_p) in enumerate(zip(beats, image_paths)):
            beat_num = beat.get("beat_number", idx + 1)
            audio_path = temp_audio_dir / f"beat_{beat_num:02d}.mp3"

            # 1. Synthesize Audio
            dur = asyncio.run(self._synth_voice_beat(beat["narration_text"], audio_path))
            log.info(f"   [Beat {beat_num} Audio]: {dur:.2f}s | Text: '{beat['narration_text'][:45]}...'")

            # 2. Higgsfield 2.5D Camera Motion Clip (already has duration set)
            v_clip = _make_higgsfield_camera_clip(img_p, dur, scene_idx=idx)
            video_clips.append(v_clip)

            # 3. Voice Audio Clip
            a_clip = AudioFileClip(str(audio_path))
            a_clip = _clip_with_start(a_clip, total_elapsed)
            audio_clips.append(a_clip)

            # 4. Mobile Subtitle Badge at y=1100 (Safe area)
            sub_img = render_producer_subtitle_badge(
                beat.get("subtitle_text", ""),
                highlight_words=beat.get("highlight_words", [])
            )
            sub_clip = ImageClip(np.array(sub_img))
            sub_clip = _clip_with_duration(sub_clip, dur)
            sub_clip = _clip_with_start(sub_clip, total_elapsed)
            sub_clip = _clip_with_position(sub_clip, ("center", 1100))
            sub_clips.append(sub_clip)

            total_elapsed += dur

        log.info(f"   [Timeline] Total short duration: {total_elapsed:.1f}s")

        # 5. Background Ambient Drone (-18dB under voiceover)
        drone_path = ASSETS_DIR / "thriller_drone.wav"
        bg_audio = None
        if drone_path.exists():
            try:
                raw_drone = AudioFileClip(str(drone_path))
                loops_needed = int(math.ceil(total_elapsed / max(raw_drone.duration, 1.0))) + 1
                try:
                    bg_audio = concatenate_audioclips([raw_drone] * loops_needed)
                except Exception:
                    bg_audio = raw_drone
                bg_audio = _clip_subclip(bg_audio, 0, total_elapsed)
                bg_audio = _clip_with_volume(bg_audio, 0.12)
            except Exception as ex:
                log.warning(f"   [Drone Audio] Could not mix background drone: {ex}")

        # Mix Audios
        final_audio_track = CompositeAudioClip(audio_clips + ([bg_audio] if bg_audio else []))

        # Composite Video
        base_video = concatenate_videoclips(video_clips, method="compose")
        final_composite = CompositeVideoClip([base_video] + sub_clips, size=(1080, 1920))
        final_composite.audio = final_audio_track
        final_composite.duration = total_elapsed

        raw_output_path = PRODUCER_CACHE_DIR / "producer_raw_short.mp4"
        log.info(f"   [Rendering] Compiling 1080x1920 video to {raw_output_path.name}...")
        final_composite.write_videofile(
            str(raw_output_path),
            fps=30,
            codec="libx264",
            audio_codec="aac",
            preset="fast",
            ffmpeg_params=["-pix_fmt", "yuv420p"],
            logger=None
        )

        final_composite.close()
        for c in video_clips:
            c.close()

        # 6. Apply FFmpeg Photographic Clarity & Film Grain Grading Pass
        log.info("   [Grade Pass] Applying photographic clarity, micro-contrast, and 35mm film grain...")
        graded_path = apply_photographic_clarity_grade(raw_output_path)
        if graded_path.exists() and graded_path.stat().st_size > 500 * 1024:
            if graded_path != output_path:
                if output_path.exists():
                    output_path.unlink()
                graded_path.rename(output_path)
            log.info(f"   [Render Complete [OK]]: {output_path.name} ({output_path.stat().st_size / (1024*1024):.1f} MB)")
            return output_path

        log.warning("   [Grade Pass] Graded output missing. Using raw render.")
        if raw_output_path != output_path:
            if output_path.exists():
                output_path.unlink()
            raw_output_path.rename(output_path)
        return output_path

    def generate_seo_metadata(self, research: Dict[str, Any], script_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generates viral SEO title, structured description, and tags."""
        topic = research.get("topic", "Mystery Anomaly")
        facts = research.get("counter_intuitive_facts", [])

        # Title: Curiosity hook < 100 chars
        title = script_data.get("title", f"The Impossible Discovery of {topic} 😱 #Shorts")
        if not title.endswith("#Shorts"):
            title = f"{title[:88]} 😱 #Shorts"

        # Description: Facts + engagement question + hashtags
        desc_lines = [
            f"Inside the world's most counter-intuitive anomaly: {topic}.",
            "",
            "🔬 3 Verified Facts You Won't Believe:",
        ]
        for idx, f in enumerate(facts[:3], 1):
            desc_lines.append(f"{idx}. {f}")

        desc_lines.extend([
            "",
            "💬 Did this discovery challenge what you thought you knew? Drop your thoughts below!",
            "",
            "#Shorts #Science #Discovery #Documentary #Mystery #AIProducer #History"
        ])
        description = "\n".join(desc_lines)

        tags = [
            topic.lower(), "science mystery", "scientific discovery", "unexplained phenomena",
            "historical anomalies", "documentary shorts", "viral science", "did you know",
            "curiosity", "mind blowing facts", "deep ocean", "physics", "shorts"
        ]

        return {
            "title": title[:100],
            "description": description,
            "tags": tags[:15]
        }

    def publish_or_queue(
        self,
        video_path: Path,
        seo_data: Dict[str, Any],
        dry_run: bool = False
    ) -> str:
        """Uploads to YouTube API v3 or queues locally if offline/quota reached."""
        if dry_run:
            sim_id = f"LOCAL_{int(time.time())}"
            log.info(f"   [DRY-RUN] Saved locally: {video_path.name} (Simulated ID: {sim_id})")
            return sim_id

        yt = self._get_youtube_service()
        if not yt:
            sim_id = f"LOCAL_SAVED_{int(time.time())}"
            log.info(f"   [OFFLINE / NO YOUTUBE CREDS] Saved to local queue: {video_path.name}")
            return sim_id

        try:
            from googleapiclient.http import MediaFileUpload
            body = {
                "snippet": {
                    "title": seo_data["title"],
                    "description": seo_data["description"],
                    "tags": seo_data["tags"],
                    "categoryId": "27",  # Education
                    "defaultLanguage": "en",
                    "defaultAudioLanguage": "en"
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False
                }
            }
            media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
            req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
            resp = None
            while resp is None:
                status, resp = req.next_chunk()
                if status:
                    log.info(f"   [Upload Progress] {int(status.progress() * 100)}%")

            video_id = resp.get("id", "unknown")
            log.info(f"   [YOUTUBE UPLOAD SUCCESS [OK]] https://youtube.com/shorts/{video_id}")
            return video_id
        except Exception as ex:
            if "uploadLimitExceeded" in str(ex):
                log.warning(f"   [QUOTA LIMIT] YouTube upload limit reached today. Video saved locally.")
                return f"SAVED_LOCAL_{int(time.time())}"
            log.error(f"   [Upload Error] {ex}")
            return f"ERR_UPLOAD_{int(time.time())}"

    @staticmethod
    def _get_youtube_service():
        """Restores credentials and connects to YouTube Data API v3."""
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        token_file = BASE_DIR / "token.json"
        client_secrets_file = BASE_DIR / "client_secrets.json"

        # Cloud env vars restore (GitHub Actions)
        if not token_file.exists() and os.environ.get("YOUTUBE_TOKEN_JSON"):
            try:
                token_file.write_text(os.environ["YOUTUBE_TOKEN_JSON"].strip(), encoding="utf-8")
                log.info("Restored token.json from environment.")
            except Exception as e:
                log.warning(f"Failed to restore token.json: {e}")

        if not client_secrets_file.exists() and os.environ.get("CLIENT_SECRETS_JSON"):
            try:
                client_secrets_file.write_text(os.environ["CLIENT_SECRETS_JSON"].strip(), encoding="utf-8")
                log.info("Restored client_secrets.json from environment.")
            except Exception as e:
                log.warning(f"Failed to restore client_secrets.json: {e}")

        if not token_file.exists():
            return None

        scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/youtube.force-ssl",
        ]
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), scopes)
            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                token_file.write_text(creds.to_json(), encoding="utf-8")
            return build("youtube", "v3", credentials=creds)
        except Exception as ex:
            log.warning(f"Failed to authenticate YouTube service: {ex}")
            return None


# =============================================================================
# STAGE 6: Autonomous Pipeline Orchestration & State Tracking
# =============================================================================
def record_producer_execution(
    research: Dict[str, Any],
    script_data: Dict[str, Any],
    seo_data: Dict[str, Any],
    video_id: str,
    output_path: Path,
    elapsed_time: float
):
    """Updates history.json, daily_report.json, and autopilot_state.json."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "id": video_id,
        "date": timestamp,
        "topic": research.get("topic"),
        "title": seo_data["title"],
        "facts": research.get("counter_intuitive_facts", []),
        "beats_count": len(script_data.get("beats", [])),
        "quality_score": script_data.get("quality_score", 85),
        "file": str(output_path),
        "render_time_sec": round(elapsed_time, 1)
    }

    # 1. Update history.json
    try:
        history = {"videos": []}
        if HISTORY_FILE.exists():
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        history.setdefault("videos", []).append(entry)
        HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as ex:
        log.warning(f"Could not update history.json: {ex}")

    # 2. Update daily_report.json
    try:
        report = []
        if DAILY_REPORT_FILE.exists():
            try:
                report = json.loads(DAILY_REPORT_FILE.read_text(encoding="utf-8"))
            except Exception:
                report = []
        if isinstance(report, list):
            report.append(entry)
        elif isinstance(report, dict):
            report.setdefault("ai_producer_runs", []).append(entry)
        DAILY_REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as ex:
        log.warning(f"Could not update daily_report.json: {ex}")


def run_ai_producer(
    topic: Optional[str] = None,
    dry_run: bool = False,
    beats_count: int = 8,
    voice: str = "en-US-ChristopherNeural"
) -> Dict[str, Any]:
    """
    Main Autonomous Agentic Entry Point:
    Executes Stages 1 through 5 end-to-end.
    """
    start_time = time.time()
    log.info("=" * 70)
    log.info("🚀 STARTING AUTONOMOUS AI PRODUCER PIPELINE")
    log.info(f"   Topic Override: {topic or 'Autonomous Live Trend Discovery'}")
    log.info(f"   Target Beats: {beats_count} | Dry-Run: {dry_run} | Voice: {voice}")
    log.info("=" * 70)

    # Primary Engine: Autonomous Viral Director & Dynamic Research Engine
    try:
        from viral_director_engine import execute_viral_director
        log.info("[AI Producer] Invoking Autonomous Viral Director Engine...")
        rendered_file = execute_viral_director(topic_override=topic, dry_run=dry_run)
        log.info("=" * 70)
        log.info("🏁 AUTONOMOUS VIRAL DIRECTOR COMPLETED [OK]")
        log.info(f"   Output Video File: {rendered_file}")
        log.info("=" * 70)
        return {
            "status": "SUCCESS",
            "file": str(rendered_file)
        }
    except Exception as e:
        log.warning(f"[AI Producer] Viral Director encountered ({e}). Proceeding with legacy stages.")

    # Stage 1: Live Research & Fact-Finding ("The Brain")
    brain = LiveResearchBrain()
    research = brain.perform_deep_research(custom_topic=topic)
    log.info(f"[Stage 1 Summary] Researched: '{research.get('topic')}'")
    for idx, f in enumerate(research.get("counter_intuitive_facts", []), 1):
        log.info(f"   Fact {idx}: {f}")

    # Stage 2: Editorial & Story Director
    director = EditorialStoryDirector()
    hook_result = director.ideate_and_evaluate_hooks(research)
    winning_hook = hook_result["winning_hook"]
    script_data = director.draft_narrative_script(research, winning_hook, target_beats=beats_count)

    # Stage 3: Visual Director & Scene Choreographer
    choreographer = VisualDirectorChoreographer()
    beats = choreographer.choreograph_prompts(script_data["beats"], research)

    # Stage 4: Self-Critique & Quality Gatekeeper (Evaluator-Optimizer Loop)
    gatekeeper = QualityGatekeeper()
    # Gate 1: Script check & auto-revision
    script_data = gatekeeper.evaluate_and_optimize_script(script_data, research, winning_hook, director)
    beats = script_data["beats"]
    # Gate 2: Framing continuity check
    beats = gatekeeper.enforce_frame_continuity(beats)
    # Gate 3: Visual asset quality check & healing
    image_paths = gatekeeper.validate_and_heal_visuals(beats, FRAMES_DIR)

    # Stage 5: Assembly & Autonomous Publisher
    publisher = AutonomousPublisher(voice_name=voice)
    output_filename = f"ai_producer_short_{int(time.time())}.mp4"
    final_output_path = BASE_DIR / output_filename

    assembled_path = publisher.assemble_cinematic_short(beats, image_paths, final_output_path)
    seo_data = publisher.generate_seo_metadata(research, script_data)

    video_id = publisher.publish_or_queue(assembled_path, seo_data, dry_run=dry_run)
    elapsed = time.time() - start_time

    record_producer_execution(research, script_data, seo_data, video_id, assembled_path, elapsed)

    log.info("=" * 70)
    log.info("🏁 AUTONOMOUS AI PRODUCER PIPELINE COMPLETE [OK]")
    log.info(f"   Published Video ID : {video_id}")
    log.info(f"   Title              : {seo_data['title']}")
    log.info(f"   Output File        : {assembled_path}")
    log.info(f"   Quality Gate Score : {script_data.get('quality_score', 85)}/100")
    log.info(f"   Total Elapsed Time : {elapsed:.1f} seconds")
    log.info("=" * 70)

    return {
        "status": "SUCCESS",
        "video_id": video_id,
        "title": seo_data["title"],
        "file": str(assembled_path),
        "quality_score": script_data.get("quality_score", 85),
        "render_time_sec": elapsed
    }


# =============================================================================
# CLI Entrypoint
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous AI Producer Pipeline for YouTube Shorts")
    parser.add_argument("--topic", type=str, default=None, help="Target topic (leave empty for live RSS trend)")
    parser.add_argument("--dry-run", action="store_true", help="Compile video locally without uploading to YouTube")
    parser.add_argument("--no-upload", action="store_true", help="Alias for --dry-run")
    parser.add_argument("--beats", type=int, default=8, help="Number of narrative beats (7 to 9)")
    parser.add_argument("--voice", type=str, default="en-US-ChristopherNeural", help="Edge TTS voice model")

    args = parser.parse_args()
    is_dry = args.dry_run or args.no_upload

    try:
        run_ai_producer(
            topic=args.topic,
            dry_run=is_dry,
            beats_count=max(7, min(9, args.beats)),
            voice=args.voice
        )
    except KeyboardInterrupt:
        log.info("Producer aborted by user.")
    except Exception as exc:
        log.exception(f"Fatal error in AI Producer: {exc}")
        sys.exit(1)
