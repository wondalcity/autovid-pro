#!/usr/bin/env python3
"""One-time YouTube OAuth2 setup script.

Run this script ONCE on any machine with a browser to obtain an OAuth2 refresh
token for headless YouTube uploads.

Usage
-----
  python setup_youtube_auth.py

Prerequisites
-------------
  1. Enable "YouTube Data API v3" in Google Cloud Console.
  2. Create OAuth2 credentials (Desktop app), download client_secrets.json.
  3. Set YOUTUBE_CLIENT_SECRETS_JSON in your .env (or export it in your shell):
       export YOUTUBE_CLIENT_SECRETS_JSON=$(cat client_secrets.json)
  4. Run this script — a browser window will open for consent.
  5. After approval, the token JSON is printed to stdout.
  6. Copy the entire printed JSON string and set it as YOUTUBE_OAUTH_TOKEN_JSON
     in your .env file, then restart the backend.

Note: The refresh_token only appears once.  Keep it safe.
"""
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def main() -> None:
    client_secrets_json = os.getenv("YOUTUBE_CLIENT_SECRETS_JSON", "")
    if not client_secrets_json:
        print(
            "ERROR: YOUTUBE_CLIENT_SECRETS_JSON is not set.\n"
            "Download client_secrets.json from Google Cloud Console and set:\n"
            "  export YOUTUBE_CLIENT_SECRETS_JSON=$(cat client_secrets.json)",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "ERROR: google-auth-oauthlib not installed.\n"
            "  pip install google-auth-oauthlib",
            file=sys.stderr,
        )
        sys.exit(1)

    client_config = json.loads(client_secrets_json)
    client_data = client_config.get("installed") or client_config.get("web") or {}

    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=_SCOPES,
    )

    # Opens a local server on port 8080 to receive the OAuth2 callback.
    # If running headless, set --noauth_local_webserver=True and follow the
    # printed URL manually.
    print("Opening browser for Google OAuth2 consent…")
    creds = flow.run_local_server(port=8080, prompt="consent", open_browser=True)

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id or client_data.get("client_id", ""),
        "client_secret": creds.client_secret or client_data.get("client_secret", ""),
        "scopes": list(creds.scopes or _SCOPES),
    }
    token_json = json.dumps(token_data)

    print("\n" + "=" * 70)
    print("SUCCESS!  Add the following line to your .env file:")
    print("=" * 70)
    print(f"YOUTUBE_OAUTH_TOKEN_JSON={token_json}")
    print("=" * 70)
    print("\nThen restart the backend server.  Step 8 is ready.\n")


if __name__ == "__main__":
    main()
