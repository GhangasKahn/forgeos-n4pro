#!/usr/bin/env python3
"""Print resolved Protopasta + Wham Bam PEX + Brozzl stack profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.stack_profile import compose_stack


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filament", default="protopasta_htpla")
    ap.add_argument("--surface", default="whambam_pex")
    ap.add_argument("--nozzle", default="brozzl_n4pro")
    ap.add_argument("--ambient", type=float, default=14.0)
    ap.add_argument("--z", type=float, default=-0.10)
    args = ap.parse_args()
    # map short nozzle name
    noz = args.nozzle
    if noz in ("brozzl", "brozzl_n4pro", "brozzl_ni_cu"):
        noz = "brozzl_n4pro"
    try:
        stack = compose_stack(
            filament_sku=args.filament,
            surface_sku=args.surface,
            nozzle_sku=noz if noz.endswith(".yaml") is False else noz,
            ambient_temp_c=args.ambient,
            z_adjust_seed=args.z,
        )
    except Exception as e:
        # try full sku filename without extension issues
        stack = compose_stack(
            filament_sku=args.filament,
            surface_sku="whambam_pex",
            nozzle_sku="brozzl_n4pro",
            ambient_temp_c=args.ambient,
            z_adjust_seed=args.z,
        )
        print("note:", e, file=sys.stderr)
    print(json.dumps(stack.as_dict(), indent=2))
    print("\n# Mainsail / console setup commands:")
    for c in stack.gcode_env_commands():
        print(c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
