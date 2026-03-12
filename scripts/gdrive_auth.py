#!/usr/bin/env python3
"""
Google Drive authentication helper for Pi Control Panel.

Usage:
    python3 scripts/gdrive_auth.py

The script prints an authorization URL. Open it in a browser, approve access,
copy the final redirected URL, and paste it back into the terminal.
"""

import os
import sys

from urllib.parse import parse_qs, urlparse

from google_auth_oauthlib.flow import InstalledAppFlow


CREDENTIALS_DIR = "/opt/pi-control/credentials"
CLIENT_SECRETS_FILE = os.path.join(CREDENTIALS_DIR, "gdrive_credentials.json")
TOKEN_FILE = os.path.join(CREDENTIALS_DIR, "gdrive_token.json")
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _extract_code(redirect_url: str) -> str:
    """Extract the OAuth code from the pasted redirect URL."""
    parsed = urlparse(redirect_url.strip())
    query = parse_qs(parsed.query)
    code = query.get("code", [""])[0]
    if not code:
        raise ValueError("No authorization code found in the pasted URL")
    return code


def main():
    print("=" * 60)
    print("  Google Drive Authentication for Pi Control Panel")
    print("=" * 60)
    print()

    if not os.path.exists(CLIENT_SECRETS_FILE):
        print("ERROR: Client secrets file not found.")
        print()
        print("1. Go to https://console.cloud.google.com/")
        print("2. Enable Google Drive API for your project")
        print("3. Create OAuth client credentials for a Desktop app")
        print("4. Copy the JSON file to:")
        print(f"   {CLIENT_SECRETS_FILE}")
        print()
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    flow.redirect_uri = "http://localhost"

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    print("Open this URL in a browser and approve access:")
    print()
    print(auth_url)
    print()
    print("After Google redirects to http://localhost, copy the full URL from the browser")
    print("address bar and paste it here.")
    print()

    redirected_url = input("Paste redirected URL: ").strip()
    if not redirected_url:
        print("ERROR: No redirected URL provided.")
        return 1

    try:
        code = _extract_code(redirected_url)
        flow.fetch_token(code=code)
    except Exception as exc:
        print(f"ERROR: Authentication failed: {exc}")
        return 1

    with open(TOKEN_FILE, "w", encoding="utf-8") as token_file:
        token_file.write(flow.credentials.to_json())

    print()
    print("Authentication successful.")
    print(f"Token saved to: {TOKEN_FILE}")
    print("Restart the pi-control service:")
    print("  sudo systemctl restart pi-control")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
