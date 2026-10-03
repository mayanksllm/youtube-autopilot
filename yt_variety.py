"""
yt_variety.py - Comprehensive YouTube Automation Variety & Freshness Engine
===========================================================================
Ensures that EVERY generated video is unique across:
- Topic Category
- Hook Format
- Visual Style Reference DNA
- Camera Movement / Motion Style
- Caption Aesthetic
- Voice Personality
- Music Mood

Maintains cooldown enforcement:
  • Style: 15 videos
  • Hook: 4 videos
  • Camera: 3 videos
  • Caption: 4 videos
  • Music: 4 videos
  • Voice: 3 videos
  • Category: 3 videos

Provides is_fresh() to prevent duplicate or repetitive content using similarity checks.
Persists state to variety_store.json.
"""

import os
import sys
import json
import time
import random
import difflib
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

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


from autopilot_config import (
    VARIETY_STORE_PATH,
    COOLDOWNS,
    SIMILARITY_THRESHOLD,
    LOGS_DIR
)

# =============================================================================
# MASTER VARIETY MATRICES (Rich, Curated & Dynamic)
# =============================================================================

TOPIC_CATEGORIES = [
    {
        "id": "unexplained_history_enigmas",
        "name": "Unexplained Ancient History & Megalithic Enigmas",
        "keywords": ["ancient", "temple", "megalith", "monolith", "archaeology", "lost civilization"]
    },
    {
        "id": "bizarre_biology_anomalies",
        "name": "3D Bizarre Biology & Human Body Anomalies",
        "keywords": ["biology", "organism", "venom", "anatomy", "medical", "evolution", "mutation"]
    },
    {
        "id": "extreme_physics_space",
        "name": "Extreme Physics & Cosmic Terrors",
        "keywords": ["neutron star", "black hole", "quantum", "space", "magnetar", "relativity"]
    },
    {
        "id": "dark_psychology_behavior",
        "name": "Dark Psychology & Cognitive Paradoxes",
        "keywords": ["psychology", "experiment", "brain", "syndrome", "illusion", "delusion"]
    },
    {
        "id": "how_it_actually_works",
        "name": "Counter-Intuitive Engineering & Industrial Secrets",
        "keywords": ["engineering", "machine", "aviation", "ship", "infrastructure", "physics"]
    },
    {
        "id": "deep_ocean_abyss",
        "name": "Deep Ocean Monsters & Abyssal Anomalies",
        "keywords": ["mariana trench", "deep sea", "bioluminescence", "abyss", "creature", "submersible"]
    },
    {
        "id": "high_stakes_heists_scandals",
        "name": "Classified Scandals & High-Stakes Operations",
        "keywords": ["classified", "cold war", "espionage", "declassified", "subterfuge", "scandal"]
    }
]

HOOK_FORMATS = [
    {
        "id": "impossible_claim_in_media_res",
        "name": "Impossible Claim (Mid-Conflict)",
        "formula": "Drop viewer into an impossible physical paradox within the first 2 seconds. No greetings.",
        "example": "Sattar ton ka thos pathar hawa me bina kisi sahare ke latak raha hai..."
    },
    {
        "id": "negative_constraint",
        "name": "Negative Constraint & Warning",
        "formula": "Start with a high-stakes cautionary action that violates common intuition.",
        "example": "Kabhi bhi kisi drowning person ke gale ko mat pakadna, varna..."
    },
    {
        "id": "shocking_metric",
        "name": "Shocking Mathematical / Physical Metric",
        "formula": "Juxtapose an everyday scale with an unfathomable cosmological or micro measurement.",
        "example": "Sirf ek teaspoon neutron star ka vajan poore Mount Everest se zyada hai."
    },
    {
        "id": "direct_provocative_question",
        "name": "Direct Provocative Question",
        "formula": "Ask an abrupt counter-intuitive question that creates an immediate cognitive gap.",
        "example": "Kya ho agar duniya ke saare ped ek sath oxygen banana band kar dein?"
    },
    {
        "id": "classified_declassified_reveal",
        "name": "Classified Document / Forbidden Revelation",
        "formula": "Reveal an anomaly that scientists or governments tried to explain away.",
        "example": "1994 me ek hospital ER me aisi mareez aayi jisne poore staff ko behosh kar diya."
    }
]

VISUAL_STYLES = [
    {
        "id": "cinematic_35mm_portra",
        "name": "Cinematic 35mm Panavision Film",
        "prompt_dna": (
            "Raw candid masterpiece photograph, shot on Kodak Portra 400, 35mm anamorphic lens, "
            "Arri Alexa 65 sensor, tack sharp focus, natural film grain, moody chiaroscuro lighting, "
            "subtle volumetric dust particles, 8k vertical 9:16"
        ),
        "c_bg": (18, 12, 24), "c_fg": (255, 195, 80), "pattern": "cinematic_anamorphic"
    },
    {
        "id": "3d_anatomical_zackd",
        "name": "3D Anatomical Cross-Section (Zack D Style)",
        "prompt_dna": (
            "3D medical hyper-detailed cutaway anatomical cross-section, glowing biological nerve pathways, "
            "Zack D Films animation style, dramatic studio spotlight, octane 3D render, translucent layers, vertical 9:16"
        ),
        "c_bg": (45, 10, 20), "c_fg": (255, 60, 90), "pattern": "bio_matrix"
    },
    {
        "id": "investigative_noir_magnates",
        "name": "Investigative MagnatesMedia Dark Noir",
        "prompt_dna": (
            "Dark investigative documentary noir aesthetic, MagnatesMedia archival style, "
            "atmospheric spotlight cutting through haze, rich charcoal and sepia tones, dramatic rim lighting, 8k vertical 9:16"
        ),
        "c_bg": (20, 20, 20), "c_fg": (210, 180, 110), "pattern": "noir_split"
    },
    {
        "id": "cyberpunk_neon_matrix",
        "name": "Cyberpunk Neon Matrix",
        "prompt_dna": (
            "Cyberpunk futuristic concept art, neon cyan and electric magenta volumetric fog, "
            "rain-slicked reflective surfaces, Blade Runner 2049 aesthetic, intricate micro-circuitry, 8k vertical 9:16"
        ),
        "c_bg": (10, 15, 30), "c_fg": (0, 240, 255), "pattern": "cyber_grid"
    },
    {
        "id": "national_geographic_macro",
        "name": "National Geographic 8K Macro Wildlife",
        "prompt_dna": (
            "National Geographic wildlife macro photography, 8k telephoto lens, tack sharp organic textures, "
            "authentic natural golden-hour sunlight, rich vibrant earthy colors, deep depth of field, vertical 9:16"
        ),
        "c_bg": (15, 35, 15), "c_fg": (80, 220, 100), "pattern": "nature_burst"
    },
    {
        "id": "cosmic_james_webb_deep_space",
        "name": "Cosmic James Webb Deep Space",
        "prompt_dna": (
            "James Webb space telescope deep field astrophotography, glowing cosmic nebula vortex, "
            "stellar accretion disc, luminous starfield, vivid indigo and violet hues, cosmic majesty, vertical 9:16"
        ),
        "c_bg": (10, 5, 30), "c_fg": (160, 60, 255), "pattern": "cosmic_nebula"
    },
    {
        "id": "ancient_indian_monolith",
        "name": "Ancient Indian Monolithic Architecture",
        "prompt_dna": (
            "Ancient Indian monolithic temple architecture, golden hour sunbeams cutting through carved stone pillars, "
            "mystical divine atmosphere, weathered tactile stone textures, photorealistic cinematic lighting, vertical 9:16"
        ),
        "c_bg": (35, 20, 5), "c_fg": (255, 180, 30), "pattern": "golden_temple"
    },
    {
        "id": "graphic_novel_neo_noir",
        "name": "Stylized Graphic Novel Cel-Shading",
        "prompt_dna": (
            "Stylized graphic novel illustration, high-contrast ink and gouache wash, dramatic comic book angles, "
            "gritty cinematic cel shading, vibrant accents, dark moody shadows, vertical 9:16"
        ),
        "c_bg": (25, 10, 30), "c_fg": (255, 230, 40), "pattern": "pop_halftone"
    }
]

CAMERA_MOVES = [
    {
        "id": "ken_burns_slow_dolly_in",
        "name": "Ken Burns Slow Dolly-In",
        "description": "Gradual push toward the focal subject (scale 1.0 -> 1.15) with smootherstep inertia."
    },
    {
        "id": "parallax_subtle_pan_right",
        "name": "Parallax Subtle Pan Right",
        "description": "Horizontal camera drift to reveal background depth while keeping the subject framed."
    },
    {
        "id": "dramatic_pull_out_reveal",
        "name": "Dramatic Pull-Out Reveal",
        "description": "Slow zoom out (scale 1.18 -> 1.0) revealing scale and context of the anomaly."
    },
    {
        "id": "dynamic_dutch_push",
        "name": "Dynamic Dutch Tilt Push",
        "description": "Subtle camera angle tilt with micro push-in to heighten psychological tension."
    },
    {
        "id": "smooth_vertical_pedestal",
        "name": "Smooth Vertical Pedestal Rise",
        "description": "Upward camera pan from detail to macro vista."
    }
]

CAPTION_STYLES = [
    {
        "id": "electric_yellow_active_badge",
        "name": "Electric Yellow Active Word",
        "font_color": (255, 235, 30),
        "stroke_color": (0, 0, 0),
        "stroke_width": 5,
        "badge_bg": (0, 0, 0, 160)
    },
    {
        "id": "neon_cyan_glow",
        "name": "Neon Cyan High-Visibility",
        "font_color": (0, 245, 255),
        "stroke_color": (10, 10, 20),
        "stroke_width": 6,
        "badge_bg": (15, 20, 35, 175)
    },
    {
        "id": "pure_white_heavy_stroke",
        "name": "Pure White Heavy Stroke",
        "font_color": (255, 255, 255),
        "stroke_color": (0, 0, 0),
        "stroke_width": 7,
        "badge_bg": (0, 0, 0, 150)
    },
    {
        "id": "golden_amber_spotlight",
        "name": "Golden Amber Spotlight",
        "font_color": (255, 205, 50),
        "stroke_color": (20, 10, 5),
        "stroke_width": 6,
        "badge_bg": (30, 20, 10, 180)
    }
]

VOICE_PERSONALITIES = [
    {
        "id": "hi_madhur_dynamic",
        "voice_id": "hi-IN-MadhurNeural",
        "lang": "hi",
        "pitch": "+0Hz",
        "rate": "+10%",
        "tone": "Authoritative, fast-paced Indian investigative thriller"
    },
    {
        "id": "hi_swara_expressive",
        "voice_id": "hi-IN-SwaraNeural",
        "lang": "hi",
        "pitch": "+0Hz",
        "rate": "+8%",
        "tone": "Gripping, dramatic storytelling with emotional modulation"
    },
    {
        "id": "en_christopher_cinematic",
        "voice_id": "en-US-ChristopherNeural",
        "lang": "en",
        "pitch": "+0Hz",
        "rate": "+6%",
        "tone": "Deep cinematic documentary narrator"
    },
    {
        "id": "en_guy_inquisitive",
        "voice_id": "en-US-GuyNeural",
        "lang": "en",
        "pitch": "+0Hz",
        "rate": "+8%",
        "tone": "Fast-paced explainer, engaging and punchy"
    }
]

MUSIC_MOODS = [
    {
        "id": "dark_sub_bass_pulse",
        "name": "Dark Sub-Bass Pulse",
        "description": "Low drone with heart-like rhythmic sub-bass impact, building tension."
    },
    {
        "id": "suspense_ticking_clock",
        "name": "Suspense Ticking Clock",
        "description": "Precise mechanical tick layered over an atmospheric ambient synth."
    },
    {
        "id": "epic_orchestral_crescendo",
        "name": "Epic Orchestral Crescendo",
        "description": "Cinematic brass and strings swelling into a massive revelation."
    },
    {
        "id": "mysterious_cyber_synth",
        "name": "Mysterious Cyber Synth",
        "description": "Ethereal arpeggiated synth evoking technological enigmas."
    },
    {
        "id": "ancient_tribal_reverberation",
        "name": "Ancient Tribal Reverberation",
        "description": "Deep frame drums and echoing drone evoking lost civilizations."
    }
]


# =============================================================================
# PERSISTENT VARIETY STORE
# =============================================================================

class VarietyStore:
    """Manages persistent variety history, cooldown enforcement, and similarity tracking."""

    def __init__(self, store_path: Path = VARIETY_STORE_PATH):
        self.store_path = store_path
        self._ensure_store()

    def _ensure_store(self):
        if not self.store_path.exists():
            default_data = {
                "productions": [],
                "replied_comment_ids": {},
                "last_used": {
                    "visual_style": [],
                    "hook_format": [],
                    "camera_move": [],
                    "caption_style": [],
                    "music_mood": [],
                    "voice": [],
                    "category": []
                }
            }
            try:
                self.store_path.write_text(json.dumps(default_data, indent=2), encoding="utf-8")
            except Exception as e:
                print(f"[VarietyStore Warning] Could not init store: {e}")

    def load(self) -> Dict[str, Any]:
        try:
            if self.store_path.exists():
                return json.loads(self.store_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[VarietyStore Warning] Failed to load store, re-creating: {e}")
        return {
            "productions": [],
            "replied_comment_ids": {},
            "last_used": {
                "visual_style": [],
                "hook_format": [],
                "camera_move": [],
                "caption_style": [],
                "music_mood": [],
                "voice": [],
                "category": []
            }
        }

    def save(self, data: Dict[str, Any]):
        try:
            # Bound productions history to last 150 items to keep store lightweight
            if len(data.get("productions", [])) > 150:
                data["productions"] = data["productions"][-150:]
            tmp = self.store_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.store_path)
        except Exception as e:
            print(f"[VarietyStore Error] Could not save store: {e}")


# =============================================================================
# VARIETY ENGINE IMPLEMENTATION
# =============================================================================

class YouTubeVarietyEngine:
    """
    Centralized Variety & Anti-Repetition Engine.
    Coordinates cooldowns, similarity checks, and production parameters for every video.
    """

    def __init__(self, store_path: Path = VARIETY_STORE_PATH):
        self.store = VarietyStore(store_path)

    # -------------------------------------------------------------------------
    # 1. Similarity Check: is_fresh()
    # -------------------------------------------------------------------------
    def is_fresh(
        self,
        topic: str,
        title: str = "",
        prompt: str = "",
        threshold: float = SIMILARITY_THRESHOLD
    ) -> Tuple[bool, str]:
        """
        Evaluates whether a topic, title, or prompt is sufficiently fresh compared
        to the lookback history in the persistent store.
        Uses token-based Jaccard similarity and SequenceMatcher ratio.
        Returns: (True, "Fresh") or (False, reason)
        """
        data = self.store.load()
        productions = data.get("productions", [])
        if not productions:
            return True, "No prior productions recorded. 100% fresh."

        clean_topic = self._normalize_text(topic)
        clean_title = self._normalize_text(title)
        clean_prompt = self._normalize_text(prompt)

        for prod in reversed(productions[-40:]):
            past_topic = self._normalize_text(prod.get("topic", ""))
            past_title = self._normalize_text(prod.get("title", ""))

            # 1. Topic Similarity
            if clean_topic and past_topic:
                sim = self._calculate_similarity(clean_topic, past_topic)
                if sim >= threshold:
                    return False, f"Topic too similar to recent upload: '{prod.get('topic')}' (Similarity: {sim:.2f} >= {threshold:.2f})"

            # 2. Title Similarity
            if clean_title and past_title:
                sim_title = self._calculate_similarity(clean_title, past_title)
                if sim_title >= threshold:
                    return False, f"Title too similar to recent upload: '{prod.get('title')}' (Similarity: {sim_title:.2f} >= {threshold:.2f})"

            # 3. Prompt Substring / Repetition Check
            if clean_prompt:
                past_prompts = prod.get("image_prompts", [])
                for pp in past_prompts:
                    clean_pp = self._normalize_text(pp)
                    if clean_pp and self._calculate_similarity(clean_prompt, clean_pp) >= 0.85:
                        return False, f"Visual prompt matches prior scene prompt: '{pp[:50]}...'"

        return True, "Item is distinct and passed freshness threshold."

    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""
        # Lowercase, strip emojis, punctuation, and extra whitespace
        t = re.sub(r'[\U00010000-\U0010ffff]', '', text)
        t = re.sub(r'[^\w\s]', ' ', t)
        return " ".join(t.lower().split())

    @classmethod
    def _calculate_similarity(cls, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        # Blend SequenceMatcher with Jaccard token overlap
        seq_ratio = difflib.SequenceMatcher(None, a, b).ratio()
        tokens_a = set(a.split())
        tokens_b = set(b.split())
        if not tokens_a or not tokens_b:
            return seq_ratio
        jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
        return 0.6 * seq_ratio + 0.4 * jaccard

    # -------------------------------------------------------------------------
    # 2. Production Bundle Picker (Cooldown Enforced)
    # -------------------------------------------------------------------------
    def pick_production_bundle(self, lang_preference: str = "hi") -> Dict[str, Any]:
        """
        Picks a complete, guaranteed-diverse production bundle respecting all cooldowns.
        """
        data = self.store.load()
        last_used = data.setdefault("last_used", {})

        # 1. Topic Category (Cooldown: 3)
        category = self._pick_with_cooldown(
            items=TOPIC_CATEGORIES,
            key_history=last_used.setdefault("category", []),
            cooldown_count=COOLDOWNS.get("category", 3),
            id_key="id"
        )

        # 2. Hook Format (Cooldown: 4)
        hook = self._pick_with_cooldown(
            items=HOOK_FORMATS,
            key_history=last_used.setdefault("hook_format", []),
            cooldown_count=COOLDOWNS.get("hook_format", 4),
            id_key="id"
        )

        # 3. Visual Style Reference DNA (Cooldown: 15)
        style = self._pick_with_cooldown(
            items=VISUAL_STYLES,
            key_history=last_used.setdefault("visual_style", []),
            cooldown_count=COOLDOWNS.get("visual_style", 15),
            id_key="id"
        )

        # 4. Camera Move (Cooldown: 3)
        camera = self._pick_with_cooldown(
            items=CAMERA_MOVES,
            key_history=last_used.setdefault("camera_move", []),
            cooldown_count=COOLDOWNS.get("camera_move", 3),
            id_key="id"
        )

        # 5. Caption Style (Cooldown: 4)
        caption = self._pick_with_cooldown(
            items=CAPTION_STYLES,
            key_history=last_used.setdefault("caption_style", []),
            cooldown_count=COOLDOWNS.get("caption_style", 4),
            id_key="id"
        )

        # 6. Voice Model (Cooldown: 3, matching lang_preference)
        matching_voices = [v for v in VOICE_PERSONALITIES if v.get("lang") == lang_preference]
        if not matching_voices:
            matching_voices = VOICE_PERSONALITIES
        voice = self._pick_with_cooldown(
            items=matching_voices,
            key_history=last_used.setdefault("voice", []),
            cooldown_count=COOLDOWNS.get("voice", 3),
            id_key="id"
        )

        # 7. Music Mood (Cooldown: 4)
        music = self._pick_with_cooldown(
            items=MUSIC_MOODS,
            key_history=last_used.setdefault("music_mood", []),
            cooldown_count=COOLDOWNS.get("music_mood", 4),
            id_key="id"
        )

        bundle = {
            "category": category,
            "hook_format": hook,
            "visual_style": style,
            "camera_move": camera,
            "caption_style": caption,
            "voice": voice,
            "music_mood": music,
            "timestamp": time.time()
        }

        return bundle

    @staticmethod
    def _pick_with_cooldown(
        items: List[Dict[str, Any]],
        key_history: List[str],
        cooldown_count: int,
        id_key: str = "id"
    ) -> Dict[str, Any]:
        """Filters out recently used keys within the cooldown window, then selects one."""
        recent_window = key_history[-cooldown_count:] if cooldown_count > 0 else []
        candidates = [item for item in items if item[id_key] not in recent_window]
        if not candidates:
            # If all are cooling down, fall back to the least recently used
            candidates = items

        chosen = random.choice(candidates)
        return chosen

    # -------------------------------------------------------------------------
    # 3. Post-Upload Recording
    # -------------------------------------------------------------------------
    def record_production(
        self,
        topic: str,
        title: str,
        bundle: Dict[str, Any],
        image_prompts: Optional[List[str]] = None,
        video_id: Optional[str] = None
    ):
        """
        Persists a completed production run into the store and updates cooldown logs.
        """
        data = self.store.load()
        last_used = data.setdefault("last_used", {})

        # Update cooldown logs
        if "category" in bundle:
            last_used.setdefault("category", []).append(bundle["category"]["id"])
        if "hook_format" in bundle:
            last_used.setdefault("hook_format", []).append(bundle["hook_format"]["id"])
        if "visual_style" in bundle:
            last_used.setdefault("visual_style", []).append(bundle["visual_style"]["id"])
        if "camera_move" in bundle:
            last_used.setdefault("camera_move", []).append(bundle["camera_move"]["id"])
        if "caption_style" in bundle:
            last_used.setdefault("caption_style", []).append(bundle["caption_style"]["id"])
        if "voice" in bundle:
            last_used.setdefault("voice", []).append(bundle["voice"]["id"])
        if "music_mood" in bundle:
            last_used.setdefault("music_mood", []).append(bundle["music_mood"]["id"])

        record = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "video_id": video_id or "LOCAL_RENDER",
            "topic": topic,
            "title": title,
            "category": bundle.get("category", {}).get("id"),
            "hook_format": bundle.get("hook_format", {}).get("id"),
            "visual_style": bundle.get("visual_style", {}).get("id"),
            "camera_move": bundle.get("camera_move", {}).get("id"),
            "caption_style": bundle.get("caption_style", {}).get("id"),
            "voice": bundle.get("voice", {}).get("id"),
            "music_mood": bundle.get("music_mood", {}).get("id"),
            "image_prompts": image_prompts or []
        }

        data.setdefault("productions", []).append(record)
        self.store.save(data)
        print(f"📝 [Variety Store] Successfully recorded production: '{title[:45]}...'")

    # -------------------------------------------------------------------------
    # 4. Comment Reply ID Tracking (Prevent Duplicate Creator Replies)
    # -------------------------------------------------------------------------
    def is_comment_replied(self, comment_id: str) -> bool:
        data = self.store.load()
        return comment_id in data.get("replied_comment_ids", {})

    def record_replied_comment(self, comment_id: str, reply_text: str):
        data = self.store.load()
        replied_map = data.setdefault("replied_comment_ids", {})
        replied_map[comment_id] = {
            "replied_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reply_text": reply_text
        }
        self.store.save(data)


# Global singleton instance
variety_engine = YouTubeVarietyEngine()
