import time

from http_utils import requests_with_retry


class TumblrAPIClient:
    """Thin wrapper around the Tumblr v2 API endpoints this project needs."""

    def __init__(self, blog_identifier, api_key, auth=None, base_url="https://api.tumblr.com/v2"):
        self.blog_identifier = blog_identifier
        self.api_key = api_key
        self.auth = auth
        self.base_url = base_url

    def fetch_posts(self, limit=20, before=None):
        url = f"{self.base_url}/blog/{self.blog_identifier}/posts"
        params = {
            "limit": min(limit, 20),
            "before": before,
            "npf": "true",
            "reblog_info": "true",
            "notes_info": "true",
        }
        if not self.auth:
            params["api_key"] = self.api_key

        r = requests_with_retry("GET", url, params=params, auth=self.auth)
        return r.json() if r else None

    def fetch_all_posts(self, earliest_timestamp: int, incremental_hours: int):
        """Page backward through the blog, keeping posts within
        [earliest_timestamp, now - incremental_hours] in chronological order.
        """
        all_posts = []
        before = None
        now = int(time.time())

        # Only posts older than this "ceiling" are processed.
        window_ceiling = now - (incremental_hours * 3600)

        while True:
            resp = self.fetch_posts(limit=20, before=before)
            if not resp:
                break

            posts = resp["response"].get("posts", [])
            if not posts:
                break

            filtered = [
                p for p in posts
                if earliest_timestamp <= p.get("timestamp", 0) <= window_ceiling
            ]

            # Tumblr returns newest first; reverse so callers can append
            # chronologically to daily files.
            all_posts.extend(reversed(filtered))

            before = posts[-1].get("timestamp")

            # If the oldest post in this batch already predates earliest_timestamp, stop.
            if before < earliest_timestamp:
                break
            time.sleep(0.2)

        return all_posts

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
