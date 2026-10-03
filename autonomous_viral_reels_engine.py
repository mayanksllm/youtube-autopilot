"""
autonomous_viral_reels_engine.py - Autonomous Viral Reels Engine (Zero-Cost Failover Cascade)
=============================================================================================
A 100% autonomous, fault-tolerant viral video generation pipeline.
If any service hits rate limits (HTTP 429), returns an empty response, or expires,
the engine cascades automatically to the next provider without crashing.

CASCADE 1: Script Generation (5 Tiers)
  • Tier 1: Google Gemini 2.5 Flash API (Free Tier key)
  • Tier 2: Groq Cloud API (llama-3.3-70b-versatile, free high-speed)
  • Tier 3: DeepSeek Free API / OpenRouter Free Tier
  • Tier 4: Cohere API (command-r free tier)
  • Tier 5: Pollinations AI Text (100% Keyless Emergency Tier)
  • Schema: {"title": str, "voiceover_clean": str, "pinned_comment": str, "scenes": [{"id": int, "prompt": str}]}

CASCADE 2: Visual Generation (4 Tiers)
  • Tier 1: Pollinations AI FLUX (1080x1920, 9:16 vertical, keyless)
  • Tier 2: Hugging Face Serverless Inference (FLUX.1-schnell free token)
  • Tier 3: Together AI Free Tier (SDXL 1.0)
  • Tier 4: Local Dynamic B-Roll Vault (assets/fallback_vault/)
  • Rules: File size > 30KB, frame average luminance >= 10.0 (no black/empty frames)

CASCADE 3: Voice Synthesis (3 Tiers)
  • Tier 1: edge-tts voice hi-IN-MadhurNeural (rate: +10%)
  • Tier 2: edge-tts voice hi-IN-SwaraNeural (rate: +10%)
  • Tier 3: Local gTTS (Google Translate Hindi TTS fallback)
"""

import os
import sys
import json
import time
import math
import random
import re
import wave
import struct
import shutil
import asyncio
import argparse
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from dotenv import load_dotenv

# Safe UTF-8 encoding for Windows terminals
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

load_dotenv()

from autopilot_config import (
    SIMILARITY_THRESHOLD,
    COOLDOWNS,
    BROWSER_HEADERS,
    GEMINI_MODELS
)
from yt_variety import variety_engine

BASE_DIR = Path(__file__).parent.resolve()

ASSETS_DIR = BASE_DIR / "assets"
DIRECTOR_SCENES_DIR = ASSETS_DIR / "director_scenes"
SFX_DIR = ASSETS_DIR / "sfx"
TEMP_DIR = ASSETS_DIR / "temp"
OUTPUT_DIR = ASSETS_DIR / "output"
FALLBACK_VAULT_DIR = ASSETS_DIR / "fallback_vault"

for d in [ASSETS_DIR, DIRECTOR_SCENES_DIR, SFX_DIR, TEMP_DIR, OUTPUT_DIR, FALLBACK_VAULT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

HISTORY_LOG_FILE = BASE_DIR / "history_log.json"
HISTORY_FILE = BASE_DIR / "history.json"
CONFIG_FILE = BASE_DIR / "autonomous_viral_reels_engine.json"

# API Keys & Configurations
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "") or os.environ.get("HUGGINGFACE_API_TOKEN", "") or os.environ.get("HUGGING_FACE_HUB_TOKEN", "")
TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY", "")

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

# Standard browser headers to avoid Cloudflare 0-byte bot rejection
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}

# 12 Master Visual Styles for Dynamic Daily Variety (Rotated per video/day)
VIRAL_VISUAL_STYLES = [
    {
        "style_name": "Cinematic 35mm Panavision Film",
        "prompt_prefix": "Masterpiece raw candid photograph, shot on Kodak Portra 400, 35mm anamorphic lens, Arri Alexa 65 sensor, dramatic chiaroscuro lighting, volumetric rim light, photorealistic, 8k vertical 9:16",
        "c_bg": (15, 12, 25), "c_fg": (255, 190, 80), "pattern": "cinematic_anamorphic"
    },
    {
        "style_name": "3D Zack D. Anatomical Cross-Section",
        "prompt_prefix": "3D medical hyper-detailed cutaway anatomical cross-section, glowing biological veins, Zack D Films animation style, dramatic studio spotlight, octane 3D render, vertical 9:16",
        "c_bg": (45, 10, 20), "c_fg": (255, 60, 90), "pattern": "bio_matrix"
    },
    {
        "style_name": "Investigative MagnatesMedia Dark Noir",
        "prompt_prefix": "Dark investigative documentary noir aesthetic, MagnatesMedia archival style, moody atmospheric spotlight, sepia and charcoal tones, high contrast textures, 8k vertical 9:16",
        "c_bg": (20, 20, 20), "c_fg": (210, 180, 110), "pattern": "noir_split"
    },
    {
        "style_name": "Cyberpunk Neon Matrix",
        "prompt_prefix": "Cyberpunk futuristic concept art, neon cyan and electric magenta volumetric fog, rain-slicked reflective surfaces, blade runner 2049 aesthetic, 8k vertical 9:16",
        "c_bg": (10, 15, 30), "c_fg": (0, 240, 255), "pattern": "cyber_grid"
    },
    {
        "style_name": "National Geographic 8K Macro",
        "prompt_prefix": "National Geographic wildlife macro photography, 8k telephoto lens, tack sharp textures, authentic natural sunlight, rich vibrant earthy colors, vertical 9:16",
        "c_bg": (15, 35, 15), "c_fg": (80, 220, 100), "pattern": "nature_burst"
    },
    {
        "style_name": "Cosmic Hubble Nebula Deep Space",
        "prompt_prefix": "James Webb space telescope deep field astrophotography, glowing cosmic nebula vortex, stellar dust clouds, luminous starfield, vivid indigo and violet hues, vertical 9:16",
        "c_bg": (10, 5, 30), "c_fg": (160, 60, 255), "pattern": "cosmic_nebula"
    },
    {
        "style_name": "Ancient Indian Temple Enigma",
        "prompt_prefix": "Ancient Indian monolithic temple architecture, golden hour sunbeams cutting through carved stone pillars, mystical divine atmosphere, photorealistic cinematic lighting, vertical 9:16",
        "c_bg": (35, 20, 5), "c_fg": (255, 180, 30), "pattern": "golden_temple"
    },
    {
        "style_name": "Graphic Novel Neo-Noir Pop Art",
        "prompt_prefix": "Stylized graphic novel illustration, high-contrast ink and gouache wash, dramatic comic book angles, gritty cinematic cel shading, vibrant accents, vertical 9:16",
        "c_bg": (25, 10, 30), "c_fg": (255, 230, 40), "pattern": "pop_halftone"
    }
]

import edge_tts
from viral_director_engine import get_ffmpeg_binary


# =============================================================================
# STEP 1: TREND RESEARCH & ANTI-REPETITION GATE (30-Upload Lookback)
# =============================================================================
class TrendResearcher:
    """
    Step 1: Trend Research
    Fetches 1 unique topic. Checks 'history_log.json' to ensure it was not used in the last 30 uploads.
    """

    CURATED_DISCOVERY_VAULT = [
        {
            "topic": "The Lepakshi Hanging Pillar Gravity Paradox",
            "category": "unexplained_indian_history",
            "headline": "A 16th-century stone temple pillar hangs in mid-air with cloth sliding freely underneath",
            "paradox": "A 10-ton solid stone pillar hovers millimeters above the floor without touching ground, acting as a seismic balance lock."
        },
        {
            "topic": "The Pistol Shrimp 8000K Sonoluminescence Paradox",
            "category": "bizarre_biology",
            "headline": "A 2-inch shrimp snaps its claw to generate a cavitation bubble hotter than the surface of the Sun",
            "paradox": "A biological creature snapping water so fast it creates 8,000°K plasma light flash and a 218dB shockwave."
        },
        {
            "topic": "The Kailash Temple Ellora Monolithic Enigma",
            "category": "unexplained_indian_history",
            "headline": "400,000 tons of solid basalt rock carved top-down with zero debris found for 50 kilometers",
            "paradox": "Carving a 100-foot multi-level monolithic temple top-down with zero tolerance for chisel errors."
        },
        {
            "topic": "Turritopsis Dohrnii: The Biologically Immortal Jellyfish",
            "category": "bizarre_biology",
            "headline": "A marine creature that reverses its own cellular clock back to infancy when facing starvation or injury",
            "paradox": "An organism that chemically resets its specialized cells back to stem cells to escape biological death."
        },
        {
            "topic": "The Musical Pillars of Vittala Temple Hampi",
            "category": "unexplained_indian_history",
            "headline": "56 solid monolithic granite pillars ring like tuned metallic bells when tapped by hand",
            "paradox": "Solid stone columns producing tuned musical notes (Shruti, Gana, Laya) carved with varying mineral densities."
        },
        {
            "topic": "Ophiocordyceps: The Zombie Ant Neuro-Puppeteer",
            "category": "bizarre_biology",
            "headline": "A fungal parasite hijacks muscle fibers to steer an insect to an exact leaf coordinate",
            "paradox": "A spore that controls an animal's locomotion without entering its brain."
        },
        {
            "topic": "The Brihadeeswarar 80-Ton Monolithic Capstone",
            "category": "unexplained_indian_history",
            "headline": "A single 80,000 kg carved granite Kumbam lifted 216 feet into the air with zero mortar",
            "paradox": "Moving and mounting an 80-ton single block of granite onto a 216-foot spire in the 11th century."
        },
        {
            "topic": "The Chand Baori 3500-Step Inverted Geometric Abyss",
            "category": "unexplained_indian_history",
            "headline": "A 13-story subterranean stepwell carved in razor-sharp optical infinity keeping water 6°C cooler",
            "paradox": "3,500 perfectly symmetrical steps creating a subterranean architectural vortex where acoustic echoes cancel out."
        },
        {
            "topic": "The Iron Pillar of Delhi 1600-Year Corrosion Paradox",
            "category": "unexplained_indian_history",
            "headline": "A 6-ton iron pillar forged in 400 CE that refuses to rust despite centuries of monsoon rain",
            "paradox": "Ancient Indian metallurgists created a passive misawite protective film that modern stainless steel manufacturers cannot duplicate."
        },
        {
            "topic": "The Padmanabhaswamy Vault B Sanskrit Snake Lock",
            "category": "unexplained_indian_history",
            "headline": "A subterranean temple door with zero latches or hinges sealed by an ancient acoustic frequency lock",
            "paradox": "A massive solid iron vault door designed to open only when a specific Garuda Mantra resonance is sung at precise pitch."
        },
        {
            "topic": "The Modhera Sun Temple Zero-Shadow Equinox Geometry",
            "category": "unexplained_indian_history",
            "headline": "An 11th-century temple engineered so the first equinox sunbeam illuminates the central diamond jewel",
            "paradox": "Built over an inverted lotus foundation that floats like a shock-absorbing piston during massive tectonic quakes."
        },
        {
            "topic": "The Konark Sun Temple Magnetic Shikhara Disruption",
            "category": "unexplained_indian_history",
            "headline": "Portuguese sailors reported ships pulled off course by a colossal magnetite lodestone capping the temple spire",
            "paradox": "The entire main stone sanctum was held in dynamic equilibrium by opposing magnetic lodestone fields."
        },
        {
            "topic": "The Golconda Fort 1-Kilometer Acoustic Whispering Telegraph",
            "category": "unexplained_indian_history",
            "headline": "A single hand-clap under the entry dome transmits with crystal clarity to the citadel 1,000 meters away",
            "paradox": "Ancient acoustic compression arches creating a physical parabolic sound lens for military defense."
        },
        {
            "topic": "The Lonar Crater Hyper-Velocity Impact Lake",
            "category": "unexplained_indian_history",
            "headline": "A 52,000-year-old basalt meteorite lake housing two distinct non-mixing water rings with opposite pH levels",
            "paradox": "An outer neutral ring (pH 7) and an inner hyper-saline alkaline pool (pH 11) coexisting in the same basin without mingling."
        },
        {
            "topic": "The Axolotl Organ and Brain Regeneration Miracle",
            "category": "bizarre_biology",
            "headline": "A salamander that can regrow severed limbs, eyes, heart muscle, and whole brain hemispheres without scars",
            "paradox": "Converting adult damaged tissue back into pluripotent blastema cells that rebuild complex neural circuits."
        },
        {
            "topic": "Tardigrades: The Indestructible Microscopic Space Travelers",
            "category": "bizarre_biology",
            "headline": "A microscopic creature that enters cryptobiosis to survive the vacuum of space, absolute zero, and boiling radiation",
            "paradox": "Replacing 99% of bodily water with glass-like protective sugars to survive for 30 years without food or oxygen."
        },
        {
            "topic": "Planarian Flatworms: Immortality and Memory Transfer",
            "category": "bizarre_biology",
            "headline": "When sliced into 300 pieces, each fragment regenerates a complete worm that retains the original memories",
            "paradox": "Memories stored outside the physical brain in distributed somatic stem-cell neural networks."
        },
        {
            "topic": "The Bombardier Beetle 100°C Chemical Rocket Defense",
            "category": "bizarre_biology",
            "headline": "An insect that mixes hydroquinone and hydrogen peroxide in an internal combustion chamber to spray boiling acid",
            "paradox": "Pulsing the toxic explosion at 500 pulses per second to avoid boiling its own abdomen alive."
        },
        {
            "topic": "The Mimic Octopus 15-Species Dynamic Shapeshifter",
            "category": "bizarre_biology",
            "headline": "A cephalopod that consciously analyzes predators and morphs its shape, skin texture, and movement into 15 species",
            "paradox": "Instantly transforming into a banded sea snake, lionfish, or flatfish depending on which predator is hunting it."
        },
        {
            "topic": "The Electric Eel 860-Volt Synchronized Organic Battery",
            "category": "bizarre_biology",
            "headline": "Thousands of stacked electrocytes discharge simultaneous electrical current capable of stunning a horse",
            "paradox": "Generating more electrical voltage than a wall outlet using biological sodium-potassium ion flow."
        },
        {
            "topic": "The Greenland Shark 400-Year Sub-Zero Living Fossil",
            "category": "bizarre_biology",
            "headline": "A massive Arctic apex predator that roams frozen abyss for 400 years and doesn't reach maturity until age 150",
            "paradox": "Tissue infused with natural trimethylamine oxide antifreeze, experiencing a biological metabolic rate close to absolute zero."
        },
        {
            "topic": "The Antikythera Mechanism: 2000-Year-Old Analog Computer",
            "category": "unexplained_history",
            "headline": "Sponge divers pulled a 37-gear bronze differential calculating planetary orbits 1,400 years before clocks",
            "paradox": "Mechanical precision engineering that vanished from human civilization for over fourteen centuries."
        },
        {
            "topic": "The Kola Superdeep Borehole 12-Kilometer Underworld Anomaly",
            "category": "unexplained_history",
            "headline": "Soviet drills pierced 40,000 feet into Earth finding boiling water in solid granite and plasticized rock",
            "paradox": "Solid rock ceasing to be brittle and behaving like soft putty under 4,000 atmospheres of lithostatic pressure."
        },
        {
            "topic": "The Richat Structure: The Eye of the Sahara Atlantis Paradox",
            "category": "unexplained_history",
            "headline": "A 40-kilometer concentric geological bullseye in Mauritania matching Plato's exact island dimensions",
            "paradox": "Concentric rings of sedimentary stone created without volcanic eruption, perfectly exposed in the desert."
        },
        {
            "topic": "The Derinkuyu 18-Story Subterranean Mega-Metropolis",
            "category": "unexplained_history",
            "headline": "An ancient underground city carved 280 feet into volcanic tuff housing 20,000 people and livestock",
            "paradox": "Engineered with thousands of ventilation shafts and 1,000-pound rolling stone doors locked only from the inside."
        },
        {
            "topic": "The Sailing Stones of Death Valley Kinetic Mystery",
            "category": "unexplained_history",
            "headline": "700-pound dolomite boulders travel hundreds of meters across dry desert playa leaving long carved tracks",
            "paradox": "Microscopic ice sheets propelled by gentle nocturnal desert breezes sliding heavy rock across mud with zero human contact."
        }
    ]

    @classmethod
    def get_recent_topics(cls, limit: int = 30) -> List[str]:
        recent = []
        if HISTORY_LOG_FILE.exists():
            try:
                with open(HISTORY_LOG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("uploads", [])[-limit:]:
                        t = item.get("topic") or item.get("title")
                        if t:
                            recent.append(t)
            except Exception:
                pass
        return recent

    @classmethod
    def research_trend(cls, category_id: Optional[str] = None) -> Dict[str, Any]:
        recent_30 = cls.get_recent_topics(30)
        print(f"\n🔍 [Trend Researcher] Checking history & variety store (Found {len(recent_30)} recent uploads in lookback memory)")

        # 0. Integrated Multi-Source Trend Aggregator (YouTube, Google Trends RSS, Reddit with RSS fallback)
        try:
            from trend_aggregator import trend_aggregator
            trend = trend_aggregator.get_fresh_daily_trend(target_category_id=category_id)
            if trend and trend.get("topic"):
                return trend
        except Exception as e:
            print(f"   [Trend Aggregator Notice] {e}, continuing failover cascade...")

        # 1. Perplexity search if key present
        if PERPLEXITY_API_KEY:
            try:
                headers = {"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"}
                prompt = (
                    "Find 1 trending breakout viral mystery, unexplained Indian history, or bizarre biology hook on YouTube Shorts this week. "
                    "Output valid JSON ONLY: {\"topic\": \"...\", \"category\": \"...\", \"headline\": \"...\", \"paradox\": \"...\"}"
                )
                payload = {"model": "sonar", "messages": [{"role": "user", "content": prompt}]}
                r = requests.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload, timeout=12)
                if r.status_code == 200:
                    content = r.json()["choices"][0]["message"]["content"]
                    s, e = content.find("{"), content.rfind("}")
                    if s != -1 and e != -1:
                        data = json.loads(content[s:e+1])
                        t_name = data.get("topic", "")
                        is_fresh, reason = variety_engine.is_fresh(topic=t_name)
                        if is_fresh and t_name not in recent_30:
                            print(f"✨ [Perplexity API] Fresh breakout topic: '{t_name}'")
                            return data
                        else:
                            print(f"   [Variety Filter] Perplexity candidate rejected: {reason}")
            except Exception as e:
                print(f"   [Perplexity Warning] {e}")

        # 2. Live Daily Trend Scraping via Google News & Google Trends RSS (Zero-Cost & Real-Time)
        rss_urls = [
            ("Google News Discovery", "https://news.google.com/rss/search?q=mystery+OR+discovery+OR+unexplained+OR+ancient&hl=en-IN&gl=IN&ceid=IN:en", "unexplained_mystery"),
            ("Google Trends India", "https://trends.google.com/trending/rss?geo=IN", "daily_viral_trend")
        ]
        import xml.etree.ElementTree as ET
        for feed_name, feed_url, default_cat in rss_urls:
            try:
                res = requests.get(feed_url, headers=BROWSER_HEADERS, timeout=8)
                if res.status_code == 200 and len(res.content) > 100:
                    root = ET.fromstring(res.content)
                    items = root.findall(".//item")
                    for item in items[:10]:
                        raw_title = item.find("title").text or ""
                        clean_t = re.sub(r' - [^-]+$', '', raw_title).strip()
                        if clean_t and len(clean_t) > 12:
                            is_fresh, reason = variety_engine.is_fresh(topic=clean_t)
                            if is_fresh and not any(clean_t.lower() in r.lower() or r.lower() in clean_t.lower() for r in recent_30):
                                print(f"✨ [Live RSS: {feed_name}] Discovered fresh daily trend: '{clean_t}'")
                                topic_candidate = {
                                    "topic": clean_t[:80],
                                    "category": default_cat,
                                    "headline": f"Shocking real-world revelation behind {clean_t[:60]}",
                                    "paradox": f"Scientists and historians are stunned by unexpected anomalies uncovered in {clean_t[:45]}."
                                }
                                return topic_candidate
                            else:
                                print(f"   [Variety Filter] RSS candidate rejected: '{clean_t[:35]}' ({reason})")
            except Exception as rss_err:
                print(f"   [RSS Trend Warning: {feed_name}] {rss_err}")

        # 3. Filter Curated Vault against variety_engine.is_fresh() and category rotation
        vault_candidates = []
        for item in cls.CURATED_DISCOVERY_VAULT:
            is_fresh, _ = variety_engine.is_fresh(topic=item["topic"])
            if is_fresh and item["topic"] not in recent_30:
                vault_candidates.append(item)

        if category_id:
            matched = [c for c in vault_candidates if category_id.lower() in c.get("category", "").lower() or c.get("category", "").lower() in category_id.lower()]
            if matched:
                vault_candidates = matched

        if not vault_candidates:
            print("   [Gate] Vault candidates filtered by variety engine. Invoking Dynamic LLM Generator for 100% fresh topic...")
            fresh = cls._generate_fresh_llm_topic(recent_30, category_id=category_id)
            if fresh:
                return fresh
            vault_candidates = cls.CURATED_DISCOVERY_VAULT

        chosen = random.choice(vault_candidates)
        print(f"🎯 [Topic Selected]: '{chosen['topic']}' ({chosen['category']})")
        print(f"   Headline: {chosen['headline']}")
        return chosen


    @classmethod
    def _generate_fresh_llm_topic(cls, recent_30: List[str]) -> Optional[Dict[str, Any]]:
        prompt = (
            "You are an investigative documentary researcher for viral science/history YouTube Shorts.\n"
            f"Here are the last 30 topics already used: {json.dumps(recent_30[:15])}\n"
            "Generate 1 COMPLETELY NEW, verified, mind-blowing topic in Indian architectural enigmas, "
            "bizarre biological phenomena, or epic historical paradoxes that is NOT in the used list.\n"
            "Respond ONLY with valid JSON:\n"
            "{\"topic\": \"...\", \"category\": \"...\", \"headline\": \"...\", \"paradox\": \"...\"}"
        )
        # Tier A: Gemini with resilient model pool
        if GEMINI_API_KEY:
            for g_model in ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]:
                try:
                    from google import genai
                    client = genai.Client(api_key=GEMINI_API_KEY)
                    resp = client.models.generate_content(model=g_model, contents=prompt)
                    raw = resp.text.strip().replace("```json", "").replace("```", "").strip()
                    s, e = raw.find("{"), raw.rfind("}")
                    if s != -1 and e != -1:
                        return json.loads(raw[s:e+1])
                except Exception as ex:
                    print(f"   [Gemini {g_model} Topic Notice]: {ex}")
                    continue

        # Tier B: Keyless Pollinations Text AI fallback
        try:
            p_payload = {
                "messages": [
                    {"role": "system", "content": "You are a documentary researcher. Output strict JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "jsonMode": True,
                "seed": random.randint(100, 99999)
            }
            r = requests.post("https://text.pollinations.ai/", json=p_payload, timeout=20)
            if r.status_code == 200:
                raw = r.text.strip().replace("```json", "").replace("```", "").strip()
                s, e = raw.find("{"), raw.rfind("}")
                if s != -1 and e != -1:
                    return json.loads(raw[s:e+1])
        except Exception:
            pass

        return None


# =============================================================================
# STEP 2: SCRIPT GENERATION CASCADE (Chain of 5 Providers)
# =============================================================================

PRE_CRAFTED_SCRIPTS = {
    "The Lepakshi Hanging Pillar Gravity Paradox": {
        "title": "Lepakshi Ka Hawa Me Latakta Khamba 🏛️ #Shorts #Mystery",
        "duration": "24-28 seconds",
        "voiceover_clean": (
            "Sattar ton ka thos pathar bina zameen ko chuye hawa me kaise latak sakta hai! "
            "Yeh hai Andhra Pradesh ka 500 saal purana Lepakshi mandir, jahan ek khamba zameen se poori tarah utha hua hai! "
            "Log iske neeche se kapda aur akhbaar nikaalte hain aur wo kahin nahi atakta. "
            "Ek British engineer ne is khambe ko hatane ki koshish ki, lekin poori mandir ki chhat hilti dekh wo khaufzada ho gaya. "
            "Ancient builders ne isme aisi invisible earthquake load-bearing physics daali hai jo modern engineers ko bhi chaunka deti hai. "
            "Aur sabse hairani ki baat ye hai ki is 70 ton ke khambe ke neeche..."
        ),
        "pinned_comment": "Kya aapko lagta hai pracheen Bharat ke paas aisi takneek thi jo aaj kho chuki hai? Comment me batao! 👇 #shorts",
        "scenes": [
            {"id": 1, "prompt": "Cinematic 3D hyper-realism, octane 3D render style, extreme macro shot of the base of an ancient carved monolithic stone pillar floating 2 inches above a smooth granite floor, visible gap with dramatic dust particles, vertical 9:16, 8k, dynamic dramatic volumetric lighting, ancient Sanskrit carvings"},
            {"id": 2, "prompt": "Cinematic 3D hyper-realism, octane 3D render style, majestic wide eye-level perspective inside Veerabhadra temple at Lepakshi, towering Vijayanagara stone pillars, flickering brass oil lamps casting warm amber glow on dark weathered stone, vertical 9:16, 8k, dynamic lighting"},
            {"id": 3, "prompt": "Cinematic 3D hyper-realism, octane 3D render style, low-angle dynamic close-up of a crimson silk cloth smoothly sliding completely underneath the floating stone pillar without touching the floor, ray-traced shadows, vertical 9:16, 8k, dynamic volumetric lighting"},
            {"id": 4, "prompt": "Cinematic 3D hyper-realism, octane 3D render style, historical colonial engineer in 1800s trying to move the hanging pillar with iron crowbars, ceiling stones groaning with dynamic dust falling from above, high-contrast cinematic chiaroscuro lighting, vertical 9:16, 8k, dynamic camera angle"},
            {"id": 5, "prompt": "Cinematic 3D hyper-realism, octane 3D render style, futuristic cyan holographic stress-line CAD telemetry projected onto ancient stone pillar demonstrating anti-seismic balance joint, high-tech archaeological inspection, vertical 9:16, 8k, dynamic lighting"},
            {"id": 6, "prompt": "Cinematic 3D hyper-realism, octane 3D render style, extreme vertical panoramic vista of Lepakshi temple silhouette under starry cosmic night sky with deep purple nebula and glowing golden aura tracing the temple gopuram, vertical 9:16, 8k, dynamic lighting"}
        ]
    },
    "The Pistol Shrimp 8000K Sonoluminescence Paradox": {
        "title": "Suraj Se Bhi Zyada Garam Jheenga 🦐🔥 #Shorts #Science",
        "duration": "24-28 seconds",
        "voiceover_clean": (
            "Suraj se bhi zyada garam aag paida karta hai samandar me chhipa ye do inch ka jheenga! "
            "Jab Pistol Shrimp apna claw 100 kilometer prati ghante ki speed se band karta hai, toh ek microscopic bubble banta hai! "
            "Yeh bubble itni tez collapse hota hai ki andar ka temperature 8,000 Kelvin tak pahunch jata hai! "
            "Yeh sooraj ki satah se bhi zyada garam hai aur isse real light flash nikalta hai jise Sonoluminescence kehte hain! "
            "Iski paida ki hui 218 decibel shockwave shikar ko behosh kar deti hai. "
            "Aur sabse hairatangez baat ye hai ki samandar ki gehraiyon me..."
        ),
        "pinned_comment": "Kya aapko pata tha ki ek chhota sa jheenga suraj se zyada heat bana sakta hai? Like karein agar nayi jaankari mili! 👇 #shorts",
        "scenes": [
            {"id": 1, "prompt": "Cinematic 3D hyper-realism, octane 3D render style, extreme macro shot of an incandescent glowing orange and electric blue Pistol Shrimp claw underwater, miniature underwater solar flare sparks, vertical 9:16, 8k, dynamic volumetric lighting"},
            {"id": 2, "prompt": "Cinematic 3D hyper-realism, octane 3D render style, high-speed macro freeze frame of claw snapping shut with high-velocity water jet creating a vacuum cavitation bubble, refracted water optics, vertical 9:16, 8k, dynamic lighting"},
            {"id": 3, "prompt": "Cinematic 3D hyper-realism, octane 3D render style, microscopic cross-section diagram of cavitation bubble collapsing under extreme pressure, incandescent white-hot core temperature visualization, vertical 9:16, 8k, dynamic lighting"},
            {"id": 4, "prompt": "Cinematic 3D hyper-realism, octane 3D render style, brilliant flash of blue-white light illuminating the pitch black deep sea abyssal ocean floor, sonoluminescence burst, vertical 9:16, 8k, volumetric deep sea lighting"},
            {"id": 5, "prompt": "Cinematic 3D hyper-realism, octane 3D render style, visual acoustic shockwave rings expanding through seawater stunning passing oceanic prey, rippling kinetic pressure waves, vertical 9:16, 8k, dynamic lighting"},
            {"id": 6, "prompt": "Cinematic 3D hyper-realism, octane 3D render style, panoramic vertical perspective of abyssal ocean trench with glowing bioluminescent creatures swimming into the deep blue abyss, vertical 9:16, 8k, dynamic lighting"}
        ]
    }
}


def _sanitize_script_response(raw_text: str, topic_name: str) -> Optional[Dict[str, Any]]:
    """Strict JSON parser and schema validator for script generation cascade."""
    s = raw_text.find("{")
    e = raw_text.rfind("}")
    if s == -1 or e == -1:
        return None
    try:
        data = json.loads(raw_text[s:e+1])
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    if "title" not in data or "voiceover_clean" not in data:
        return None

    # Strip bracketed stage directions or notes from spoken narration
    vo = data["voiceover_clean"]
    vo = re.sub(r"\[.*?\]", "", vo)
    vo = re.sub(r"\(.*?\)", "", vo)
    vo = " ".join(vo.split()).strip()
    data["voiceover_clean"] = vo

    if "pinned_comment" not in data:
        data["pinned_comment"] = f"Aapka is baare me kya manna hai? Comments me batayein! 👇 #shorts"

    scenes = data.get("scenes", [])
    if not isinstance(scenes, list) or len(scenes) == 0:
        return None

    normalized_scenes = []
    for i, sc in enumerate(scenes[:6]):
        sc_id = sc.get("id", i + 1)
        sc_prompt = sc.get("prompt", sc.get("visual_prompt", f"Cinematic 3D hyper-realism, octane 3D render style, {topic_name}, scene {i+1}, vertical 9:16, 8k, dynamic lighting"))
        normalized_scenes.append({"id": sc_id, "prompt": sc_prompt})

    while len(normalized_scenes) < 6:
        idx = len(normalized_scenes) + 1
        normalized_scenes.append({
            "id": idx,
            "prompt": f"Cinematic 3D hyper-realism, octane 3D render style, {topic_name} climactic visual {idx}, vertical 9:16, 8k, dynamic lighting"
        })

    data["scenes"] = normalized_scenes
    return data


def _apply_critic_pass(data: Dict[str, Any], topic_name: str, bundle: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Pass 2: Runs adversarial critic scoring & auto-rewrite loop."""
    try:
        from script_critic import script_critic
        final_script, critique = script_critic.run_writer_critic_pipeline(data, topic_name, bundle=bundle)
        return final_script
    except Exception as e:
        print(f"   [Script Critic Pass Notice] {e}")
        return data


def generate_script_with_failover(topic_data: Any, bundle: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    SCRIPT GENERATION CASCADE (Chain of 5 Providers)
    - Tier 1: Google Gemini 2.5 Flash API (Free Tier key)
    - Tier 2: Groq Cloud API (llama-3.3-70b-versatile - Free high-speed tier)
    - Tier 3: DeepSeek Free API / OpenRouter Free Tier
    - Tier 4: Cohere API (command-r free tier)
    - Tier 5 (Keyless Emergency): Pollinations AI Text (https://text.pollinations.ai)
    """
    if isinstance(topic_data, dict):
        topic_name = topic_data.get("topic", "The Ancient Mystery")
        headline = topic_data.get("headline", "")
        paradox = topic_data.get("paradox", "")
    else:
        topic_name = str(topic_data)
        headline = ""
        paradox = ""

    # Check for direct vault hit first
    if topic_name in PRE_CRAFTED_SCRIPTS:
        print(f"📜 [Script Generator] Using pre-crafted 24-28s script for '{topic_name}'.")
        return PRE_CRAFTED_SCRIPTS[topic_name]

    # Select distinct visual aesthetic and hook from bundle or matrix
    if bundle and "visual_style" in bundle:
        chosen_style = {
            "style_name": bundle["visual_style"]["name"],
            "prompt_prefix": bundle["visual_style"]["prompt_dna"],
            "c_bg": bundle["visual_style"].get("c_bg", (15, 12, 25)),
            "c_fg": bundle["visual_style"].get("c_fg", (255, 190, 80))
        }
        hook_format = bundle.get("hook_format")
    else:
        style_idx = (int(time.time()) // 86400 + random.randint(0, len(VIRAL_VISUAL_STYLES) - 1)) % len(VIRAL_VISUAL_STYLES)
        chosen_style = VIRAL_VISUAL_STYLES[style_idx]
        hook_format = None

    print(f"🎨 [Visual Style Directed]: {chosen_style['style_name']}")
    if hook_format:
        print(f"🪝 [Hook Format Directed]: {hook_format['name']}")

    hook_directive = ""
    if hook_format:
        hook_directive = (
            f"Hook Format Formula: {hook_format['name']} -> {hook_format['formula']}\n"
            f"Hook Model Example: \"{hook_format['example']}\"\n"
        )

    script_prompt = (
        f"You are a master viral retention scriptwriter for YouTube Shorts and Instagram Reels.\n"
        f"Topic: {topic_name}\n"
        f"Headline: {headline}\n"
        f"Paradox: {paradox}\n"
        f"Visual Aesthetic Directive: {chosen_style['prompt_prefix']}\n"
        f"{hook_directive}\n"
        "Generate a 24-28 second video script. Respond in STRICT JSON ONLY matching this exact schema:\n"
        "{\n"
        "  \"title\": \"Shocking headline with emojis and #Shorts\",\n"
        "  \"voiceover_clean\": \"Spoken Hindi/Hinglish speech only. 60-75 words total. Zero stage directions, zero brackets, zero emojis in spoken text. Drop viewer into an unresolved paradox in the first 2 seconds with seamless circular loop back to word 1.\",\n"
        "  \"pinned_comment\": \"Engaging question in Hindi/English to drive comments\",\n"
        "  \"scenes\": [\n"
        f"    {{\"id\": 1, \"prompt\": \"{chosen_style['prompt_prefix']}, dramatic opening hook visual, vertical 9:16, dynamic cinematic lighting, scene 1...\"}},\n"
        f"    {{\"id\": 2, \"prompt\": \"{chosen_style['prompt_prefix']}, revealing backstory detail, vertical 9:16, high contrast, scene 2...\"}},\n"
        f"    {{\"id\": 3, \"prompt\": \"{chosen_style['prompt_prefix']}, escalation of tension, vertical 9:16, moody chiaroscuro, scene 3...\"}},\n"
        f"    {{\"id\": 4, \"prompt\": \"{chosen_style['prompt_prefix']}, shocking twist discovery, vertical 9:16, volumetric lighting, scene 4...\"}},\n"
        f"    {{\"id\": 5, \"prompt\": \"{chosen_style['prompt_prefix']}, climactic visual proof, vertical 9:16, vivid textures, scene 5...\"}},\n"
        f"    {{\"id\": 6, \"prompt\": \"{chosen_style['prompt_prefix']}, circular infinite loop reveal, vertical 9:16, dramatic silhouette, scene 6...\"}}\n"
        "  ]\n"
        "}\n\n"
        "RULES:\n"
        "- 'voiceover_clean' MUST be pure conversational Hindi/Hinglish. NO [SFX], (whisper), or bracketed notes.\n"
        "- Hook (first 2 seconds): Apply the assigned Hook Format Formula strictly. Start mid-conflict with an impossible claim. No greetings like 'Namaste' or 'Did you know'.\n"
        "- Exactly 6 scenes in 'scenes' array. Each scene's prompt must describe specific scene action matching the aesthetic."
    )

    # -------------------------------------------------------------------------
    # Tier 1: Google Gemini Flash API (Confirmed models pool)
    # -------------------------------------------------------------------------
    if GEMINI_API_KEY:
        for g_model in ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]:
            try:
                from google import genai
                client = genai.Client(api_key=GEMINI_API_KEY)
                resp = client.models.generate_content(
                    model=g_model,
                    contents=script_prompt
                )
                data = _sanitize_script_response(resp.text, topic_name)
                if data:
                    print(f"   [Tier 1: Gemini ({g_model})] Script generated successfully.")
                    return _apply_critic_pass(data, topic_name, bundle=bundle)
            except Exception as e:
                print(f"   [Gemini {g_model} Script Notice]: {e}")
                continue
        print("[WARNING] All Gemini Flash models in pool exhausted. Falling back to Provider Groq Cloud API...")
    else:
        print("[WARNING] Provider Gemini Flash key not set. Falling back to Provider Groq Cloud API...")

    # -------------------------------------------------------------------------
    # Tier 2: Groq Cloud API (llama-3.3-70b-versatile)
    # -------------------------------------------------------------------------
    if GROQ_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are a viral YouTube Shorts scriptwriter. Output strict JSON only."},
                    {"role": "user", "content": script_prompt}
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            }
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=15)
            if r.status_code == 200:
                txt = r.json()["choices"][0]["message"]["content"]
                data = _sanitize_script_response(txt, topic_name)
                if data:
                    print("   [Tier 2: Groq Cloud Llama 3.3] Script generated successfully.")
                    return _apply_critic_pass(data, topic_name, bundle=bundle)
            print(f"[WARNING] Provider Groq Cloud API rate-limited (HTTP {r.status_code}). Falling back to Provider DeepSeek / OpenRouter...")
        except Exception as e:
            print(f"[WARNING] Provider Groq Cloud API rate-limited. Falling back to Provider DeepSeek / OpenRouter... (Error: {e})")
    else:
        print("[WARNING] Provider Groq Cloud API key not set. Falling back to Provider DeepSeek / OpenRouter...")

    # -------------------------------------------------------------------------
    # Tier 3: DeepSeek Free API / OpenRouter Free Tier
    # -------------------------------------------------------------------------
    or_key = OPENROUTER_API_KEY or DEEPSEEK_API_KEY
    if or_key:
        try:
            if OPENROUTER_API_KEY:
                endpoint = "https://openrouter.ai/api/v1/chat/completions"
                model_name = "meta-llama/llama-3.3-70b-instruct:free"
            else:
                endpoint = "https://api.deepseek.com/chat/completions"
                model_name = "deepseek-chat"
            headers = {"Authorization": f"Bearer {or_key}", "Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "Output valid JSON only matching the schema."},
                    {"role": "user", "content": script_prompt}
                ],
                "temperature": 0.7
            }
            r = requests.post(endpoint, headers=headers, json=payload, timeout=20)
            if r.status_code == 200:
                txt = r.json()["choices"][0]["message"]["content"]
                data = _sanitize_script_response(txt, topic_name)
                if data:
                    print(f"   [Tier 3: {model_name}] Script generated successfully.")
                    return _apply_critic_pass(data, topic_name, bundle=bundle)
            print(f"[WARNING] Provider DeepSeek / OpenRouter rate-limited (HTTP {r.status_code}). Falling back to Provider Cohere API...")
        except Exception as e:
            print(f"[WARNING] Provider DeepSeek / OpenRouter rate-limited. Falling back to Provider Cohere API... (Error: {e})")
    else:
        print("[WARNING] Provider DeepSeek / OpenRouter key not set. Falling back to Provider Cohere API...")

    # -------------------------------------------------------------------------
    # Tier 4: Cohere API (command-r free tier)
    # -------------------------------------------------------------------------
    if COHERE_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {COHERE_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "command-r",
                "messages": [{"role": "user", "content": script_prompt}]
            }
            r = requests.post("https://api.cohere.com/v2/chat", headers=headers, json=payload, timeout=20)
            if r.status_code == 200:
                txt = r.json()["message"]["content"][0]["text"]
                data = _sanitize_script_response(txt, topic_name)
                if data:
                    print("   [Tier 4: Cohere Command-R] Script generated successfully.")
                    return _apply_critic_pass(data, topic_name, bundle=bundle)
            print(f"[WARNING] Provider Cohere API rate-limited (HTTP {r.status_code}). Falling back to Provider Pollinations AI Text...")
        except Exception as e:
            print(f"[WARNING] Provider Cohere API rate-limited. Falling back to Provider Pollinations AI Text... (Error: {e})")
    else:
        print("[WARNING] Provider Cohere API key not set. Falling back to Provider Pollinations AI Text...")

    # -------------------------------------------------------------------------
    # Tier 5 (Keyless Emergency): Pollinations AI Text
    # -------------------------------------------------------------------------
    try:
        payload = {
            "messages": [
                {"role": "system", "content": "You are a viral YouTube Shorts scriptwriter. Respond in strict JSON only."},
                {"role": "user", "content": script_prompt}
            ],
            "jsonMode": True,
            "seed": random.randint(100, 99999)
        }
        r = requests.post("https://text.pollinations.ai/", json=payload, timeout=25)
        if r.status_code == 200:
            data = _sanitize_script_response(r.text, topic_name)
            if data:
                print("   [Tier 5: Pollinations AI Text] Script generated successfully without any API keys.")
                return _apply_critic_pass(data, topic_name, bundle=bundle)
        print(f"[WARNING] Provider Pollinations AI Text returned HTTP {r.status_code}. Falling back to Pre-Crafted Vault...")
    except Exception as e:
        print(f"[WARNING] Provider Pollinations AI Text failed. Falling back to Pre-Crafted Vault... (Error: {e})")

    # Final Safety Net: Pre-crafted script from vault
    print("   [Script Fallback] Selecting pre-crafted master viral script.")
    fallback = PRE_CRAFTED_SCRIPTS.get("The Lepakshi Hanging Pillar Gravity Paradox")
    return _apply_critic_pass(fallback, topic_name, bundle=bundle) if fallback else data


class ScriptGenerator:
    """Wrapper class maintaining compatibility with pipeline interfaces."""
    @classmethod
    def generate_script(cls, topic_data: Dict[str, Any]) -> Dict[str, Any]:
        return generate_script_with_failover(topic_data)


# =============================================================================
# STEP 3: VISUAL GENERATION CASCADE (Chain of 4 Free Engines)
# =============================================================================

def _validate_image_file(path: Path) -> bool:
    """
    Validates:
    1. File exists and file size > 30KB.
    2. Check frame average luminance to ensure NO black or empty frames pass through.
    """
    if not path.exists():
        return False
    if path.stat().st_size < 30 * 1024:
        return False
    try:
        with Image.open(path) as im:
            stat = np.array(im.convert("L"))
            mean_lum = float(np.mean(stat))
            if mean_lum < 10.0:
                print(f"      [Luminance Reject] Image too dark/empty (Mean luminance: {mean_lum:.2f} < 10.0)")
                return False
        return True
    except Exception:
        return False


def _generate_procedural_fallback_frame(prompt: str, scene_idx: int, out_path: Path) -> Path:
    """Generates a high-contrast, multi-style cinematic vertical motion graphic as an absolute guarantee."""
    W, H = 1080, 1920
    # Select distinct color style and geometric layout from VIRAL_VISUAL_STYLES
    style = VIRAL_VISUAL_STYLES[scene_idx % len(VIRAL_VISUAL_STYLES)]
    c_bg = style.get("c_bg", (20, 15, 30))
    c_fg = style.get("c_fg", (255, 200, 50))
    pattern = style.get("pattern", "cyber_grid")

    im = Image.new("RGB", (W, H), c_bg)
    draw = ImageDraw.Draw(im)

    # 1. Multi-Stop Gradient Background
    for y in range(H):
        ratio = y / H
        r = int(c_bg[0] + (c_fg[0] * 0.25 - c_bg[0]) * ratio)
        g = int(c_bg[1] + (c_fg[1] * 0.25 - c_bg[1]) * ratio)
        b = int(c_bg[2] + (c_fg[2] * 0.25 - c_bg[2]) * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    cx, cy = W // 2, H // 2

    # 2. Pattern-Specific Geometric Elements
    if pattern in ("cyber_grid", "bio_matrix"):
        # Perspective grid lines & digital scanlines
        for x in range(0, W, 60):
            draw.line([(x, 0), (x, H)], fill=(c_fg[0] // 5, c_fg[1] // 5, c_fg[2] // 5), width=1)
        for y in range(0, H, 80):
            draw.line([(0, y), (W, y)], fill=(c_fg[0] // 6, c_fg[1] // 6, c_fg[2] // 6), width=1)
        # Center glowing tech diamond
        for rad in range(300, 0, -30):
            a_col = (int(c_fg[0] * (1 - rad / 350)), int(c_fg[1] * (1 - rad / 350)), int(c_fg[2] * (1 - rad / 350)))
            draw.polygon([(cx, cy - rad), (cx + rad, cy), (cx, cy + rad), (cx - rad, cy)], outline=a_col, width=3)
    elif pattern in ("noir_split", "pop_halftone"):
        # Dynamic diagonal split with sharp high-contrast bands
        draw.polygon([(0, 0), (W, H // 3), (W, H), (0, H * 2 // 3)], fill=(c_bg[0] + 20, c_bg[1] + 20, c_bg[2] + 20))
        for ang in range(-45, 90, 15):
            draw.line([(0, cy + int(ang * 12)), (W, cy + int(ang * 8))], fill=(c_fg[0] // 4, c_fg[1] // 4, c_fg[2] // 4), width=2)
    else:
        # Volumetric radial light burst with particle stars
        for rad in range(550, 0, -35):
            factor = 1.0 - (rad / 550)
            col = (int(c_bg[0] + (c_fg[0] - c_bg[0]) * factor * 0.7),
                   int(c_bg[1] + (c_fg[1] - c_bg[1]) * factor * 0.7),
                   int(c_bg[2] + (c_fg[2] - c_bg[2]) * factor * 0.7))
            draw.ellipse([(cx - rad, cy - rad), (cx + rad, cy + rad)], fill=col)
        # Random particle stars
        rng = random.Random(scene_idx * 1337)
        for _ in range(70):
            px, py = rng.randint(40, W - 40), rng.randint(80, H - 80)
            psize = rng.randint(2, 5)
            draw.ellipse([(px, py), (px + psize, py + psize)], fill=(255, 255, 255, 180))

    # 3. Cinematic Viewfinder Corner Brackets
    bracket_len = 45
    b_col = (min(255, c_fg[0] + 50), min(255, c_fg[1] + 50), min(255, c_fg[2] + 50))
    for bx, by in [(80, 120), (W - 80, 120), (80, H - 120), (W - 80, H - 120)]:
        dx = bracket_len if bx < cx else -bracket_len
        dy = bracket_len if by < cy else -bracket_len
        draw.line([(bx, by), (bx + dx, by)], fill=b_col, width=3)
        draw.line([(bx, by), (bx, by + dy)], fill=b_col, width=3)

    # 4. Clean Cross-Platform Typography / Scene Watermark
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf"
    ]
    font = None
    for fp in font_candidates:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 56)
                break
            except Exception:
                pass
    if not font:
        font = ImageFont.load_default()

    # Scene Badge text
    badge_text = f"SCENE 0{scene_idx + 1}"
    draw.text((cx, cy), badge_text, anchor="mm", font=font, fill=(255, 255, 255, 220), stroke_width=3, stroke_fill=(0, 0, 0, 255))

    im.save(out_path, quality=95)
    return out_path


def generate_scene_image_with_failover(prompt: str, scene_idx: int) -> str:
    """
    VISUAL GENERATION CASCADE (Chain of 6 Multi-Engine Tiers)
    - Tier 1: Pollinations AI FLUX / Turbo (with Browser Headers, Keyless & 9:16 Vertical)
    - Tier 2: Free Pexels 4K Stock Photography (via PEXELS_API_KEY)
    - Tier 3: Wikimedia Commons High-Res Topic Photography (Keyless & Zero Cost)
    - Tier 4: Lorem Picsum HD Photographic Cinematic Assets (Keyless & Zero Cost)
    - Tier 5: Local Dynamic B-Roll Vault (assets/fallback_vault/)
    - Tier 6: Multi-Style Procedural Cinematic Graphic (The Absolute Guarantee)
    """
    import io as _io
    clean_prompt = prompt.replace("\n", " ").strip()
    target_path = DIRECTOR_SCENES_DIR / f"scene_{scene_idx:02d}_{int(time.time())}.jpg"
    seed = random.randint(100, 99999)

    # -------------------------------------------------------------------------
    # Tier 1: Pollinations AI FLUX / Turbo / Default (With Browser UA Headers)
    # -------------------------------------------------------------------------
    for model_name in ["flux", "turbo", "default"]:
        try:
            encoded_prompt = urllib.parse.quote(clean_prompt[:350])
            if model_name == "default":
                poll_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true&seed={seed}"
            else:
                poll_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model={model_name}&nologo=true&seed={seed}"
            r = requests.get(poll_url, headers=BROWSER_HEADERS, timeout=28)
            if r.status_code == 200 and len(r.content) > 25 * 1024:
                with open(target_path, "wb") as f:
                    f.write(r.content)
                if _validate_image_file(target_path):
                    print(f"   [Tier 1: Pollinations ({model_name})] Scene {scene_idx:02d} rendered ({target_path.stat().st_size // 1024} KB).")
                    return str(target_path)
            elif r.status_code in (402, 429):
                print(f"   [Pollinations {model_name}] rate-limited ({r.status_code}), cascading to next tier...")
                break
        except Exception as e:
            print(f"   [Pollinations {model_name}] notice: {e}")

    # -------------------------------------------------------------------------
    # Tier 2: Free Pexels 4K Stock Photography (via PEXELS_API_KEY)
    # -------------------------------------------------------------------------
    if PEXELS_API_KEY:
        try:
            q = re.sub(r'[^a-zA-Z0-9 ]', '', clean_prompt.split(',')[0])[:50].strip() or "cinematic dramatic portrait"
            p_url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(q)}&orientation=portrait&per_page=3"
            pr = requests.get(p_url, headers={"Authorization": PEXELS_API_KEY}, timeout=12).json()
            photos = pr.get("photos", [])
            if photos:
                p_img_url = photos[scene_idx % len(photos)]["src"].get("large2x") or photos[scene_idx % len(photos)]["src"].get("original")
                c = requests.get(p_img_url, headers=BROWSER_HEADERS, timeout=15).content
                if len(c) > 20 * 1024:
                    with Image.open(_io.BytesIO(c)) as p_im:
                        p_im.convert("RGB").resize((1080, 1920), Image.Resampling.LANCZOS).save(target_path, quality=93)
                    if _validate_image_file(target_path):
                        print(f"   [Tier 2: Pexels 4K Photo] Scene {scene_idx:02d} sourced ({target_path.stat().st_size // 1024} KB).")
                        return str(target_path)
        except Exception as e:
            print(f"   [Tier 2 Pexels Warning] {e}")

    # -------------------------------------------------------------------------
    # Tier 3: Wikimedia Commons High-Res Topic Photography (Keyless & Zero Cost)
    # -------------------------------------------------------------------------
    try:
        q_clean = re.sub(r'[^a-zA-Z0-9 ]', '', clean_prompt.split(',')[0])[:35].strip()
        if q_clean:
            w_url = f"https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageimages&generator=search&gsrsearch={urllib.parse.quote(q_clean)}&gsrlimit=3&pithumbsize=1080"
            wr = requests.get(w_url, headers={"User-Agent": "YouTubeAutopilotProducer/2.0"}, timeout=8).json()
            pages = wr.get("query", {}).get("pages", {})
            for page in pages.values():
                thumb = page.get("thumbnail", {}).get("source")
                if thumb:
                    tc = requests.get(thumb, headers=BROWSER_HEADERS, timeout=10).content
                    if len(tc) > 15 * 1024:
                        with Image.open(_io.BytesIO(tc)) as w_im:
                            w_im.convert("RGB").resize((1080, 1920), Image.Resampling.LANCZOS).save(target_path, quality=93)
                        if _validate_image_file(target_path):
                            print(f"   [Tier 3: Wikimedia Topic Photo] Scene {scene_idx:02d} sourced ({target_path.stat().st_size // 1024} KB).")
                            return str(target_path)
    except Exception as e:
        print(f"   [Tier 3 Wikimedia Warning] {e}")

    # -------------------------------------------------------------------------
    # Tier 4: Lorem Picsum HD Photographic Cinematic Assets (Keyless & Zero Cost)
    # -------------------------------------------------------------------------
    try:
        picsum_url = f"https://picsum.photos/1080/1920?random={seed}"
        pr = requests.get(picsum_url, headers=BROWSER_HEADERS, timeout=10)
        if pr.status_code == 200 and len(pr.content) > 30 * 1024:
            with open(target_path, "wb") as f:
                f.write(pr.content)
            if _validate_image_file(target_path):
                print(f"   [Tier 4: Lorem Picsum HD] Scene {scene_idx:02d} real photo loaded ({target_path.stat().st_size // 1024} KB).")
                return str(target_path)
    except Exception as e:
        print(f"   [Tier 4 Picsum Warning] {e}")

    # -------------------------------------------------------------------------
    # Tier 5: Local Dynamic B-Roll Vault (assets/fallback_vault/)
    # -------------------------------------------------------------------------
    vault_images = list(FALLBACK_VAULT_DIR.glob("*.jpg")) + list(FALLBACK_VAULT_DIR.glob("*.png"))
    if not vault_images:
        vault_images = list(DIRECTOR_SCENES_DIR.glob("*.jpg"))

    if vault_images:
        chosen_vault_img = vault_images[(scene_idx - 1) % len(vault_images)]
        try:
            with Image.open(chosen_vault_img) as im:
                im_resized = im.resize((1080, 1920), Image.Resampling.LANCZOS)
                im_resized.save(target_path, quality=95)
            if _validate_image_file(target_path):
                print(f"   [Tier 5: Fallback Vault] Loaded {chosen_vault_img.name}.")
                return str(target_path)
        except Exception as e:
            print(f"   [Tier 5 Vault Warning] {e}")

    # -------------------------------------------------------------------------
    # Tier 6: Multi-Style Procedural Cinematic Graphic (The Absolute Guarantee)
    # -------------------------------------------------------------------------
    _generate_procedural_fallback_frame(clean_prompt, scene_idx, target_path)
    print(f"   [Tier 6: Procedural Graphic] Generated bespoke canvas for scene {scene_idx:02d}.")
    return str(target_path)


# =============================================================================
# STEP 4: VOICE SYNTHESIS CASCADE (Chain of 3 Providers)
# =============================================================================

def _clean_narration_for_tts(text: str) -> str:
    clean = re.sub(r"\[.*?\]", "", text)
    clean = re.sub(r"\(.*?\)", "", clean)
    clean = clean.replace("\n", " ").strip()
    return " ".join(clean.split())


def _get_audio_duration_seconds(path: Path) -> float:
    try:
        ffmpeg_exe = get_ffmpeg_binary()
        res = subprocess.run([ffmpeg_exe, "-i", str(path)], capture_output=True, text=True)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
        if m:
            return float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return 4.2


async def _synthesize_edge_tts(text: str, voice: str, rate: str, out_path: Path) -> bool:
    try:
        tts = edge_tts.Communicate(text, voice, rate=rate)
        await tts.save(str(out_path))
        return out_path.exists() and out_path.stat().st_size > 2000
    except Exception:
        return False


def generate_voice_with_failover(text: str, out_path: Optional[Path] = None, voice_id: Optional[str] = None, rate: str = "+10%") -> str:
    """
    VOICE SYNTHESIS CASCADE
    - Tier 1: Variety bundle voice (or hi-IN-MadhurNeural)
    - Tier 2: edge-tts voice hi-IN-SwaraNeural
    - Tier 3: Local gTTS (Google Translate TTS Hindi fallback)
    """
    if out_path is None:
        out_path = TEMP_DIR / f"voice_{int(time.time() * 1000)}.mp3"

    clean_text = _clean_narration_for_tts(text)

    # Optional Tier 0: ElevenLabs if key present
    if ELEVENLABS_API_KEY:
        try:
            headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
            payload = {
                "text": clean_text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.45, "similarity_boost": 0.85}
            }
            v_url = "https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB"
            r = requests.post(v_url, headers=headers, json=payload, timeout=18)
            if r.status_code == 200:
                with open(out_path, "wb") as f:
                    f.write(r.content)
                if out_path.exists() and out_path.stat().st_size > 2000:
                    print("   [Tier 0: ElevenLabs] Synthesized via eleven_multilingual_v2.")
                    return str(out_path)
            print("[WARNING] Provider ElevenLabs rate-limited. Falling back to Provider edge-tts...")
        except Exception as e:
            print(f"[WARNING] Provider ElevenLabs rate-limited. Falling back to Provider edge-tts... (Error: {e})")

    # -------------------------------------------------------------------------
    # Tier 1: Selected Variety Voice or Default hi-IN-MadhurNeural
    # -------------------------------------------------------------------------
    primary_voice = voice_id or "hi-IN-MadhurNeural"
    try:
        ok = asyncio.run(_synthesize_edge_tts(clean_text, primary_voice, rate, out_path))
        if ok:
            print(f"   [Tier 1: edge-tts ({primary_voice})] Voice synthesized successfully.")
            return str(out_path)
        print(f"[WARNING] Provider edge-tts ({primary_voice}) rate-limited. Falling back to SwaraNeural...")
    except Exception as e:
        print(f"[WARNING] Provider edge-tts ({primary_voice}) rate-limited. Falling back to SwaraNeural... (Error: {e})")

    # -------------------------------------------------------------------------
    # Tier 2: edge-tts voice hi-IN-SwaraNeural (rate: +10%)
    # -------------------------------------------------------------------------
    try:
        ok = asyncio.run(_synthesize_edge_tts(clean_text, "hi-IN-SwaraNeural", "+10%", out_path))
        if ok:
            print("   [Tier 2: edge-tts (SwaraNeural)] Voice synthesized successfully.")
            return str(out_path)
        print("[WARNING] Provider edge-tts (SwaraNeural) rate-limited. Falling back to Provider Local gTTS...")
    except Exception as e:
        print(f"[WARNING] Provider edge-tts (SwaraNeural) rate-limited. Falling back to Provider Local gTTS... (Error: {e})")

    # -------------------------------------------------------------------------
    # Tier 3: Local gTTS (Google Translate TTS Hindi fallback)
    # -------------------------------------------------------------------------
    try:
        from gtts import gTTS
        tts = gTTS(text=clean_text, lang="hi", slow=False)
        tts.save(str(out_path))
        print("   [Tier 3: Local gTTS Hindi] Audio synthesized successfully.")
        return str(out_path)
    except Exception as e:
        print(f"[ERROR] Local gTTS failed: {e}")
        # Absolute acoustic failover (generate silent wave to prevent pipeline stall)
        with wave.open(str(out_path), "w") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(np.zeros(int(44100 * 3.5), dtype=np.int16).tobytes())
        return str(out_path)


class VoiceSynthesizer:
    """Wrapper class maintaining compatibility with pipeline interfaces."""
    @classmethod
    async def synthesize(cls, text: str, out_path: Path) -> float:
        res_str = generate_voice_with_failover(text, out_path)
        return _get_audio_duration_seconds(Path(res_str))


# =============================================================================
# STEP 5: VIDEO ASSEMBLY & AUDIO MIXING
# =============================================================================

class RemotionVideoAssembler:
    """
    Step 5: Video Assembly
    - 6 distinct scenes (3-4s each)
    - Center-aligned uppercase 48pt captions with #FFFF00 yellow active-word highlight
    - Master Audio Mix: voiceover 0dB, impact_sfx_on_cuts -16dB, ambient_music -22dB
    """

    def __init__(self):
        self.ffmpeg_exe = get_ffmpeg_binary()
        self.sfx_impact = SFX_DIR / "impact.wav"
        self.ambient_music = SFX_DIR / "ambient_drone.wav"
        self._ensure_soundtrack()

    def _ensure_soundtrack(self):
        sr = 44100
        if not self.sfx_impact.exists():
            dur = 0.8
            n = int(sr * dur)
            t = np.linspace(0, dur, n, endpoint=False)
            pitch = 110 * np.exp(-t * 8) + 38
            body = np.sin(2 * np.pi * pitch * t)
            env = np.exp(-t * 5.0)
            impact = (body * env + 0.15 * np.random.uniform(-1, 1, n) * np.exp(-t * 25)) * 0.95
            with wave.open(str(self.sfx_impact), "w") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
                w.writeframes((impact * 32767).astype(np.int16).tobytes())

        if not self.ambient_music.exists():
            dur = 30.0
            n = int(sr * dur)
            t = np.linspace(0, dur, n, endpoint=False)
            lfo = 0.7 + 0.3 * np.sin(2 * np.pi * 0.25 * t)
            drone = (0.45 * np.sin(2 * np.pi * 55.0 * t) + 0.30 * np.sin(2 * np.pi * 82.4 * t) + 0.15 * np.sin(2 * np.pi * 110.0 * t)) * lfo
            env = np.minimum(1.0, t / 1.5) * np.minimum(1.0, (dur - t) / 1.5)
            with wave.open(str(self.ambient_music), "w") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
                w.writeframes(((drone * env * 0.85) * 32767).astype(np.int16).tobytes())

    def render_caption_badge(self, text: str, highlight_word: str, out_png: Path, caption_style: Optional[Dict[str, Any]] = None) -> Path:
        """Center-aligned, uppercase, 48pt font, active-word highlight, drop-shadow."""
        W, H = 1080, 1920
        font_paths = [
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ]
        font = None
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, 64)
                    break
                except Exception:
                    pass
        if not font:
            font = ImageFont.load_default()

        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        words = text.strip().upper().split()
        if not words:
            img.save(out_png)
            return out_png

        # Extract styling from bundle or fallback
        if caption_style:
            f_col = tuple(caption_style.get("font_color", (255, 235, 30)))
            s_col = tuple(caption_style.get("stroke_color", (0, 0, 0)))
            s_width = caption_style.get("stroke_width", 5)
            active_color = f_col + (255,) if len(f_col) == 3 else f_col
            stroke_rgba = s_col + (240,) if len(s_col) == 3 else s_col
        else:
            active_color = (255, 255, 0, 255)
            stroke_rgba = (0, 0, 0, 240)
            s_width = 5

        space_w = d.textbbox((0, 0), " ", font=font)[2]
        word_widths = [d.textbbox((0, 0), w, font=font)[2] - d.textbbox((0, 0), w, font=font)[0] for w in words]
        total_w = sum(word_widths) + space_w * (len(words) - 1)
        x = (W - total_w) // 2
        y = 1200

        for idx, w in enumerate(words):
            is_active = (highlight_word.upper() in w) if highlight_word else False
            color = active_color if is_active else (255, 255, 255, 255)
            for ox in range(-s_width, s_width + 1, max(1, s_width // 2)):
                for oy in range(-s_width, s_width + 1, max(1, s_width // 2)):
                    if ox != 0 or oy != 0:
                        d.text((x + ox, y + oy), w, font=font, fill=stroke_rgba)
            d.text((x, y), w, font=font, fill=color)
            x += word_widths[idx] + space_w

        img.save(out_png)
        return out_png

    def assemble(self, script_data: Dict[str, Any], output_file: Path, bundle: Optional[Dict[str, Any]] = None) -> Path:
        scenes = script_data.get("scenes", [])
        voiceover_full = script_data.get("voiceover_clean", "")

        # Extract bundle parameters
        caption_style = bundle.get("caption_style") if bundle else None
        camera_move = bundle.get("camera_move", {}) if bundle else {}
        voice_id = bundle.get("voice", {}).get("voice_id") if bundle else None

        # Split voiceover across 6 scenes if scenes do not have direct narration
        raw_sentences = [s.strip() for s in re.split(r"[.!?।|]+", voiceover_full) if len(s.strip()) > 3]
        if not raw_sentences:
            raw_sentences = [voiceover_full]

        total_scenes = len(scenes)
        print(f"\n🎬 [Video Assembler] Assembling reel across {total_scenes} scenes with failover cascades...")

        temp_audio_dir = TEMP_DIR / "audio_remotion"
        temp_scenes_dir = TEMP_DIR / "scenes_remotion"
        temp_audio_dir.mkdir(parents=True, exist_ok=True)
        temp_scenes_dir.mkdir(parents=True, exist_ok=True)

        scene_durations = []
        scene_audio_files = []
        scene_narrations = []

        for idx, s in enumerate(scenes):
            s_num = s.get("id", idx + 1)
            # Assign narration chunk
            if "narration" in s:
                chunk = s["narration"]
            else:
                sent_idx = min(idx, len(raw_sentences) - 1)
                chunk = raw_sentences[sent_idx]
            scene_narrations.append(chunk)

            a_path = temp_audio_dir / f"scene_{s_num:02d}.mp3"
            generate_voice_with_failover(chunk, a_path, voice_id=voice_id)
            dur = _get_audio_duration_seconds(a_path)
            dur = max(3.5, min(4.8, dur))
            scene_durations.append(dur)
            scene_audio_files.append(a_path)
            print(f"   Scene {s_num:02d}: {dur:.2f}s | Voice: '{chunk[:45]}...'")

        total_duration = sum(scene_durations)
        print(f"⏱️ [Video Assembler] Total Video Length: {total_duration:.2f}s (Target: 24-28 seconds)")

        rendered_scene_mp4s = []
        for idx, (s, dur, chunk) in enumerate(zip(scenes, scene_durations, scene_narrations)):
            s_num = s.get("id", idx + 1)
            out_scene_mp4 = temp_scenes_dir / f"clip_{s_num:02d}.mp4"

            # Visual Generation with Failover Cascade & Quality Gate
            prompt = s.get("prompt", f"Cinematic 3D hyper-realism, octane 3D render style, scene {s_num}, vertical 9:16, 8k")
            img_path_str = generate_scene_image_with_failover(prompt, s_num)
            try:
                from visual_quality_gate import quality_gate
                img_path_str = quality_gate.verify_or_regenerate_frame(
                    img_path_str=img_path_str,
                    prompt=prompt,
                    scene_idx=s_num,
                    regenerate_func=generate_scene_image_with_failover
                )
            except Exception as qg_err:
                print(f"   [Quality Gate Notice] {qg_err}")
            img_path = Path(img_path_str)

            # Caption keywords extraction
            words = chunk.split()
            cap_text = " ".join(words[:4]).upper() if words else "MYSTERY REVEALED"
            active_w = words[0] if words else "MYSTERY"
            b_png = temp_scenes_dir / f"badge_{s_num:02d}.png"
            self.render_caption_badge(cap_text, active_w, b_png, caption_style=caption_style)

            # Camera zoompan motion based on variety bundle
            total_frames = int(dur * 30)
            c_id = camera_move.get("id", "")
            if c_id == "dramatic_pull_out_reveal":
                z_expr = "max(1.15-0.0015*on,1.0)"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"
            elif c_id == "parallax_subtle_pan_right":
                z_expr = "1.08"
                x_expr = "(iw-iw/zoom)*(on/d)"
                y_expr = "ih/2-(ih/zoom/2)"
            elif c_id == "smooth_vertical_pedestal":
                z_expr = "1.08"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "(ih-ih/zoom)*(on/d)"
            else:
                # Default: ken_burns_slow_dolly_in
                z_expr = "min(zoom+0.0015,1.15)"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"

            filter_str = (
                f"[0:v]zoompan=z='{z_expr}':d={total_frames}:x='{x_expr}':y='{y_expr}':s=1080x1920:fps=30[bg]; "
                f"[bg][1:v]overlay=0:0[outv]"
            )

            cmd = [
                self.ffmpeg_exe, "-y",
                "-loop", "1", "-i", str(img_path),
                "-loop", "1", "-i", str(b_png),
                "-filter_complex", filter_str,
                "-map", "[outv]",
                "-t", f"{dur:.3f}",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                str(out_scene_mp4)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            rendered_scene_mp4s.append(out_scene_mp4)

        # Concatenate video clips
        concat_txt = temp_scenes_dir / "concat_remotion.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for r_mp4 in rendered_scene_mp4s:
                f.write(f"file '{r_mp4.resolve().as_posix()}'\n")

        raw_video = temp_scenes_dir / "raw_remotion_concat.mp4"
        cmd_concat = [
            self.ffmpeg_exe, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            str(raw_video)
        ]
        subprocess.run(cmd_concat, capture_output=True, check=True)

        # Mix Audio: voiceover 0dB, impact_sfx_on_cuts -16dB, ambient_music -22dB
        master_audio = temp_audio_dir / "master_remotion_audio.wav"
        self._mix_audio(scene_audio_files, scene_durations, master_audio)

        # Final Render with Cinematic Color Grade + Light 35mm Film Grain
        print(f"🚀 [Video Assembler] Rendering master reel with color grade & grain: {output_file.name}...")
        cmd_final = [
            self.ffmpeg_exe, "-y",
            "-i", str(raw_video),
            "-i", str(master_audio),
            "-vf", "unsharp=5:5:0.6:5:5:0.0,eq=contrast=1.06:saturation=1.12:brightness=0.01,noise=c1s=6:c0f=u",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_file)
        ]
        subprocess.run(cmd_final, capture_output=True, check=True)
        mb = output_file.stat().st_size / (1024 * 1024)
        print(f"🎉 [Video Assembler] Render Complete! File: {output_file} ({mb:.2f} MB)")
        return output_file

    def _mix_audio(self, voice_files: List[Path], durations: List[float], out_wav: Path):
        sr = 44100
        total_dur = sum(durations)
        total_samples = int(sr * (total_dur + 0.5))

        master_l = np.zeros(total_samples, dtype=np.float32)
        master_r = np.zeros(total_samples, dtype=np.float32)

        # 1. Ambient Music (-22dB = 0.0794 linear)
        if self.ambient_music.exists():
            with wave.open(str(self.ambient_music), "r") as w:
                n = w.getnframes()
                raw = w.readframes(n)
                drone_arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            drone_full = np.tile(drone_arr, int(math.ceil(total_samples / len(drone_arr))))[:total_samples]
            ambient_vol = 0.0794
            master_l += drone_full * ambient_vol
            master_r += drone_full * ambient_vol

        # 2. Voiceover (0dB = 0.88 linear) + Impact SFX on cuts (-16dB = 0.1585 linear)
        current_sample = 0
        sfx_vol = 0.1585

        for idx, (v_file, dur) in enumerate(zip(voice_files, durations)):
            temp_wav = TEMP_DIR / f"temp_v_{idx}.wav"
            cmd = [self.ffmpeg_exe, "-y", "-i", str(v_file), "-ar", "44100", "-ac", "1", str(temp_wav)]
            subprocess.run(cmd, capture_output=True, check=True)
            with wave.open(str(temp_wav), "r") as w:
                raw = w.readframes(w.getnframes())
                v_arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

            v_len = min(len(v_arr), total_samples - current_sample)
            master_l[current_sample:current_sample + v_len] += v_arr[:v_len] * 0.88
            master_r[current_sample:current_sample + v_len] += v_arr[:v_len] * 0.88

            # Add impact on cuts
            if idx > 0 and self.sfx_impact.exists():
                with wave.open(str(self.sfx_impact), "r") as w:
                    raw = w.readframes(w.getnframes())
                    s_arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                s_len = min(len(s_arr), total_samples - current_sample)
                master_l[current_sample:current_sample + s_len] += s_arr[:s_len] * sfx_vol
                master_r[current_sample:current_sample + s_len] += s_arr[:s_len] * sfx_vol

            current_sample += int(dur * sr)

        # Soft Limiter
        peak = max(np.max(np.abs(master_l)), np.max(np.abs(master_r)))
        if peak > 0.98:
            master_l = (master_l / peak) * 0.96
            master_r = (master_r / peak) * 0.96

        stereo = np.empty((total_samples, 2), dtype=np.int16)
        stereo[:, 0] = (master_l * 32767).astype(np.int16)
        stereo[:, 1] = (master_r * 32767).astype(np.int16)

        with wave.open(str(out_wav), "w") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes(stereo.tobytes())


# =============================================================================
# PERSISTENCE & MASTER EXECUTION
# =============================================================================

def log_to_history_log(meta: Dict[str, Any]):
    log_data = {"uploads": []}
    if HISTORY_LOG_FILE.exists():
        try:
            with open(HISTORY_LOG_FILE, "r", encoding="utf-8") as f:
                log_data = json.load(f)
        except Exception:
            log_data = {"uploads": []}

    log_data["uploads"].append(meta)
    with open(HISTORY_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    print(f"📝 [History Log] Recorded '{meta.get('title')}' in history_log.json")

    hist_data = {"videos": []}
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                hist_data = json.load(f)
        except Exception:
            hist_data = {"videos": []}
    hist_data["videos"].append(meta)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(hist_data, f, indent=2, ensure_ascii=False)


def restore_youtube_credentials():
    token_file = BASE_DIR / "token.json"
    client_secrets_file = BASE_DIR / "client_secrets.json"

    # 1. Restore client_secrets.json from Base64 or JSON string
    if not client_secrets_file.exists():
        if os.environ.get("YOUTUBE_CLIENT_SECRET_BASE64"):
            try:
                import base64
                raw = base64.b64decode(os.environ["YOUTUBE_CLIENT_SECRET_BASE64"].strip())
                client_secrets_file.write_bytes(raw)
                print("   [Auth] Restored client_secrets.json from YOUTUBE_CLIENT_SECRET_BASE64.")
            except Exception as e:
                print(f"   [Auth Warning] Failed to decode YOUTUBE_CLIENT_SECRET_BASE64: {e}")
        elif os.environ.get("CLIENT_SECRETS_JSON"):
            try:
                client_secrets_file.write_text(os.environ["CLIENT_SECRETS_JSON"].strip(), encoding="utf-8")
                print("   [Auth] Restored client_secrets.json from CLIENT_SECRETS_JSON.")
            except Exception as e:
                print(f"   [Auth Warning] Failed to write CLIENT_SECRETS_JSON: {e}")

    # 2. Restore token.json from Refresh Token or Token JSON string
    if not token_file.exists():
        if os.environ.get("YOUTUBE_TOKEN_JSON"):
            try:
                token_file.write_text(os.environ["YOUTUBE_TOKEN_JSON"].strip(), encoding="utf-8")
                print("   [Auth] Restored token.json from YOUTUBE_TOKEN_JSON.")
            except Exception as e:
                print(f"   [Auth Warning] Failed to write YOUTUBE_TOKEN_JSON: {e}")
        elif os.environ.get("YOUTUBE_REFRESH_TOKEN") and client_secrets_file.exists():
            try:
                cs_data = json.loads(client_secrets_file.read_text(encoding="utf-8"))
                app_info = cs_data.get("installed") or cs_data.get("web") or {}
                tok_struct = {
                    "token": "",
                    "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"].strip(),
                    "token_uri": app_info.get("token_uri", "https://oauth2.googleapis.com/token"),
                    "client_id": app_info.get("client_id", ""),
                    "client_secret": app_info.get("client_secret", ""),
                    "scopes": [
                        "https://www.googleapis.com/auth/youtube.upload",
                        "https://www.googleapis.com/auth/youtube.readonly",
                        "https://www.googleapis.com/auth/youtube.force-ssl"
                    ]
                }
                token_file.write_text(json.dumps(tok_struct, indent=2), encoding="utf-8")
                print("   [Auth] Generated token.json from YOUTUBE_REFRESH_TOKEN.")
            except Exception as e:
                print(f"   [Auth Warning] Failed to build token.json from refresh token: {e}")


def upload_to_youtube(video_path: Path, title: str, description: str, tags: List[str]) -> Optional[str]:
    restore_youtube_credentials()
    token_file = BASE_DIR / "token.json"
    if not token_file.exists():
        print("   [Upload Info] No token.json available. Video rendered and saved locally.")
        return None

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.auth.transport.requests import Request

        scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/youtube.force-ssl"
        ]
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")

        yt = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags[:15],
                "categoryId": "27",
                "defaultLanguage": "hi",
                "defaultAudioLanguage": "hi"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }
        print(f"📡 [YouTube API] Uploading '{title[:60]}'...")
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"   [Upload Progress] {int(status.progress() * 100)}% transferred...")

        vid_id = response.get("id")
        print(f"🎉 [YouTube API] Published Successfully! Video Link: https://youtu.be/{vid_id}")
        return vid_id
    except Exception as e:
        print(f"   [YouTube Upload Warning] {e}")
        return None


def run_autonomous_viral_reels_engine(dry_run: bool = True) -> str:
    print("\n" + "=" * 75)
    print("  🎬 AUTONOMOUS VIRAL REELS ENGINE (Zero-Cost Failover Cascade)")
    print("  Gemini/Groq/DeepSeek/Cohere • FLUX/HF/SDXL/Vault • EdgeTTS/gTTS")
    print("=" * 75)

    # Variety Engine: Pick Production Bundle with full cooldowns
    bundle = variety_engine.pick_production_bundle()
    print("\n✨ [Variety Bundle Selected]:")
    print(f"   • Category:     {bundle['category']['name']}")
    print(f"   • Visual Style: {bundle['visual_style']['name']}")
    print(f"   • Hook Format:  {bundle['hook_format']['name']}")
    print(f"   • Camera Move:  {bundle['camera_move']['name']}")
    print(f"   • Caption:      {bundle['caption_style']['name']}")
    print(f"   • Voice:        {bundle['voice']['voice_id']}")
    print(f"   • Music Mood:   {bundle['music_mood']['name']}")

    # Step 1: Research Trend with Variety Freshness Gate
    topic_data = TrendResearcher.research_trend(category_id=bundle["category"]["id"])

    # Step 2: Script Generation Cascade with Bundle
    script_data = generate_script_with_failover(topic_data, bundle=bundle)
    print(f"\n📜 [Script Title]: '{script_data.get('title')}'")
    print(f"   Voiceover Clean: '{script_data.get('voiceover_clean', '')[:80]}...'")
    print(f"   Pinned Comment: '{script_data.get('pinned_comment', '')}'")

    # Step 3, 4, 5: Visual, Audio & Assembly Cascade with Bundle
    assembler = RemotionVideoAssembler()
    out_name = f"reels_engine_short_{int(time.time())}.mp4"
    out_path = OUTPUT_DIR / out_name

    rendered_file = assembler.assemble(script_data, out_path, bundle=bundle)

    # Step 6: YouTube Upload (if not dry_run)
    video_id = None
    if not dry_run:
        tags = [topic_data["topic"].split()[0], "Shorts", "Facts", "Mystery", "Science", "Viral"]
        desc = (
            f"{script_data.get('title')}\n\n"
            f"{topic_data.get('headline', '')}\n\n"
            f"Pinned Question: {script_data.get('pinned_comment', '')}\n\n"
            f"#Shorts #Facts #Mystery #Trending"
        )
        video_id = upload_to_youtube(rendered_file, script_data.get("title"), desc, tags)

    meta = {
        "id": f"REELS_{int(time.time())}",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "project": "AutonomousViralReelsEngine",
        "topic": topic_data["topic"],
        "title": script_data.get("title", f"{topic_data['topic']} #Shorts"),
        "category": bundle["category"]["id"],
        "duration": "24-28 seconds",
        "file": str(rendered_file.resolve()),
        "engine": "MultiTierFailoverCascade",
        "pinned_comment": script_data.get("pinned_comment", ""),
        "youtube_video_id": video_id,
        "status": "PUBLISHED" if video_id else "RENDER_COMPLETE"
    }
    log_to_history_log(meta)

    # Record to Variety Store for persistent cooldown tracking
    variety_engine.record_production(
        topic=topic_data["topic"],
        title=script_data.get("title", f"{topic_data['topic']} #Shorts"),
        bundle=bundle,
        image_prompts=[s.get("prompt", "") for s in script_data.get("scenes", [])],
        video_id=video_id
    )

    return str(rendered_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Viral Reels Engine")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Render locally without uploading")
    parser.add_argument("--upload", action="store_true", default=False, help="Upload rendered video to YouTube")
    args = parser.parse_args()

    # In CI/GitHub Actions, default to upload if credentials are provided unless --dry-run is explicitly passed
    is_dry_run = args.dry_run
    if not is_dry_run and not args.upload and os.environ.get("GITHUB_ACTIONS") != "true":
        # Check if local credentials exist; if not, dry_run
        has_token = (BASE_DIR / "token.json").exists() or bool(os.environ.get("YOUTUBE_TOKEN_JSON")) or bool(os.environ.get("YOUTUBE_REFRESH_TOKEN"))
        if not has_token:
            is_dry_run = True

    run_autonomous_viral_reels_engine(dry_run=is_dry_run)
