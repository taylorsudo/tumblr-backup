#!/usr/bin/env python3

import os
import re
import json
import time
import requests
from requests_oauthlib import OAuth1
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlparse
from download_utils import download_media


EARLIEST_DEFAULT = "2025-01-01"
MAX_RETRIES = 5
RATE_LIMIT_BASE_DELAY = 1.0


def sanitize_md(text: str) -> str:
    return text.replace("[", r"\[").replace("]", r"\]")


def parse_earliest(date_str: str, tz: ZoneInfo) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
    return int(dt.timestamp())
    
    
def best_media_url(media_list):
    if not media_list:
        return ""
    try:
        best = max(media_list, key=lambda m: m.get("width", 0))
        return best.get("url", media_list[0].get("url", ""))
    except (ValueError, IndexError):
        return ""


def requests_with_retry(method: str, url: str, max_retries: int = MAX_RETRIES, **kwargs):
    delay = RATE_LIMIT_BASE_DELAY

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.request(method, url, **kwargs)

            if r.status_code == 429:
                try:
                    wait = int(r.headers.get("Retry-After", delay))
                except ValueError:
                    wait = delay # Fallback to your base delay
                time.sleep(wait)
                delay *= 2
                continue

            r.raise_for_status()
            return r

        except requests.RequestException:
            if attempt == max_retries:
                return None
            time.sleep(delay * (2 ** (attempt - 1)))

    return None


class TumblrBackup:
    def __init__(
        self,
        blog_identifier,
        api_key,
        output_dir="Tumblr",
        download_image=True,
        download_video=True,
        download_audio=True,
        consumer_secret=None,
        oauth_token=None,
        oauth_token_secret=None,
        incremental_hours=24,
        earliest_date=EARLIEST_DEFAULT,
        delete_after_backup=False,
    ):
        self.blog_identifier = blog_identifier
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.base_url = "https://api.tumblr.com/v2"

        self.download_image = download_image
        self.download_video = download_video
        self.download_audio = download_audio

        self.incremental_hours = incremental_hours
        self.delete_after_backup = delete_after_backup

        self.tz = ZoneInfo("Australia/Sydney")
        self.earliest_timestamp = parse_earliest(earliest_date, self.tz)

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

    def fetch_posts(self, limit=20, before=None): # Changed offset to before
        url = f"{self.base_url}/blog/{self.blog_identifier}/posts"
        params = {
            "limit": min(limit, 20),
            "before": before, # Use timestamp instead of offset
            "npf": "true",
            "notes_info": "true",
        }
        if not self.auth:
            params["api_key"] = self.api_key
    
        r = requests_with_retry("GET", url, params=params, auth=self.auth)
        return r.json() if r else None

    # ---------------- STREAM SAFE FETCH ----------------

    def fetch_all_posts(self):
        all_posts = []
        before = None 
        now = int(time.time())
        
        # This is the "cutoff" - only posts older than this will be processed
        window_ceiling = now - (self.incremental_hours * 3600)
        
        while True:
            resp = self.fetch_posts(limit=20, before=before)
            if not resp: break
            
            posts = resp["response"].get("posts", [])
            if not posts: break
    
            # Filter: Post must be older than the ceiling AND newer than your earliest start date
            filtered = [
                p for p in posts 
                if self.earliest_timestamp <= p.get("timestamp", 0) <= window_ceiling
            ]
            
            # Since Tumblr returns newest first, and we want to save chronological daily files,
            # we keep them in reverse order to append correctly later.
            all_posts.extend(reversed(filtered))
    
            before = posts[-1].get("timestamp")
            
            # If the oldest post in this batch is already past our earliest backup date, stop.
            if before < self.earliest_timestamp:
                break
            time.sleep(0.2)
        return all_posts

    # ---------------- ATTACHMENTS ----------------

    def download_attachment(self, url: str, folder: Path, ts: int) -> str:
        try:
            ext = os.path.splitext(urlparse(url).path)[1].lower() or ""
            
            # Category Check
            if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tiff", ".bmp", ".svg", ".heic", ".heif", ".avif"}:
                subfolder = "Images"
            elif ext in {".mp4", ".mov", ".webm", ".mkv", ".avi", ".wmv", ".m4v", ".mpg", ".mpeg", ".3gp"}:
                subfolder = "Videos"
            elif ext in {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".aiff", ".m4b"}:
                subfolder = "Audio"
            else:
                subfolder = "" # Other files go to Attachment root

            # Logic to create directory
            target_dir = folder / subfolder if subfolder else folder
            target_dir.mkdir(parents=True, exist_ok=True)

            base = datetime.fromtimestamp(ts, tz=self.tz).strftime("%Y-%m-%d-%H%M%S")
            path = target_dir / f"{base}{ext}"

            i = 1
            while path.exists():
                path = target_dir / f"{base}-{i}{ext}"
                i += 1

            r = requests_with_retry("GET", url, stream=True)
            if not r: return url

            with open(path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)

            # Construct relative path for Markdown
            # If subfolder is empty, it just returns "Attachments/filename.ext"
            rel_path = f"Attachments/{subfolder}/{path.name}" if subfolder else f"Attachments/{path.name}"
            return rel_path

        except Exception:
            return url
    
    # ---------------- NOTES ----------------

    def _format_notes(self, post):
        # 1. Filter Check: Only record notes if the post belongs to your blog
        # 'blog_name' in the post object refers to the author of the post
        if post.get("blog_name", "").lower() != self.blog_identifier.lower():
            return ""

        notes = post.get("notes", [])
        post_ts = post.get("timestamp", 0)

        # Only process notes that happened at or after the post time
        filtered = [n for n in notes if n.get("timestamp", 0) >= post_ts]

        # Extract Likes
        likes = [
            f"[{n.get('blog_name','unknown')}](https://www.tumblr.com/{n.get('blog_name','unknown')})"
            for n in filtered if n.get("type") == "like"
        ]

        # Extract Reblogs
        reblogs = [
            f"[{n.get('blog_name','unknown')}](https://www.tumblr.com/{n.get('blog_name','unknown')})"
            for n in filtered if n.get("type") == "reblog"
        ]

        # Extract and sort Replies
        replies = [n for n in filtered if n.get("type") == "reply"]
        replies.sort(key=lambda x: x.get("timestamp", 0))

        out = []

        # 2. Formatting with extra line breaks
        if likes:
            out.append("**Likes:** " + ", ".join(likes))

        if reblogs:
            # Join with \n\n for an extra line break between sections
            out.append("**Reblogs:** " + ", ".join(reblogs))

        if replies:
            reply_blocks = []
            for r in replies:
                user = f"[{r.get('blog_name','unknown')}](https://www.tumblr.com/{r.get('blog_name','unknown')})"
                text = sanitize_md(r.get("reply_text", ""))
                reply_blocks.append(f"{user} replied:\n> {text}")
            out.extend(reply_blocks)

        # Join all existing sections with double newlines
        return "\n\n".join(out).strip()

    # ---------------- CONTENT ----------------

    def _process_blocks(self, blocks, attachments_dir: Path, ts: int):
        out = []
        for block in blocks:
            b_type = block.get("type")
            
            if b_type == "text":
                text = sanitize_md(block.get("text", ""))
                subtype = block.get("subtype", "")
                prefix = {
                    "heading1": "# ",
                    "heading2": "## ",
                    "quote": "> ",
                    "unordered": "- ",
                    "ordered": "1. ",
                }.get(subtype, "")
                out.append(f"{prefix}{text}")
    
            elif b_type in ["video", "audio"]:
                should_download = getattr(self, f"download_{b_type}", False)
                provider = block.get("provider", "").lower()
                url = block.get("url") or block.get("embed_url") or best_media_url(block.get("media", []))
    
                if url and should_download:
                    # Add spotify to the check
                    external_providers = ["youtube", "vimeo", "bandcamp", "soundcloud", "spotify"]
                    
                    if any(p in provider or p in url for p in external_providers):
                        url = download_media(url, attachments_dir)
                    else:
                        url = self.download_attachment(url, attachments_dir, ts)
                
                if url:
                    label = b_type.capitalize()
                    out.append(f"![{label}]({url})")
            
            elif b_type == "image":
                should_download = getattr(self, "download_image", True)
                # NPF images often have a media list; we want the best quality
                url = best_media_url(block.get("media", []))
                
                if url and should_download:
                    url = self.download_attachment(url, attachments_dir, ts)
                
                if url:
                    out.append(f"![Image]({url})")
                
        return "\n".join(out)

    # ---------------- MARKDOWN ----------------

    def convert_to_markdown(self, post, attachments_dir: Path) -> str:
        md = []

        pid = str(post.get("id_string", post.get("id")))
        ts = post.get("timestamp", 0)

        md.append(f"<!-- tumblr-post-id: {pid} -->")
        md.append(f"## {datetime.fromtimestamp(ts, tz=self.tz).strftime('%H:%M')}")
        md.append("")

        # trail
        for item in post.get("trail", []):
            blog = item.get("blog", {}).get("name", "unknown")
            md.append(f"**{blog}:**")

            trail = self._process_blocks(item.get("content", []), attachments_dir, ts)
            md.append("\n".join([f"> {l}" if l.strip() else ">" for l in trail.split("\n")]))
            md.append("")

        content = post.get("content")
        # Check if content is None or an empty list
        if not content:
            content = [
                {
                    "type": "text", 
                    "text": (post.get("summary") or post.get("body") or post.get("caption") or "")
                }
            ]
        
        md.append(self._process_blocks(content, attachments_dir, ts))
        
        # ---------------- TAGS (FIXED) ----------------
        tags = post.get("tags", [])
        if tags:
            formatted = [f"`{t}`" if " " in t else t for t in tags]
            md.append(" ".join(formatted))

        # ---------------- NOTES ----------------
        notes_md = self._format_notes(post)
        if notes_md:
            md.append("")
            md.append(notes_md)

        return "\n".join(md)

    # ---------------- SAVE ----------------

    def save_daily_posts(self, date_key: str, posts):
        y, m, d = date_key.split("/")
        folder = self.output_dir / y / m
        folder.mkdir(parents=True, exist_ok=True)

        file = folder / f"{d}.md"
        attachments = folder / "Attachments"

        existing = file.read_text("utf-8") if file.exists() else ""
        seen = set(re.findall(r"<!-- tumblr-post-id: (\d+) -->", existing))

        new_blocks = []
        delete_queue = []

        for p in posts:
            pid = str(p.get("id_string", p.get("id")))

            if pid in seen:
                continue

            new_blocks.append(self.convert_to_markdown(p, attachments))
            new_blocks.append("\n---\n")

            if self.delete_after_backup:
                delete_queue.append(pid)

        if not new_blocks:
            return

        separator = "\n\n---\n\n" if existing.strip() else ""
        full = existing.rstrip() + separator + "\n".join(new_blocks).strip()

        tmp = file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(full)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp, file)

        print("Transaction complete")

        for pid in delete_queue:
            self.delete_post(pid)

    def delete_post(self, pid: str) -> bool:
        if not self.auth:
            return False

        url = f"{self.base_url}/blog/{self.blog_identifier}/post/delete"
        r = requests_with_retry(
            "POST",
            url,
            data={"id": pid, "blog-identifier": self.blog_identifier},
            auth=self.auth,
        )
        return r is not None

    # ---------------- ENTRY ----------------

    def backup(self):
        posts = self.fetch_all_posts()
        if not posts:
            return

        grouped = {}
        for p in posts:
            key = datetime.fromtimestamp(p["timestamp"], tz=self.tz).strftime("%Y/%m/%d")
            grouped.setdefault(key, []).append(p)

        for k, v in grouped.items():
            v.sort(key=lambda x: x.get("timestamp", 0))
            self.save_daily_posts(k, v)


def load_config():
    def b(k, d=False):
        v = os.environ.get(k)
        return v.lower() in ("1", "true", "yes") if v else d

    def i(k, d=None):
        v = os.environ.get(k)
        return int(v) if v else d

    cfg_file = Path("config.json")
    file_cfg = json.loads(cfg_file.read_text()) if cfg_file.exists() else {}

    def g(k, d=None):
        env_val = os.environ.get(k.upper())
        return env_val if env_val is not None else file_cfg.get(k, d)

    return {
        "blog_identifier": g("blog_identifier"),
        "api_key": g("api_key"),
        "output_dir": g("output_dir", "Tumblr"),
        "download_image": b("DOWNLOAD_IMAGE", True),
        "download_video": b("DOWNLOAD_VIDEO", True),
        "download_audio": b("DOWNLOAD_AUDIO", True),
        "incremental_hours": i("INCREMENTAL_HOURS", 24),
        "earliest_date": g("earliest_date", EARLIEST_DEFAULT),
        "delete_after_backup": b("DELETE_AFTER_BACKUP", False),
        "consumer_secret": g("consumer_secret"),
        "oauth_token": g("oauth_token"),
        "oauth_token_secret": g("oauth_token_secret"),
    }


def main():
    cfg = load_config()

    if not cfg["blog_identifier"] or not cfg["api_key"]:
        return

    backup = TumblrBackup(
        blog_identifier=cfg["blog_identifier"],
        api_key=cfg["api_key"],
        output_dir=cfg["output_dir"],
        download_image=cfg["download_image"],
        download_video=cfg["download_video"],
        download_audio=cfg["download_audio"],
        consumer_secret=cfg["consumer_secret"],
        oauth_token=cfg["oauth_token"],
        oauth_token_secret=cfg["oauth_token_secret"],
        incremental_hours=cfg["incremental_hours"],
        earliest_date=cfg["earliest_date"],
        delete_after_backup=cfg["delete_after_backup"],
    )

    backup.backup()


if __name__ == "__main__":
    main()