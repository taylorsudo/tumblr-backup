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
                 oauth_token_secret: Optional[str] = None, incremental_hours: Optional[int] = 5,
                 delete_after_backup: bool = False, add_to_youtube_playlist: bool = False):

        self.blog_identifier = blog_identifier
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.base_url = "https://api.tumblr.com/v2"
        self.download_images = download_images
        self.download_videos = download_videos
        self.download_audio = download_audio
        self.incremental_hours = incremental_hours
        self.delete_after_backup = delete_after_backup
        self.add_to_youtube_playlist = add_to_youtube_playlist
        self.youtube_urls: List[str] = []
        self.tz = ZoneInfo("Australia/Sydney")

        self.consumer_secret = consumer_secret
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret

        self.auth = None
        if all([consumer_secret, oauth_token, oauth_token_secret]):
            self.auth = OAuth1(
                client_key=api_key,
                client_secret=consumer_secret,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret
            )
            print("Using OAuth authentication for private blog access")

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch_posts(self, limit: int = 20, offset: int = 0) -> Dict[str, Any] | None:
        url = f"{self.base_url}/blog/{self.blog_identifier}/posts"
        params = {"limit": min(limit, 20), "offset": offset, "npf": "true"}

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
        all_posts = []
        offset = 0
        limit = 20

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

            if cutoff_timestamp:
                new_posts = [p for p in posts if p.get("timestamp", 0) >= cutoff_timestamp]
                all_posts.extend(new_posts)

                if len(new_posts) < len(posts) or (posts and posts[-1].get("timestamp", 0) < cutoff_timestamp):
                    break
            else:
                all_posts.extend(posts)

            if not cutoff_timestamp:
                total_posts = response["response"].get("total_posts", 0)
                if len(all_posts) >= total_posts:
                    break

            offset += limit
            time.sleep(0.2)

        return all_posts

    # ✅ FIXED
    def download_attachments(self, attachments_url: str, attachments_dir: Path, timestamp: int) -> str:
        try:
            parsed_url = urlparse(attachments_url)

            date = datetime.fromtimestamp(timestamp, tz=self.tz)
            base_filename = date.strftime("%Y-%m-%d-%H%M")

            ext = os.path.splitext(parsed_url.path)[1] or ""

            attachments_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{base_filename}{ext}"
            attachments_path = attachments_dir / filename

            counter = 1
            while attachments_path.exists():
                filename = f"{base_filename}-{counter}{ext}"
                attachments_path = attachments_dir / filename
                counter += 1

            response = requests.get(attachments_url, timeout=30, stream=True)
            response.raise_for_status()

            with open(attachments_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return f"Attachments/{filename}"

        except Exception as e:
            print(f"Warning: Failed to download attachments: {e}")
            return attachments_url

    def is_external_attachments(self, url: str, attachments_type: str) -> bool:
        if attachments_type == "video":
            return any(domain in url.lower() for domain in ['youtube.com', 'youtu.be', 'vimeo.com', 'instagram.com'])
        elif attachments_type == "audio":
            return any(domain in url.lower() for domain in ['spotify.com', 'soundcloud.com', 'bandcamp.com'])
        return False

    def is_youtube_url(self, url: str) -> bool:
        return 'youtube.com' in url.lower() or 'youtu.be' in url.lower()

    # ✅ UPDATED SIGNATURE
    def process_npf_content_blocks(self, blocks: List[Dict[str, Any]], attachments_dir: Path, timestamp: int, quote_level: int = 0) -> List[str]:
        lines = []
        quote_prefix = ">" * quote_level if quote_level > 0 else ""

        for i, block in enumerate(blocks):
            block_type = block.get("type", "")

            if block_type == "text":
                text = block.get("text", "")
                if text:
                    for line in text.split("\n"):
                        lines.append(f"{quote_prefix}{line}")
                    if i < len(blocks) - 1:
                        lines.append("")

            elif block_type == "image":
                media = block.get("media", [])
                if media:
                    url = media[0].get("url", "")
                    if url:
                        if self.download_images:
                            image_path = self.download_attachments(url, attachments_dir, timestamp)
                            lines.append(f"{quote_prefix}![Image]({image_path})")
                        else:
                            lines.append(f"{quote_prefix}![Image]({url})")
                        if i < len(blocks) - 1:
                            lines.append("")

            elif block_type == "video":
                media = block.get("media", {})
                url = media.get("url", "")
                if url:
                    if self.download_videos and not self.is_external_attachments(url, "video"):
                        video_path = self.download_attachments(url, attachments_dir, timestamp)
                        lines.append(f"{quote_prefix}[Video]({video_path})")
                    else:
                        lines.append(f"{quote_prefix}[Video]({url})")
                    if i < len(blocks) - 1:
                        lines.append("")

            elif block_type == "audio":
                media = block.get("media", {})
                url = media.get("url", "")
                if url:
                    if self.download_audio and not self.is_external_attachments(url, "audio"):
                        audio_path = self.download_attachments(url, attachments_dir, timestamp)
                        lines.append(f"{quote_prefix}[Audio]({audio_path})")
                    else:
                        lines.append(f"{quote_prefix}[Audio]({url})")
                    if i < len(blocks) - 1:
                        lines.append("")

        return lines

    def convert_to_markdown(self, post: Dict[str, Any], attachments_dir: Path, include_timestamp_heading: bool = True) -> str:
        md_content = []

        timestamp = post.get("timestamp", 0)
        date = datetime.fromtimestamp(timestamp, tz=self.tz)

        if include_timestamp_heading:
            md_content.append(f"## {date.strftime('%H:%M')}")
            md_content.append("")

        trail = post.get("trail", [])
        if trail:
            for trail_item in trail:
                blog_name = trail_item.get("blog", {}).get("name", "unknown")
                md_content.append(f"{blog_name}:")
                trail_lines = self.process_npf_content_blocks(
                    trail_item.get("content", []),
                    attachments_dir,
                    timestamp,
                    quote_level=1
                )
                md_content.extend(trail_lines)
                md_content.append("")

        content = post.get("content", [])
        if content:
            content_lines = self.process_npf_content_blocks(
                content,
                attachments_dir,
                timestamp,
                quote_level=0
            )
            md_content.extend(content_lines)

        return "\n".join(md_content)

    def get_daily_posts(self, posts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        daily_posts = {}
        for post in posts:
            timestamp = post.get("timestamp", 0)
            date = datetime.fromtimestamp(timestamp, tz=self.tz)
            date_key = date.strftime("%Y/%m/%d")

            daily_posts.setdefault(date_key, []).append(post)

        return daily_posts

    def save_daily_posts(self, date_key: str, posts: List[Dict[str, Any]]) -> None:
        year, month, day = date_key.split('/')

        day_dir = self.output_dir / year / month
        day_dir.mkdir(parents=True, exist_ok=True)

        filepath = day_dir / f"{day}-tumblr.md"

        attachments_dir = day_dir / "Attachments"

        daily_content = [f"# {year}-{month}-{day}", ""]

        for post in posts:
            post_md = self.convert_to_markdown(post, attachments_dir, True)
            daily_content.append(post_md)
            daily_content.append("\n---\n")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(daily_content))

    def backup(self) -> None:
        posts = self.fetch_all_posts()
        daily_posts = self.get_daily_posts(posts)

        for date_key, day_posts in daily_posts.items():
            self.save_daily_posts(date_key, day_posts)


def main():
    with open("config.json") as f:
        config = json.load(f)

    backup = TumblrBackup(
        config["blog_identifier"],
        config["api_key"],
        config.get("output_dir", "backup")
    )

    backup.backup()


if __name__ == "__main__":
    main()