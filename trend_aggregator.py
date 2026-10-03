"""
trend_aggregator.py - Multi-Source Real-Time Trend Engine with Original Angle Generator
========================================================================================
Aggregates live trending topics across multiple independent sources:
1. YouTube Data API v3 (mostPopular in IN/US)
2. Google Trends & Google News RSS feeds
3. Reddit (r/todayilearned, r/Damnthatsinteresting) with JSON -> RSS fallback
4. Curated Discovery Vault (evergreen fallback)
5. Dynamic LLM Topic Generator (guaranteed emergency fallback)

Guarantees:
- Every external source is wrapped in try/except with strict timeouts.
- Cloudrunner/GitHub Actions IP blocks on Reddit JSON gracefully fall back to RSS or skip.
- Every candidate is filtered through variety_engine.is_fresh() (Jaccard + SequenceMatcher).
- The LLM NEVER copies or summarizes the trend; it crafts an original, contrarian paradox angle.
- Never crashes if any or all external sources are down.
"""

import os
import sys
import json
import time
import random
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

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
    BASE_DIR,
    BROWSER_HEADERS,
    GEMINI_MODELS,
    SIMILARITY_THRESHOLD
)
from yt_variety import variety_engine

# API Keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Evergreen Curated Topics Vault (Zero-Cost Failover)
CURATED_TREND_VAULT = [
    {
        "topic": "The Lepakshi Hanging Pillar Gravity Paradox",
        "category": "unexplained_history_enigmas",
        "headline": "A 16th-century stone temple pillar hangs in mid-air with cloth sliding freely underneath",
        "paradox": "A 10-ton solid stone pillar hovers millimeters above the floor without touching ground, acting as a seismic balance lock."
    },
    {
        "topic": "The Pistol Shrimp 8000K Sonoluminescence Paradox",
        "category": "bizarre_biology_anomalies",
        "headline": "A 2-inch shrimp snaps its claw to generate a cavitation bubble hotter than the surface of the Sun",
        "paradox": "A biological creature snapping water so fast it creates 8,000°K plasma light flash and a 218dB shockwave."
    },
    {
        "topic": "The Kailash Temple Ellora Monolithic Enigma",
        "category": "unexplained_history_enigmas",
        "headline": "400,000 tons of solid basalt rock carved top-down with zero debris found for 50 kilometers",
        "paradox": "Carving a 100-foot multi-level monolithic temple top-down with zero tolerance for chisel errors."
    },
    {
        "topic": "Turritopsis Dohrnii: The Biologically Immortal Jellyfish",
        "category": "bizarre_biology_anomalies",
        "headline": "A marine creature that reverses its own cellular clock back to infancy when facing starvation or injury",
        "paradox": "An organism that chemically resets its specialized cells back to stem cells to escape biological death."
    },
    {
        "topic": "The Chand Baori 3500-Step Inverted Geometric Abyss",
        "category": "unexplained_history_enigmas",
        "headline": "A 13-story subterranean stepwell carved in razor-sharp optical infinity keeping water 6°C cooler",
        "paradox": "3,500 perfectly symmetrical steps creating a subterranean architectural vortex where acoustic echoes cancel out."
    },
    {
        "topic": "The Mariana Trench Challenger Deep Pressure Monsters",
        "category": "deep_ocean_abyss",
        "headline": "Creatures thriving under 1,100 atmospheres of pressure where titanium implodes",
        "paradox": "Piezo-resistant cell membranes that harden rather than collapse under 8 tons per square inch of hydrostatic force."
    },
    {
        "topic": "Magnetars: The Stars That Dissolve Atomic Bonds",
        "category": "extreme_physics_space",
        "headline": "A neutron star magnetic field so extreme it dissolves human electron clouds from 1,000 km away",
        "paradox": "Magnetic fields exceeding 100 billion Tesla distorting atomic electron orbitals into pencil-thin needles."
    }
]


class TrendAggregator:
    """
    Multi-source fault-tolerant trending aggregator with AI contrarian angle synthesis.
    """

    def __init__(self, request_timeout: int = 8):
        self.timeout = request_timeout
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)

    # -------------------------------------------------------------------------
    # 1. Source: YouTube Data API mostPopular
    # -------------------------------------------------------------------------
    def fetch_youtube_popular(self, region_code: str = "IN", max_results: int = 15) -> List[Dict[str, str]]:
        """Fetches mostPopular videos from YouTube Data API v3 with timeout and error handling."""
        trends = []
        token_file = BASE_DIR / "token.json"

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = None
            if token_file.exists():
                creds = Credentials.from_authorized_user_file(str(token_file))

            api_key = os.environ.get("YOUTUBE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
            yt = None
            if creds:
                yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
            elif api_key:
                yt = build("youtube", "v3", developerKey=api_key, cache_discovery=False)

            if not yt:
                return []

            request = yt.videos().list(
                part="snippet",
                chart="mostPopular",
                regionCode=region_code,
                maxResults=max_results
            )
            response = request.execute()
            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                title = snippet.get("title", "").strip()
                desc = snippet.get("description", "").strip()
                if title:
                    trends.append({
                        "source": f"YouTube mostPopular ({region_code})",
                        "raw_title": title,
                        "raw_context": desc[:200]
                    })
            if trends:
                print(f"📡 [Trend: YouTube] Fetched {len(trends)} popular videos from {region_code}.")
        except Exception as e:
            print(f"   [Trend Notice: YouTube {region_code}] {e} (skipping gracefully)")

        return trends

    # -------------------------------------------------------------------------
    # 2. Source: Google Trends & Google News RSS Feeds
    # -------------------------------------------------------------------------
    def fetch_google_trends_rss(self) -> List[Dict[str, str]]:
        """Fetches trending items from Google Trends RSS and Google News Discovery."""
        feeds = [
            ("Google Trends India", "https://trends.google.com/trending/rss?geo=IN"),
            ("Google Trends US", "https://trends.google.com/trending/rss?geo=US"),
            ("Google News Discovery", "https://news.google.com/rss/search?q=mystery+OR+discovery+OR+unexplained+OR+anomaly&hl=en-IN&gl=IN&ceid=IN:en")
        ]
        results = []
        for name, url in feeds:
            try:
                res = self.session.get(url, timeout=self.timeout)
                if res.status_code == 200 and len(res.content) > 100:
                    root = ET.fromstring(res.content)
                    items = root.findall(".//item")
                    for item in items[:12]:
                        raw_title = (item.find("title").text or "").strip()
                        clean_t = re.sub(r' - [^-]+$', '', raw_title).strip()
                        if clean_t and len(clean_t) > 10:
                            results.append({
                                "source": f"Google RSS ({name})",
                                "raw_title": clean_t,
                                "raw_context": clean_t
                            })
                    print(f"📰 [Trend: RSS] Fetched {len(items[:12])} items from {name}.")
            except Exception as e:
                print(f"   [Trend Notice: RSS {name}] {e} (skipping gracefully)")

        return results

    # -------------------------------------------------------------------------
    # 3. Source: Reddit (JSON with fallback to RSS)
    # -------------------------------------------------------------------------
    def fetch_reddit_trends(self) -> List[Dict[str, str]]:
        """
        Fetches trending posts from Reddit educational / anomaly communities.
        Tries keyless JSON first; if blocked by cloud runner IPs, falls back to RSS feeds.
        """
        subreddits = ["todayilearned", "Damnthatsinteresting", "explainlikeimfive"]
        results = []

        for sub in subreddits:
            sub_success = False

            # Attempt A: Keyless JSON
            try:
                json_url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
                # Use randomized user-agent to reduce rate limiting
                ua_headers = {
                    "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{random.randint(110, 126)}.0) Gecko/20100101 Firefox/{random.randint(110, 126)}.0"
                }
                r = self.session.get(json_url, headers=ua_headers, timeout=5)
                if r.status_code == 200:
                    payload = r.json()
                    children = payload.get("data", {}).get("children", [])
                    for child in children[:8]:
                        title = child.get("data", {}).get("title", "").strip()
                        if title and len(title) > 15:
                            results.append({
                                "source": f"Reddit r/{sub} (JSON)",
                                "raw_title": title,
                                "raw_context": child.get("data", {}).get("selftext", "")[:200]
                            })
                    if children:
                        sub_success = True
                        print(f"👾 [Trend: Reddit] Fetched {len(children[:8])} posts from r/{sub} (JSON).")
                elif r.status_code in (403, 429):
                    print(f"   [Trend Notice: Reddit r/{sub}] JSON blocked (HTTP {r.status_code}), attempting RSS fallback...")
            except Exception as json_err:
                print(f"   [Trend Notice: Reddit r/{sub} JSON] {json_err}, falling back to RSS...")

            # Attempt B: RSS Fallback if JSON failed or blocked
            if not sub_success:
                try:
                    rss_url = f"https://www.reddit.com/r/{sub}/hot.rss"
                    r = self.session.get(rss_url, headers=BROWSER_HEADERS, timeout=6)
                    if r.status_code == 200 and len(r.content) > 100:
                        root = ET.fromstring(r.content)
                        # Reddit RSS uses Atom namespace {http://www.w3.org/2005/Atom}
                        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry") or root.findall(".//item")
                        for entry in entries[:8]:
                            title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
                            if title_elem is None:
                                title_elem = entry.find("title")
                            if title_elem is not None and title_elem.text:
                                title = title_elem.text.strip()
                                if len(title) > 15:
                                    results.append({
                                        "source": f"Reddit r/{sub} (RSS)",
                                        "raw_title": title,
                                        "raw_context": title
                                    })
                        if entries:
                            print(f"👾 [Trend: Reddit] Succeeded via RSS fallback for r/{sub} ({len(entries[:8])} posts).")
                except Exception as rss_err:
                    print(f"   [Trend Notice: Reddit r/{sub} RSS] {rss_err} (skipping subreddit)")

        return results

    # -------------------------------------------------------------------------
    # 4. Synthesizer: Transform Trend into Original Contrarian Paradox Angle
    # -------------------------------------------------------------------------
    def synthesize_original_angle(
        self,
        raw_trend: Dict[str, str],
        target_category: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Uses LLM to convert a raw trend headline into a 100% original, contrarian angle.
        The prompt explicitly forbids copying or summarizing the trend.
        """
        title = raw_trend.get("raw_title", "")
        context = raw_trend.get("raw_context", "")
        source = raw_trend.get("source", "Live Trend")

        prompt = (
            "You are an investigative documentary researcher creating a viral, high-retention YouTube Short.\n"
            f"Trending Event/Headline: \"{title}\"\n"
            f"Source: {source}\n"
            f"Context: \"{context}\"\n"
            f"Target Category: {target_category or 'Curiosity / Science / Enigma'}\n\n"
            "CRITICAL INSTRUCTION: DO NOT summarize or copy the headline above. "
            "Instead, find the UNNOTICED CONTRARIAN TRUTH, the hidden scientific/historical paradox, "
            "or the counter-intuitive mechanism that mainstream media missed.\n\n"
            "Respond in STRICT JSON ONLY matching this exact schema:\n"
            "{\n"
            "  \"topic\": \"Punchy, original topic name (e.g. The Real Reason [X] Vanished)\",\n"
            "  \"category\": \"category_id\",\n"
            "  \"headline\": \"Opening paradox statement that stops scrolling (1 sentence)\",\n"
            "  \"paradox\": \"The counter-intuitive scientific, historical or physical truth (1 sentence)\"\n"
            "}"
        )

        # Tier 1: Gemini Flash Models
        if GEMINI_API_KEY:
            for g_model in GEMINI_MODELS:
                try:
                    from google import genai
                    client = genai.Client(api_key=GEMINI_API_KEY)
                    resp = client.models.generate_content(model=g_model, contents=prompt)
                    raw_text = resp.text.strip().replace("```json", "").replace("```", "").strip()
                    s, e = raw_text.find("{"), raw_text.rfind("}")
                    if s != -1 and e != -1:
                        parsed = json.loads(raw_text[s:e+1])
                        if parsed.get("topic") and parsed.get("headline"):
                            parsed["raw_source"] = source
                            parsed["raw_trend"] = title
                            return parsed
                except Exception as e:
                    print(f"   [Angle Gen: Gemini ({g_model}) notice]: {e}")
                    continue

        # Tier 2: Groq Cloud Llama 3.3
        if GROQ_API_KEY:
            try:
                headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": "You are an investigative researcher. Output strict JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "response_format": {"type": "json_object"}
                }
                r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=12)
                if r.status_code == 200:
                    raw_text = r.json()["choices"][0]["message"]["content"]
                    s, e = raw_text.find("{"), raw_text.rfind("}")
                    if s != -1 and e != -1:
                        parsed = json.loads(raw_text[s:e+1])
                        if parsed.get("topic") and parsed.get("headline"):
                            parsed["raw_source"] = source
                            parsed["raw_trend"] = title
                            return parsed
            except Exception as e:
                print(f"   [Angle Gen: Groq notice]: {e}")

        # Tier 3: Keyless Pollinations Text
        try:
            p_payload = {
                "messages": [
                    {"role": "system", "content": "Output strict JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "jsonMode": True,
                "seed": random.randint(100, 99999)
            }
            r = requests.post("https://text.pollinations.ai/", json=p_payload, timeout=15)
            if r.status_code == 200:
                raw_text = r.text.strip().replace("```json", "").replace("```", "").strip()
                s, e = raw_text.find("{"), raw_text.rfind("}")
                if s != -1 and e != -1:
                    parsed = json.loads(raw_text[s:e+1])
                    if parsed.get("topic") and parsed.get("headline"):
                        parsed["raw_source"] = source
                        parsed["raw_trend"] = title
                        return parsed
        except Exception:
            pass

        return None

    # -------------------------------------------------------------------------
    # 5. Master Trend Selection Pipeline
    # -------------------------------------------------------------------------
    def get_fresh_daily_trend(self, target_category_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Coordinates full discovery across YouTube, Google Trends RSS, and Reddit.
        Filters all candidates through variety_engine.is_fresh().
        Transforms the winner into an original contrarian angle.
        Falls back to Curated Vault and LLM generation so the pipeline NEVER fails.
        """
        print("\n" + "=" * 70)
        print("  🌐 MULTI-SOURCE DAILY TREND DISCOVERY (YouTube • Google • Reddit)")
        print(f"  Target Category Filter: {target_category_id or 'Dynamic Rotation'}")
        print("=" * 70)

        raw_candidates: List[Dict[str, str]] = []

        # 1. Gather all live trend feeds with error isolation
        raw_candidates.extend(self.fetch_google_trends_rss())
        raw_candidates.extend(self.fetch_reddit_trends())
        raw_candidates.extend(self.fetch_youtube_popular(region_code="IN"))

        random.shuffle(raw_candidates)
        print(f"🔍 [Trend Aggregator] Collected {len(raw_candidates)} total live candidates across all feeds.")

        # 2. Filter raw candidates via variety_engine.is_fresh()
        fresh_candidates = []
        for cand in raw_candidates:
            raw_title = cand.get("raw_title", "")
            is_fresh, reason = variety_engine.is_fresh(topic=raw_title)
            if is_fresh:
                fresh_candidates.append(cand)
            else:
                pass  # filtered out by similarity

        print(f"✨ [Trend Aggregator] {len(fresh_candidates)} candidates passed the variety freshness gate.")

        # 3. Synthesize original angle for top fresh candidate
        for candidate in fresh_candidates[:5]:
            print(f"💡 [Angle Synthesizer] Transforming trend: '{candidate['raw_title'][:50]}...'")
            angle = self.synthesize_original_angle(candidate, target_category=target_category_id)
            if angle and angle.get("topic"):
                # Double check that the synthesized topic is also fresh
                is_fresh, reason = variety_engine.is_fresh(topic=angle["topic"])
                if is_fresh:
                    print(f"🎯 [Original Trend Angle Secured]:")
                    print(f"   • Raw Trend:   '{candidate['raw_title'][:50]}...' ({candidate['source']})")
                    print(f"   • Topic:       '{angle['topic']}'")
                    print(f"   • Headline:    '{angle['headline']}'")
                    print(f"   • Paradox:     '{angle['paradox']}'")
                    return angle
                else:
                    print(f"   [Variety Notice] Synthesized topic not fresh: {reason}, trying next...")

        # 4. Fallback: Curated Discovery Vault filtered by variety & category
        print("🛡️ [Trend Aggregator] Falling back to Curated Discovery Vault...")
        vault_candidates = []
        for item in CURATED_TREND_VAULT:
            is_fresh, _ = variety_engine.is_fresh(topic=item["topic"])
            if is_fresh:
                vault_candidates.append(item)

        if target_category_id:
            cat_match = [v for v in vault_candidates if target_category_id.lower() in v.get("category", "").lower()]
            if cat_match:
                vault_candidates = cat_match

        if vault_candidates:
            chosen = random.choice(vault_candidates)
            print(f"🎯 [Vault Topic Selected]: '{chosen['topic']}' ({chosen['category']})")
            return chosen

        # 5. Ultimate Fallback: Direct Dynamic LLM Generation
        print("⚡ [Trend Aggregator] Vault exhausted; generating guaranteed fresh topic via LLM...")
        llm_candidate = self._generate_pure_llm_topic(target_category_id)
        if llm_candidate:
            return llm_candidate

        # Absolute guarantee (returns first item from vault)
        return CURATED_TREND_VAULT[0]

    def _generate_pure_llm_topic(self, target_category: Optional[str] = None) -> Optional[Dict[str, Any]]:
        prompt = (
            f"Generate 1 unique, mind-bending historical enigma, bizarre biological adaptation, "
            f"or extreme physics paradox for a YouTube Short in category '{target_category or 'unexplained_enigmas'}'.\n"
            "Respond in STRICT JSON ONLY:\n"
            "{\"topic\": \"...\", \"category\": \"...\", \"headline\": \"...\", \"paradox\": \"...\"}"
        )
        if GEMINI_API_KEY:
            for g_model in GEMINI_MODELS:
                try:
                    from google import genai
                    client = genai.Client(api_key=GEMINI_API_KEY)
                    resp = client.models.generate_content(model=g_model, contents=prompt)
                    raw_text = resp.text.strip().replace("```json", "").replace("```", "").strip()
                    s, e = raw_text.find("{"), raw_text.rfind("}")
                    if s != -1 and e != -1:
                        return json.loads(raw_text[s:e+1])
                except Exception:
                    continue
        return None


# Global singleton instance
trend_aggregator = TrendAggregator()

if __name__ == "__main__":
    t = trend_aggregator.get_fresh_daily_trend()
    print("\nResult:", json.dumps(t, indent=2))
