"""
YouTube Playlist Integration
Handles adding videos to a YouTube playlist using the YouTube Data API v3
"""

import os
import re
import pickle
from pathlib import Path
from typing import List, Optional, Set
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class YouTubePlaylistManager:
    """Manages adding videos to a YouTube playlist"""

    SCOPES = ['https://www.googleapis.com/auth/youtube']

    def __init__(self, client_id: str, client_secret: str, playlist_id: str, refresh_token: Optional[str] = None):
        """
        Initialize YouTube playlist manager

        Args:
            client_id: Google OAuth2 client ID
            client_secret: Google OAuth2 client secret
            playlist_id: YouTube playlist ID to add videos to
            refresh_token: Optional refresh token for headless authentication (GitHub Actions)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.playlist_id = playlist_id
        self.refresh_token = refresh_token
        self.youtube = None
        self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with YouTube API using OAuth2"""
        creds = None

        # If refresh token provided, use it directly (for GitHub Actions)
        if self.refresh_token:
            creds = Credentials(
                None,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=self.SCOPES
            )
            # Refresh to get access token
            creds.refresh(Request())
        else:
            # Interactive authentication with token caching
            token_file = Path('youtube_token.pickle')

            # Load existing credentials
            if token_file.exists():
                with open(token_file, 'rb') as token:
                    creds = pickle.load(token)

            # If no valid credentials, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # Create client config
                    client_config = {
                        "installed": {
                            "client_id": self.client_id,
                            "client_secret": self.client_secret,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "redirect_uris": ["http://localhost"]
                        }
                    }

                    flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
                    creds = flow.run_local_server(port=0)

                # Save credentials for next run
                with open(token_file, 'wb') as token:
                    pickle.dump(creds, token)

        self.youtube = build('youtube', 'v3', credentials=creds)

    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract YouTube video ID from various URL formats

        Args:
            url: YouTube URL

        Returns:
            Video ID if found, None otherwise
        """
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def get_playlist_video_ids(self) -> Set[str]:
        """
        Get all video IDs currently in the playlist

        Returns:
            Set of video IDs
        """
        video_ids = set()
        next_page_token = None

        try:
            while True:
                request = self.youtube.playlistItems().list(
                    part='contentDetails',
                    playlistId=self.playlist_id,
                    maxResults=50,
                    pageToken=next_page_token
                )
                response = request.execute()

                for item in response.get('items', []):
                    video_id = item['contentDetails']['videoId']
                    video_ids.add(video_id)

                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break

        except HttpError as e:
            print(f"Warning: Failed to fetch existing playlist items: {e}")

        return video_ids

    def add_video_to_playlist(self, video_id: str) -> bool:
        """
        Add a single video to the playlist

        Args:
            video_id: YouTube video ID

        Returns:
            True if successful, False otherwise
        """
        try:
            request = self.youtube.playlistItems().insert(
                part='snippet',
                body={
                    'snippet': {
                        'playlistId': self.playlist_id,
                        'resourceId': {
                            'kind': 'youtube#video',
                            'videoId': video_id
                        }
                    }
                }
            )
            request.execute()
            return True

        except HttpError as e:
            error_reason = e.error_details[0].get('reason', '') if e.error_details else ''

            # Video already in playlist is not a real error
            if error_reason == 'videoAlreadyInPlaylist':
                return False

            print(f"Warning: Failed to add video {video_id}: {e}")
            return False

    def add_videos_to_playlist(self, video_urls: List[str]) -> dict:
        """
        Add multiple videos to the playlist

        Args:
            video_urls: List of YouTube URLs

        Returns:
            Dictionary with results: {'added': int, 'skipped': int, 'failed': int}
        """
        results = {'added': 0, 'skipped': 0, 'failed': 0}

        # Extract video IDs from URLs
        video_ids = []
        for url in video_urls:
            video_id = self.extract_video_id(url)
            if video_id:
                video_ids.append(video_id)

        if not video_ids:
            return results

        # Get existing playlist items to avoid duplicates
        print(f"Checking playlist for existing videos...")
        existing_ids = self.get_playlist_video_ids()

        # Add videos
        for video_id in video_ids:
            if video_id in existing_ids:
                results['skipped'] += 1
                continue

            if self.add_video_to_playlist(video_id):
                results['added'] += 1
                print(f"Added video: {video_id}")
            else:
                results['failed'] += 1

        return results


def add_youtube_videos_to_playlist(video_urls: List[str], client_id: str,
                                   client_secret: str, playlist_id: str,
                                   refresh_token: Optional[str] = None) -> None:
    """
    Convenience function to add YouTube videos to a playlist

    Args:
        video_urls: List of YouTube URLs
        client_id: Google OAuth2 client ID
        client_secret: Google OAuth2 client secret
        playlist_id: YouTube playlist ID
        refresh_token: Optional refresh token for headless authentication
    """
    if not video_urls:
        print("No YouTube videos to add to playlist")
        return

    print(f"\nAdding {len(video_urls)} YouTube video(s) to playlist...")

    try:
        manager = YouTubePlaylistManager(client_id, client_secret, playlist_id, refresh_token)
        results = manager.add_videos_to_playlist(video_urls)

        print(f"\nYouTube playlist update complete:")
        print(f"  Added: {results['added']}")
        print(f"  Already in playlist: {results['skipped']}")
        if results['failed'] > 0:
            print(f"  Failed: {results['failed']}")

    except Exception as e:
        print(f"Error adding videos to YouTube playlist: {e}")
