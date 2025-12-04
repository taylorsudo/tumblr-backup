#!/usr/bin/env python
"""
Tumblr Backup Script
Backs up Tumblr posts to markdown files using the Tumblr API v2
"""

import os
import json
import requests
from requests_oauthlib import OAuth1
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import List, Dict, Any, Set, Optional
import time
import re
from urllib.parse import urlparse


class TumblrBackup:
    def __init__(self, blog_identifier: str, api_key: str, output_dir: str = "backup",
                 download_images: bool = True, download_videos: bool = True, download_audio: bool = True,
                 consumer_secret: Optional[str] = None, oauth_token: Optional[str] = None,
                 oauth_token_secret: Optional[str] = None, incremental_hours: Optional[int] = 5):
        """
        Initialize the Tumblr backup tool

        Args:
            blog_identifier: Your Tumblr username
            api_key: Your Tumblr API consumer key
            output_dir: Directory to save backup files
            download_images: Whether to download images locally
            download_videos: Whether to download videos locally
            download_audio: Whether to download audio files locally
            consumer_secret: OAuth consumer secret (required for private blogs)
            oauth_token: OAuth token (required for private blogs)
            oauth_token_secret: OAuth token secret (required for private blogs)
            incremental_hours: Only fetch posts from the last N hours (default: 5, set to None for full backup)
        """
        self.blog_identifier = blog_identifier
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.base_url = "https://api.tumblr.com/v2"
        self.download_images = download_images
        self.download_videos = download_videos
        self.download_audio = download_audio
        self.incremental_hours = incremental_hours
        self.tz = ZoneInfo("Australia/Sydney")

        # OAuth credentials for private blogs
        self.consumer_secret = consumer_secret
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret

        # Setup OAuth if credentials provided
        self.auth = None
        if all([consumer_secret, oauth_token, oauth_token_secret]):
            self.auth = OAuth1(
                client_key=api_key,
                client_secret=consumer_secret,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret
            )
            print("Using OAuth authentication for private blog access")

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
            "limit": min(limit, 20),
            "offset": offset,
            "npf": "true"  # Use Neue Post Format for better content structure
        }

        # Add api_key only if not using OAuth
        if not self.auth:
            params["api_key"] = self.api_key

        try:
            response = requests.get(url, params=params, auth=self.auth)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching posts: {e}")
            return None

    def fetch_all_posts(self) -> List[Dict[str, Any]]:
        """
        Fetch all posts from the blog with pagination
        If incremental_hours is set, only fetch posts from the last N hours

        Returns:
            List of all posts
        """
        all_posts = []
        offset = 0
        limit = 20

        # Calculate cutoff time if incremental mode
        cutoff_timestamp = None
        if self.incremental_hours:
            cutoff_timestamp = int(time.time()) - (self.incremental_hours * 3600)
            print(f"Fetching posts from the last {self.incremental_hours} hours...")
        else:
            print(f"Fetching posts from {self.blog_identifier}...")

        while True:
            response = self.fetch_posts(limit=limit, offset=offset)

            if not response or "response" not in response:
                break

            posts = response["response"].get("posts", [])
            if not posts:
                break

            # If incremental mode, filter and check if we've gone past the cutoff
            if cutoff_timestamp:
                # Filter posts that are newer than cutoff
                new_posts = [p for p in posts if p.get("timestamp", 0) >= cutoff_timestamp]
                all_posts.extend(new_posts)

                # If we got fewer posts than requested, or the oldest post is before cutoff, we're done
                if len(new_posts) < len(posts) or (posts and posts[-1].get("timestamp", 0) < cutoff_timestamp):
                    print(f"Reached cutoff time. Total posts fetched: {len(all_posts)}")
                    break
            else:
                all_posts.extend(posts)

            print(f"Fetched {len(all_posts)} posts so far...")

            # Check if we've fetched all posts
            if not cutoff_timestamp:
                total_posts = response["response"].get("total_posts", 0)
                if len(all_posts) >= total_posts:
                    break

            offset += limit

            # Respect rate limits (300 per minute, 1000 per hour)
            time.sleep(0.2)  # Small delay between requests

        if not cutoff_timestamp:
            print(f"Total posts fetched: {len(all_posts)}")
        return all_posts

    def download_attachments(self, attachments_url: str, attachments_dir: Path) -> str:
        """
        Download a attachments file and save it locally

        Args:
            attachments_url: URL of the attachments to download
            attachments_dir: Directory to save the attachments file

        Returns:
            Relative path to the saved attachments file
        """
        try:
            # Parse URL to get filename
            parsed_url = urlparse(attachments_url)
            filename = os.path.basename(parsed_url.path)

            # Ensure attachments directory exists
            attachments_dir.mkdir(parents=True, exist_ok=True)

            attachments_path = attachments_dir / filename

            # Skip if already downloaded
            if attachments_path.exists():
                return f"Attachments/{filename}"

            # Download the attachments
            response = requests.get(attachments_url, timeout=30, stream=True)
            response.raise_for_status()

            # Check file size (skip if > 100MB)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 100 * 1024 * 1024:
                print(f"Warning: File too large (>100MB), skipping.")
                return attachments_url

            with open(attachments_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return f"Attachments/{filename}"

        except Exception as e:
            print(f"Warning: Failed to download attachments: {e}")
            return attachments_url  # Return original URL as fallback

    def is_external_attachments(self, url: str, attachments_type: str) -> bool:
        """
        Check if attachments URL is external (YouTube, Vimeo, Spotify, etc.)

        Args:
            url: Attachments URL
            attachments_type: Type of attachments (video or audio)

        Returns:
            True if external, False otherwise
        """
        if attachments_type == "video":
            return any(domain in url.lower() for domain in ['youtube.com', 'youtu.be', 'vimeo.com', 'instagram.com'])
        elif attachments_type == "audio":
            return any(domain in url.lower() for domain in ['spotify.com', 'soundcloud.com', 'bandcamp.com'])
        return False

    def process_npf_content_blocks(self, blocks: List[Dict[str, Any]], attachments_dir: Path, quote_level: int = 0) -> List[str]:
        """
        Process NPF content blocks and convert them to markdown

        Args:
            blocks: List of NPF content blocks
            attachments_dir: Directory to save attachments files
            quote_level: Level of quote nesting (0 = no quotes, 1 = >, 2 = >>, etc.)

        Returns:
            List of markdown lines
        """
        lines = []
        quote_prefix = ">" * quote_level if quote_level > 0 else ""

        for block in blocks:
            block_type = block.get("type", "")

            if block_type == "text":
                text = block.get("text", "")
                if text:
                    # Handle formatting
                    subtype = block.get("subtype", "")

                    # Apply subtype formatting (headings, etc.)
                    if subtype == "heading1":
                        text = f"# {text}"
                    elif subtype == "heading2":
                        text = f"## {text}"
                    elif subtype == "quote":
                        text = f"> {text}"
                    elif subtype == "indented":
                        text = f"  {text}"
                    elif subtype == "chat":
                        text = f"**{text}**"

                    # Split text into lines and add quote prefix to each
                    for line in text.split("\n"):
                        lines.append(f"{quote_prefix}{line}")

            elif block_type == "image":
                media = block.get("media", [])
                if media:
                    # Get the largest available size
                    url = media[0].get("url", "")
                    if url:
                        if self.download_images:
                            image_path = self.download_attachments(url, attachments_dir)
                            lines.append(f"{quote_prefix}![Image]({image_path})")
                        else:
                            lines.append(f"{quote_prefix}![Image]({url})")

            elif block_type == "video":
                media = block.get("media", {})
                url = media.get("url", "")
                if url:
                    if self.download_videos and not self.is_external_attachments(url, "video"):
                        video_path = self.download_attachments(url, attachments_dir)
                        lines.append(f"{quote_prefix}[Video]({video_path})")
                    else:
                        lines.append(f"{quote_prefix}[Video]({url})")

            elif block_type == "audio":
                media = block.get("media", {})
                url = media.get("url", "")
                if url:
                    if self.download_audio and not self.is_external_attachments(url, "audio"):
                        audio_path = self.download_attachments(url, attachments_dir)
                        lines.append(f"{quote_prefix}[Audio]({audio_path})")
                    else:
                        lines.append(f"{quote_prefix}[Audio]({url})")

            elif block_type == "link":
                url = block.get("url", "")
                title = block.get("title", url)
                if url:
                    lines.append(f"{quote_prefix}[{title}]({url})")

        return lines

    def convert_to_markdown(self, post: Dict[str, Any], attachments_dir: Path) -> str:
        """
        Convert a Tumblr post to markdown format

        Args:
            post: Post data from API
            attachments_dir: Directory to save attachments files for this post

        Returns:
            Markdown formatted string
        """
        md_content = []

        # Header with metadata
        post_type = post.get("type", "unknown")
        # post_id = post.get("id_string", post.get("id", "unknown"))
        timestamp = post.get("timestamp", 0)
        date = datetime.fromtimestamp(timestamp, tz=self.tz).strftime("%Y-%m-%d %H:%M:%S")
        tags = post.get("tags", [])
        # post_url = post.get("post_url", "")

        md_content.append("---")
        # md_content.append(f"post_id: {post_id}")
        # md_content.append(f"title: {post.get('summary', 'Untitled')}")
        md_content.append(f"date: {date}")
        # md_content.append(f"type: {post_type}")
        # md_content.append(f"url: {post_url}")
        if tags:
            md_content.append("tags:")
            for tag in tags:
                md_content.append(f"  - {tag}")
        md_content.append("---")
        md_content.append("")

        # Process reblog trail if it exists (for reblogs)
        trail = post.get("trail", [])
        if trail:
            # Process trail in original order (original first, most recent last)
            for i, trail_item in enumerate(trail):
                blog = trail_item.get("blog", {})
                blog_name = blog.get("name", "unknown")

                # Add username header
                md_content.append(f"{blog_name}:")

                # Process the content blocks with single quote level
                trail_content = trail_item.get("content", [])
                if trail_content:
                    trail_lines = self.process_npf_content_blocks(trail_content, attachments_dir, quote_level=1)
                    md_content.extend(trail_lines)
                    md_content.append("")

        # Process your own content (what you added when reblogging or original post content)
        content = post.get("content", [])
        if content:
            # Add horizontal rule before your content if there was a trail
            if trail:
                md_content.append("---")
                md_content.append("")
            content_lines = self.process_npf_content_blocks(content, attachments_dir, quote_level=0)
            md_content.extend(content_lines)

        # Fallback to legacy post type handling if no NPF content
        if not trail and not content:
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

                # Legacy photos field
                for photo in photos:
                    original_size = photo.get("original_size", {})
                    url = original_size.get("url", "")
                    if url:
                        # Download image if enabled
                        if self.download_images:
                            image_path = self.download_attachments(url, attachments_dir)
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
                    if self.download_videos and not self.is_external_attachments(video_url, "video"):
                        video_path = self.download_attachments(video_url, attachments_dir)
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
                    if self.download_audio and not self.is_external_attachments(audio_url, "audio"):
                        audio_path = self.download_attachments(audio_url, attachments_dir)
                        md_content.append(f"[Audio]({audio_path})")
                    else:
                        md_content.append(f"[Audio]({audio_url})")
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
        Save a single post to its own markdown file with attachments in a subfolder

        Args:
            post: Post data from API
        """
        timestamp = post.get("timestamp", 0)
        date = datetime.fromtimestamp(timestamp, tz=self.tz)
        post_id = post.get("id_string", post.get("id", "unknown"))

        # Get post title and sanitize
        title = post.get("summary", post.get("title", "Untitled"))
        if title == "Untitled" or not title:
            title = f"post-{post_id}"
        safe_title = self.sanitize_filename(title)

        # Create directory structure: yyyy/mm/dd/
        year = date.strftime("%Y")
        month = date.strftime("%m")
        day = date.strftime("%d")
        time_str = date.strftime("%H-%M")

        post_dir = self.output_dir / year / month / day
        post_dir.mkdir(parents=True, exist_ok=True)

        # Create filename
        filename = f"{time_str}-{safe_title}.md"
        filepath = post_dir / filename

        # Skip if already exists
        if filepath.exists():
            return

        # Create attachments directory for this post
        attachments_dir = post_dir / "Attachments"

        # Convert to markdown
        markdown_content = self.convert_to_markdown(post, attachments_dir)

        # Save the markdown file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_content)

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
    incremental_hours = config.get("incremental_hours", 5)  # Default 5 hours, set to None for full backup

    # OAuth credentials for private blogs
    consumer_secret = config.get("consumer_secret")
    oauth_token = config.get("oauth_token")
    oauth_token_secret = config.get("oauth_token_secret")

    if not blog_identifier or not api_key:
        print("Error: blog_identifier and api_key are required in config.json")
        return

    # Create backup instance and run
    backup = TumblrBackup(
        blog_identifier,
        api_key,
        output_dir,
        download_images,
        download_videos,
        download_audio,
        consumer_secret,
        oauth_token,
        oauth_token_secret,
        incremental_hours
    )
    backup.backup()


if __name__ == "__main__":
    main()
