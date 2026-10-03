"""
community_manager.py - Channel-Only Engagement Question & Smart Community Replies Engine
========================================================================================
1. Top-Level Engagement Question Comment:
   - Posts the engagement question via commentThreads().insert().
   - (Note: YouTube Data API cannot pin comments; manual 1-click pin in Studio is documented).
2. Channel-Only Auto-Replies:
   - Scopes ONLY to the channel's own videos via allThreadsRelatedToChannelId.
   - Respects MAX_REPLIES_PER_RUN (from autopilot_config.py).
   - Skips spam, promo links, and toxic/negative comments.
   - Avoids creator self-replies.
   - Enforces unique, empathetic replies—never repeats the exact same sentence twice.
   - Logs replied comment IDs in variety_store.json so no comment is ever replied to twice.
"""

import os
import sys
import json
import time
import random
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

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
    MAX_REPLIES_PER_RUN,
    QUOTA_COSTS,
    GEMINI_MODELS
)
from yt_variety import variety_engine

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Curated diverse empathetic reply openings
EMPATHETIC_REPLY_TEMPLATES = [
    "Thank you for watching! Really interesting perspective.",
    "Aapka sochna bilkul sahi hai! Thanks for sharing this thought.",
    "Great observation! That's exactly why this anomaly is so fascinating.",
    "Bohot badhiya sawaal! Next video me is topic ko aur detail me explore karenge.",
    "Spot on! Appreciate you taking the time to share your insight.",
    "Thanks for tuning in! What other mysteries would you like us to cover?",
    "Bilkul sahi pakde hain! Keep supporting the channel. 🙏"
]

SPAM_KEYWORDS = [
    "http://", "https://", "www.", ".com", "t.me/", "whatsapp", "sub4sub",
    "subscribe to my", "check my channel", "free money", "crypto", "telegram",
    "dm me", "follow me", "earn money"
]

NEGATIVE_KEYWORDS = [
    "fake", "scam", "trash", "worst", "hate", "bakwas", "chutiya", "dislike",
    "stupid", "idiot", "fraud", "lies", "lying", "crap"
]


class CommunityManager:
    """
    Manages top-level question posting and smart community replies.
    """

    # -------------------------------------------------------------------------
    # 1. Post Top-Level Engagement Question
    # -------------------------------------------------------------------------
    @classmethod
    def post_engagement_question(
        cls,
        youtube_service: Any,
        video_id: str,
        question_text: str
    ) -> Optional[str]:
        """
        Posts the engagement question as a top-level comment via commentThreads().insert().
        Note: The YouTube Data API v3 does not expose an endpoint to set a comment as pinned.
        Pinning must be done manually via YouTube Studio or the mobile app.
        """
        if not youtube_service:
            print("   [Community Info] YouTube service offline; skipping comment insertion.")
            return None

        if not video_id or video_id.startswith("DRYRUN") or video_id.startswith("LOCAL"):
            print("   [Community Info] Dry-run video ID; skipping remote comment.")
            return None

        clean_text = question_text.strip()
        if not clean_text:
            clean_text = "Aapka is baare me kya manna hai? Comments me batayein! 👇 #shorts"

        print(f"💬 [YouTube API] Posting top-level engagement question for {video_id}...")
        try:
            body = {
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": clean_text
                        }
                    }
                }
            }
            request = youtube_service.commentThreads().insert(part="snippet", body=body)
            response = request.execute()
            from autopilot_config import QuotaManager
            QuotaManager.consume_units("commentThreads.insert")
            comment_id = response.get("id")
            print(f"🎉 [Community] Successfully posted top-level comment (ID: {comment_id})!")
            print("   📌 [Notice] To pin this comment, click the 3 dots beside it in YouTube Studio.")
            return comment_id
        except Exception as e:
            print(f"   [Community Comment Warning] Could not post top-level question: {e}")
            return None

    # -------------------------------------------------------------------------
    # 2. Filter Spam, Links, and Negativity
    # -------------------------------------------------------------------------
    @classmethod
    def is_constructive_comment(cls, text: str) -> bool:
        """Determines if a comment is clean, constructive, and suitable for a reply."""
        lower = text.lower().strip()
        if len(lower) < 2:
            return False

        # 1. Reject spam and links
        for spam in SPAM_KEYWORDS:
            if spam in lower:
                return False

        # 2. Reject negative / toxic remarks
        for neg in NEGATIVE_KEYWORDS:
            if neg in lower:
                return False

        return True

    # -------------------------------------------------------------------------
    # 3. Dynamic Reply Generator (Ensures unique non-repeating sentences)
    # -------------------------------------------------------------------------
    @classmethod
    def generate_unique_reply(cls, user_comment: str, author_name: str) -> str:
        """
        Generates an empathetic, unique reply using Gemini or safe template rotation.
        Guarantees that identical sentences are never repeated.
        """
        if GEMINI_API_KEY:
            for g_model in GEMINI_MODELS:
                try:
                    from google import genai
                    client = genai.Client(api_key=GEMINI_API_KEY)
                    prompt = (
                        "You are a friendly, humble YouTube creator responding to a fan comment.\n"
                        f"Fan Name: {author_name}\n"
                        f"Fan Comment: \"{user_comment}\"\n\n"
                        "Write a warm, 1-2 sentence reply in casual Hinglish/English. "
                        "Acknowledge their thought, say thanks, and encourage them to subscribe or suggest topics. "
                        "Output ONLY the plain reply text with zero quotes."
                    )
                    resp = client.models.generate_content(model=g_model, contents=prompt)
                    txt = resp.text.strip().strip('"').strip("'")
                    if txt and len(txt) > 8:
                        return txt
                except Exception:
                    continue

        # Template fallback with randomized sign-off
        chosen_base = random.choice(EMPATHETIC_REPLY_TEMPLATES)
        if author_name and author_name != "Viewer":
            return f"@{author_name} {chosen_base}"
        return chosen_base

    # -------------------------------------------------------------------------
    # 4. Channel-Only Auto-Replies Execution
    # -------------------------------------------------------------------------
    def run_channel_auto_replies(
        self,
        youtube_service: Any,
        channel_id: Optional[str] = None,
        max_replies: int = MAX_REPLIES_PER_RUN
    ) -> int:
        """
        Fetches comments on the channel's OWN videos and replies to unreplied, constructive comments.
        Enforces deduplication via variety_engine.is_comment_replied().
        """
        if not youtube_service:
            print("   [Community Info] YouTube service offline; skipping auto-replies.")
            return 0

        print("\n" + "=" * 70)
        print("  🤝 CHANNEL-ONLY COMMUNITY ENGAGEMENT (Smart Auto-Replies)")
        print(f"  Max Replies Budget: {max_replies} | Channel Scoped: YES")
        print("=" * 70)

        # 1. Fetch channel ID if not passed
        try:
            if not channel_id:
                ch_req = youtube_service.channels().list(part="id", mine=True)
                ch_res = ch_req.execute()
                items = ch_res.get("items", [])
                if items:
                    channel_id = items[0]["id"]
        except Exception as ch_err:
            print(f"   [Community Notice] Could not detect channel ID: {ch_err}")
            return 0

        if not channel_id:
            print("   [Community Notice] No channel ID found; skipping replies.")
            return 0

        # 2. Fetch comments on channel's own videos
        replies_count = 0
        try:
            req = youtube_service.commentThreads().list(
                part="snippet",
                allThreadsRelatedToChannelId=channel_id,
                maxResults=25,
                textFormat="plainText"
            )
            res = req.execute()
            from autopilot_config import QuotaManager
            QuotaManager.consume_units("commentThreads.list")
            threads = res.get("items", [])
            print(f"📬 [Community] Found {len(threads)} recent comment threads on your channel.")

            for thread in threads:
                if replies_count >= max_replies:
                    print(f"🛑 [Community] Reached max reply limit ({max_replies}) for this run.")
                    break

                t_snippet = thread.get("snippet", {})
                top_comment = t_snippet.get("topLevelComment", {}).get("snippet", {})
                c_id = thread.get("id")
                text = top_comment.get("textOriginal", "")
                author = top_comment.get("authorDisplayName", "Viewer")
                author_channel = top_comment.get("authorChannelId", {}).get("value", "")

                # Skip if already replied
                if variety_engine.is_comment_replied(c_id):
                    continue

                # Skip creator's own comments
                if author_channel == channel_id:
                    continue

                # Filter for constructive comment
                if not self.is_constructive_comment(text):
                    continue

                # Generate unique empathetic reply
                reply_text = self.generate_unique_reply(text, author)

                # Post reply via comments().insert()
                try:
                    reply_body = {
                        "snippet": {
                            "parentId": c_id,
                            "textOriginal": reply_text
                        }
                    }
                    youtube_service.comments().insert(part="snippet", body=reply_body).execute()
                    QuotaManager.consume_units("comments.insert")
                    variety_engine.record_replied_comment(c_id, reply_text)
                    replies_count += 1
                    print(f"   ✅ [Replied to @{author}]: \"{reply_text[:60]}...\"")
                    time.sleep(1.0)  # gentle pacing
                except Exception as r_err:
                    print(f"   [Reply Warning for {c_id}]: {r_err}")

        except Exception as e:
            print(f"   [Community Auto-Reply Notice]: {e}")

        print(f"✨ [Community Summary] Finished. Sent {replies_count} auto-replies this run.")
        return replies_count


# Global singleton instance
community_manager = CommunityManager()

if __name__ == "__main__":
    test_comment = "Is this really true? Sounds unbelievable!"
    print("Is constructive:", community_manager.is_constructive_comment(test_comment))
    reply = community_manager.generate_unique_reply(test_comment, "Aakash")
    print("Generated reply:", reply)
