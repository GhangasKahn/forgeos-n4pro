#!/usr/bin/env bash
# Bring up Chrome + browser-harness senses on DISPLAY=:1
set -euo pipefail
export DISPLAY="${DISPLAY:-:1}"
export PATH="$HOME/.local/bin:$PATH"
mkdir -p /tmp/forgeos-chrome-profile /opt/cursor/artifacts/computer_use
if ! curl -sf http://127.0.0.1:9222/json/version >/dev/null; then
  google-chrome --no-first-run --no-default-browser-check --disable-gpu \
    --remote-debugging-port=9222 \
    --user-data-dir=/tmp/forgeos-chrome-profile \
    --window-size=1600,1000 about:blank >/tmp/forgeos-chrome.log 2>&1 &
  sleep 2
fi
browser-harness --doctor || true
python3 "$(dirname "$0")/computer_use.py" senses
