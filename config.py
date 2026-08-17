import os
import json
from pathlib import Path

EARLIEST_DEFAULT = "2025-01-01"


def _bool_env(key: str, default: bool = False) -> bool:
    v = os.environ.get(key)
    return v.lower() in ("1", "true", "yes") if v else default


def _int_env(key: str, default=None):
    v = os.environ.get(key)
    return int(v) if v else default


def load_config() -> dict:
    cfg_file = Path("config.json")
    file_cfg = json.loads(cfg_file.read_text()) if cfg_file.exists() else {}

    def g(key, default=None):
        env_val = os.environ.get(key.upper())
        return env_val if env_val is not None else file_cfg.get(key, default)

    return {
        "blog_identifier": g("blog_identifier"),
        "api_key": g("api_key"),
        "output_dir": g("output_dir", "Tumblr"),
        "download_image": _bool_env("DOWNLOAD_IMAGE", True),
        "download_video": _bool_env("DOWNLOAD_VIDEO", True),
        "download_audio": _bool_env("DOWNLOAD_AUDIO", True),
        "incremental_hours": _int_env("INCREMENTAL_HOURS", 24),
        "earliest_date": g("earliest_date", EARLIEST_DEFAULT),
        "delete_after_backup": _bool_env("DELETE_AFTER_BACKUP", False),
        "consumer_secret": g("consumer_secret"),
        "oauth_token": g("oauth_token"),
        "oauth_token_secret": g("oauth_token_secret"),
    }
