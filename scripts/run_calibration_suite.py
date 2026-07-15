#!/usr/bin/env python3
"""ForgeOS calibration suite CLI — plan, analyze, generate G-code, live run.

Examples:
  python3 scripts/run_calibration_suite.py --plan one_time
  python3 scripts/run_calibration_suite.py --plan fine_tune
  python3 scripts/run_calibration_suite.py --analyze mesh --p2p 0.19
  python3 scripts/run_calibration_suite.py --analyze pa --height 12.5
  python3 scripts/run_calibration_suite.py --analyze flow --wall 0.44 --line 0.44
  python3 scripts/run_calibration_suite.py --analyze g3 --measured 99.85
  python3 scripts/run_calibration_suite.py --gcode flow_cube -o artifacts/gcodes/flow_cube.gcode
  python3 scripts/run_calibration_suite.py --live one_time --host 192.168.1.178 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.calibration.analysis import (
    analyze_accuracy_error,
    analyze_flow_wall_thickness,
    analyze_mesh_matrix,
    analyze_pa_tower_height,
    analyze_precision_span,
)
from forgeos.calibration.gcodes import gcode_for_test_id
from forgeos.calibration.ledger import GateLedger
from forgeos.calibration.registry import (
    CALIBRATION_CATALOG,
    calibration_tests_for_category,
)
from forgeos.calibration.runner import CalibrationRunner
from forgeos.calibration.types import CalCategory
from forgeos.core.evidence import append_jsonl, write_evidence
from forgeos.journal import Journal
from forgeos.moonraker_client import MoonrakerClient
from forgeos.safety import SafetyGate
from forgeos.stack_profile import compose_stack


def cmd_list(_: argparse.Namespace) -> int:
    for tid, t in sorted(CALIBRATION_CATALOG.items()):
        print(
            "%-24s %-10s %-10s %s"
            % (tid, t.category.value, t.phase.value, t.name)
        )
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    runner = CalibrationRunner()
    report = runner.plan_report(args.plan)
    print(json.dumps(report, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("wrote", args.out)
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    if args.analyze == "mesh":
        if args.matrix_file:
            import ast

            data = ast.literal_eval(Path(args.matrix_file).read_text(encoding="utf-8"))
            result = analyze_mesh_matrix(data)
        elif args.p2p is not None:
            # synthetic 3x3 for p2p-only quick check
            base = 0.0
            matrix = [[base, base + args.p2p / 2, base + args.p2p]]
            result = analyze_mesh_matrix(matrix)
        else:
            print("mesh: provide --p2p or --matrix-file")
            return 2
    elif args.analyze == "pa":
        if args.height is None:
            print("pa: provide --height (mm to sharpest corner)")
            return 2
        result = analyze_pa_tower_height(args.height, args.pa_start, args.pa_factor)
    elif args.analyze == "flow":
        if args.wall is None:
            print("flow: provide --wall (measured mm)")
            return 2
        result = analyze_flow_wall_thickness(args.wall, args.line or 0.44)
    elif args.analyze == "g3":
        if args.measured is None:
            print("g3: provide --measured (mm)")
            return 2
        result = analyze_accuracy_error(args.measured, args.nominal or 100.0)
        led = GateLedger(precision_tier="cnc")
        led.record_g3(float(args.measured), float(args.nominal or 100.0))
        path = write_evidence(
            "g3_measure",
            {
                "mean_mm": float(args.measured),
                "n": 1,
                "verdict": "PASS" if result.passed else "FAIL",
                "analysis": result.as_dict(),
                "ledger": led.as_dict(),
            },
            stamp=True,
        )
        print("evidence:", path)
    elif args.analyze == "g4":
        if not args.measurements:
            print("g4: provide --measurements 99.9 100.0 99.95")
            return 2
        result = analyze_precision_span(args.measurements)
        led = GateLedger(precision_tier="cnc")
        led.record_g4([float(x) for x in args.measurements])
        path = write_evidence(
            "g4_measure",
            {
                "measurements_mm": list(args.measurements),
                "n": len(args.measurements),
                "verdict": "PASS" if result.passed else "FAIL",
                "analysis": result.as_dict(),
                "ledger": led.as_dict(),
            },
            stamp=True,
        )
        print("evidence:", path)
    else:
        print("unknown analyze mode")
        return 2
    print(json.dumps(result.as_dict(), indent=2))
    append_jsonl(
        "cal_run_log_%s" % __import__("time").strftime("%Y%m%d"),
        {"event": "analyze", "mode": args.analyze, "passed": result.passed, "summary": result.summary},
    )
    return 0 if result.passed else 1


def cmd_gcode(args: argparse.Namespace) -> int:
    stack = compose_stack(ambient_temp_c=args.ambient)
    # Aliases for catalog ids
    key = args.gcode
    try:
        body = gcode_for_test_id(
            key,
            bed_c=stack.bed_c,
            nozzle_c=stack.nozzle_c,
            line_w=stack.line_width_mm,
            first_speed_mm_s=stack.first_layer_speed_mm_s,
            layer_h=stack.first_layer_height_mm,
        )
    except ValueError as exc:
        print(exc)
        return 2
    out = Path(args.out or "artifacts/gcodes/cal_%s.gcode" % key)
    out.parent.mkdir(parents=True, exist_ok=True)
    header = "\n".join(stack.gcode_env_commands()) + "\n"
    out.write_text(header + body, encoding="utf-8")
    print("wrote", out)
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    journal = Journal(ROOT / "artifacts" / "calibration_journal.sqlite3")
    safety = SafetyGate()
    client = MoonrakerClient(args.host, args.port, timeout_s=30.0)
    runner = CalibrationRunner(journal=journal, safety=safety, client=client)
    if not args.dry_run:
        if not args.arm_token:
            tok = safety.arm("campaign")
            print("armed with token:", tok)
            runner.arm(tok)
        else:
            runner.arm(args.arm_token)
    summary = runner.run_live_sequence(mode=args.live, dry_run=args.dry_run)
    print(json.dumps(summary, indent=2))
    report_path = Path(args.report or ROOT / "artifacts" / "calibration_live_report.json")
    runner.write_report(report_path)
    print("report:", report_path)
    return 0 if summary.get("all_ok") else 1


def cmd_catalog(args: argparse.Namespace) -> int:
    cat = CalCategory(args.category) if args.category else None
    tests = calibration_tests_for_category(cat) if cat else list(CALIBRATION_CATALOG.values())
    print(json.dumps([t.as_dict() for t in tests], indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ForgeOS calibration suite")
    sub = ap.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="List all calibration tests")
    p_list.set_defaults(func=cmd_list)

    p_plan = sub.add_parser("plan", help="Plan calibration sequence")
    p_plan.add_argument("plan", choices=["one_time", "fine_tune", "full", "cnc_close"])
    p_plan.add_argument("--out", default="")
    p_plan.set_defaults(func=cmd_plan)

    p_an = sub.add_parser("analyze", help="Analyze measurement")
    p_an.add_argument("analyze", choices=["mesh", "pa", "flow", "g3", "g4"])
    p_an.add_argument("--p2p", type=float)
    p_an.add_argument("--matrix-file")
    p_an.add_argument("--height", type=float)
    p_an.add_argument("--pa-start", type=float, default=0.0)
    p_an.add_argument("--pa-factor", type=float, default=0.005)
    p_an.add_argument("--wall", type=float)
    p_an.add_argument("--line", type=float, default=0.44)
    p_an.add_argument("--measured", type=float)
    p_an.add_argument("--nominal", type=float, default=100.0)
    p_an.add_argument("--measurements", type=float, nargs="+")
    p_an.set_defaults(func=cmd_analyze)

    p_gc = sub.add_parser("gcode", help="Generate calibration G-code")
    p_gc.add_argument(
        "gcode",
        choices=[
            "flow_cube",
            "flow_rate",
            "first_layer",
            "first_layer_squish",
            "pressure_advance",
            "temperature_tower",
            "retraction_distance",
            "rotation_distance",
            "z_offset_live",
        ],
    )
    p_gc.add_argument("-o", "--out", default="")
    p_gc.add_argument("--ambient", type=float, default=14.0)
    p_gc.set_defaults(func=cmd_gcode)

    p_live = sub.add_parser("live", help="Run live calibration on printer")
    p_live.add_argument("live", choices=["one_time", "fine_tune", "full", "cnc_close"])
    p_live.add_argument("--host", default="192.168.1.178")
    p_live.add_argument("--port", type=int, default=7125)
    p_live.add_argument("--dry-run", action="store_true")
    p_live.add_argument("--arm-token", default="")
    p_live.add_argument("--report", default="")
    p_live.set_defaults(func=cmd_live)

    p_cat = sub.add_parser("catalog", help="Dump catalog JSON")
    p_cat.add_argument("--category", choices=[c.value for c in CalCategory])
    p_cat.set_defaults(func=cmd_catalog)

    # Top-level shortcuts (backward compatible)
    ap.add_argument("--plan", choices=["one_time", "fine_tune", "full", "cnc_close"])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--analyze", choices=["mesh", "pa", "flow", "g3", "g4"])
    ap.add_argument(
        "--gcode",
        choices=[
            "flow_cube",
            "flow_rate",
            "first_layer",
            "first_layer_squish",
            "pressure_advance",
            "temperature_tower",
            "retraction_distance",
            "rotation_distance",
            "z_offset_live",
        ],
    )
    ap.add_argument("--live", choices=["one_time", "fine_tune", "full", "cnc_close"])
    ap.add_argument("--host", default="192.168.1.178")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--p2p", type=float)
    ap.add_argument("--height", type=float)
    ap.add_argument("--wall", type=float)
    ap.add_argument("--measured", type=float)
    ap.add_argument("--measurements", type=float, nargs="+")
    ap.add_argument("--ambient", type=float, default=14.0)

    args = ap.parse_args()
    if args.command:
        return args.func(args)
    # shortcut mode
    if args.list:
        return cmd_list(args)
    if args.plan:
        args.out = args.out  # noqa — plan subparser field
        ns = argparse.Namespace(plan=args.plan, out=args.out)
        return cmd_plan(ns)
    if args.analyze:
        ns = argparse.Namespace(
            analyze=args.analyze,
            p2p=args.p2p,
            matrix_file=None,
            height=args.height,
            pa_start=0.0,
            pa_factor=0.005,
            wall=args.wall,
            line=0.44,
            measured=args.measured,
            nominal=100.0,
            measurements=args.measurements,
        )
        return cmd_analyze(ns)
    if args.gcode:
        ns = argparse.Namespace(gcode=args.gcode, out=args.out, ambient=args.ambient)
        return cmd_gcode(ns)
    if args.live:
        ns = argparse.Namespace(
            live=args.live,
            host=args.host,
            port=7125,
            dry_run=args.dry_run,
            arm_token="",
            report="",
        )
        return cmd_live(ns)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
