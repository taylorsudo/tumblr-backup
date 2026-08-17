#!/usr/bin/env python3

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from requests_oauthlib import OAuth1

from config import load_config, EARLIEST_DEFAULT
from tumblr_api import TumblrAPIClient
from markdown_convert import MarkdownConverter
from storage import save_daily_posts

DEFAULT_TIMEZONE = "Australia/Sydney"


def parse_earliest(date_str: str, tz: ZoneInfo) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
    return int(dt.timestamp())


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
        self.output_dir = Path(output_dir)
        self.incremental_hours = incremental_hours
        self.delete_after_backup = delete_after_backup

        self.tz = ZoneInfo(DEFAULT_TIMEZONE)
        self.earliest_timestamp = parse_earliest(earliest_date, self.tz)

        auth = None
        if all([consumer_secret, oauth_token, oauth_token_secret]):
            auth = OAuth1(
                client_key=api_key,
                client_secret=consumer_secret,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret,
            )

        self.api = TumblrAPIClient(blog_identifier, api_key, auth=auth)
        self.converter = MarkdownConverter(
            blog_identifier,
            self.tz,
            download_image=download_image,
            download_video=download_video,
            download_audio=download_audio,
        )

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def backup(self):
        posts = self.api.fetch_all_posts(self.earliest_timestamp, self.incremental_hours)
        if not posts:
            return

        grouped = {}
        for p in posts:
            key = datetime.fromtimestamp(p["timestamp"], tz=self.tz).strftime("%Y/%m/%d")
            grouped.setdefault(key, []).append(p)

        for date_key, day_posts in grouped.items():
            day_posts.sort(key=lambda x: x.get("timestamp", 0))
            save_daily_posts(
                self.output_dir,
                date_key,
                day_posts,
                render_fn=self.converter.convert_to_markdown,
                delete_after_backup=self.delete_after_backup,
                delete_fn=self.api.delete_post if self.delete_after_backup else None,
            )


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
