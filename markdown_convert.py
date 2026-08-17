from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from attachments import download_attachment
from download_utils import download_media


def sanitize_md(text: str) -> str:
    return text.replace("[", r"\[").replace("]", r"\]")


def best_media_url(media_list):
    if not media_list:
        return ""
    try:
        best = max(media_list, key=lambda m: m.get("width", 0))
        return best.get("url", media_list[0].get("url", ""))
    except (ValueError, IndexError):
        return ""


class MarkdownConverter:
    """Converts Tumblr NPF posts into Markdown, downloading attachments as needed."""

    EXTERNAL_PROVIDERS = ["youtube", "vimeo", "bandcamp", "soundcloud", "spotify"]

    TEXT_BLOCK_PREFIXES = {
        "heading1": "# ",
        "heading2": "## ",
        "quote": "> ",
        "unordered": "- ",
        "ordered": "1. ",
    }

    def __init__(self, blog_identifier, tz: ZoneInfo, download_image=True, download_video=True, download_audio=True):
        self.blog_identifier = blog_identifier
        self.tz = tz
        self.download_image = download_image
        self.download_video = download_video
        self.download_audio = download_audio

    # ---------------- CONTENT ----------------

    def _process_blocks(self, blocks, attachments_dir: Path, ts: int) -> str:
        out = []
        for block in blocks:
            b_type = block.get("type")

            if b_type == "text":
                text = sanitize_md(block.get("text", ""))
                subtype = block.get("subtype", "")
                prefix = self.TEXT_BLOCK_PREFIXES.get(subtype, "")
                out.append(f"{prefix}{text}")

            elif b_type in ("video", "audio"):
                should_download = getattr(self, f"download_{b_type}", False)
                provider = block.get("provider", "").lower()

                # Order of priority: explicit url -> embed_url -> media object
                url = block.get("url") or block.get("embed_url")
                if not url:
                    url = best_media_url(block.get("media", []))

                # Extract Metadata (Title/Artist) for Audio
                title = block.get("title")
                artist = block.get("artist")
                label = f"{artist} - {title}" if (artist and title) else (title or b_type.capitalize())

                if url and should_download:
                    is_external = any(p in provider for p in self.EXTERNAL_PROVIDERS) or \
                                  any(p in url.lower() for p in self.EXTERNAL_PROVIDERS)

                    if is_external:
                        # Pass the metadata to the downloader if it's Spotify/Audio
                        url = download_media(url, attachments_dir)
                    else:
                        # Native Tumblr content
                        url = download_attachment(url, attachments_dir, ts, self.tz)

                if url:
                    out.append(f"![{label}]({url})")

            elif b_type == "image":
                should_download = self.download_image
                # NPF images often have a media list; we want the best quality
                url = best_media_url(block.get("media", []))

                if url and should_download:
                    url = download_attachment(url, attachments_dir, ts, self.tz)

                if url:
                    out.append(f"![Image]({url})")

        return "\n".join(out)

    # ---------------- NOTES ----------------

    def _format_notes(self, post) -> str:
        # Only record notes if the post belongs to this blog
        if post.get("blog_name", "").lower() != self.blog_identifier.lower():
            return ""

        notes = post.get("notes", [])
        post_ts = post.get("timestamp", 0)

        # Only process notes that happened at or after the post time
        filtered = [n for n in notes if n.get("timestamp", 0) >= post_ts]

        likes = [
            f"[{n.get('blog_name','unknown')}](https://www.tumblr.com/{n.get('blog_name','unknown')})"
            for n in filtered if n.get("type") == "like"
        ]

        reblogs = [
            f"[{n.get('blog_name','unknown')}](https://www.tumblr.com/{n.get('blog_name','unknown')})"
            for n in filtered if n.get("type") == "reblog"
        ]

        replies = [n for n in filtered if n.get("type") == "reply"]
        replies.sort(key=lambda x: x.get("timestamp", 0))

        out = []

        if likes:
            out.append("**Likes:** " + ", ".join(likes))

        if reblogs:
            out.append("**Reblogs:** " + ", ".join(reblogs))

        if replies:
            reply_blocks = []
            for r in replies:
                user = f"[{r.get('blog_name','unknown')}](https://www.tumblr.com/{r.get('blog_name','unknown')})"
                text = sanitize_md(r.get("reply_text", ""))
                reply_blocks.append(f"{user} replied:\n> {text}")
            out.extend(reply_blocks)

        return "\n\n".join(out).strip()

    # ---------------- MARKDOWN ----------------

    def convert_to_markdown(self, post, attachments_dir: Path) -> str:
        md = []

        pid = str(post.get("id_string", post.get("id")))
        ts = post.get("timestamp", 0)

        md.append(f"<!-- tumblr-post-id: {pid} -->")
        md.append(f"## {datetime.fromtimestamp(ts, tz=self.tz).strftime('%H:%M')}")
        md.append("")

        for item in post.get("trail", []):
            blog = item.get("blog", {}).get("name", "unknown")
            md.append(f"**{blog}:**")

            trail = self._process_blocks(item.get("content", []), attachments_dir, ts)
            md.append("\n".join([f"> {l}" if l.strip() else ">" for l in trail.split("\n")]))
            md.append("")

        content = post.get("content")
        if not content:
            content = [
                {
                    "type": "text",
                    "text": (post.get("summary") or post.get("body") or post.get("caption") or "")
                }
            ]

        md.append(self._process_blocks(content, attachments_dir, ts))

        tags = post.get("tags", [])
        if tags:
            md.append("")
            formatted = [f"`{t}`" if " " in t else f"#{t}" for t in tags]
            md.append(", ".join(formatted))

        notes_md = self._format_notes(post)
        if notes_md:
            md.append("")
            md.append(notes_md)

        return "\n".join(md)
