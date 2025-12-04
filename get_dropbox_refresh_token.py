#!/usr/bin/env python
"""
Helper script to generate a Dropbox refresh token.
Run this once to get your refresh token, then use it in your upload script.
"""

import os
import sys
from dropbox import DropboxOAuth2FlowNoRedirect

def get_refresh_token():
    """
    Interactive script to get a Dropbox refresh token.
    """
    print("=== Dropbox Refresh Token Generator ===\n")

    # Get app credentials
    app_key = input("Enter your Dropbox App Key: ").strip()
    app_secret = input("Enter your Dropbox App Secret: ").strip()

    if not app_key or not app_secret:
        print("ERROR: App Key and App Secret are required")
        sys.exit(1)

    # Start OAuth flow
    auth_flow = DropboxOAuth2FlowNoRedirect(
        app_key,
        app_secret,
        token_access_type='offline'  # This is key for getting a refresh token!
    )

    # Get authorization URL
    authorize_url = auth_flow.start()

    print("\n1. Go to this URL in your browser:")
    print(f"   {authorize_url}")
    print("\n2. Click 'Allow' (you might have to log in first)")
    print("3. Copy the authorization code\n")

    auth_code = input("Enter the authorization code here: ").strip()

    try:
        # Exchange the authorization code for tokens
        oauth_result = auth_flow.finish(auth_code)

        print("\n" + "="*60)
        print("SUCCESS! Here are your credentials:")
        print("="*60)
        print(f"\nDROPBOX_APP_KEY={app_key}")
        print(f"DROPBOX_APP_SECRET={app_secret}")
        print(f"DROPBOX_REFRESH_TOKEN={oauth_result.refresh_token}")
        print("\n" + "="*60)
        print("\nAdd these to your environment variables or .env file")
        print("The refresh token will not expire!")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    get_refresh_token()
