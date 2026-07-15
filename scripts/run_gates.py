#!/usr/bin/env python3
"""Evaluate zero-trust gates G0–G7 from local evidence / optional live Moonraker.

Examples:
  python3 scripts/run_gates.py --g0
  python3 scripts/run_gates.py --g3-error 0.12 --g4-span 0.06
  python3 scripts/run_gates.py --host 192.168.1.178 --live-g1-g2
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.gates.verification import (
    VerificationReport,
    gate_g0_static,
    gate_g1_hardware,
    gate_g2_process_sensors,
    gate_g3_accuracy,
    gate_g4_precision,
    gate_g5_speed,
    gate_g6_anneal,
    gate_g7_reliability,
)
from forgeos.materials import default_materials_dir, load_all_packs
from forgeos.moonraker_client import MoonrakerClient


def _run_pytest() -> int:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        return 0
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="ForgeOS zero-trust gate harness")
    ap.add_argument("--g0", action="store_true", help="Run pytest + material count")
    ap.add_argument("--live-g1-g2", action="store_true")
    ap.add_argument("--host", default="192.168.1.178")
    ap.add_argument("--port", type=int, default=7125)
    ap.add_argument("--abrasive", action="store_true")
    ap.add_argument("--nozzle-ok", action="store_true", default=True)
    ap.add_argument("--shaper-ok", action="store_true", default=False)
    ap.add_argument("--thermal-stable", action="store_true", default=True)
    ap.add_argument("--mesh-p2p", type=float, default=None)
    ap.add_argument("--g3-error", type=float, default=None, help="|err| mm per 100 mm")
    ap.add_argument("--g4-span", type=float, default=None)
    ap.add_argument("--g5-duration", type=float, default=None)
    ap.add_argument("--g5-baseline", type=float, default=None)
    ap.add_argument("--g6-err", type=float, default=None)
    ap.add_argument("--g7-mcu-losses", type=int, default=None)
    ap.add_argument("--g7-log-mb", type=float, default=None)
    ap.add_argument("--g7-soak-h", type=float, default=None)
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "gate_report.json"))
    args = ap.parse_args()

    report = VerificationReport()

    if args.g0:
        failures = _run_pytest()
        n = len(load_all_packs(default_materials_dir()))
        report.add(gate_g0_static(n, failures))

    if args.live_g1_g2:
        client = MoonrakerClient(host=args.host, port=args.port)
        ready = client.is_ready()
        disk = shutil.disk_usage(str(ROOT)).free / (1024 * 1024)
        report.add(
            gate_g1_hardware(
                mcu_ready=ready,
                disk_free_mb=disk,
                abrasive=args.abrasive,
                nozzle_ok=args.nozzle_ok,
            )
        )
        p2p = args.mesh_p2p
        if p2p is None:
            p2p = client.mesh_peak_to_peak()
        if p2p is None:
            p2p = 0.99  # force soft fail if unknown on live request
        report.add(
            gate_g2_process_sensors(
                mesh_peak_to_peak_mm=float(p2p),
                shaper_ok=args.shaper_ok,
                thermal_stable=args.thermal_stable,
            )
        )
    elif args.mesh_p2p is not None:
        report.add(
            gate_g2_process_sensors(
                mesh_peak_to_peak_mm=args.mesh_p2p,
                shaper_ok=args.shaper_ok,
                thermal_stable=args.thermal_stable,
            )
        )

    if args.g3_error is not None:
        report.add(gate_g3_accuracy(args.g3_error))
    if args.g4_span is not None:
        report.add(gate_g4_precision(args.g4_span))
    if args.g5_duration is not None and args.g5_baseline is not None:
        report.add(gate_g5_speed(args.g5_duration, args.g5_baseline))
    if args.g6_err is not None:
        report.add(gate_g6_anneal(args.g6_err))
    if args.g7_mcu_losses is not None:
        report.add(
            gate_g7_reliability(
                mcu_losses=args.g7_mcu_losses,
                log_growth_mb_per_day=float(args.g7_log_mb or 1.0),
                soak_hours=float(args.g7_soak_h or 2.0),
            )
        )

    if not report.results:
        ap.print_help()
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = report.summary()
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("all_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
