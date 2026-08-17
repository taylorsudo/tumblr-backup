import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from http_utils import requests_with_retry
from media_types import subfolder_for_extension


def download_attachment(url: str, folder: Path, ts: int, tz: ZoneInfo) -> str:
    """Download a Tumblr-hosted attachment into folder/Attachments/<Category>.

    Returns a relative path string for embedding in Markdown on success,
    or the original url unchanged on failure.
    """
    try:
        ext = os.path.splitext(urlparse(url).path)[1].lower() or ""
        subfolder = subfolder_for_extension(ext)

        target_dir = folder / subfolder if subfolder else folder
        target_dir.mkdir(parents=True, exist_ok=True)

        base = datetime.fromtimestamp(ts, tz=tz).strftime("%Y-%m-%d-%H%M%S")
        path = target_dir / f"{base}{ext}"

        i = 1
        while path.exists():
            path = target_dir / f"{base}-{i}{ext}"
            i += 1

        r = requests_with_retry("GET", url, stream=True)
        if not r:
            return url

        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

        rel_path = f"Attachments/{subfolder}/{path.name}" if subfolder else f"Attachments/{path.name}"
        return rel_path

    except Exception:
        return url
