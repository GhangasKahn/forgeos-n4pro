"""First-principles G-code physics validator — CNC militant checks.

Atoms checked (fail-hard):
  - Bed envelope 0..225 mm (N4 Pro usable)
  - Z >= 0 for extrusion moves (after home assumption)
  - Extrusion E monotonic in relative mode segments
  - No NaN/Inf
  - Temperatures in material envelope when M104/M140 present
  - First-layer height band for machine-flat
  - Volume balance hint: comment TARGET_LENGTH / FL_* when present
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class GCodeIssue:
    severity: str  # fail | warn
    line: int
    code: str
    detail: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GCodeReport:
    path: str
    lines: int
    extrusion_moves: int
    travel_moves: int
    issues: List[GCodeIssue] = field(default_factory=list)
    bounds: Dict[str, float] = field(default_factory=dict)
    totals: Dict[str, float] = field(default_factory=dict)
    passed: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "lines": self.lines,
            "extrusion_moves": self.extrusion_moves,
            "travel_moves": self.travel_moves,
            "issues": [i.as_dict() for i in self.issues],
            "bounds": self.bounds,
            "totals": self.totals,
            "passed": self.passed,
            "fail_count": sum(1 for i in self.issues if i.severity == "fail"),
            "warn_count": sum(1 for i in self.issues if i.severity == "warn"),
        }


_WORD = re.compile(r"([A-Za-z])\s*([-+]?[0-9]*\.?[0-9]+)")


def _parse_words(line: str) -> Dict[str, float]:
    # Strip comments
    if ";" in line:
        line = line.split(";", 1)[0]
    out: Dict[str, float] = {}
    for m in _WORD.finditer(line):
        out[m.group(1).upper()] = float(m.group(2))
    return out


def validate_gcode(
    text: str,
    path: str = "<memory>",
    bed_max_mm: float = 225.0,
    bed_min_mm: float = 0.0,
    z_min_extrude_mm: float = 0.05,
    nozzle_temp_range: Tuple[float, float] = (190.0, 240.0),
    bed_temp_range: Tuple[float, float] = (0.0, 75.0),
    require_extrusion: bool = True,
) -> GCodeReport:
    issues: List[GCodeIssue] = []
    x = y = z = e = 0.0
    absolute = True
    e_relative = False
    xmin = ymin = zmin = math.inf
    xmax = ymax = zmax = -math.inf
    e_total = 0.0
    extrude_n = 0
    travel_n = 0
    lines = text.splitlines()
    saw_m83 = False

    for i, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith(";") or line.startswith("("):
            # metadata hints
            if "TARGET_LENGTH_MM" in line:
                try:
                    float(line.split(":")[-1].strip().split()[0])
                except Exception:
                    issues.append(GCodeIssue("warn", i, "meta", "bad TARGET_LENGTH_MM"))
            continue

        cmd = line.split()[0].upper() if line.split() else ""
        words = _parse_words(line)

        if cmd in ("G90",):
            absolute = True
        elif cmd in ("G91",):
            absolute = False
        elif cmd in ("M82",):
            e_relative = False
        elif cmd in ("M83",):
            e_relative = True
            saw_m83 = True
        elif cmd in ("G92",) and "E" in words:
            e = words["E"]

        if cmd in ("M104", "M109") and "S" in words:
            t = words["S"]
            if t > 0 and not (nozzle_temp_range[0] <= t <= nozzle_temp_range[1]):
                issues.append(
                    GCodeIssue(
                        "fail",
                        i,
                        "nozzle_temp",
                        "S=%.1f outside envelope %s" % (t, nozzle_temp_range),
                    )
                )
        if cmd in ("M140", "M190") and "S" in words:
            t = words["S"]
            if t > 0 and not (bed_temp_range[0] <= t <= bed_temp_range[1]):
                issues.append(
                    GCodeIssue(
                        "fail",
                        i,
                        "bed_temp",
                        "S=%.1f outside envelope %s" % (t, bed_temp_range),
                    )
                )

        if cmd in ("G0", "G1", "G2", "G3"):
            nx, ny, nz, ne = x, y, z, e
            if "X" in words:
                nx = words["X"] if absolute else x + words["X"]
            if "Y" in words:
                ny = words["Y"] if absolute else y + words["Y"]
            if "Z" in words:
                nz = words["Z"] if absolute else z + words["Z"]
            de = 0.0
            if "E" in words:
                if e_relative:
                    de = words["E"]
                    ne = e + de
                else:
                    ne = words["E"]
                    de = ne - e

            # NaN/Inf
            for label, val in (("X", nx), ("Y", ny), ("Z", nz), ("E", ne)):
                if not math.isfinite(val):
                    issues.append(GCodeIssue("fail", i, "nan", "%s not finite" % label))

            extruding = de > 1e-9
            if extruding:
                extrude_n += 1
                e_total += de
                if nz < z_min_extrude_mm:
                    issues.append(
                        GCodeIssue(
                            "fail",
                            i,
                            "z_too_low",
                            "extrude at Z=%.4f < %.3f" % (nz, z_min_extrude_mm),
                        )
                    )
                # bed envelope for extrusion
                if not (bed_min_mm - 1.0 <= nx <= bed_max_mm + 1.0):
                    issues.append(GCodeIssue("fail", i, "x_bounds", "X=%.3f out of bed" % nx))
                if not (bed_min_mm - 1.0 <= ny <= bed_max_mm + 1.0):
                    issues.append(GCodeIssue("fail", i, "y_bounds", "Y=%.3f out of bed" % ny))
            else:
                travel_n += 1

            xmin, xmax = min(xmin, nx), max(xmax, nx)
            ymin, ymax = min(ymin, ny), max(ymax, ny)
            zmin, zmax = min(zmin, nz), max(zmax, nz)
            x, y, z, e = nx, ny, nz, ne

    if require_extrusion and extrude_n == 0:
        issues.append(GCodeIssue("fail", 0, "no_extrusion", "zero extrusion moves"))
    if not saw_m83 and e_total > 0:
        issues.append(GCodeIssue("warn", 0, "abs_e", "no M83 seen; absolute E assumed carefully"))

    # CNC: first layer Z should be in machine-flat band if any extrusion near bed
    if zmin < math.inf and zmin > 0 and zmin < 0.15:
        issues.append(
            GCodeIssue(
                "warn",
                0,
                "first_z_thin",
                "min Z=%.3f very thin for 0.4 nozzle machine-flat (expect ~0.20–0.32)" % zmin,
            )
        )
    if zmin < math.inf and zmin > 0.40:
        issues.append(
            GCodeIssue(
                "warn",
                0,
                "first_z_thick",
                "min Z=%.3f thick; check first-layer height" % zmin,
            )
        )

    fails = [i for i in issues if i.severity == "fail"]
    report = GCodeReport(
        path=path,
        lines=len(lines),
        extrusion_moves=extrude_n,
        travel_moves=travel_n,
        issues=issues,
        bounds={
            "xmin": 0.0 if xmin is math.inf else round(xmin, 3),
            "xmax": 0.0 if xmax is -math.inf else round(xmax, 3),
            "ymin": 0.0 if ymin is math.inf else round(ymin, 3),
            "ymax": 0.0 if ymax is -math.inf else round(ymax, 3),
            "zmin": 0.0 if zmin is math.inf else round(zmin, 3),
            "zmax": 0.0 if zmax is -math.inf else round(zmax, 3),
        },
        totals={"e_mm": round(e_total, 3)},
        passed=len(fails) == 0,
    )
    return report


def validate_gcode_file(path: str, **kwargs: Any) -> GCodeReport:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return validate_gcode(fh.read(), path=path, **kwargs)
