#!/usr/bin/env python3
"""ForgeOS real-time dynamic vision/ML service.

Fully dynamic every tick:
  - Moonraker telemetry features
  - Optional camera / placeholder vision scorer
  - Adaptive EMA state
  - Multi-objective controller (flat / Z / flow / speed / thermal)
  - Hot-reload of vision_rig.yaml
  - JSONL journal for online learning

Default is suggest-only; --arm applies within envelopes.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# allow `python3 -m forgeos.vision.service` from repo root
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forgeos.vision.bus import MoonrakerBus
from forgeos.vision.realtime_loop import RealtimeVisionLoop


def main() -> int:
    ap = argparse.ArgumentParser(description="ForgeOS real-time dynamic ML/vision loop")
    ap.add_argument("--moonraker", default="http://192.168.1.178:7125")
    ap.add_argument(
        "--interval",
        type=float,
        default=0.25,
        help="control tick seconds (real-time default 0.25s)",
    )
    ap.add_argument("--arm", action="store_true", help="auto-apply actions within envelopes")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--max-ticks", type=int, default=None)
    ap.add_argument(
        "--phone-url",
        default=None,
        help="Android IP Webcam base URL, e.g. http://192.168.1.42:8080 (Nothing Phone eyes)",
    )
    ap.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "vision_rig.yaml",
    )
    ap.add_argument(
        "--state",
        type=Path,
        default=ROOT / "artifacts" / "vision_adaptive_state.json",
    )
    ap.add_argument(
        "--journal",
        type=Path,
        default=ROOT / "artifacts" / "vision_rt_journal.jsonl",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("forgeos.vision.service")
    bus = MoonrakerBus(args.moonraker)

    vision_fn = None
    phone_url = args.phone_url
    # config override
    if not phone_url and args.config.exists():
        try:
            import yaml

            cfg = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
            phone_url = (cfg.get("phone_camera") or {}).get("url") or phone_url
        except Exception:  # noqa: BLE001
            pass
    if phone_url:
        from forgeos.vision.phone_camera import PhoneCameraSource

        cam = PhoneCameraSource(
            phone_url,
            save_dir=str(ROOT / "artifacts" / "phone_cam"),
        )
        ping = cam.ping()
        log.info("phone camera ping: %s", ping)
        if not ping.get("ok"):
            log.warning(
                "Phone not reachable yet — will retry each tick. "
                "Start IP Webcam on the phone. url=%s err=%s",
                phone_url,
                ping.get("error"),
            )
        vision_fn = cam

    loop = RealtimeVisionLoop(
        bus,
        interval_s=args.interval,
        armed=args.arm,
        state_path=args.state,
        journal_path=args.journal,
        config_path=args.config if args.config.exists() else None,
        vision_feature_fn=vision_fn,
    )
    log.info(
        "dynamic RT service moonraker=%s interval=%.3f armed=%s phone=%s",
        args.moonraker,
        args.interval,
        args.arm,
        phone_url or "none",
    )
    loop.run(once=args.once, max_ticks=args.max_ticks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
