#!/usr/bin/env python3
"""Run FilmSwarm + Grok symbiosis bridge (shared inbox/outbox).

  python3 scripts/symbiosis_bridge.py --phone-url http://192.168.1.250:8080 -v

Grok writes commands via:
  python3 -c "from forgeos.swarm.symbiosis import grok_emit; grok_emit('burst', count=10)"
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.swarm.orchestrator import FilmSwarm
from forgeos.swarm.symbiosis import SymbiosisBridge, grok_emit

_stop = False


def _sig(*_a):
    global _stop
    _stop = True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phone-url", default="http://192.168.1.250:8080")
    ap.add_argument("--moonraker", default="http://192.168.1.178:7125")
    ap.add_argument("--adb-serial", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--bootstrap-test", action="store_true", help="run full test suite on start")
    args = ap.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    serial = args.adb_serial
    if not serial:
        p = ROOT / "artifacts" / "film_cam" / "adb_serial.txt"
        if p.exists():
            serial = p.read_text(encoding="utf-8").strip()

    # stop note: assume outer launcher killed competitors
    swarm = FilmSwarm(
        phone_url=args.phone_url,
        moonraker=args.moonraker,
        adb_serial=serial,
    )
    bridge = SymbiosisBridge(swarm)
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)
    swarm.start()
    grok_emit("status", note="symbiosis_bridge_online")
    if args.bootstrap_test:
        time.sleep(1)
        grok_emit("test", suite="full")

    logging.info("Symbiosis bridge ONLINE — Grok↔swarm")
    while not _stop:
        bridge.tick()
        time.sleep(0.4)
    swarm.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
