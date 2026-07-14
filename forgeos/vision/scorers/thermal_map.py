"""Thermal bed map scoring (IR grid → soak / dissipation metrics)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple
import math


@dataclass
class ThermalMapResult:
    mean_c: float
    min_c: float
    max_c: float
    p2p_c: float
    std_c: float
    uniform: bool
    cold_quadrant: str  # nw|ne|sw|se|center|none
    suggestion: str

    def as_dict(self):
        return self.__dict__.copy()


def analyze_thermal_grid(
    grid: Sequence[Sequence[float]],
    target_c: float = 65.0,
    max_p2p_c: float = 4.0,
) -> ThermalMapResult:
    """grid: row-major temperatures in C (e.g. 24x32 MLX90640)."""
    vals: List[float] = [float(v) for row in grid for v in row]
    if not vals:
        return ThermalMapResult(0, 0, 0, 0, 0, False, "none", "NO_DATA")
    mean = sum(vals) / len(vals)
    mn, mx = min(vals), max(vals)
    p2p = mx - mn
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = math.sqrt(var)

    # crude quadrant mins
    rows = len(grid)
    cols = len(grid[0])
    mid_r, mid_c = rows // 2, cols // 2

    def quad_mean(r0, r1, c0, c1):
        s, n = 0.0, 0
        for r in range(r0, r1):
            for c in range(c0, c1):
                s += float(grid[r][c])
                n += 1
        return s / max(1, n)

    q = {
        "nw": quad_mean(0, mid_r, 0, mid_c),
        "ne": quad_mean(0, mid_r, mid_c, cols),
        "sw": quad_mean(mid_r, rows, 0, mid_c),
        "se": quad_mean(mid_r, rows, mid_c, cols),
    }
    cold = min(q, key=q.get)
    uniform = p2p <= max_p2p_c and abs(mean - target_c) < 3.0
    if not uniform:
        if p2p > max_p2p_c:
            suggestion = "EXTEND_SOAK cold_quad=%s" % cold
        else:
            suggestion = "WAIT_TARGET mean=%.1f target=%.1f" % (mean, target_c)
    else:
        suggestion = "SOAK_OK"
        cold = "none"

    return ThermalMapResult(
        mean_c=mean,
        min_c=mn,
        max_c=mx,
        p2p_c=p2p,
        std_c=std,
        uniform=uniform,
        cold_quadrant=cold,
        suggestion=suggestion,
    )
