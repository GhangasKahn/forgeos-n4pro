"""CLI: python -m forgeos.calibration

Examples:
  python -m forgeos.calibration plan --suite onetime
  python -m forgeos.calibration dry-run --suite full
  python -m forgeos.calibration compute-flow --measured 0.46 --line-width 0.44
  python -m forgeos.calibration compute-pa --height 6.2
  python -m forgeos.calibration compute-rd --current 7.5 --actual 98.5
  python -m forgeos.calibration patterns --out artifacts/calibration
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forgeos.calibration.math_cal import (
    compute_flow_multiplier,
    compute_pressure_advance,
    compute_rotation_distance,
)
from forgeos.calibration.patterns import (
    generate_extrude_cal_script,
    generate_first_layer_patch,
    generate_flow_shell,
    generate_pa_fine_tower,
    generate_pa_tower,
    write_pattern,
)
from forgeos.calibration.protocol import CalSuite, build_plan
from forgeos.calibration.runner import CalibrationRunner
from forgeos.journal import Journal
from forgeos.safety import SafetyGate


def _cmd_plan(args: argparse.Namespace) -> int:
    plan = build_plan(
        suite=CalSuite(args.suite),
        sku=args.sku,
        has_adxl=args.adxl,
        include_optional=not args.no_optional,
    )
    print(json.dumps(plan.as_dict(), indent=2))
    return 0


def _cmd_dry_run(args: argparse.Namespace) -> int:
    journal = Journal(Path(args.journal))
    runner = CalibrationRunner(
        journal=journal,
        safety=SafetyGate(),
        artifacts_dir=Path(args.out),
    )
    runner.start(
        suite=CalSuite(args.suite),
        dry_run=True,
        has_adxl=args.adxl,
        sku=args.sku,
        include_optional=not args.no_optional,
    )
    report = runner.run_all_dry()
    path = runner.write_report(report, Path(args.report) if args.report else None)
    print(
        json.dumps(
            {"report": str(path), "steps": len(report.results), "failed": report.failed},
            indent=2,
        )
    )
    return 1 if report.failed else 0


def _cmd_patterns(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "extrude_cal.gcode": generate_extrude_cal_script(),
        "flow_shell.gcode": generate_flow_shell(),
        "pa_tower.gcode": generate_pa_tower(),
        "pa_fine.gcode": generate_pa_fine_tower(seed_pa=args.pa),
        "first_layer_patch.gcode": generate_first_layer_patch(pa=args.pa),
    }
    written = [write_pattern(str(out / name), content) for name, content in files.items()]
    print(json.dumps({"written": written}, indent=2))
    return 0


def _cmd_compute_flow(args: argparse.Namespace) -> int:
    r = compute_flow_multiplier(
        args.measured,
        line_width_mm=args.line_width,
        perimeters=args.perimeters,
        current_flow=args.current,
    )
    print(json.dumps(r.__dict__, indent=2))
    return 0


def _cmd_compute_pa(args: argparse.Namespace) -> int:
    r = compute_pressure_advance(args.height, start=args.start, factor=args.factor)
    print(json.dumps(r.__dict__, indent=2))
    return 0


def _cmd_compute_rd(args: argparse.Namespace) -> int:
    r = compute_rotation_distance(args.current, commanded_mm=args.commanded, actual_mm=args.actual)
    print(json.dumps(r.__dict__, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="forgeos.calibration",
        description="ForgeOS N4 Pro calibration OS",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="Print calibration plan JSON")
    p.add_argument("--suite", choices=["onetime", "finetune", "full"], default="full")
    p.add_argument("--sku", default="protopasta_htpla")
    p.add_argument("--adxl", action="store_true")
    p.add_argument("--no-optional", action="store_true")
    p.set_defaults(func=_cmd_plan)

    p = sub.add_parser("dry-run", help="Dry-run full campaign; write gcodes + report")
    p.add_argument("--suite", choices=["onetime", "finetune", "full"], default="full")
    p.add_argument("--sku", default="protopasta_htpla")
    p.add_argument("--adxl", action="store_true")
    p.add_argument("--no-optional", action="store_true")
    p.add_argument("--journal", default=str(ROOT / "artifacts" / "forgeos_journal.sqlite3"))
    p.add_argument("--out", default=str(ROOT / "artifacts" / "calibration"))
    p.add_argument("--report", default="")
    p.set_defaults(func=_cmd_dry_run)

    p = sub.add_parser("patterns", help="Write all calibration gcode patterns")
    p.add_argument("--out", default=str(ROOT / "artifacts" / "calibration"))
    p.add_argument("--pa", type=float, default=0.030)
    p.set_defaults(func=_cmd_patterns)

    p = sub.add_parser("compute-flow", help="Compute flow from measured wall")
    p.add_argument("--measured", type=float, required=True)
    p.add_argument("--line-width", type=float, default=0.44)
    p.add_argument("--perimeters", type=int, default=1)
    p.add_argument("--current", type=float, default=1.0)
    p.set_defaults(func=_cmd_compute_flow)

    p = sub.add_parser("compute-pa", help="Compute PA from tower height")
    p.add_argument("--height", type=float, required=True)
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--factor", type=float, default=0.005)
    p.set_defaults(func=_cmd_compute_pa)

    p = sub.add_parser("compute-rd", help="Compute rotation_distance")
    p.add_argument("--current", type=float, required=True)
    p.add_argument("--actual", type=float, required=True)
    p.add_argument("--commanded", type=float, default=100.0)
    p.set_defaults(func=_cmd_compute_rd)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
