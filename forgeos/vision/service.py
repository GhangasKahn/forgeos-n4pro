#!/usr/bin/env python3
"""Optional real-time vision/telemetry loop (Jetson cameras later).

Zero-vision adaptive brain is primary — use `python3 -m forgeos.adaptive.service`.
This loop scores telemetry (+ optional classical first-layer features) only.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forgeos.moonraker_bus import MoonrakerBus
from forgeos.vision.realtime_loop import RealtimeVisionLoop


def main() -> int:
    ap = argparse.ArgumentParser(description="ForgeOS optional RT vision/telemetry loop")
    ap.add_argument("--moonraker", default="http://192.168.1.178:7125")
    ap.add_argument("--interval", type=float, default=0.25)
    ap.add_argument("--arm", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--max-ticks", type=int, default=None)
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "vision_rig.yaml")
    ap.add_argument("--state", type=Path, default=ROOT / "artifacts" / "vision_adaptive_state.json")
    ap.add_argument("--journal", type=Path, default=ROOT / "artifacts" / "vision_rt_journal.jsonl")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("forgeos.vision.service")
    bus = MoonrakerBus(args.moonraker)
    loop = RealtimeVisionLoop(
        bus,
        interval_s=args.interval,
        armed=args.arm,
        state_path=args.state,
        journal_path=args.journal,
        config_path=args.config if args.config.exists() else None,
        vision_feature_fn=None,
    )
    log.info(
        "RT telemetry loop moonraker=%s interval=%.3f armed=%s",
        args.moonraker,
        args.interval,
        args.arm,
    )
    loop.run(once=args.once, max_ticks=args.max_ticks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
