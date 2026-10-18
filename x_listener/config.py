from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _expand(path: str) -> Path:
    return Path(path).expanduser().resolve()


@dataclass(frozen=True)
class Settings:
    handles: tuple[str, ...]
    storage_state_path: Path
    poll_interval_seconds: int
    max_posts_per_profile: int
    navigation_timeout_ms: int
    data_dir: Path
    database_path: Path
    log_level: str
    telegram_bot_token: str
    telegram_chat_id: str
    diamond_webhook_enabled: bool
    diamond_webhook_url: str
    diamond_webhook_token: str

    @classmethod
    def load(cls, env_file: str | None = ".env") -> "Settings":
        if env_file:
            load_dotenv(env_file, override=False)
        raw_handles = os.getenv("X_MONITORED_HANDLES", "")
        handles = tuple(dict.fromkeys(
            h.strip().lstrip("@").lower() for h in raw_handles.split(",") if h.strip()
        ))
        for handle in handles:
            if not handle.replace("_", "").isalnum() or len(handle) > 15:
                raise ValueError(f"Invalid X handle in X_MONITORED_HANDLES: {handle!r}")

        data_dir = _expand(os.getenv("X_DATA_DIR", "~/.local/share/x-subscriber-listener"))
        db_default = str(data_dir / "posts.sqlite3")
        webhook_enabled = _bool("DIAMOND_WEBHOOK_ENABLED", False)
        webhook_url = os.getenv("DIAMOND_WEBHOOK_URL", "").strip()
        webhook_token = os.getenv("DIAMOND_WEBHOOK_TOKEN", "").strip()
        if webhook_enabled:
            if not webhook_url or not webhook_token:
                raise ValueError("Webhook enabled but DIAMOND_WEBHOOK_URL or DIAMOND_WEBHOOK_TOKEN is missing")
            parsed = urlparse(webhook_url)
            loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
                raise ValueError("Webhook URL must use HTTPS; HTTP is permitted only for localhost/loopback")
            if parsed.username or parsed.password:
                raise ValueError("Do not embed credentials in DIAMOND_WEBHOOK_URL")

        return cls(
            handles=handles,
            storage_state_path=_expand(os.getenv("X_STORAGE_STATE_PATH", "~/.local/share/x-subscriber-listener/storage_state.json")),
            poll_interval_seconds=_int("POLL_INTERVAL_SECONDS", 300, 120),
            max_posts_per_profile=min(_int("MAX_POSTS_PER_PROFILE", 30, 1), 100),
            navigation_timeout_ms=_int("NAVIGATION_TIMEOUT_MS", 45000, 10000),
            data_dir=data_dir,
            database_path=_expand(os.getenv("X_DATABASE_PATH", db_default)),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
            diamond_webhook_enabled=webhook_enabled,
            diamond_webhook_url=webhook_url,
            diamond_webhook_token=webhook_token,
        )

    def validate_runtime(self) -> None:
        if not self.handles:
            raise ValueError("Set X_MONITORED_HANDLES in .env to one or more handles you are authorized to view")
        if not self.storage_state_path.is_file():
            raise FileNotFoundError(
                f"X browser state not found at {self.storage_state_path}. Run scripts/save_x_login.py on a trusted desktop, "
                "then transfer the file securely to the VM and set X_STORAGE_STATE_PATH."
            )
        if bool(self.telegram_bot_token) != bool(self.telegram_chat_id):
            raise ValueError("Set both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, or leave both blank")
