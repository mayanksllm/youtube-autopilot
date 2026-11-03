"""
set_github_secrets.py - Sync & Display GitHub Actions Secrets
=============================================================
Easily sync your YouTube tokens and API keys to GitHub Secrets:
  https://github.com/mayanksllm/youtube-autopilot/settings/secrets/actions

Usage:
  python set_github_secrets.py           # Display formatted secrets ready to copy-paste
  python set_github_secrets.py --sync    # Automatically push secrets via GitHub Personal Access Token (PAT)
"""

import os
import sys
import json
import base64
from pathlib import Path
from dotenv import load_dotenv

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

BASE_DIR = Path(__file__).resolve().parent
TOKEN_FILE = BASE_DIR / "token.json"
CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
ENV_FILE = BASE_DIR / ".env"

REPO_OWNER = "mayanksllm"
REPO_NAME = "youtube-autopilot"

load_dotenv(dotenv_path=ENV_FILE)


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Encrypts a secret value using the repository's libsodium public key."""
    from nacl import encoding, public
    public_key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def upload_secrets_to_github(pat_token: str, secrets_dict: dict) -> bool:
    """Uploads secrets directly to GitHub repository via REST API."""
    import requests

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {pat_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # 1. Get repository public key
    pub_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/secrets/public-key"
    r = requests.get(pub_url, headers=headers)
    if r.status_code != 200:
        print(f"❌ Failed to fetch repo public key ({r.status_code}): {r.text}")
        return False

    key_data = r.json()
    key_id = key_data["key_id"]
    public_key = key_data["key"]

    # 2. Put each secret
    all_ok = True
    for sec_name, sec_val in secrets_dict.items():
        if not sec_val:
            continue
        enc_val = encrypt_secret(public_key, sec_val)
        put_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/secrets/{sec_name}"
        payload = {
            "encrypted_value": enc_val,
            "key_id": key_id
        }
        pr = requests.put(put_url, headers=headers, json=payload)
        if pr.status_code in (201, 204):
            print(f"  ✅ Secret set successfully: {sec_name}")
        else:
            print(f"  ❌ Failed to set {sec_name} ({pr.status_code}): {pr.text}")
            all_ok = False

    return all_ok


def main():
    print("\n" + "=" * 75)
    print("  🔑 YOUTUBE AUTOPILOT - GITHUB ACTIONS SECRETS MANAGER")
    print(f"  Target: https://github.com/{REPO_OWNER}/{REPO_NAME}/settings/secrets/actions")
    print("=" * 75)

    # 1. Read token.json
    token_json_str = ""
    refresh_token = ""
    if TOKEN_FILE.exists():
        try:
            token_json_str = TOKEN_FILE.read_text(encoding="utf-8").strip()
            t_data = json.loads(token_json_str)
            refresh_token = t_data.get("refresh_token", "")
        except Exception as e:
            print(f"⚠️ Error reading token.json: {e}")

    # 2. Read client_secrets.json
    client_secrets_str = ""
    b64_client_secrets = ""
    if CLIENT_SECRETS_FILE.exists():
        try:
            client_secrets_str = CLIENT_SECRETS_FILE.read_text(encoding="utf-8").strip()
            b64_client_secrets = base64.b64encode(CLIENT_SECRETS_FILE.read_bytes()).decode("utf-8")
        except Exception as e:
            print(f"⚠️ Error reading client_secrets.json: {e}")

    # 3. Read API keys from .env
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    pexels_key = os.environ.get("PEXELS_API_KEY", "")
    groq_key = os.environ.get("GROQ_API_KEY", "")

    # Quick token health check
    if not token_json_str or not refresh_token:
        print("\n⚠️ WARNING: 'token.json' is missing or has no refresh_token.")
        print("👉 Run: python auth_youtube.py first to authorize your YouTube channel!")
    else:
        # Check if expired
        try:
            from autopilot_config import verify_youtube_credentials
            ok, info, _ = verify_youtube_credentials(force_restore=False)
            if ok:
                print(f"\n✅ Local YouTube Token: ACTIVE ({info})")
            else:
                print(f"\n⚠️ Local YouTube Token Check: {info}")
                if "invalid_grant" in str(info):
                    print("👉 Your local token has expired! Run: python auth_youtube.py first.")
        except Exception:
            pass

    secrets = {
        "YOUTUBE_TOKEN_JSON": token_json_str,
        "YOUTUBE_REFRESH_TOKEN": refresh_token,
        "YOUTUBE_CLIENT_SECRET_BASE64": b64_client_secrets,
        "CLIENT_SECRETS_JSON": client_secrets_str,
        "GEMINI_API_KEY": gemini_key,
        "PEXELS_API_KEY": pexels_key,
    }
    if groq_key:
        secrets["GROQ_API_KEY"] = groq_key

    # Check for --sync flag
    sync_mode = "--sync" in sys.argv
    if sync_mode:
        print("\n🚀 AUTOMATIC SYNC VIA GITHUB REST API:")
        pat = os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_TOKEN")
        if not pat:
            try:
                pat = input("Enter your GitHub Personal Access Token (with 'repo' scope): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nCancelled.")
                return 0
        if pat:
            print("\nUploading encrypted secrets to GitHub...")
            success = upload_secrets_to_github(pat, secrets)
            if success:
                print("\n🎉 ALL SECRETS SYNCHRONIZED TO GITHUB SUCCESSFULLY!")
                return 0
            else:
                print("\n⚠️ Some secrets failed to upload. Check permissions.")

    # Display secrets for manual copy-paste
    print("\n" + "-" * 75)
    print("📋 SECRETS READY TO ADD/UPDATE IN GITHUB ACTIONS")
    print(f"👉 Open: https://github.com/{REPO_OWNER}/{REPO_NAME}/settings/secrets/actions")
    print("-" * 75)

    print("\n[1] Secret Name: YOUTUBE_REFRESH_TOKEN")
    print("Value:")
    print(refresh_token if refresh_token else "(Run python auth_youtube.py to generate)")

    print("\n[2] Secret Name: YOUTUBE_CLIENT_SECRET_BASE64")
    print("Value:")
    print(b64_client_secrets if b64_client_secrets else "(client_secrets.json not found)")

    print("\n[3] Secret Name: YOUTUBE_TOKEN_JSON")
    print("Value:")
    print(token_json_str if token_json_str else "(Run python auth_youtube.py to generate)")

    print("\n[4] Secret Name: GEMINI_API_KEY")
    print(f"Value: {gemini_key if gemini_key else '(Not set in .env)'}")

    print("\n[5] Secret Name: PEXELS_API_KEY")
    print(f"Value: {pexels_key if pexels_key else '(Not set in .env)'}")

    print("\n" + "=" * 75)
    print("💡 TIP: You can also auto-sync these directly without copy-pasting:")
    print("   python set_github_secrets.py --sync")
    print("=" * 75 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
