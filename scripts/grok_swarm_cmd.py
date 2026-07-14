#!/usr/bin/env python3
"""Grok CLI into the film swarm outbox.

  python3 scripts/grok_swarm_cmd.py burst --count 12
  python3 scripts/grok_swarm_cmd.py closeup
  python3 scripts/grok_swarm_cmd.py focus
  python3 scripts/grok_swarm_cmd.py torch --on
  python3 scripts/grok_swarm_cmd.py test --suite full
  python3 scripts/grok_swarm_cmd.py status
  python3 scripts/grok_swarm_cmd.py inbox
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.swarm.symbiosis import grok_emit, grok_read_inbox, grok_status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--count", type=int, default=12)
    ap.add_argument("--suite", default="full")
    ap.add_argument("--scene", default="printer_bed")
    ap.add_argument("--on", action="store_true")
    ap.add_argument("--off", action="store_true")
    ap.add_argument("--op", default="wake")
    ap.add_argument("--text", default="")
    args = ap.parse_args()

    if args.cmd == "inbox":
        print(json.dumps(grok_read_inbox(25), indent=2))
        return 0
    if args.cmd == "status":
        print(json.dumps(grok_status(), indent=2)[:4000])
        return 0

    payload = {}
    if args.cmd == "burst":
        payload["count"] = args.count
    elif args.cmd == "torch":
        payload["on"] = not args.off
    elif args.cmd == "scene":
        payload["scene"] = args.scene
    elif args.cmd == "test":
        payload["suite"] = args.suite
    elif args.cmd == "adb":
        payload["op"] = args.op
    elif args.cmd == "prompt":
        payload["text"] = args.text

    row = grok_emit(args.cmd, **payload)
    print(json.dumps({"sent": row, "status_preview": grok_status().get("recent_topics", [])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
