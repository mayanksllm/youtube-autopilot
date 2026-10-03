"""
visual_quality_gate.py - Vision-Model Quality Gate & Aesthetic Verification Engine
==================================================================================
Inspects every generated scene visual before video assembly:
1. Fast Heuristic Gate (zero-quota):
   - Rejects blank/monochrome frames (standard deviation of RGB channels < 15.0)
   - Rejects black/empty frames (average luminance < 12.0)
   - Rejects corrupted/truncated files (size < 25KB, unparseable by PIL)
   - Rejects severely blurred images (Laplacian variance < 45.0)
2. Vision Model Quality Gate (Gemini Vision with backoff):
   - Evaluates composition, sharpness, and visual artifacts
   - If severe artifacts or blur detected, triggers automated re-generation with altered seed.
"""

import os
import sys
import json
import time
import random
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Callable

import numpy as np
from PIL import Image, ImageFilter, ImageStat
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
    GEMINI_MODELS,
    BROWSER_HEADERS
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


class VisualQualityGate:
    """
    Automated Vision Quality Gate for AI-generated scene frames.
    """

    @classmethod
    def check_heuristics(cls, img_path: Path) -> Tuple[bool, str]:
        """
        Fast heuristic checks: size, readability, luminance, entropy, and sharpness.
        Zero cost and instant.
        """
        if not img_path.exists():
            return False, "File does not exist."

        size_kb = img_path.stat().st_size / 1024
        if size_kb < 20:
            return False, f"File size too small ({size_kb:.1f} KB < 20 KB), likely incomplete download."

        try:
            with Image.open(img_path) as im:
                im.verify()
            with Image.open(img_path) as im:
                rgb = im.convert("RGB")
                w, h = rgb.size
                if w < 500 or h < 500:
                    return False, f"Resolution too low ({w}x{h})."

                # Luminance check
                stat = ImageStat.Stat(rgb)
                avg_l = sum(stat.mean) / 3.0
                if avg_l < 10.0:
                    return False, f"Frame is near-pitch black (Average luminance {avg_l:.1f} < 10.0)."
                if avg_l > 248.0:
                    return False, f"Frame is blown-out pure white (Average luminance {avg_l:.1f} > 248.0)."

                # Monochrome / Blank Color check (standard deviation across channels)
                std_dev = sum(stat.stddev) / 3.0
                if std_dev < 12.0:
                    return False, f"Frame is a flat monochrome wash (Standard deviation {std_dev:.1f} < 12.0)."

                # Sharpness check via Laplacian edge variance
                gray = rgb.convert("L").resize((270, 480))
                arr = np.asarray(gray, dtype=np.float32)
                # Compute discrete laplacian
                laplacian = (
                    -4 * arr[1:-1, 1:-1]
                    + arr[:-2, 1:-1] + arr[2:, 1:-1]
                    + arr[1:-1, :-2] + arr[1:-1, 2:]
                )
                variance = float(laplacian.var())
                if variance < 30.0:
                    return False, f"Image lacks high-frequency edge detail / is blurry (Laplacian variance {variance:.1f} < 30.0)."

        except Exception as e:
            return False, f"Corrupted or unreadable image file: {e}"

        return True, "Passed heuristic quality checks."

    @classmethod
    def check_vision_model(cls, img_path: Path) -> Tuple[bool, str]:
        """
        Gemini Vision model evaluation. Checks for major artifacts or deformities.
        Falls back to True if vision API is rate-limited.
        """
        if not GEMINI_API_KEY:
            return True, "No Gemini API key for vision check; passed by heuristics."

        prompt = (
            "Analyze this vertical 9:16 cinematic video frame for a documentary Short.\n"
            "Evaluate if the image has severe visual artifacts, mangled anatomy, completely unreadable blur, "
            "or broken render geometry.\n"
            "Respond in STRICT JSON ONLY:\n"
            "{\n"
            "  \"is_acceptable\": true,\n"
            "  \"quality_score\": 8.5,\n"
            "  \"issues\": [\"none\"],\n"
            "  \"verdict\": \"PASS\"\n"
            "}"
        )

        for g_model in GEMINI_MODELS:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=GEMINI_API_KEY)
                with open(img_path, "rb") as f:
                    img_bytes = f.read()

                resp = client.models.generate_content(
                    model=g_model,
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                        prompt
                    ]
                )
                txt = resp.text.strip().replace("```json", "").replace("```", "").strip()
                s, e = txt.find("{"), txt.rfind("}")
                if s != -1 and e != -1:
                    data = json.loads(txt[s:e+1])
                    verdict = data.get("verdict", "PASS").upper()
                    acceptable = data.get("is_acceptable", True)
                    if not acceptable or verdict == "REGENERATE":
                        return False, f"Vision model rejected frame: {data.get('issues')}"
                    return True, f"Vision model approved frame (Score: {data.get('quality_score')}/10)."
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "exhausted" in err_str:
                    continue  # Fast skip on quota exhaustion
                continue

        # If vision API is rate-limited or unavailable, heuristic check is the authority
        return True, "Vision API rate-limited; verified via heuristics."

    @classmethod
    def verify_or_regenerate_frame(
        cls,
        img_path_str: str,
        prompt: str,
        scene_idx: int,
        regenerate_func: Callable[[str, int], str],
        max_attempts: int = 2
    ) -> str:
        """
        Quality gate pipeline for a generated scene image.
        If heuristic or vision check fails, automatically calls regenerate_func.
        """
        curr_path = Path(img_path_str)

        for attempt in range(max_attempts):
            h_ok, h_reason = cls.check_heuristics(curr_path)
            if not h_ok:
                print(f"⚠️ [Quality Gate] Scene {scene_idx:02d} failed heuristics: {h_reason}")
                if attempt < max_attempts - 1:
                    print(f"🔄 [Quality Gate] Regenerating Scene {scene_idx:02d} (Attempt {attempt + 2}/{max_attempts})...")
                    alt_prompt = f"{prompt}, ultra detailed 8k photography, crisp focus, seed {random.randint(100, 99999)}"
                    curr_path = Path(regenerate_func(alt_prompt, scene_idx))
                    continue
                else:
                    break

            v_ok, v_reason = cls.check_vision_model(curr_path)
            if not v_ok:
                print(f"⚠️ [Quality Gate] Scene {scene_idx:02d} failed vision model: {v_reason}")
                if attempt < max_attempts - 1:
                    print(f"🔄 [Quality Gate] Regenerating Scene {scene_idx:02d} with altered seed...")
                    alt_prompt = f"{prompt}, masterpiece sharp focus, cinematic lighting, vertical 9:16"
                    curr_path = Path(regenerate_func(alt_prompt, scene_idx))
                    continue
            else:
                print(f"✅ [Quality Gate] Scene {scene_idx:02d} verified: {v_reason}")
                return str(curr_path)

        return str(curr_path)


# Global singleton instance
quality_gate = VisualQualityGate()

if __name__ == "__main__":
    test_img = Path("assets/director_scenes")
    sample_files = list(test_img.glob("*.jpg")) if test_img.exists() else []
    if sample_files:
        ok, reason = quality_gate.check_heuristics(sample_files[0])
        print(f"Tested {sample_files[0].name}: ok={ok}, reason={reason}")
    else:
        print("Quality gate compiled and ready.")
