from __future__ import annotations

import logging
import re
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, TimeoutError as PlaywrightTimeoutError, sync_playwright

from .models import XPost, utc_now_iso

LOG = logging.getLogger(__name__)


class XAccessError(RuntimeError):
    """Login/challenge/rate-limit detected; stop instead of trying to bypass it."""


def _status_id(href: str) -> str | None:
    match = re.search(r"/status/(\d+)", href)
    return match.group(1) if match else None


class XBrowser(AbstractContextManager):
    def __init__(self, storage_state_path: Path, timeout_ms: int, max_posts: int):
        self.storage_state_path = storage_state_path
        self.timeout_ms = timeout_ms
        self.max_posts = max_posts
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def __enter__(self) -> "XBrowser":
        if not self.storage_state_path.is_file():
            raise FileNotFoundError(f"Browser state not found: {self.storage_state_path}")
        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.launch(headless=True)
            self.context = self.browser.new_context(storage_state=str(self.storage_state_path), viewport={"width": 1280, "height": 900})
            self.page = self.context.new_page()
            self.page.set_default_timeout(self.timeout_ms)
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for obj in (self.context, self.browser):
            try:
                if obj:
                    obj.close()
            except Exception:
                pass
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass

    def fetch_profile_posts(self, handle: str) -> list[XPost]:
        if not self.page:
            raise RuntimeError("Browser not started")
        url = f"https://x.com/{handle}"
        LOG.info("Checking configured profile @%s", handle)
        try:
            response = self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"Timed out loading @{handle}; will retry next cycle") from exc
        if response and response.status in (401, 403, 429):
            raise XAccessError(f"X returned HTTP {response.status}; stop and check account/session/rate limit manually")
        self.page.wait_for_timeout(1500)
        current = self.page.url.lower()
        if "/i/flow/login" in current or "/account/access" in current or "/account/suspended" in current:
            raise XAccessError(f"X redirected to an authentication, access or suspension page: {self.page.url}")
        body = (self.page.locator("body").inner_text(timeout=10000) or "")[:20000].lower()
        if any(marker in body for marker in ("rate limit exceeded", "verify you are human", "unusual activity", "account access temporarily limited")):
            raise XAccessError("X displayed a rate-limit or access-challenge message; stop for manual review")

        articles = self.page.locator('article[data-testid="tweet"]')
        try:
            count = min(articles.count(), self.max_posts)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"Could not read the profile timeline for @{handle}") from exc
        posts: list[XPost] = []
        observed = utc_now_iso()
        for index in range(count):
            article = articles.nth(index)
            try:
                time_el = article.locator("time").first
                dt = time_el.get_attribute("datetime", timeout=1500) or observed
                links = article.locator('a[href*="/status/"]').evaluate_all("els => els.map(e => e.getAttribute('href')).filter(Boolean)")
                post_id = next((_status_id(href) for href in links if _status_id(href)), None)
                if not post_id:
                    continue
                text_el = article.locator('[data-testid="tweetText"]')
                text = "\n".join(text_el.all_text_contents()).strip() if text_el.count() else ""
                if not text:
                    continue
                path = next((href for href in links if _status_id(href) == post_id), f"/{handle}/status/{post_id}")
                posts.append(XPost(
                    post_id=post_id,
                    handle=handle,
                    url=urljoin("https://x.com", path),
                    created_at=dt,
                    observed_at=observed,
                    text=text[:8000],
                ))
            except PlaywrightTimeoutError:
                LOG.debug("Skipping a timeline card that did not finish rendering")
        return posts
