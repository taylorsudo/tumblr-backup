import os
import re
from pathlib import Path


def save_daily_posts(output_dir: Path, date_key: str, posts, render_fn, delete_after_backup: bool, delete_fn=None):
    """Append newly-seen posts to output_dir/YYYY/MM/DD.md.

    render_fn(post, attachments_dir) -> markdown string.
    Existing posts (matched by the embedded tumblr-post-id comment) are skipped.
    When delete_after_backup is set, delete_fn(post_id) is called for each
    post that was newly saved.
    """
    y, m, d = date_key.split("/")
    folder = output_dir / y / m
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

        new_blocks.append(render_fn(p, attachments))
        new_blocks.append("\n---\n")

        if delete_after_backup:
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

    if delete_fn:
        for pid in delete_queue:
            delete_fn(pid)
