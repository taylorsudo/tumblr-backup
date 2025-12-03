#!/usr/bin/env python3
"""
Helper script to obtain OAuth tokens for private Tumblr blogs
"""

from requests_oauthlib import OAuth1Session

def get_oauth_tokens():
    """
    Interactive script to obtain OAuth tokens from Tumblr
    """
    print("Tumblr OAuth Token Generator")
    print("=" * 50)
    print("\nThis script will help you obtain OAuth tokens for accessing private Tumblr blogs.")
    print("\nFirst, register your app at: https://www.tumblr.com/oauth/apps")
    print()

    # Get consumer credentials
    consumer_key = input("Enter your Consumer Key (OAuth Consumer Key): ").strip()
    consumer_secret = input("Enter your Consumer Secret: ").strip()

    if not consumer_key or not consumer_secret:
        print("\nError: Consumer Key and Consumer Secret are required!")
        return

    print("\nAuthenticating with Tumblr...")

    try:
        # Step 1: Get request token
        oauth = OAuth1Session(consumer_key, client_secret=consumer_secret)
        request_token_url = 'https://www.tumblr.com/oauth/request_token'
        request_token = oauth.fetch_request_token(request_token_url)

        # Step 2: Get authorization
        authorization_url = oauth.authorization_url('https://www.tumblr.com/oauth/authorize')
        print(f"\nVisit this URL to authorize the app:\n{authorization_url}")
        print("\nAfter authorizing, you'll be redirected to a URL with 'oauth_verifier' parameter.")

        oauth_verifier = input("\nEnter the oauth_verifier code from the redirect URL: ").strip()

        if not oauth_verifier:
            print("\nError: OAuth verifier is required!")
            return

        # Step 3: Get access token
        access_token_url = 'https://www.tumblr.com/oauth/access_token'
        oauth = OAuth1Session(
            consumer_key,
            client_secret=consumer_secret,
            resource_owner_key=request_token.get('oauth_token'),
            resource_owner_secret=request_token.get('oauth_token_secret'),
            verifier=oauth_verifier
        )
        oauth_tokens = oauth.fetch_access_token(access_token_url)

        # Display results
        print("\n" + "=" * 50)
        print("SUCCESS! Your OAuth tokens:")
        print("=" * 50)
        print(f"\nConsumer Key: {consumer_key}")
        print(f"Consumer Secret: {consumer_secret}")
        print(f"OAuth Token: {oauth_tokens.get('oauth_token')}")
        print(f"OAuth Token Secret: {oauth_tokens.get('oauth_token_secret')}")

        print("\n" + "=" * 50)
        print("\nAdd these to your config.json:")
        print("=" * 50)
        print(f"""
{{
  "blog_identifier": "yourblog",
  "api_key": "{consumer_key}",
  "consumer_secret": "{consumer_secret}",
  "oauth_token": "{oauth_tokens.get('oauth_token')}",
  "oauth_token_secret": "{oauth_tokens.get('oauth_token_secret')}",
  "output_dir": "backup",
  "download_images": true,
  "download_videos": true,
  "download_audio": true
}}
        """)

        print("\nFor GitHub Actions, add these as repository secrets:")
        print("=" * 50)
        print(f"BLOG_IDENTIFIER: yourblog")
        print(f"API_KEY: {consumer_key}")
        print(f"CONSUMER_SECRET: {consumer_secret}")
        print(f"OAUTH_TOKEN: {oauth_tokens.get('oauth_token')}")
        print(f"OAUTH_TOKEN_SECRET: {oauth_tokens.get('oauth_token_secret')}")

    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you:")
        print("1. Registered your app at https://www.tumblr.com/oauth/apps")
        print("2. Used the correct Consumer Key and Consumer Secret")
        print("3. Authorized the app and copied the verifier code correctly")

if __name__ == "__main__":
    get_oauth_tokens()
