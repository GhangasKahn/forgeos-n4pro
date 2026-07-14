#!/usr/bin/env python3
"""Import caliper CSV and fit dimensional scales.

CSV columns: axis,nominal_mm,measured_mm
Example:
  X,100.0,99.85
  Y,100.0,99.90
  Z,20.0,20.10
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.campaigns.dimensional_fit import DimSample, fit_scales
from forgeos.journal import Journal


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--journal", default=str(ROOT / "artifacts" / "forgeos_journal.sqlite3"))
    ap.add_argument("--print-id", type=int, default=None)
    args = ap.parse_args()

    samples = []
    with open(args.csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            samples.append(
                DimSample(
                    axis=row["axis"],
                    nominal_mm=float(row["nominal_mm"]),
                    measured_mm=float(row["measured_mm"]),
                )
            )
    fit = fit_scales(samples)
    journal = Journal(args.journal)
    for s in samples:
        journal.record_measurement(args.print_id, s.axis, s.nominal_mm, s.measured_mm)
    journal.log_event(
        "dim_fit",
        {
            "xy_scale": fit.xy_scale,
            "z_scale": fit.z_scale,
            "mean_abs_error_100mm": fit.mean_abs_error_100mm,
            "samples": fit.samples,
        },
    )
    print(
        json.dumps(
            {
                "xy_scale": fit.xy_scale,
                "z_scale": fit.z_scale,
                "mean_abs_error_100mm": fit.mean_abs_error_100mm,
                "samples": fit.samples,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
