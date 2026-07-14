#!/usr/bin/env python3
"""Run G0 static zero-trust gate (materials + unit tests)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.gates.verification import gate_g0_static
from forgeos.materials import load_all_packs, default_materials_dir


def main() -> int:
    packs = load_all_packs(default_materials_dir())
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    failures = 0 if proc.returncode == 0 else 1
    result = gate_g0_static(len(packs), failures)
    print(result.as_dict())
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
    return 0 if result.status.value == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
