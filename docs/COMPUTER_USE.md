# Computer Use / Browser Use — agent senses

Open-source control stack for this cloud agent’s XFCE desktop (`DISPLAY=:1`).

| Layer | Package | Role |
|---|---|---|
| **Browser harness** | [browser-use](https://github.com/browser-use/browser-use) / [browser-harness](https://github.com/browser-use/browser-harness) | CDP attach to live Chrome |
| **Playwright** | `playwright` | Deterministic headless/headed Chromium |
| **Desktop** | `xdotool` + `scrot` + `forgeos.computer_use.desktop` | Click/type/screenshot XFCE |

## Quick senses check

```bash
export DISPLAY=:1
export PATH="$HOME/.local/bin:$PATH"

python3 scripts/computer_use.py senses
```

## Browser harness (attached to Chrome)

Chrome must be running with remote debugging (port 9222):

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/forgeos-chrome-profile &
browser-harness --doctor   # chrome + daemon + connections = ok

browser-harness <<'PY'
ensure_real_tab()
new_tab("https://www.klipper3d.org/Pressure_Advance.html")
wait_for_load()
print(page_info())
print(capture_screenshot())
PY
```

## Desktop hands

```bash
python3 scripts/computer_use.py desktop-shot
python3 scripts/computer_use.py open-chrome https://example.com
```

```python
from forgeos.computer_use import Desktop, BrowserSession

d = Desktop()
d.screenshot("desk")
d.open_chrome("https://docs.elegoo.com")

with BrowserSession(headless=True) as b:
    b.goto("https://www.klipper3d.org/")
    print(b.title(), b.screenshot("klipper"))
```

## Limits (zero-lie)

- These senses control **this agent’s desktop/browser**, not your shop LAN.
- Printer at `192.168.1.178` still needs a real tunnel (Tailscale / reverse SSH).
- Browser Use Cloud auth is optional (`browser-harness auth login`) for remote browsers.
