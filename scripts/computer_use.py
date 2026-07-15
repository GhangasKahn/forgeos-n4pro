#!/usr/bin/env python3
"""ForgeOS computer-use CLI — fill out desktop + browser senses.

Examples:
  python3 scripts/computer_use.py desktop-shot
  python3 scripts/computer_use.py open-chrome https://docs.klipper3d.org/Pressure_Advance.html
  python3 scripts/computer_use.py browse https://github.com/browser-use/browser-use
  python3 scripts/computer_use.py browse-shot https://www.elegoo.com
  python3 scripts/computer_use.py senses   # self-test all senses
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.computer_use.browser import BrowserSession
from forgeos.computer_use.desktop import Desktop


def cmd_desktop_shot(_: argparse.Namespace) -> int:
    d = Desktop()
    path = d.screenshot("desktop")
    print(json.dumps({"ok": True, "path": str(path), "windows": d.window_list()[:500]}, indent=2))
    return 0


def cmd_open_chrome(args: argparse.Namespace) -> int:
    d = Desktop()
    d.open_chrome(args.url)
    time.sleep(2)
    path = d.screenshot("chrome_open")
    print(json.dumps({"ok": True, "url": args.url, "shot": str(path)}, indent=2))
    return 0


def cmd_browse(args: argparse.Namespace) -> int:
    with BrowserSession(headless=not args.headed) as b:
        b.goto(args.url)
        shot = b.screenshot("browse")
        info = b.info()
        info["shot"] = str(shot)
        info["snippet"] = b.content_snippet(300)
        print(json.dumps(info, indent=2))
    return 0


def cmd_senses(_: argparse.Namespace) -> int:
    """Atomic self-test: desktop screenshot + playwright navigate + extract."""
    report = {"desktop": {}, "browser": {}, "ok": False}
    d = Desktop()
    try:
        shot = d.screenshot("sense_desktop")
        report["desktop"] = {
            "ok": True,
            "shot": str(shot),
            "mouse": d.get_mouse(),
            "windows": d.window_list()[:300],
        }
    except Exception as exc:  # noqa: BLE001
        report["desktop"] = {"ok": False, "error": str(exc)}

    try:
        with BrowserSession(headless=True) as b:
            b.goto("https://example.com")
            shot = b.screenshot("sense_browser")
            report["browser"] = {
                "ok": True,
                "title": b.title(),
                "url": b.url(),
                "shot": str(shot),
                "has_example": "Example Domain" in b.text(),
            }
    except Exception as exc:  # noqa: BLE001
        report["browser"] = {"ok": False, "error": str(exc)}

    report["ok"] = bool(report["desktop"].get("ok") and report["browser"].get("ok"))
    out = Path("/opt/cursor/artifacts/computer_use/senses_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("report:", out)
    return 0 if report["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="ForgeOS computer-use senses")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("desktop-shot")
    p.set_defaults(func=cmd_desktop_shot)

    p = sub.add_parser("open-chrome")
    p.add_argument("url", nargs="?", default="https://example.com")
    p.set_defaults(func=cmd_open_chrome)

    p = sub.add_parser("browse")
    p.add_argument("url")
    p.add_argument("--headed", action="store_true")
    p.set_defaults(func=cmd_browse)

    p = sub.add_parser("browse-shot")
    p.add_argument("url")
    p.add_argument("--headed", action="store_true")
    p.set_defaults(func=cmd_browse)

    p = sub.add_parser("senses")
    p.set_defaults(func=cmd_senses)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
