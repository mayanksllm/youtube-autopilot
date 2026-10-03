"""
script_critic.py - Two-Pass Scriptwriting & Adversarial Critic Quality Engine
=============================================================================
Pass 1 (Writer Pass): Drafts high-retention viral script based on topic, hook format, and style DNA.
Pass 2 (Critic Pass): Evaluates Hook (1-10), Pacing (1-10), and Retention (1-10).
Auto-Rewrite: If overall score is below CRITIC_MIN_SCORE (7.0), rewrites automatically.
"""

import os
import sys
import json
import time
import random
import re
from typing import Dict, Any, Tuple, Optional, List

import requests
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
    CRITIC_MIN_SCORE,
    MAX_SCRIPT_REVISIONS
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


def _call_llm_json(prompt: str, system_prompt: str = "Output strict JSON only.") -> Optional[Dict[str, Any]]:
    """Resilient JSON LLM caller with backoff retry on 429 and multi-provider failover."""
    # Tier 1: Gemini Flash Models with 429 fast skip
    if GEMINI_API_KEY:
        for g_model in GEMINI_MODELS:
            try:
                from google import genai
                client = genai.Client(api_key=GEMINI_API_KEY)
                resp = client.models.generate_content(
                    model=g_model,
                    contents=f"{system_prompt}\n\n{prompt}"
                )
                txt = resp.text.strip().replace("```json", "").replace("```", "").strip()
                s, e = txt.find("{"), txt.rfind("}")
                if s != -1 and e != -1:
                    return json.loads(txt[s:e+1])
            except Exception as ex:
                err_str = str(ex).lower()
                if "429" in err_str or "exhausted" in err_str:
                    continue  # Daily quota exhausted, try next model immediately
                continue

    # Tier 2: Groq Cloud Llama 3.3
    if GROQ_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            }
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10)
            if r.status_code == 200:
                txt = r.json()["choices"][0]["message"]["content"]
                s, e = txt.find("{"), txt.rfind("}")
                if s != -1 and e != -1:
                    return json.loads(txt[s:e+1])
        except Exception:
            pass

    # Tier 3: Keyless Pollinations Text AI
    try:
        p_payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "jsonMode": True,
            "seed": random.randint(100, 99999)
        }
        r = requests.post("https://text.pollinations.ai/", json=p_payload, timeout=5)
        if r.status_code == 200:
            txt = r.text.strip().replace("```json", "").replace("```", "").strip()
            s, e = txt.find("{"), txt.rfind("}")
            if s != -1 and e != -1:
                return json.loads(txt[s:e+1])
    except Exception:
        pass

    return None


class ScriptCriticEngine:
    """
    Two-pass Writer + Adversarial Critic engine.
    Guarantees script retention, hook power, and pacing before video rendering.
    """

    @classmethod
    def evaluate_script(cls, script_data: Dict[str, Any], topic_name: str) -> Dict[str, Any]:
        """
        Pass 2: Adversarial Critic evaluation.
        Scores Hook, Pacing, and Retention from 1 to 10.
        """
        title = script_data.get("title", "")
        voiceover = script_data.get("voiceover_clean", "")
        pinned = script_data.get("pinned_comment", "")
        word_count = len(voiceover.split())

        critic_prompt = (
            "You are a ruthless YouTube Shorts script editor and retention algorithm expert.\n"
            f"Topic: {topic_name}\n"
            f"Draft Title: {title}\n"
            f"Voiceover Text ({word_count} words): \"{voiceover}\"\n"
            f"Pinned Engagement Question: \"{pinned}\"\n\n"
            "Score this script strictly on three metrics (integer or float 1.0 to 10.0):\n"
            "1. hook_score: Does sentence 1 drop the viewer directly into high-stakes conflict/paradox with zero fluff or greeting? (1=boring 'Did you know', 10=impossible mind-melt)\n"
            "2. pacing_score: Is the word count strictly 55-75 words? Does each sentence escalate tension without filler words? (1=dragging/repetitive, 10=razor sharp rhythm)\n"
            "3. retention_score: Does the voiceover end on a circular loop back to the opening word? Does it demand immediate re-watching? (1=flat ending, 10=seamless infinite loop)\n\n"
            "Respond in STRICT JSON ONLY:\n"
            "{\n"
            "  \"hook_score\": 8.5,\n"
            "  \"pacing_score\": 7.0,\n"
            "  \"retention_score\": 9.0,\n"
            "  \"critique\": \"Short diagnostic summary of what worked and what was weak\",\n"
            "  \"recommended_improvements\": \"Specific sentence-level fix instructions\"\n"
            "}"
        )

        critique_result = _call_llm_json(critic_prompt, "You are a ruthless script editor. Output strict JSON only.")
        if not critique_result:
            # Fallback heuristic evaluation
            h_score = 7.5 if not any(w in voiceover.lower() for w in ["hello", "namaste", "did you know", "aaj hum"]) else 5.0
            p_score = 8.5 if 50 <= word_count <= 80 else 6.0
            r_score = 7.5
            critique_result = {
                "hook_score": h_score,
                "pacing_score": p_score,
                "retention_score": r_score,
                "critique": f"Heuristic evaluation: {word_count} words.",
                "recommended_improvements": "Keep sentence 1 under 12 words."
            }

        # Calculate weighted score (Hook: 40%, Pacing: 30%, Retention: 30%)
        h = float(critique_result.get("hook_score", 7.0))
        p = float(critique_result.get("pacing_score", 7.0))
        r = float(critique_result.get("retention_score", 7.0))
        overall = round(h * 0.40 + p * 0.30 + r * 0.30, 2)

        critique_result["overall_score"] = overall
        return critique_result

    @classmethod
    def rewrite_script(
        cls,
        original_script: Dict[str, Any],
        topic_name: str,
        critique: Dict[str, Any],
        bundle: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Targeted Rewrite Pass addressing the critic's specific feedback.
        """
        chosen_style = bundle.get("visual_style", {}) if bundle else {}
        hook_format = bundle.get("hook_format", {}) if bundle else {}

        rewrite_prompt = (
            "You are a master viral scriptwriter. Your previous draft scored below retention standards.\n"
            f"Topic: {topic_name}\n"
            f"Previous Draft Voiceover: \"{original_script.get('voiceover_clean')}\"\n"
            f"Critic Score: {critique.get('overall_score')}/10\n"
            f"Critic Diagnosis: {critique.get('critique')}\n"
            f"Critic Required Improvements: {critique.get('recommended_improvements')}\n"
            f"Visual Style: {chosen_style.get('name', 'Cinematic')}\n"
            f"Hook Formula: {hook_format.get('name', 'Impossible Claim')} -> {hook_format.get('formula', '')}\n\n"
            "RULES FOR REWRITE:\n"
            "- 'voiceover_clean': Exactly 60-75 words in pure spoken conversational Hindi/Hinglish.\n"
            "- First 2 seconds MUST drop viewer into the conflict. Zero greetings ('Namaste', 'Hello', 'Kya aap jaante hain' are strictly forbidden).\n"
            "- Final sentence MUST loop seamlessly back to the first word.\n"
            "- Exactly 6 scenes with cinematic prompts.\n\n"
            "Respond in STRICT JSON ONLY matching this schema:\n"
            "{\n"
            "  \"title\": \"Shocking headline with emojis and #Shorts\",\n"
            "  \"voiceover_clean\": \"Spoken Hindi speech only...\",\n"
            "  \"pinned_comment\": \"Engaging question in Hindi/English\",\n"
            "  \"scenes\": [\n"
            "    {\"id\": 1, \"prompt\": \"...\"},\n"
            "    {\"id\": 2, \"prompt\": \"...\"},\n"
            "    {\"id\": 3, \"prompt\": \"...\"},\n"
            "    {\"id\": 4, \"prompt\": \"...\"},\n"
            "    {\"id\": 5, \"prompt\": \"...\"},\n"
            "    {\"id\": 6, \"prompt\": \"...\"}\n"
            "  ]\n"
            "}"
        )

        revised = _call_llm_json(rewrite_prompt, "You are a master viral scriptwriter. Output strict JSON only.")
        if revised and revised.get("voiceover_clean") and len(revised.get("scenes", [])) >= 4:
            return revised
        return original_script

    @classmethod
    def run_writer_critic_pipeline(
        cls,
        draft_script: Dict[str, Any],
        topic_name: str,
        bundle: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Executes the two-pass engine:
        1. Critic evaluates the draft.
        2. If overall_score < CRITIC_MIN_SCORE (7.0), rewrites up to MAX_SCRIPT_REVISIONS.
        3. Returns (final_script, final_critique).
        """
        print("\n" + "=" * 70)
        print("  🧠 TWO-PASS SCRIPT QUALITY ENGINE (Writer Pass + Adversarial Critic)")
        print(f"  Target Threshold: {CRITIC_MIN_SCORE}/10 | Max Revisions: {MAX_SCRIPT_REVISIONS}")
        print("=" * 70)

        current_script = draft_script
        current_critique = cls.evaluate_script(current_script, topic_name)

        print(f"📊 [Critic Pass 1 Scores]:")
        print(f"   • Hook Power:     {current_critique.get('hook_score')}/10")
        print(f"   • Pacing & Flow:  {current_critique.get('pacing_score')}/10")
        print(f"   • Retention Loop: {current_critique.get('retention_score')}/10")
        print(f"   • OVERALL SCORE:  {current_critique.get('overall_score')}/10")
        print(f"   • Critique:       {current_critique.get('critique')}")

        revision = 0
        while current_critique.get("overall_score", 0) < CRITIC_MIN_SCORE and revision < MAX_SCRIPT_REVISIONS:
            revision += 1
            print(f"\n⚠️ [Script Critic] Score {current_critique.get('overall_score')} < {CRITIC_MIN_SCORE}. Initiating Rewrite Pass #{revision}...")
            revised_script = cls.rewrite_script(current_script, topic_name, current_critique, bundle)
            if not revised_script or revised_script.get("voiceover_clean") == current_script.get("voiceover_clean"):
                print("   [Script Critic] Rewrite unavailable from current providers; keeping best draft.")
                break
            new_critique = cls.evaluate_script(revised_script, topic_name)

            print(f"📊 [Critic Pass #{revision+1} Scores]:")
            print(f"   • Hook Power:     {new_critique.get('hook_score')}/10")
            print(f"   • Pacing & Flow:  {new_critique.get('pacing_score')}/10")
            print(f"   • Retention Loop: {new_critique.get('retention_score')}/10")
            print(f"   • OVERALL SCORE:  {new_critique.get('overall_score')}/10")

            if new_critique.get("overall_score", 0) >= current_critique.get("overall_score", 0):
                current_script = revised_script
                current_critique = new_critique

            if current_critique.get("overall_score", 0) >= CRITIC_MIN_SCORE:
                print(f"✅ [Script Critic] Standard satisfied ({current_critique.get('overall_score')} >= {CRITIC_MIN_SCORE})!")
                break

        current_script["critic_evaluation"] = current_critique
        return current_script, current_critique


# Global singleton instance
script_critic = ScriptCriticEngine()

if __name__ == "__main__":
    sample_script = {
        "title": "Shocking Ocean Abomination #Shorts",
        "voiceover_clean": "Sperm whale ke pet me jab giant squid ka sharp beak chubh jata hai, toh whale ek deadly infection se ladne lagti hai. Par yahi infection banata hai duniya ka sabse anokha aur keemti perfume jise ambergris kehte hain. Lakhon rupaye per gram bikne wala ye pathar samandar ke andhere abyss me tairta rehta hai.",
        "pinned_comment": "Kya aapko ambergris ki ye sachai pehle pata thi? Comments me batayein! 👇 #shorts",
        "scenes": [{"id": 1, "prompt": "Scene 1"}, {"id": 2, "prompt": "Scene 2"}, {"id": 3, "prompt": "Scene 3"}, {"id": 4, "prompt": "Scene 4"}]
    }
    final_s, final_c = script_critic.run_writer_critic_pipeline(sample_script, "The Terrifying Origin of Deep Ocean Musk")
    print("\nFinal Script Title:", final_s.get("title"))
    print("Final Score:", final_c.get("overall_score"))
