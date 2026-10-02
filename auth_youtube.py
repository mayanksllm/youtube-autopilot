"""
YouTube One-Time OAuth 2.0 Authentication Helper
Dynamic open port assignment with atomic state handling.
"""
import os
import sys
import wsgiref.simple_server
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow, _RedirectWSGIApp, _ExclusiveWSGIServer, _WSGIRequestHandler

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

def main():
    if not os.path.exists("client_secrets.json"):
        print("Error: client_secrets.json not found!", flush=True)
        return

    print("\n" + "=" * 65, flush=True)
    print("INITIATING YOUTUBE DATA API V3 AUTHENTICATION", flush=True)
    print("=" * 65, flush=True)

    flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", YOUTUBE_SCOPES)
    wsgi_app = _RedirectWSGIApp("Authorization successful! You can close this tab and return to the terminal.")
    
    server = wsgiref.simple_server.make_server(
        "localhost",
        0,  # Dynamically pick an open port
        wsgi_app,
        server_class=_ExclusiveWSGIServer,
        handler_class=_WSGIRequestHandler
    )

    port = server.server_port
    flow.redirect_uri = f"http://localhost:{port}/"

    try:
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

        print(f"\nLocal callback listener active on port {port}...", flush=True)
        print("👉 AUTHORIZATION LINK (Click to open or copy into browser):", flush=True)
        print(auth_url, flush=True)
        print("\nOpening your default browser now...\n", flush=True)

        try:
            webbrowser.open(auth_url, new=1, autoraise=True)
        except Exception:
            pass

        # Handle the callback request from Google
        server.handle_request()

        auth_response = wsgi_app.last_request_uri.replace("http://", "https://")
        flow.fetch_token(authorization_response=auth_response)
        creds = flow.credentials

        with open("token.json", "w", encoding="utf-8") as f:
            f.write(creds.to_json())

        print("\n" + "=" * 65, flush=True)
        print("🎉 SUCCESS: YouTube authenticated! token.json has been created.", flush=True)
        print("=" * 65 + "\n", flush=True)
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
