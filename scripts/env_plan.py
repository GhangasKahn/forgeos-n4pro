#!/usr/bin/env python3
"""Print environment-aware before/during/after plan (homeostasis)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.environment.models import AmbientReading, EnclosureMode
from forgeos.environment.session import build_session_plan


def main() -> int:
    ap = argparse.ArgumentParser(description="ForgeOS environmental session plan")
    ap.add_argument("--sku", default="protopasta_htpla")
    ap.add_argument("--profile", default=str(ROOT / "environments" / "basement_default.yaml"))
    ap.add_argument("--temp", type=float, default=None, help="Override ambient C")
    ap.add_argument("--rh", type=float, default=None, help="Override RH %")
    ap.add_argument(
        "--enclosure",
        choices=["open", "ajar", "enclosed"],
        default=None,
    )
    args = ap.parse_args()

    ambient = None
    if args.temp is not None or args.rh is not None or args.enclosure is not None:
        # start from profile then override
        from forgeos.environment.loader import load_environment_profile

        base = load_environment_profile(Path(args.profile)).ambient
        enc = base.enclosure
        if args.enclosure:
            enc = EnclosureMode(args.enclosure if args.enclosure != "ajar" else "door_ajar")
            if args.enclosure == "ajar":
                enc = EnclosureMode.DOOR_AJAR
            elif args.enclosure == "enclosed":
                enc = EnclosureMode.ENCLOSED
            else:
                enc = EnclosureMode.OPEN
        ambient = AmbientReading(
            temperature_c=float(args.temp if args.temp is not None else base.temperature_c),
            rh_percent=float(args.rh if args.rh is not None else base.rh_percent),
            enclosure=enc,
            draft_level=base.draft_level,
            source="cli",
        )

    plan = build_session_plan(
        material_sku=args.sku,
        ambient=ambient,
        env_profile_path=None if ambient is not None else Path(args.profile),
    )
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
