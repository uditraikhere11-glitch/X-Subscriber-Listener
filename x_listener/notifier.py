from __future__ import annotations

import logging
from typing import Any

import requests

from .config import Settings

LOG = logging.getLogger(__name__)


def candidate_text(post: dict[str, Any]) -> str:
    signal = post["candidate"]
    targets = ", ".join(str(x) for x in signal.get("targets", [])) or "not specified"
    return (
        "X TRADING SIGNAL CANDIDATE — REVIEW ONLY\n"
        f"Source: @{post['handle']}\n"
        f"Symbol: {signal.get('symbol')} | Direction: {signal.get('direction')} | Type: {signal.get('instrument')}\n"
        f"Entry: {signal.get('entry') if signal.get('entry') is not None else 'not specified'}\n"
        f"Stop-loss: {signal.get('stop_loss') if signal.get('stop_loss') is not None else 'not specified'}\n"
        f"Targets: {targets}\n"
        f"Confidence: {signal.get('confidence')} | Missing: {', '.join(signal.get('missing_fields', [])) or 'none'}\n"
        f"Post: {post['url']}\n\n"
        "Human verification required. No live order has been placed."
    )


class Notifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()

    def enabled_channels(self) -> list[str]:
        channels = []
        if self.settings.telegram_bot_token and self.settings.telegram_chat_id:
            channels.append("telegram")
        if self.settings.diamond_webhook_enabled:
            channels.append("diamond_webhook")
        return channels

    def send(self, channel: str, post: dict[str, Any]) -> None:
        signal = post["candidate"]
        if channel == "telegram":
            url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
            response = self.session.post(url, json={
                "chat_id": self.settings.telegram_chat_id,
                "text": candidate_text(post),
                "disable_web_page_preview": True,
            }, timeout=15)
        elif channel == "diamond_webhook":
            url = self.settings.diamond_webhook_url
            response = self.session.post(url, headers={
                "Authorization": f"Bearer {self.settings.diamond_webhook_token}",
                "Idempotency-Key": str(post["post_id"]),
            }, json={
                "schema_version": 1,
                "event_type": "candidate_trading_signal",
                "source": "x_subscriber_listener",
                "idempotency_key": str(post["post_id"]),
                "post": {
                    "id": str(post["post_id"]), "handle": post["handle"],
                    "url": post["url"], "created_at": post["created_at"],
                    "observed_at": post["observed_at"],
                    "text_excerpt": post["text"][:2000],
                },
                "signal": signal,
                "safety": {"requires_human_review": True, "live_trading_allowed": False},
            }, timeout=15)
        else:
            raise ValueError(f"Unknown notification channel: {channel}")
        response.raise_for_status()
        if channel == "telegram":
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError("Telegram API returned ok=false")
