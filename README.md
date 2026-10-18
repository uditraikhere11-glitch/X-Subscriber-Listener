# X Subscriber Listener for Diamond Bot

A read-only Playwright listener that checks explicitly configured X profiles using a session your account is authorized to use, extracts candidate NSE/F&O signals, deduplicates posts in SQLite, and optionally forwards candidates to Telegram and a generic webhook.

## Safety defaults

- No X API dependency; uses the normal rendered website UI.
- Only use this for posts that your account is authorized to view and in accordance with X's current terms. If X displays a challenge, rate limit, suspension, or login wall, stop and resolve it manually. No bypass or stealth behavior is implemented.
- Configure explicit handles; this version does not scrape the entire following/subscription list.
- **No live trading.** Parsed text is a candidate for human review. The generic webhook is disabled by default and is not assumed to match Diamond Bot's endpoint schema.
- Keep browser state, `.env`, tokens, database files and logs out of Git.

## Install

Python 3.11+ recommended.

```bash
git clone https://github.com/uditraikhere11-glitch/X-Subscriber-Listener.git
cd X-Subscriber-Listener
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
```

Edit `.env`: set `X_MONITORED_HANDLES=creator_one,creator_two`, only for creators whose posts you can legitimately view. The defaults use a conservative 300-second poll interval.

## Sign in safely

On a trusted desktop with a graphical browser, run:

```bash
python scripts/save_x_login.py
```

Sign in manually. The script writes Playwright storage-state JSON outside the repo at `~/.local/share/x-subscriber-listener/storage_state.json` by default, with restrictive file permissions. Transfer that file securely to the VM, keep it outside the repository and set `X_STORAGE_STATE_PATH` to its final path. Do not upload the file to GitHub, issue trackers, or chat.

## Test and run

```bash
pytest -q
python -m x_listener.cli --once
python -m x_listener.cli
python -m x_listener.cli --show-stats
```

Use `--once` while verifying account access. The continuous loop stops if it detects an access/login/rate-limit condition rather than trying to bypass it.

## Notifications

Telegram notifications are disabled unless both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set in a host-local `.env`. Diamond Bot forwarding is disabled by default. Only enable it after reviewing the actual receiver's URL, authentication, idempotency and JSON schema. This listener sends a generic schema version 1 payload with an idempotency key; it does not place orders.

## VM installation

The helper `deploy/install_vm.sh` installs the Python environment and Chromium. Review `deploy/x-subscriber-listener.service.example` and update Linux username/path if needed before installing the systemd unit. For service operation, keep settings in a host-local file such as `~/.config/x-subscriber-listener/.env` with mode 600. Check service logs with `journalctl -u x-subscriber-listener -f` after installing the unit.

## Limits

The X website UI can change and login sessions expire. The first version reads rendered text from a limited number of visible timeline cards; it does not parse text embedded only in images or guarantee detection of every post. Signal extraction is heuristic and must be validated against real examples before use.
