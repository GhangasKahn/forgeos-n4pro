#!/usr/bin/env python3
"""Run ForgeOS calibration campaign (dry-run by default).

Examples:
  python3 scripts/run_full_cal.py --suite onetime
  python3 scripts/run_full_cal.py --suite full --adxl
  python3 scripts/run_full_cal.py --suite finetune --patterns-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.calibration import CalSuite, CalibrationRunner
from forgeos.calibration.patterns import (
    generate_extrude_cal_script,
    generate_first_layer_patch,
    generate_flow_shell,
    generate_pa_fine_tower,
    generate_pa_tower,
    write_pattern,
)
from forgeos.journal import Journal
from forgeos.moonraker_client import MoonrakerClient
from forgeos.safety import SafetyGate


def main() -> int:
    ap = argparse.ArgumentParser(description="ForgeOS N4 Pro calibration runner")
    ap.add_argument("--suite", choices=["onetime", "finetune", "full"], default="full")
    ap.add_argument("--sku", default="protopasta_htpla")
    ap.add_argument("--adxl", action="store_true", help="Accelerometer present for shaper step")
    ap.add_argument("--no-optional", action="store_true")
    ap.add_argument("--patterns-only", action="store_true", help="Only write gcode patterns")
    ap.add_argument("--execute", action="store_true", help="Live Moonraker AUTO steps (requires --arm)")
    ap.add_argument("--arm", action="store_true", help="Arm SafetyGate campaign token")
    ap.add_argument("--host", default="192.168.1.178")
    ap.add_argument("--port", type=int, default=7125)
    ap.add_argument("--journal", default=str(ROOT / "artifacts" / "forgeos_journal.sqlite3"))
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "calibration"))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.patterns_only:
        files = {
            "extrude_cal.gcode": generate_extrude_cal_script(),
            "flow_shell.gcode": generate_flow_shell(),
            "pa_tower.gcode": generate_pa_tower(),
            "pa_fine.gcode": generate_pa_fine_tower(),
            "first_layer_patch.gcode": generate_first_layer_patch(),
        }
        written = [write_pattern(str(out / n), c) for n, c in files.items()]
        print(json.dumps({"written": written}, indent=2))
        return 0

    journal = Journal(args.journal)
    safety = SafetyGate()
    client = None
    token = None
    dry_run = not args.execute
    if args.execute:
        if not args.arm:
            print("ERROR: --execute requires --arm (zero-trust)", file=sys.stderr)
            return 2
        token = safety.arm("campaign", ttl_s=4 * 3600)
        client = MoonrakerClient(host=args.host, port=args.port)
        if not client.is_ready():
            print("ERROR: printer not ready at %s:%d" % (args.host, args.port), file=sys.stderr)
            return 3
        try:
            safety.sync_printer_arm(client, purpose="campaign")
        except Exception as exc:  # noqa: BLE001
            print("WARN: printer arm sync failed: %s" % exc, file=sys.stderr)

    runner = CalibrationRunner(
        journal=journal,
        safety=safety,
        client=client,
        artifacts_dir=out,
    )
    plan = runner.start(
        suite=CalSuite(args.suite),
        arm_token=token,
        dry_run=dry_run,
        execute=args.execute,
        has_adxl=args.adxl,
        include_optional=not args.no_optional,
        sku=args.sku,
    )
    print(json.dumps({"plan_steps": [s.id for s in plan.steps], "dry_run": dry_run}, indent=2))

    if dry_run:
        report = runner.run_all_dry()
        path = runner.write_report(report)
        print(json.dumps({"report": str(path), "steps": len(report.results), "failed": report.failed}, indent=2))
        return 1 if report.failed else 0

    # Live: run AUTO steps; pause on interactive/measure with WAITING status
    results = []
    while runner.current_step is not None:
        result = runner.run_current(auto_pass_dry=False)
        results.append(result.as_dict())
        print(json.dumps(result.as_dict(), indent=2))
        if result.status.value == "waiting_operator":
            print(
                "OPERATOR: complete step '%s' then:\n"
                "  python3 -m forgeos.calibration  # use submit via API / next session\n"
                "  or advance evidence with CalibrationRunner.submit_evidence(...)"
                % result.step_id,
                file=sys.stderr,
            )
            break
        if result.status.value == "failed":
            break
        if runner.advance() is None and runner._idx >= len(plan.steps):
            break

    path = out / "cal_live_partial.json"
    path.write_text(json.dumps({"results": results}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"partial_report": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
