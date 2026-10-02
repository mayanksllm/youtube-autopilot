"""
Professional YouTube Channel Branding & SEO Optimizer
Pushes world-class high-CPM channel branding directly to YouTube Data API v3.
"""
import sys
from agent_manager import get_youtube_service

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def update_channel():
    yt = get_youtube_service()
    if not yt:
        print("Error: YouTube service not authenticated.")
        return

    channels = yt.channels().list(mine=True, part="id,snippet,brandingSettings").execute()
    items = channels.get("items", [])
    if not items:
        print("Error: No channel found.")
        return

    channel_id = items[0]["id"]
    current_title = items[0]["snippet"]["title"]
    print(f"Connecting to Channel: {current_title} ({channel_id})")

    elite_bio = (
        "Welcome to the edge of wealth, dark psychology, and unexplained reality.\n\n"
        "Here, we decode the hidden financial paradoxes of the top 1%, the subconscious manipulation "
        "mechanisms running society, and the strangest anomalies of human civilization—delivered in "
        "rapid, high-impact 60-second deep dives.\n\n"
        "• High-CPM Financial Paradoxes & Wealth Systems\n"
        "• Dark Psychology, Cognitive Biases & Subconscious Influence\n"
        "• Unexplained Scientific Anomalies & Reality Glitches\n\n"
        "Elevate your cognitive edge and financial sovereignty. Hit Subscribe to join the top 1%."
    )

    elite_keywords = (
        '"financial paradoxes" "dark psychology" "wealth mindset" "money psychology" '
        '"psychological facts" "mind hacks" "unexplained mysteries" "the cantillon effect" '
        '"cognitive biases" "manipulation tactics" "deep psychology" "high cpm finance" '
        'shorts viral "youtube shorts"'
    )

    body = {
        "id": channel_id,
        "brandingSettings": {
            "channel": {
                "description": elite_bio,
                "keywords": elite_keywords,
                "defaultLanguage": "en"
            }
        }
    }

    print("\nPushing world-class branding to YouTube Data API v3...")
    res = yt.channels().update(part="brandingSettings", body=body).execute()
    print("\n" + "=" * 65)
    print("🎉 SUCCESS: YouTube Channel Profile & SEO Successfully Updated Live!")
    print("=" * 65)
    print("\nChannel Description:\n", res["brandingSettings"]["channel"]["description"])
    print("\nChannel Keywords:\n", res["brandingSettings"]["channel"]["keywords"])
    print("\n" + "=" * 65)

if __name__ == "__main__":
    update_channel()
