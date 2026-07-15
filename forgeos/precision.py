"""CNC-grade precision / process capability for fixture prints.

Target bands (100 mm feature):
  SHOP     |err| ≤ 0.20 mm, span ≤ 0.10 mm  (legacy)
  FIXTURE  |err| ≤ 0.15 mm, span ≤ 0.08 mm
  CNC      |err| ≤ 0.10 mm, span ≤ 0.05 mm  (GOD-TIER default)

Repeatability uses span + sample std-dev + simple Cp/Cpk against bilateral
tolerance (process capability).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from math import sqrt
from typing import Any, Dict, List, Optional, Sequence


class PrecisionTier(str, Enum):
    SHOP = "shop"
    FIXTURE = "fixture"
    CNC = "cnc"


@dataclass(frozen=True)
class PrecisionBand:
    """Bilateral tolerance on a 100 mm feature."""

    name: str
    abs_error_max_mm: float
    span_max_mm: float
    mesh_p2p_max_mm: float
    mesh_preferred_mm: float
    perfect_error_mm: float = 0.02
    perfect_span_mm: float = 0.02

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


BANDS: Dict[PrecisionTier, PrecisionBand] = {
    PrecisionTier.SHOP: PrecisionBand("shop", 0.20, 0.10, 0.80, 0.40),
    PrecisionTier.FIXTURE: PrecisionBand("fixture", 0.15, 0.08, 0.40, 0.25),
    PrecisionTier.CNC: PrecisionBand("cnc", 0.10, 0.05, 0.25, 0.15),
}

DEFAULT_TIER = PrecisionTier.CNC


def get_band(tier: PrecisionTier = DEFAULT_TIER) -> PrecisionBand:
    return BANDS[tier]


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = _mean(xs)
    return sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


@dataclass
class ProcessCapability:
    """Simple process capability on a dimensional feature."""

    nominal_mm: float
    tolerance_mm: float  # bilateral ±
    n: int
    mean_mm: float
    stdev_mm: float
    span_mm: float
    mean_error_mm: float
    abs_mean_error_mm: float
    cp: Optional[float]
    cpk: Optional[float]
    within_tolerance: bool
    passed: bool
    tier: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def process_capability(
    measurements_mm: Sequence[float],
    nominal_mm: float = 100.0,
    tier: PrecisionTier = DEFAULT_TIER,
) -> ProcessCapability:
    """Cp/Cpk vs bilateral CNC band; requires ≥2 samples for stdev/Cp."""
    band = get_band(tier)
    tol = band.abs_error_max_mm
    xs = [float(x) for x in measurements_mm]
    n = len(xs)
    mean = _mean(xs)
    stdev = _stdev(xs)
    span = (max(xs) - min(xs)) if n >= 2 else 0.0
    err = mean - nominal_mm
    usl = nominal_mm + tol
    lsl = nominal_mm - tol
    cp: Optional[float] = None
    cpk: Optional[float] = None
    if stdev > 1e-12 and n >= 2:
        cp = (usl - lsl) / (6.0 * stdev)
        cpu = (usl - mean) / (3.0 * stdev)
        cpl = (mean - lsl) / (3.0 * stdev)
        cpk = min(cpu, cpl)
    within = all(abs(x - nominal_mm) <= tol for x in xs)
    # CNC pass: span + mean error within band; Cpk ≥ 1.0 when n≥3
    passed = within and span <= band.span_max_mm
    if n >= 3 and cpk is not None:
        passed = passed and cpk >= 1.0
    return ProcessCapability(
        nominal_mm=nominal_mm,
        tolerance_mm=tol,
        n=n,
        mean_mm=round(mean, 5),
        stdev_mm=round(stdev, 5),
        span_mm=round(span, 5),
        mean_error_mm=round(err, 5),
        abs_mean_error_mm=round(abs(err), 5),
        cp=round(cp, 3) if cp is not None else None,
        cpk=round(cpk, 3) if cpk is not None else None,
        within_tolerance=within,
        passed=passed,
        tier=band.name,
    )


def scale_correction(nominal_mm: float, measured_mm: float) -> float:
    """XY scale to apply so next print hits nominal (nominal/measured)."""
    if abs(measured_mm) < 1e-9:
        return 1.0
    return float(nominal_mm) / float(measured_mm)


def recommend_xy_scale(measurements_mm: Sequence[float], nominal_mm: float = 100.0) -> float:
    """Mean-based scale from replicate coupons."""
    if not measurements_mm:
        return 1.0
    mean = _mean(measurements_mm)
    return scale_correction(nominal_mm, mean)
