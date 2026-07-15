"""ForgeOS computer-use senses — desktop + browser control on the agent display.

Open-source stack:
  - browser-use / Playwright → Chromium automation
  - xdotool / scrot / mss → XFCE desktop (DISPLAY=:1)

This is the control surface for research, docs, CAD viewers, and engineering UIs.
It does NOT magically reach RFC1918 printers — use a real tunnel for that.
"""

from __future__ import annotations

from forgeos.computer_use.desktop import Desktop
from forgeos.computer_use.browser import BrowserSession

__all__ = ["Desktop", "BrowserSession"]
