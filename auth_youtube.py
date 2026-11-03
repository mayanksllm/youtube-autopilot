"""
auth_youtube.py - Interactive YouTube OAuth 2.0 Authenticator
=============================================================
Authorizes your YouTube channel for autonomous video uploads.
Generates a fresh token.json with offline access (refresh_token).
"""

import os
import sys
import json
from pathlib import Path

# Ensure UTF-8 output on Windows
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

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

BASE_DIR = Path(__file__).resolve().parent
CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
TOKEN_FILE = BASE_DIR / "token.json"

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]


def main():
    print("\n" + "=" * 75)
    print("  🔐 YOUTUBE DATA API V3 - INTERACTIVE AUTHENTICATION")
    print("=" * 75)

    if not CLIENT_SECRETS_FILE.exists():
        print(f"\n❌ Error: '{CLIENT_SECRETS_FILE.name}' not found!")
        print("Please place your OAuth client secrets JSON file in this directory.")
        return 1

    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    print("\n1. Preparing OAuth 2.0 Consent Flow...")
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        scopes=YOUTUBE_SCOPES
    )

    print("2. Opening default browser for Google Authorization...")
    print("   👉 If the browser doesn't open automatically, look for the link below.")
    print("   ⚠️ Note: If you see 'Google hasn't verified this app', click:")
    print("      'Advanced' -> 'Go to <app name> (unsafe)' and continue.\n")

    try:
        # Prompt consent forces Google to return a new refresh_token
        creds = flow.run_local_server(
            port=0,
            prompt="consent",
            access_type="offline"
        )
    except Exception as e:
        print(f"❌ Failed to complete authentication: {e}")
        return 1

    # Save credentials to token.json
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print("\n" + "=" * 75)
    print("  🎉 SUCCESS: YouTube authenticated! 'token.json' has been created.")
    print("=" * 75)

    # Verify channel connection
    try:
        yt = build("youtube", "v3", credentials=creds)
        res = yt.channels().list(mine=True, part="snippet").execute()
        items = res.get("items", [])
        if items:
            title = items[0]["snippet"].get("title", "Unknown")
            cid = items[0].get("id", "")
            print(f"  Connected YouTube Channel: '{title}' (ID: {cid})")
    except Exception as e:
        print(f"  [Channel Notice] Could not fetch channel info: {e}")

    print("\n" + "!" * 75)
    print("  🚨 CRITICAL STEP TO PREVENT 7-DAY EXPIRATION:")
    print("  1. Go to Google Cloud Console: https://console.cloud.google.com/apis/credentials/consent")
    print("  2. In 'OAuth consent screen', check 'Publishing status'.")
    print("  3. If it says 'Testing', click the button 'PUBLISH APP' to switch to 'In production'.")
    print("     (Without this, Google will revoke this token again after exactly 7 days!)")
    print("!" * 75)

    print("\n👉 Next Step: Update your GitHub Actions secrets:")
    print("   Run: python set_github_secrets.py")
    print("=" * 75 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
