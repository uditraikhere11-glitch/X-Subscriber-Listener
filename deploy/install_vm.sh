#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium

install -d -m 700 "$HOME/.config/x-subscriber-listener"
install -d -m 700 "$HOME/.local/share/x-subscriber-listener"
if [[ ! -f "$HOME/.config/x-subscriber-listener/.env" ]]; then
  install -m 600 .env.example "$HOME/.config/x-subscriber-listener/.env"
  echo "Created $HOME/.config/x-subscriber-listener/.env — edit it before running the listener."
fi

echo "Dependencies installed. Next: configure the host-local .env, transfer storage_state.json securely, then run:"
echo "  $ROOT/.venv/bin/python -m x_listener.cli --once"
echo "Review deploy/x-subscriber-listener.service.example before installing a systemd unit."
