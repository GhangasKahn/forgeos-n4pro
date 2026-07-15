#!/usr/bin/env python3
"""Zero-vision adaptive service — real-time process brain (no cameras).

Run on any host that can reach Moonraker (Mac, Pi, Jetson without cams).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forgeos.adaptive.process_brain import ZeroVisionBrain, ZeroVisionState
from forgeos.safety import SafetyGate
from forgeos.vision.bus import MoonrakerBus


log = logging.getLogger("forgeos.adaptive")


def main() -> int:
    ap = argparse.ArgumentParser(description="ForgeOS zero-vision adaptive process brain")
    ap.add_argument("--moonraker", default="http://192.168.1.178:7125")
    ap.add_argument("--interval", type=float, default=0.5, help="tick seconds (default 2 Hz)")
    ap.add_argument("--arm", action="store_true", help="apply actions within envelopes")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--max-ticks", type=int, default=None)
    ap.add_argument(
        "--state",
        type=Path,
        default=ROOT / "artifacts" / "zero_vision_state.json",
    )
    ap.add_argument(
        "--journal",
        type=Path,
        default=ROOT / "artifacts" / "zero_vision_journal.jsonl",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    bus = MoonrakerBus(args.moonraker)
    st = ZeroVisionState.load(args.state)
    safety = SafetyGate()
    arm_token: Optional[str] = None
    if args.arm:
        arm_token = safety.arm_runtime(ttl_s=8 * 3600)
        try:
            safety.sync_printer_arm(bus, purpose="autotune")
        except Exception as exc:  # noqa: BLE001
            log.warning("printer arm sync failed (continuing with host token): %s", exc)
    st.armed = bool(args.arm)
    st.mode = "armed" if args.arm else "suggest"
    brain = ZeroVisionBrain(st, safety=safety, arm_token=arm_token)

    names = [
        "print_stats",
        "extruder",
        "heater_bed",
        "heater_generic heater_bed_outer",
        "toolhead",
        "gcode_move",
        "virtual_sdcard",
        "fan",
        "bed_mesh",
    ]

    log.info(
        "zero-vision brain start mr=%s interval=%.2f armed=%s",
        args.moonraker,
        args.interval,
        args.arm,
    )

    n = 0
    while True:
        t0 = time.time()
        try:
            status = bus.objects_query(names)
            tick = brain.plan(status)
            scripts = brain.scripts_to_apply(tick)
            for s in scripts:
                log.warning("APPLY %s", s.replace("\n", " | "))
                bus.gcode(s)

            q = tick.quality
            log.info(
                "tick#%d %s print=%s prec=%.2f bedU=%.2f nozT=%.2f moist=%.2f flat=%.2f acts=%d z=%.3f",
                st.ticks,
                tick.mode,
                tick.telemetry.get("print_state"),
                q.get("precision_belief", 0),
                q.get("bed_uniform", 0),
                q.get("nozzle_track", 0),
                q.get("moisture_risk", 0),
                q.get("flat_volume", 0),
                len([a for a in tick.actions if a.kind == "gcode"]),
                float(tick.telemetry.get("z_adjust_mm") or 0),
            )
            if args.verbose:
                for a in tick.actions[:5]:
                    log.debug("  plan[%s] p=%d %s", a.source, a.priority, a.reason)

            args.journal.parent.mkdir(parents=True, exist_ok=True)
            with args.journal.open("a", encoding="utf-8") as f:
                f.write(json.dumps(tick.as_dict()) + "\n")
            st.save(args.state)
        except Exception as exc:
            log.exception("tick error: %s", exc)

        n += 1
        if args.once or (args.max_ticks is not None and n >= args.max_ticks):
            break
        time.sleep(max(0.0, args.interval - (time.time() - t0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
