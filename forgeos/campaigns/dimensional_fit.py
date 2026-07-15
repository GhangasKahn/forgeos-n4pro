"""Fit scale / flow corrections from caliper measurements (CNC-capable)."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from forgeos.precision import PrecisionTier, process_capability, recommend_xy_scale


@dataclass
class DimSample:
    axis: str  # X, Y, Z, hole
    nominal_mm: float
    measured_mm: float

    @property
    def error_mm(self) -> float:
        return self.measured_mm - self.nominal_mm

    @property
    def scale(self) -> float:
        if abs(self.nominal_mm) < 1e-9:
            return 1.0
        return self.nominal_mm / self.measured_mm if abs(self.measured_mm) > 1e-9 else 1.0


@dataclass
class DimFitResult:
    xy_scale: float
    z_scale: float
    mean_abs_error_100mm: float
    samples: int
    capability: Optional[Dict[str, Any]] = None
    cnc_passed: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def fit_scales(
    samples: List[DimSample],
    tier: PrecisionTier = PrecisionTier.CNC,
) -> DimFitResult:
    xy_scales: List[float] = []
    z_scales: List[float] = []
    err100: List[float] = []
    xy_meas: List[float] = []
    xy_nom: float = 100.0
    for s in samples:
        axis = s.axis.upper()
        if axis in {"X", "Y", "XY"}:
            xy_scales.append(s.scale)
            xy_meas.append(s.measured_mm)
            xy_nom = s.nominal_mm
            if abs(s.nominal_mm) > 1e-9:
                err100.append(abs(s.error_mm) * (100.0 / abs(s.nominal_mm)))
        elif axis == "Z":
            z_scales.append(s.scale)
    xy = sum(xy_scales) / len(xy_scales) if xy_scales else 1.0
    z = sum(z_scales) / len(z_scales) if z_scales else 1.0
    mean_err = sum(err100) / len(err100) if err100 else 0.0
    cap = None
    cnc_ok = False
    if len(xy_meas) >= 2:
        pc = process_capability(xy_meas, nominal_mm=xy_nom, tier=tier)
        cap = pc.as_dict()
        cnc_ok = pc.passed
    elif len(xy_meas) == 1:
        from forgeos.precision import get_band

        cnc_ok = abs(xy_meas[0] - xy_nom) <= get_band(tier).abs_error_max_mm
    return DimFitResult(
        xy_scale=xy,
        z_scale=z,
        mean_abs_error_100mm=mean_err,
        samples=len(samples),
        capability=cap,
        cnc_passed=cnc_ok,
    )


def apply_anneal_compensation(print_xy_scale: float, anneal_xy_scale: float) -> float:
    """Combine print scale with expected anneal shrink precompensation."""
    return float(print_xy_scale) * float(anneal_xy_scale)


def fit_xy_from_replicates(measurements_mm: List[float], nominal_mm: float = 100.0) -> float:
    return recommend_xy_scale(measurements_mm, nominal_mm)
