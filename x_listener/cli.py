from __future__ import annotations

import argparse
import logging
import time

from .browser import XAccessError, XBrowser
from .config import Settings
from .database import Store
from .models import utc_now_iso
from .notifier import Notifier
from .parser import parse_candidate


def setup_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def cycle(settings: Settings, store: Store, notifier: Notifier) -> None:
    log = logging.getLogger(__name__)
    channels = notifier.enabled_channels()
    with XBrowser(settings.storage_state_path, settings.navigation_timeout_ms, settings.max_posts_per_profile) as browser:
        for handle in settings.handles:
            posts = browser.fetch_profile_posts(handle)
            log.info("Read %d visible posts from @%s", len(posts), handle)
            for post in posts:
                candidate = parse_candidate(post.text)
                inserted = store.save_post(post, candidate, channels)
                if inserted:
                    if candidate:
                        log.warning("New signal candidate from @%s: %s %s (review required)", handle, candidate["direction"], candidate["symbol"])
                    else:
                        log.debug("Stored post %s (no trading candidate)", post.post_id)
    # Queue is durable; delivery failures are retried on later cycles.
    for channel in notifier.enabled_channels():
        for post in store.pending_deliveries(channel):
            try:
                notifier.send(channel, post)
                store.record_delivery(post["post_id"], channel)
                log.info("Delivered post %s to %s", post["post_id"], channel)
            except Exception as exc:
                store.record_delivery(post["post_id"], channel, str(exc))
                log.exception("Delivery to %s failed for post %s", channel, post["post_id"])
    log.info("Store stats: %s", store.stats())
    if not channels:
        log.warning("No notification channel configured; candidates are being stored only")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only X post listener and trading-signal candidate parser")
    parser.add_argument("--once", action="store_true", help="run a single profile polling cycle")
    parser.add_argument("--show-stats", action="store_true", help="show local database counts without opening X")
    args = parser.parse_args()

    settings = Settings.load()
    setup_logging(settings.log_level)
    store = Store(settings.database_path)
    if args.show_stats:
        print(store.stats())
        return 0
    settings.validate_runtime()
    notifier = Notifier(settings)
    log = logging.getLogger(__name__)
    while True:
        started = time.monotonic()
        try:
            cycle(settings, store, notifier)
        except XAccessError:
            log.exception("X access/login/rate-limit condition detected. Stopping; resolve manually before restarting.")
            return 2
        except Exception:
            log.exception("Listener cycle failed")
        if args.once:
            return 0
        elapsed = time.monotonic() - started
        time.sleep(max(1, settings.poll_interval_seconds - int(elapsed)))


if __name__ == "__main__":
    raise SystemExit(main())
