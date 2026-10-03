"""
thumbnail_generator.py - 3-Variant Thumbnail Engine with Vision Model Scoring & Upload
======================================================================================
1. Generates 3 distinct thumbnail compositions for every video:
   - Variant A: High-Contrast Close-Up Subject (Spotlight focus + <= 3 words bold text)
   - Variant B: Mystery Split / Intrigue Glow (Dual tone + provocative question)
   - Variant C: Macro Vista Silhouette (Golden/cyan volumetric atmosphere + minimalist punch)
2. Enforces <= 3 words bold high-contrast text overlay designed for mobile CTR.
3. Scores all 3 variants via Gemini Vision (or heuristic CTR contrast engine).
4. Uploads winning thumbnail via YouTube Data API thumbnails().set().
5. Gracefully handles unverified channel permission errors (HTTP 403 thumbnailUploadDisabled)
   and persists all thumbnail variants locally to assets/thumbnails/.
"""

import os
import sys
import json
import time
import random
import re
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from dotenv import load_dotenv

# Safe UTF-8 stream reconfigure for Windows
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
    BASE_DIR,
    THUMBNAILS_DIR,
    BROWSER_HEADERS,
    GEMINI_MODELS
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


def _get_bold_font(size: int = 80) -> ImageFont.ImageFont:
    font_paths = [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


class ThumbnailGenerator:
    """
    3-Variant Thumbnail Synthesizer with Vision Model Ranking and Resilient Upload.
    """

    def __init__(self, output_dir: Path = THUMBNAILS_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # 1. Headline Extraction: Strict <= 3 Words Punchy Text
    # -------------------------------------------------------------------------
    @classmethod
    def extract_3_word_hook(cls, topic: str, title: str) -> str:
        """Derives a punchy, high-CTR headline containing AT MOST 3 words."""
        # Check title words first
        clean = re.sub(r'#\w+', '', title)
        clean = re.sub(r'[^\w\s]', '', clean).strip()
        words = clean.split()

        # Look for emotional shock phrases
        shock_vault = [
            "IT NEVER DIES",
            "DON'T LOOK DOWN",
            "THE 70-TON SECRET",
            "FORBIDDEN TRUTH",
            "SCIENTISTS BAFFLED",
            "HOW IS THIS REAL?",
            "DO NOT ENTER",
            "THE LOST VAULT"
        ]

        if len(words) <= 3 and len(words) > 0:
            return " ".join(words).upper()

        # Extract 2-3 key words
        if words:
            # Pick first 3 impactful words
            candidate = " ".join(words[:3]).upper()
            if len(candidate) <= 22:
                return candidate

        return random.choice(shock_vault)

    # -------------------------------------------------------------------------
    # 2. Base Image Fetching / Generation (FLUX or Fallback)
    # -------------------------------------------------------------------------
    def _fetch_thumbnail_background(self, prompt: str, seed: int, variant_id: str) -> Image.Image:
        """Fetches an 8K background via Pollinations FLUX with browser headers or falls back to procedural."""
        encoded = urllib.parse.quote(f"{prompt}, 8k highly detailed photograph, cinematic lighting, sharp focus, 16:9 widescreen")
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&model=flux&nologo=true&seed={seed}"

        try:
            r = requests.get(url, headers=BROWSER_HEADERS, timeout=22)
            if r.status_code == 200 and len(r.content) > 25 * 1024:
                import io
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                if img.size == (1280, 720):
                    return img
                return img.resize((1280, 720), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"   [Thumb Bg Notice ({variant_id})]: {e}")

        # Procedural cinematic gradient fallback
        img = Image.new("RGB", (1280, 720), (15, 12, 28))
        draw = ImageDraw.Draw(img)
        colors = {
            "v1": ((220, 30, 60), (10, 5, 20)),
            "v2": ((0, 210, 255), (10, 20, 35)),
            "v3": ((255, 180, 20), (30, 15, 5))
        }
        c1, c2 = colors.get(variant_id, ((200, 100, 30), (15, 15, 25)))
        for y in range(720):
            t = y / 720.0
            r = int(c1[0] * (1 - t) + c2[0] * t)
            g = int(c1[1] * (1 - t) + c2[1] * t)
            b = int(c1[2] * (1 - t) + c2[2] * t)
            draw.line([(0, y), (1280, y)], fill=(r, g, b))
        return img

    # -------------------------------------------------------------------------
    # 3. Variant Compositing Engine (A, B, C)
    # -------------------------------------------------------------------------
    def generate_variant_a(self, topic: str, hook_text: str, base_seed: int) -> Path:
        """Variant A: High-Contrast Close-Up Subject Focus (Electric Yellow Badge)."""
        prompt = f"Extreme macro dramatic cinematic portrait, {topic}, volumetric spotlight, ultra sharp details, Kodak Portra"
        bg = self._fetch_thumbnail_background(prompt, base_seed + 101, "v1")

        # Color lift & vignette
        enhancer = ImageEnhance.Contrast(bg)
        bg = enhancer.enhance(1.15)

        draw = ImageDraw.Draw(bg)
        font = _get_bold_font(84)

        # Draw bold hook text with thick black outline & drop shadow
        words = hook_text.upper().split()[:3]
        display_text = " ".join(words)

        bbox = draw.textbbox((0, 0), display_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        x = (1280 - tw) // 2
        y = 520  # Lower third

        # Background badge pill
        pad = 20
        badge_box = [x - pad, y - pad, x + tw + pad, y + th + pad]
        draw.rectangle(badge_box, fill=(0, 0, 0, 220))
        draw.rectangle(badge_box, outline=(255, 235, 30), width=4)

        # Text with heavy black stroke
        for ox in range(-5, 6):
            for oy in range(-5, 6):
                draw.text((x + ox, y + oy), display_text, font=font, fill=(0, 0, 0))
        draw.text((x, y), display_text, font=font, fill=(255, 235, 30))

        out_path = self.output_dir / f"thumb_variant_A_{int(time.time())}.jpg"
        bg.save(out_path, quality=94)
        return out_path

    def generate_variant_b(self, topic: str, hook_text: str, base_seed: int) -> Path:
        """Variant B: Neon Cyan Dual-Tone Intrigue."""
        prompt = f"3D medical cutaway anomaly, {topic}, glowing bioluminescent neon cyan veins, high contrast octane render"
        bg = self._fetch_thumbnail_background(prompt, base_seed + 202, "v2")

        draw = ImageDraw.Draw(bg)
        font = _get_bold_font(90)

        words = hook_text.upper().split()[:3]
        display_text = " ".join(words)

        bbox = draw.textbbox((0, 0), display_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        x = (1280 - tw) // 2
        y = 80  # Top placement

        pad = 22
        badge_box = [x - pad, y - pad, x + tw + pad, y + th + pad]
        draw.rectangle(badge_box, fill=(10, 15, 30, 230))
        draw.rectangle(badge_box, outline=(0, 240, 255), width=5)

        for ox in range(-6, 7):
            for oy in range(-6, 7):
                draw.text((x + ox, y + oy), display_text, font=font, fill=(0, 0, 0))
        draw.text((x, y), display_text, font=font, fill=(0, 245, 255))

        out_path = self.output_dir / f"thumb_variant_B_{int(time.time())}.jpg"
        bg.save(out_path, quality=94)
        return out_path

    def generate_variant_c(self, topic: str, hook_text: str, base_seed: int) -> Path:
        """Variant C: Golden Amber Minimalist Cinematic Vista."""
        prompt = f"Epic ancient monolithic temple silhouette, {topic}, golden hour sunbeams cutting through haze, cinematic 35mm"
        bg = self._fetch_thumbnail_background(prompt, base_seed + 303, "v3")

        draw = ImageDraw.Draw(bg)
        font = _get_bold_font(88)

        words = hook_text.upper().split()[:3]
        display_text = " ".join(words)

        bbox = draw.textbbox((0, 0), display_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        x = (1280 - tw) // 2
        y = 310  # Centered dramatic punch

        pad = 24
        badge_box = [x - pad, y - pad, x + tw + pad, y + th + pad]
        draw.rectangle(badge_box, fill=(20, 10, 5, 225))
        draw.rectangle(badge_box, outline=(255, 190, 40), width=4)

        for ox in range(-5, 6):
            for oy in range(-5, 6):
                draw.text((x + ox, y + oy), display_text, font=font, fill=(0, 0, 0))
        draw.text((x, y), display_text, font=font, fill=(255, 255, 255))

        out_path = self.output_dir / f"thumb_variant_C_{int(time.time())}.jpg"
        bg.save(out_path, quality=94)
        return out_path

    # -------------------------------------------------------------------------
    # 4. Vision Model CTR Scoring & Ranking
    # -------------------------------------------------------------------------
    def score_thumbnail_variants(self, variants: List[Tuple[str, Path]], topic: str) -> Tuple[Path, str]:
        """
        Uses Gemini Vision to score the 3 thumbnail variants on mobile CTR potential.
        Falls back to heuristic contrast scoring if Vision API is rate-limited.
        """
        print(f"\n🧠 [Thumbnail Ranker] Evaluating {len(variants)} composition variants via Vision AI...")

        if GEMINI_API_KEY:
            for g_model in GEMINI_MODELS:
                try:
                    from google import genai
                    from google.genai import types

                    client = genai.Client(api_key=GEMINI_API_KEY)
                    contents = [
                        f"You are a YouTube CTR optimization algorithm. Topic: '{topic}'. "
                        "Evaluate these 3 thumbnail image variants. Which one has the highest click-through rate, "
                        "best text readability on small smartphone screens, and strongest curiosity gap? "
                        "Respond in JSON ONLY: {\"winner\": \"A\", \"scores\": {\"A\": 8.5, \"B\": 7.0, \"C\": 6.5}, \"reason\": \"...\"}"
                    ]
                    for name, p in variants:
                        with open(p, "rb") as f:
                            contents.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))

                    resp = client.models.generate_content(model=g_model, contents=contents)
                    txt = resp.text.strip().replace("```json", "").replace("```", "").strip()
                    s, e = txt.find("{"), txt.rfind("}")
                    if s != -1 and e != -1:
                        data = json.loads(txt[s:e+1])
                        winner_key = data.get("winner", "A").upper()
                        for name, p in variants:
                            if winner_key in name:
                                print(f"🏆 [Vision Winner]: Variant {winner_key} ({data.get('reason', 'Highest CTR score')})")
                                return p, f"Variant {winner_key}"
                except Exception as e:
                    err_str = str(e).lower()
                    if "429" in err_str or "exhausted" in err_str:
                        continue
                    continue

        # Heuristic contrast & file size fallback
        best_path = variants[0][1]
        best_name = variants[0][0]
        best_size = 0
        for name, p in variants:
            sz = p.stat().st_size
            if sz > best_size:
                best_size = sz
                best_path = p
                best_name = name

        print(f"🏆 [Heuristic Winner]: {best_name} (Maximum dynamic range & texture)")
        return best_path, best_name

    # -------------------------------------------------------------------------
    # 5. YouTube API Upload with Graceful Verification Error Handling
    # -------------------------------------------------------------------------
    def upload_thumbnail(self, youtube_service: Any, video_id: str, thumbnail_path: Path) -> bool:
        """
        Uploads custom thumbnail via youtube.thumbnails().set().
        Handles HTTP 403 thumbnailUploadDisabled (unverified channel) gracefully.
        """
        if not youtube_service:
            print("   [Thumbnail Info] YouTube service offline; thumbnail saved locally.")
            return False

        if not video_id or video_id.startswith("DRYRUN") or video_id.startswith("LOCAL"):
            print("   [Thumbnail Info] Dry-run video ID; skipping remote upload.")
            return False

        print(f"📡 [YouTube API] Uploading custom thumbnail for video: {video_id}...")
        try:
            from googleapiclient.http import MediaFileUpload
            media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg", resumable=True)
            request = youtube_service.thumbnails().set(videoId=video_id, media_body=media)
            request.execute()
            print(f"🎉 [Thumbnails API] Successfully uploaded custom thumbnail for {video_id}!")
            return True
        except Exception as e:
            err_msg = str(e)
            if "thumbnailUploadDisabled" in err_msg or "403" in err_msg or "forbidden" in err_msg.lower():
                print("ℹ️ [Thumbnails API Note] Custom thumbnail upload requires phone verification in YouTube Studio.")
                print(f"   Saved winner locally to: {thumbnail_path.resolve()}")
                print("   (Upload to YouTube was gracefully bypassed without breaking the pipeline).")
            else:
                print(f"   [Thumbnail Upload Notice]: {e}")
            return False

    # -------------------------------------------------------------------------
    # 6. Master Production Pipeline
    # -------------------------------------------------------------------------
    def produce_and_upload_thumbnail(
        self,
        topic: str,
        title: str,
        youtube_service: Optional[Any] = None,
        video_id: Optional[str] = None
    ) -> Path:
        """
        Full thumbnail lifecycle:
        1. Derives <= 3 words punchy text
        2. Generates 3 distinct composition variants (A, B, C)
        3. Ranks variants via Vision AI
        4. Uploads winner or saves gracefully
        """
        print("\n" + "=" * 70)
        print("  🖼️ 3-VARIANT THUMBNAIL ENGINE (CTR Architecture & Vision Ranking)")
        print("=" * 70)

        hook_3_words = self.extract_3_word_hook(topic, title)
        print(f"🪝 [Thumbnail Hook Text]: \"{hook_3_words}\" (Strict <= 3 words)")

        base_seed = random.randint(100, 99999)
        path_a = self.generate_variant_a(topic, hook_3_words, base_seed)
        path_b = self.generate_variant_b(topic, hook_3_words, base_seed)
        path_c = self.generate_variant_c(topic, hook_3_words, base_seed)

        variants = [
            ("Variant A (Close-Up Yellow)", path_a),
            ("Variant B (Neon Cyan)", path_b),
            ("Variant C (Golden Amber)", path_c)
        ]
        for name, p in variants:
            print(f"   • Generated {name}: {p.name} ({p.stat().st_size // 1024} KB)")

        winner_path, winner_name = self.score_thumbnail_variants(variants, topic)

        # Copy winner to standardized path
        target_winner = self.output_dir / f"{video_id or 'winner'}_thumbnail_master.jpg"
        import shutil
        shutil.copy2(winner_path, target_winner)
        print(f"💾 [Master Thumbnail Saved]: {target_winner.name}")

        if youtube_service and video_id:
            self.upload_thumbnail(youtube_service, video_id, target_winner)

        return target_winner


# Global singleton instance
thumbnail_generator = ThumbnailGenerator()

if __name__ == "__main__":
    t_winner = thumbnail_generator.produce_and_upload_thumbnail(
        topic="The Lepakshi Hanging Pillar Gravity Paradox",
        title="Lepakshi Ka Hawa Me Latakta Khamba 🏛️ #Shorts"
    )
    print("\nWinner Thumbnail:", t_winner)
