#!/usr/bin/env python3
"""python3 -m forgeos.swarm --phone-url http://192.168.1.250:8080"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forgeos.swarm.orchestrator import FilmSwarm


def main() -> int:
    ap = argparse.ArgumentParser(description="ForgeOS multi-agent film capture swarm")
    ap.add_argument("--phone-url", default="http://192.168.1.250:8080")
    ap.add_argument("--moonraker", default="http://192.168.1.178:7125")
    ap.add_argument("--adb-serial", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--burst", type=int, default=0, help="emit burst command then run")
    ap.add_argument("--closeup", action="store_true", help="start in closeup mode")
    args = ap.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    swarm = FilmSwarm(
        phone_url=args.phone_url,
        moonraker=args.moonraker,
        adb_serial=args.adb_serial,
    )
    swarm.start()
    if args.burst:
        swarm.command("burst", count=args.burst)
    if args.closeup:
        swarm.command("closeup")
    try:
        while True:
            import time

            time.sleep(1)
            (Path(ROOT) / "artifacts" / "film_swarm" / "SWARM_LIVE").write_text(
                "OK\n", encoding="utf-8"
            )
    except KeyboardInterrupt:
        swarm.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
