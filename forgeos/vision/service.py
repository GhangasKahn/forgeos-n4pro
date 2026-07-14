#!/usr/bin/env python3
"""ForgeOS vision service entry (runs on Jetson).

V0: connect to Moonraker, poll status, emit placeholder first-layer events.
Cameras/IR attach in capture.py later.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from forgeos.vision.bus import MoonrakerBus
from forgeos.vision.calib.fsm import VisionCalibFSM
from forgeos.vision.scorers.first_layer import score_from_gray_rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--moonraker", default="http://192.168.1.178:7125")
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--arm", action="store_true", help="allow auto babystep suggestions to apply")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("forgeos.vision")
    bus = MoonrakerBus(args.moonraker)
    fsm = VisionCalibFSM(armed=args.arm)

    log.info("vision service start moonraker=%s armed=%s", args.moonraker, args.arm)

    while True:
        try:
            info = bus.printer_info()
            status = bus.objects_query(
                ["print_stats", "extruder", "heater_bed", "toolhead", "gcode_move"]
            )
            printing = str(status.get("print_stats", {}).get("state", "")).lower() == "printing"
            z = (status.get("gcode_move", {}) or {}).get("homing_origin", [0, 0, 0])[2]
            log.info(
                "printer=%s print=%s z=%.3f noz=%.1f",
                info.get("state"),
                status.get("print_stats", {}).get("state"),
                float(z or 0),
                float((status.get("extruder") or {}).get("temperature") or 0),
            )

            if printing and fsm.state.value in ("idle", "wait_first_layer", "adjust", "scoring"):
                if fsm.state.value == "idle":
                    fsm.arm() if args.arm else setattr(fsm, "state", fsm.state.WAIT_FIRST_LAYER)
                # Placeholder features until real frames wired
                # (replace with OpenCV row means from cam_oblique)
                fake_rows = [120 + (i % 5) * 8 for i in range(40)]
                result = score_from_gray_rows(fake_rows, coverage=0.75)
                event = fsm.on_first_layer_result(result)
                log.info("vision_event %s", json.dumps(event.as_dict()))
                if args.arm and event.suggestion in ("FORGE_BABY_UP", "FORGE_BABY_DOWN"):
                    log.warning("AUTO APPLY %s", event.suggestion)
                    bus.gcode(event.suggestion)
        except Exception as exc:
            log.exception("loop error: %s", exc)

        if args.once:
            break
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
