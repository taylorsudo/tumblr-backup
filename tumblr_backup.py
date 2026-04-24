#!/usr/bin/env python
"""
Tumblr Backup Script
"""

import os
import json
import requests
from requests_oauthlib import OAuth1
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import List, Dict, Any, Optional
import time
from urllib.parse import urlparse

try:
    from youtube_playlist import add_youtube_videos_to_playlist
except ImportError:
    add_youtube_videos_to_playlist = None


class TumblrBackup:
    def __init__(
        self,
        blog_identifier: str,
        api_key: str,
        output_dir: str = "backup",
        download_images: bool = True,
        download_videos: bool = True,
        download_audio: bool = True,
        consumer_secret: Optional[str] = None,
        oauth_token: Optional[str] = None,
        oauth_token_secret: Optional[str] = None,
        incremental_hours: Optional[int] = 5,
        delete_after_backup: bool = False,
        add_to_youtube_playlist: bool = False,
    ):
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
        self.youtube_urls: set[str] = set()
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
                resource_owner_secret=oauth_token_secret,
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ---------------- API ----------------

    def fetch_posts(self, limit=20, offset=0):
        url = f"{self.base_url}/blog/{self.blog_identifier}/posts"
        params = {"limit": min(limit, 20), "offset": offset, "npf": "true"}

        if not self.auth:
            params["api_key"] = self.api_key

        retries = 0

        while True:
            try:
                r = requests.get(url, params=params, auth=self.auth)

                if r.status_code in (401, 403):
                    raise RuntimeError("Authentication failed (check API key or OAuth credentials)")

                if r.status_code == 429:
                    wait = int(r.headers.get("Retry-After", 60))
                    print(f"Rate limited. Sleeping {wait}s...")
                    time.sleep(wait)
                    retries += 1
                    if retries > 5:
                        raise RuntimeError("Exceeded retry limit (429)")
                    continue

                r.raise_for_status()
                return r.json()

            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"API request failed: {e}")

    def fetch_all_posts(self):
        all_posts = []
        offset = 0
        limit = 20

        EARLIEST = int(datetime(2025, 1, 1, tzinfo=self.tz).timestamp())

        cutoff = None
        if self.incremental_hours:
            cutoff = int(time.time()) - self.incremental_hours * 3600

        while True:
            res = self.fetch_posts(limit, offset)

            if "response" not in res:
                raise RuntimeError("Malformed API response")

            posts = res["response"].get("posts", [])
            if not posts:
                break

            valid_in_batch = False

            for p in posts:
                ts = p.get("timestamp", 0)

                if cutoff:
                    if EARLIEST <= ts <= cutoff:
                        all_posts.append(p)
                        valid_in_batch = True
                else:
                    if ts >= EARLIEST:
                        all_posts.append(p)
                        valid_in_batch = True

            if not valid_in_batch:
                break

            offset += limit
            time.sleep(0.2)

        return all_posts

    # ---------------- MEDIA ----------------

    def download_attachments(self, url, directory, timestamp, index=0):
        try:
            directory.mkdir(parents=True, exist_ok=True)

            ext = os.path.splitext(urlparse(url).path)[1] or ""
            base = datetime.fromtimestamp(timestamp, tz=self.tz).strftime(
                "%Y-%m-%d-%H%M%S"
            )

            filename = f"{base}-{index}{ext}" if index else f"{base}{ext}"
            path = directory / filename

            counter = 1
            while path.exists():
                path = directory / f"{base}-{index}-{counter}{ext}"
                counter += 1

            r = requests.get(url, stream=True, timeout=30)
            r.raise_for_status()

            with open(path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)

            return f"Attachments/{path.name}"

        except Exception:
            return url

    def is_external_attachments(self, url, t):
        if t == "video":
            return any(x in url.lower() for x in ["youtube.com", "youtu.be", "vimeo.com"])
        if t == "audio":
            return any(x in url.lower() for x in ["spotify.com", "soundcloud.com"])
        return False

    def is_youtube_url(self, url):
        return any(x in url.lower() for x in ["youtube.com", "youtu.be"])

    # ---------------- NPF ----------------

    def process_npf_content_blocks(self, blocks, dir, ts, quote_level=0):
        lines = []
        prefix = ">" * quote_level if quote_level else ""

        for i, b in enumerate(blocks):
            t = b.get("type")

            if t == "text":
                text = b.get("text", "")
                subtype = b.get("subtype", "")

                if subtype == "heading1":
                    text = f"# {text}"
                elif subtype == "heading2":
                    text = f"## {text}"
                elif subtype == "quote":
                    text = f"> {text}"
                elif subtype == "unordered":
                    text = f"- {text}"
                elif subtype == "ordered":
                    text = f"1. {text}"

                for line in text.split("\n"):
                    lines.append(prefix + line)

            elif t in ["image", "video", "audio"]:
                media = b.get("media", [])
                url = media[0].get("url", "") if media else ""
                if not url:
                    continue

                if t == "image":
                    path = (
                        self.download_attachments(url, dir, ts, i)
                        if self.download_images
                        else url
                    )
                    lines.append(f"{prefix}![Image]({path})")
                else:
                    label = "Video" if t == "video" else "Audio"

                    if t == "video" and self.add_to_youtube_playlist and self.is_youtube_url(url):
                        self.youtube_urls.add(url)

                    if (
                        (t == "video" and self.download_videos)
                        or (t == "audio" and self.download_audio)
                    ) and not self.is_external_attachments(url, t):
                        path = self.download_attachments(url, dir, ts, i)
                    else:
                        path = url

                    lines.append(f"{prefix}[{label}]({path})")

            elif t == "link":
                url = b.get("url")
                title = b.get("title", url)
                lines.append(f"{prefix}[{title}]({url})")

            if i < len(blocks) - 1:
                lines.append("")

        return lines

    # ---------------- MARKDOWN ----------------

    def convert_to_markdown(self, post, dir):
        md = []
        ts = post.get("timestamp", 0)
        dt = datetime.fromtimestamp(ts, tz=self.tz)

        md.append(f"## {dt.strftime('%H:%M')}")
        md.append("")

        content = post.get("content", [])
        if content:
            md.extend(self.process_npf_content_blocks(content, dir, ts))

        return "\n".join(md)

    # ---------------- FILE WRITING ----------------

    def save_daily_posts(self, date_key, posts):
        y, m, d = date_key.split("/")
        base = self.output_dir / y / m / "Tumblr"
        base.mkdir(parents=True, exist_ok=True)

        file = base / f"{d}.md"
        attachments = base / "Attachments"

        existing_ids = set()
        if file.exists():
            with open(file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("<!--ID:"):
                        existing_ids.add(line.strip())

        new_blocks = []

        for p in posts:
            pid = str(p.get("id"))
            marker = f"<!--ID:{pid}-->"
            if marker in existing_ids:
                continue

            new_blocks.append(
                "\n\n".join([
                    marker,
                    self.convert_to_markdown(p, attachments)
                ])
            )

            if self.delete_after_backup:
                self.delete_post(pid)

        if not new_blocks:
            return

        new_content = "\n\n---\n\n".join(new_blocks)

        if file.exists() and file.stat().st_size > 0:
            with open(file, "a", encoding="utf-8") as f:
                f.write("\n\n---\n\n" + new_content)
        else:
            with open(file, "w", encoding="utf-8") as f:
                f.write(new_content)

    # ---------------- DELETE ----------------

    def delete_post(self, post_id):
        if not self.auth:
            return False
        try:
            r = requests.post(
                f"{self.base_url}/blog/{self.blog_identifier}/post/delete",
                data={"id": post_id},
                auth=self.auth,
            )
            return r.status_code == 200
        except Exception:
            return False

    # ---------------- RUN ----------------

    def backup(self):
        posts = self.fetch_all_posts()

        grouped = {}
        for p in posts:
            key = datetime.fromtimestamp(p["timestamp"], tz=self.tz).strftime("%Y/%m/%d")
            grouped.setdefault(key, []).append(p)

        for k, v in grouped.items():
            v.sort(key=lambda x: x["timestamp"])
            self.save_daily_posts(k, v)

        return list(self.youtube_urls)


# ---------------- MAIN ----------------

def main():
    try:
        with open("config.json") as f:
            config = json.load(f)

        tb = TumblrBackup(
            config["blog_identifier"],
            config["api_key"],
            config.get("output_dir", "backup"),
            config.get("download_images", True),
            config.get("download_videos", True),
            config.get("download_audio", True),
            config.get("consumer_secret"),
            config.get("oauth_token"),
            config.get("oauth_token_secret"),
            config.get("incremental_hours", 5),
            config.get("delete_after_backup", False),
            config.get("add_to_youtube_playlist", False),
        )

        urls = tb.backup()

        if config.get("add_to_youtube_playlist") and urls:
            if add_youtube_videos_to_playlist:
                add_youtube_videos_to_playlist(
                    urls,
                    config.get("youtube_client_id"),
                    config.get("youtube_client_secret"),
                    config.get("youtube_playlist_id"),
                    config.get("youtube_refresh_token"),
                )
            else:
                print("Warning: youtube_playlist module not available")

    except RuntimeError as e:
        print(f"FAILED: {e}")
    except FileNotFoundError:
        print("Error: config.json not found.")


if __name__ == "__main__":
    main()