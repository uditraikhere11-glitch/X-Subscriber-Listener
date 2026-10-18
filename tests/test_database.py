from pathlib import Path

from x_listener.database import Store
from x_listener.models import XPost


def post(post_id="123"):
    return XPost(post_id=post_id, handle="creator", url=f"https://x.com/creator/status/{post_id}",
                 created_at="2026-10-17T10:00:00Z", observed_at="2026-10-17T10:01:00Z",
                 text="BUY SYMBOL: RELIANCE ENTRY: 1250")


def candidate():
    return {"candidate": True, "symbol": "RELIANCE", "direction": "BUY", "live_trading_allowed": False}


def test_insert_is_deduplicated_and_delivery_queued(tmp_path: Path):
    store = Store(tmp_path / "data.sqlite3")
    assert store.save_post(post(), candidate(), ["telegram"]) is True
    assert store.save_post(post(), candidate(), ["telegram"]) is False
    pending = store.pending_deliveries("telegram")
    assert len(pending) == 1
    assert pending[0]["post_id"] == "123"
    store.record_delivery("123", "telegram")
    assert store.pending_deliveries("telegram") == []


def test_candidate_without_channel_can_be_queued_later(tmp_path: Path):
    store = Store(tmp_path / "data.sqlite3")
    store.save_post(post(), candidate(), [])
    store.save_post(post(), candidate(), ["telegram"])
    assert len(store.pending_deliveries("telegram")) == 1


def test_plain_post_is_not_queued_for_notifications(tmp_path: Path):
    store = Store(tmp_path / "data.sqlite3")
    store.save_post(post(), None, ["telegram"])
    assert store.pending_deliveries("telegram") == []
    assert store.stats()["posts_seen"] == 1
