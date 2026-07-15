#!/usr/bin/env python3
"""Plan and record dependency-ordered Neptune 4 Pro calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.calibration.audit import audit_klipper_base
from forgeos.calibration.profile import ProfileError, load_machine_profile
from forgeos.calibration.suite import CalibrationRun, build_calibration_suite

DEFAULT_STATE = ROOT / "artifacts" / "local" / "calibration_run.json"


def _evidence(values: list) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("evidence must be KEY=VALUE: %s" % value)
        key, item = value.split("=", 1)
        if not key.strip():
            raise ValueError("evidence key may not be empty")
        result[key.strip()] = item.strip()
    return result


def _load_or_create(path: Path, profile) -> CalibrationRun:
    return CalibrationRun.load(path) if path.is_file() else CalibrationRun.create(profile)


def _print_test(test, result: str = "pending") -> None:
    marker = {"pass": "[PASS]", "fail": "[FAIL]", "skipped": "[SKIP]"}.get(result, "[TODO]")
    print("%s %s — %s" % (marker, test.id, test.title))
    print("  phase/cadence: %s / %s" % (test.phase, test.cadence))
    if test.depends_on:
        print("  requires:", ", ".join(test.depends_on))
    for step in test.procedure:
        print("  -", step)
    if test.commands:
        print("  commands:", " ; ".join(test.commands))
    print("  accept:", test.acceptance)
    print("  evidence:", ", ".join(test.evidence))
    if test.conditional:
        print("  conditional: may be explicitly skipped with a reason")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=str(ROOT / "configs" / "neptune4pro.yaml"))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="print the complete calibration plan")
    plan.add_argument("--phase", choices=("one_time", "fine_tuning"))

    sub.add_parser("init", help="initialize a calibration evidence file")
    sub.add_parser("status", help="show recorded and pending tests")
    sub.add_parser("next", help="show currently unblocked tests")

    record = sub.add_parser("record", help="record a physical test result")
    record.add_argument("test_id")
    record.add_argument("result", choices=("pass", "fail", "skipped"))
    record.add_argument("--evidence", action="append", default=[], metavar="KEY=VALUE")

    audit = sub.add_parser("audit", help="compare canonical profile with Klipper base")
    audit.add_argument("--config", default=str(ROOT / "klipper" / "base" / "printer_n4pro.cfg"))

    args = parser.parse_args()
    try:
        profile = load_machine_profile(args.profile)
        tests = build_calibration_suite(profile)
        state_path = Path(args.state)
        if args.command == "plan":
            selected = [test for test in tests if args.phase is None or test.phase == args.phase]
            print("# %s calibration plan (%d tests)" % (profile.model, len(selected)))
            for test in selected:
                _print_test(test)
            return 0
        if args.command == "audit":
            findings = audit_klipper_base(profile, Path(args.config))
            if not findings:
                print("PASS: canonical machine profile matches Klipper base")
                return 0
            for finding in findings:
                print("%s: %s" % (finding.level.upper(), finding.message))
            return 1 if any(item.level == "error" for item in findings) else 0
        if args.command == "init":
            if state_path.exists():
                print("Refusing to overwrite existing run:", state_path, file=sys.stderr)
                return 2
            run = CalibrationRun.create(profile)
            run.save(state_path)
            print("Initialized:", state_path)
            return 0

        run = _load_or_create(state_path, profile)
        if run.machine_model != profile.model:
            raise ValueError("state machine does not match profile")
        if args.command == "record":
            by_id = {test.id: test for test in tests}
            if args.test_id not in by_id:
                raise ValueError("unknown test id: %s" % args.test_id)
            run.record(by_id[args.test_id], args.result, _evidence(args.evidence), tests)
            run.save(state_path)
            print("Recorded %s=%s" % (args.test_id, args.result))
            return 0
        if args.command == "next":
            ready = run.next_tests(tests)
            if not ready:
                print("No unblocked tests. Resolve failures or the run is complete.")
            for test in ready:
                _print_test(test)
            return 0
        if args.command == "status":
            print(json.dumps(run.summary(tests), sort_keys=True))
            for test in tests:
                result = run.results.get(test.id, {}).get("result", "pending")
                print("%-9s %s" % (result.upper(), test.id))
            return 1 if run.summary(tests)["fail"] else 0
    except (OSError, ValueError, ProfileError, json.JSONDecodeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
