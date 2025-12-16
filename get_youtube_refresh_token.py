#!/usr/bin/env python
"""
Get YouTube OAuth2 Refresh Token
Run this script locally to generate a refresh token for use in GitHub Actions
"""

import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/youtube']


def get_refresh_token(client_id: str, client_secret: str):
    """
    Generate a YouTube OAuth2 refresh token

    Args:
        client_id: Google OAuth2 client ID
        client_secret: Google OAuth2 client secret
    """
    # Create client config
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"]
        }
    }

    # Run OAuth flow
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n" + "="*60)
    print("SUCCESS! Your YouTube refresh token:")
    print("="*60)
    print(creds.refresh_token)
    print("="*60)
    print("\nAdd this to your config.json or GitHub Actions secrets:")
    print('  "youtube_refresh_token": "' + creds.refresh_token + '"')
    print("\nThis token does not expire and can be reused.")
    print("="*60)


if __name__ == "__main__":
    print("YouTube OAuth2 Refresh Token Generator")
    print("="*60)
    print("\nThis will open a browser window to authorize access to YouTube.")
    print("Make sure you're logged into the Google account that owns the playlist.\n")

    client_id = input("Enter your Google OAuth Client ID: ").strip()
    client_secret = input("Enter your Google OAuth Client Secret: ").strip()

    if not client_id or not client_secret:
        print("\nError: Both Client ID and Client Secret are required.")
        sys.exit(1)

    try:
        get_refresh_token(client_id, client_secret)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
