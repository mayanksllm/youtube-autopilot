"""
verify_youtube_auth.py - Pre-Flight YouTube API Authentication Validator
========================================================================
Validates that YouTube credentials and OAuth tokens are active and can successfully
make authenticated API calls to YouTube Data API v3.

Used in GitHub Actions workflows to fail fast if tokens are expired, and locally
to check account health.
"""

import sys
import os
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

from autopilot_config import verify_youtube_credentials, restore_youtube_credentials

def main():
    print("=" * 75)
    print("  🔍 PRE-FLIGHT CHECK: YOUTUBE DATA API V3 CREDENTIAL VALIDATION")
    print("=" * 75)

    is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    if is_ci:
        print("  Running in CI: GitHub Actions Environment")
    else:
        print("  Running locally")

    success, info, channel_id = verify_youtube_credentials(force_restore=True)

    if success:
        print("\n" + "=" * 75)
        print("  🎉 [SUCCESS] YOUTUBE AUTHENTICATION VERIFIED & ACTIVE!")
        print(f"  Connected {info}")
        print("  Quota & Upload capabilities: READY")
        print("=" * 75 + "\n")
        sys.exit(0)
    else:
        print("\n" + "=" * 75)
        print("  ❌ [FAILURE] YOUTUBE CREDENTIAL VALIDATION FAILED")
        print(f"  Error details: {info}")
        print("=" * 75)
        print("\n📋 ROOT CAUSE & IMMEDIATE ACTION PLAN:")
        print("---------------------------------------------------------------------------")
        if "invalid_grant" in str(info):
            print("1. WHY THIS HAPPENED:")
            print("   Google expired or revoked the OAuth refresh token (invalid_grant).")
            print("   By default, Google Cloud projects in 'Testing' mode expire tokens after 7 DAYS.")
            print("\n2. PERMANENT FIX (Stop 7-day expiration):")
            print("   a. Open Google Cloud Console: https://console.cloud.google.com/apis/credentials/consent")
            print("   b. Under 'Publishing status', click 'PUBLISH APP' to switch to 'In production'.")
            print("      (You do not need Google verification for personal automation scripts).")
            print("\n3. GENERATE A FRESH TOKEN:")
            print("   a. In your local terminal, run:")
            print("      python auth_youtube.py")
            print("   b. Approve access with your YouTube channel account.")
            print("\n4. UPDATE GITHUB SECRETS:")
            print("   a. Run: python set_github_secrets.py")
            print("      (or copy from token.json to https://github.com/mayanksllm/youtube-autopilot/settings/secrets/actions)")
            print("   b. Update secret 'YOUTUBE_TOKEN_JSON' and 'YOUTUBE_REFRESH_TOKEN'.")
        else:
            print("1. Missing or unreadable credentials.")
            print("2. Ensure token.json or GitHub secrets (YOUTUBE_TOKEN_JSON / YOUTUBE_REFRESH_TOKEN) are set.")
            print("3. Run 'python auth_youtube.py' locally to generate credentials.")
        print("---------------------------------------------------------------------------\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
