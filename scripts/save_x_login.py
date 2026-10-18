#!/usr/bin/env python3
"""Open a visible browser for manual X sign-in and save Playwright storage state.

Run on a trusted computer with a graphical desktop. Never commit the resulting file.
"""
from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    default = "~/.local/share/x-subscriber-listener/storage_state.json"
    path = Path(os.getenv("X_STORAGE_STATE_PATH", default)).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
        print("Sign in to X manually in the opened browser.")
        print("Complete normal verification in X if requested; this script does not bypass challenges.")
        input("When your signed-in home timeline is visible, return here and press Enter to save session state... ")
        if "/i/flow/login" in page.url.lower():
            print("X still shows its login flow. No state saved; finish sign-in and try again.")
            browser.close()
            return 2
        context.storage_state(path=str(path))
        os.chmod(path, 0o600)
        browser.close()
    print(f"Saved sensitive browser state to: {path}")
    print("Keep it outside Git; transfer it securely to the VM and set X_STORAGE_STATE_PATH.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
