#!/usr/bin/env python3
"""
Tumblr Backup Script
Backs up Tumblr posts to markdown files using the Tumblr API v2
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Set
import time
import re
from urllib.parse import urlparse


class TumblrBackup:
    def __init__(self, blog_identifier: str, api_key: str, output_dir: str = "backup",
                 download_images: bool = True, download_videos: bool = True, download_audio: bool = True):
        """
        Initialize the Tumblr backup tool

        Args:
            blog_identifier: Your blog name (e.g., 'yourblog.tumblr.com' or just 'yourblog')
            api_key: Your Tumblr API consumer key
            output_dir: Directory to save backup files
            download_images: Whether to download images locally
            download_videos: Whether to download videos locally
            download_audio: Whether to download audio files locally
        """
        self.blog_identifier = blog_identifier
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.base_url = "https://api.tumblr.com/v2"
        self.download_images = download_images
        self.download_videos = download_videos
        self.download_audio = download_audio

        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch_posts(self, limit: int = 20, offset: int = 0) -> Dict[str, Any] | None:
        """
        Fetch posts from Tumblr API

        Args:
            limit: Number of posts to fetch per request (max 20)
            offset: Offset for pagination

        Returns:
            API response as dictionary, or None if request fails
        """
        url = f"{self.base_url}/blog/{self.blog_identifier}/posts"
        params = {
            "api_key": self.api_key,
            "limit": min(limit, 20),
            "offset": offset,
            "npf": "true"  # Use Neue Post Format for better content structure
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching posts: {e}")
            return None

    def fetch_all_posts(self) -> List[Dict[str, Any]]:
        """
        Fetch all posts from the blog with pagination

        Returns:
            List of all posts
        """
        all_posts = []
        offset = 0
        limit = 20

        print(f"Fetching posts from {self.blog_identifier}...")

        while True:
            response = self.fetch_posts(limit=limit, offset=offset)

            if not response or "response" not in response:
                break

            posts = response["response"].get("posts", [])
            if not posts:
                break

            all_posts.extend(posts)
            print(f"Fetched {len(all_posts)} posts so far...")

            total_posts = response["response"].get("total_posts", 0)
            if len(all_posts) >= total_posts:
                break

            offset += limit

            # Respect rate limits (300 per minute, 1000 per hour)
            time.sleep(0.2)  # Small delay between requests

        print(f"Total posts fetched: {len(all_posts)}")
        return all_posts

    def download_media(self, media_url: str, media_dir: Path) -> str:
        """
        Download a media file and save it locally

        Args:
            media_url: URL of the media to download
            media_dir: Directory to save the media file

        Returns:
            Relative path to the saved media file
        """
        try:
            # Parse URL to get filename
            parsed_url = urlparse(media_url)
            filename = os.path.basename(parsed_url.path)

            # Ensure media directory exists
            media_dir.mkdir(parents=True, exist_ok=True)

            media_path = media_dir / filename

            # Skip if already downloaded
            if media_path.exists():
                return f"media/{filename}"

            # Download the media
            response = requests.get(media_url, timeout=30, stream=True)
            response.raise_for_status()

            # Check file size (skip if > 100MB)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 100 * 1024 * 1024:
                print(f"Warning: File too large (>100MB), skipping: {media_url}")
                return media_url

            with open(media_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return f"media/{filename}"

        except Exception as e:
            print(f"Warning: Failed to download media {media_url}: {e}")
            return media_url  # Return original URL as fallback

    def is_external_media(self, url: str, media_type: str) -> bool:
        """
        Check if media URL is external (YouTube, Vimeo, Spotify, etc.)

        Args:
            url: Media URL
            media_type: Type of media (video or audio)

        Returns:
            True if external, False otherwise
        """
        if media_type == "video":
            return any(domain in url.lower() for domain in ['youtube.com', 'youtu.be', 'vimeo.com', 'instagram.com'])
        elif media_type == "audio":
            return any(domain in url.lower() for domain in ['spotify.com', 'soundcloud.com', 'bandcamp.com'])
        return False

    def convert_to_markdown(self, post: Dict[str, Any], media_dir: Path) -> str:
        """
        Convert a Tumblr post to markdown format

        Args:
            post: Post data from API
            media_dir: Directory to save media files for this post

        Returns:
            Markdown formatted string
        """
        md_content = []

        # Header with metadata
        post_type = post.get("type", "unknown")
        post_id = post.get("id_string", post.get("id", "unknown"))
        timestamp = post.get("timestamp", 0)
        date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        tags = post.get("tags", [])
        post_url = post.get("post_url", "")

        md_content.append("---")
        md_content.append(f"post_id: {post_id}")
        md_content.append(f"title: {post.get('summary', 'Untitled')}")
        md_content.append(f"date: {date}")
        md_content.append(f"type: {post_type}")
        md_content.append(f"url: {post_url}")
        if tags:
            md_content.append("tags:")
            for tag in tags:
                md_content.append(f"  - {tag}")
        md_content.append("---")
        md_content.append("")

        # Handle different post types
        if post_type == "text":
            title = post.get("title", "")
            if title:
                md_content.append(f"## {title}")
                md_content.append("")
            body = post.get("body", "")
            md_content.append(body)

        elif post_type == "photo":
            caption = post.get("caption", "")
            if caption:
                md_content.append(caption)
                md_content.append("")

            photos = post.get("photos", [])
            for photo in photos:
                original_size = photo.get("original_size", {})
                url = original_size.get("url", "")
                if url:
                    # Download image if enabled
                    if self.download_images:
                        image_path = self.download_media(url, media_dir)
                        md_content.append(f"![Photo]({image_path})")
                    else:
                        md_content.append(f"![Photo]({url})")
                    md_content.append("")

        elif post_type == "quote":
            text = post.get("text", "")
            source = post.get("source", "")
            md_content.append(f"> {text}")
            md_content.append("")
            if source:
                md_content.append(f"— {source}")
                md_content.append("")

        elif post_type == "link":
            title = post.get("title", "")
            url = post.get("url", "")
            description = post.get("description", "")
            md_content.append(f"## [{title}]({url})")
            md_content.append("")
            if description:
                md_content.append(description)
                md_content.append("")

        elif post_type == "video":
            caption = post.get("caption", "")
            if caption:
                md_content.append(caption)
                md_content.append("")

            # Try to get video URL from different possible fields
            video_url = post.get("video_url", "")
            if not video_url and "player" in post:
                players = post.get("player", [])
                if players and isinstance(players, list):
                    video_url = players[-1].get("embed_code", "")
                    # Extract URL from embed code if needed
                    if video_url and "src=" in video_url:
                        import re
                        match = re.search(r'src="([^"]+)"', video_url)
                        if match:
                            video_url = match.group(1)

            if video_url:
                # Download video if enabled and not external
                if self.download_videos and not self.is_external_media(video_url, "video"):
                    video_path = self.download_media(video_url, media_dir)
                    md_content.append(f"[Video]({video_path})")
                else:
                    md_content.append(f"[Video]({video_url})")
                md_content.append("")

        elif post_type == "audio":
            caption = post.get("caption", "")
            artist = post.get("artist", "")
            track_name = post.get("track_name", "")

            if artist or track_name:
                md_content.append(f"## {artist} - {track_name}")
                md_content.append("")
            if caption:
                md_content.append(caption)
                md_content.append("")

            # Try to get audio URL
            audio_url = post.get("audio_url", "")
            if not audio_url and "audio_source_url" in post:
                audio_url = post.get("audio_source_url", "")

            if audio_url:
                # Download audio if enabled and not external
                if self.download_audio and not self.is_external_media(audio_url, "audio"):
                    audio_path = self.download_media(audio_url, media_dir)
                    md_content.append(f"[Audio]({audio_path})")
                else:
                    md_content.append(f"[Audio]({audio_url})")
                md_content.append("")

        else:
            # Fallback for other types or NPF content
            if "content" in post:
                for block in post.get("content", []):
                    block_type = block.get("type", "")
                    if block_type == "text":
                        text = block.get("text", "")
                        md_content.append(text)
                        md_content.append("")
                    elif block_type == "image":
                        media = block.get("media", [{}])[0]
                        url = media.get("url", "")
                        if url:
                            # Download image if enabled
                            if self.download_images:
                                image_path = self.download_media(url, media_dir)
                                md_content.append(f"![Image]({image_path})")
                            else:
                                md_content.append(f"![Image]({url})")
                            md_content.append("")
                    elif block_type == "video":
                        media = block.get("media", {})
                        url = media.get("url", "")
                        if url:
                            # Download video if enabled and not external
                            if self.download_videos and not self.is_external_media(url, "video"):
                                video_path = self.download_media(url, media_dir)
                                md_content.append(f"[Video]({video_path})")
                            else:
                                md_content.append(f"[Video]({url})")
                            md_content.append("")
                    elif block_type == "audio":
                        media = block.get("media", {})
                        url = media.get("url", "")
                        if url:
                            # Download audio if enabled and not external
                            if self.download_audio and not self.is_external_media(url, "audio"):
                                audio_path = self.download_media(url, media_dir)
                                md_content.append(f"[Audio]({audio_path})")
                            else:
                                md_content.append(f"[Audio]({url})")
                            md_content.append("")

        return "\n".join(md_content)

    def sanitize_filename(self, title: str) -> str:
        """
        Sanitize a title to be used as a filename

        Args:
            title: Post title

        Returns:
            Sanitized filename
        """
        # Remove or replace invalid characters
        title = re.sub(r'[<>:"/\\|?*]', '', title)
        # Replace spaces with hyphens
        title = title.replace(' ', '-')
        # Limit length
        title = title[:100]
        # Remove trailing hyphens
        title = title.strip('-')
        return title if title else "untitled"

    def save_post(self, post: Dict[str, Any]) -> None:
        """
        Save a single post to its own markdown file with media in a subfolder

        Args:
            post: Post data from API
        """
        timestamp = post.get("timestamp", 0)
        date = datetime.fromtimestamp(timestamp)
        post_id = post.get("id_string", post.get("id", "unknown"))

        # Get post title and sanitize
        title = post.get("summary", post.get("title", "Untitled"))
        if title == "Untitled" or not title:
            title = f"post-{post_id}"
        safe_title = self.sanitize_filename(title)

        # Create directory structure: yyyy/yyyy-mm/yyyy-mm-dd/
        year = date.strftime("%Y")
        year_month = date.strftime("%Y-%m")
        date_str = date.strftime("%Y-%m-%d")

        post_dir = self.output_dir / year / year_month / date_str
        post_dir.mkdir(parents=True, exist_ok=True)

        # Create filename
        filename = f"{safe_title}.md"
        filepath = post_dir / filename

        # Skip if already exists
        if filepath.exists():
            print(f"Skipping existing post: {filepath}")
            return

        # Create media directory for this post
        media_dir = post_dir / "media"

        # Convert to markdown
        markdown_content = self.convert_to_markdown(post, media_dir)

        # Save the markdown file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        print(f"Saved: {filepath}")

    def backup(self) -> None:
        """
        Perform full backup of all posts
        """
        posts = self.fetch_all_posts()

        if not posts:
            print("No posts to backup.")
            return

        print(f"\nSaving {len(posts)} posts to {self.output_dir}...")

        # Save each post to its own file
        for post in posts:
            self.save_post(post)

        print(f"\nBackup complete! Posts saved to {self.output_dir.absolute()}")


def main():
    """
    Main function to run the backup
    """
    # Load configuration
    config_file = Path("config.json")

    if not config_file.exists():
        print("Error: config.json not found!")
        print("Please create a config.json file with your Tumblr API credentials.")
        print("See config.example.json for the required format.")
        return

    with open(config_file, "r") as f:
        config = json.load(f)

    blog_identifier = config.get("blog_identifier")
    api_key = config.get("api_key")
    output_dir = config.get("output_dir", "backup")
    download_images = config.get("download_images", True)
    download_videos = config.get("download_videos", True)
    download_audio = config.get("download_audio", True)

    if not blog_identifier or not api_key:
        print("Error: blog_identifier and api_key are required in config.json")
        return

    # Create backup instance and run
    backup = TumblrBackup(blog_identifier, api_key, output_dir, download_images, download_videos, download_audio)
    backup.backup()


if __name__ == "__main__":
    main()
