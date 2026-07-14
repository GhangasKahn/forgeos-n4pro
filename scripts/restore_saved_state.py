#!/usr/bin/env python3
"""Restore ForgeOS shop process state to the live printer from saved YAML."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--state",
        default=str(ROOT / "configs" / "saved_state_shop_n4pro.yaml"),
    )
    ap.add_argument("--host", default=None, help="override moonraker host URL")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    state = yaml.safe_load(Path(args.state).read_text(encoding="utf-8"))
    base = args.host or state.get("printer", {}).get("moonraker") or "http://192.168.1.178:7125"
    base = base.rstrip("/")

    def gcode(script: str):
        qs = urllib.parse.urlencode({"script": script})
        req = urllib.request.Request(base + "/printer/gcode/script?" + qs, method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    block = state.get("restore_gcode") or ""
    lines = [ln.strip() for ln in block.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    print("Restoring", state.get("name"), "→", base)
    for ln in lines:
        print(" ", ln)
        if not args.dry_run:
            try:
                r = gcode(ln)
                print("   →", r.get("result"))
            except Exception as e:
                print("   FAIL", e)
                return 1
    print("Done." if not args.dry_run else "Dry-run only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
