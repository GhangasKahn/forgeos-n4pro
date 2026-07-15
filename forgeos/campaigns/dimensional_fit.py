"""Fit scale / flow corrections from caliper measurements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


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
        # If part measures short, scale CAD/print up
        return self.nominal_mm / self.measured_mm if abs(self.measured_mm) > 1e-9 else 1.0


@dataclass
class DimFitResult:
    xy_scale: float
    z_scale: float
    mean_abs_error_100mm: float
    samples: int


def fit_scales(samples: List[DimSample]) -> DimFitResult:
    xy_scales: List[float] = []
    z_scales: List[float] = []
    err100: List[float] = []
    for s in samples:
        axis = s.axis.upper()
        if axis in {"X", "Y", "XY"}:
            xy_scales.append(s.scale)
            # normalize error to 100 mm span
            if abs(s.nominal_mm) > 1e-9:
                err100.append(abs(s.error_mm) * (100.0 / abs(s.nominal_mm)))
        elif axis == "Z":
            z_scales.append(s.scale)
        elif axis == "HOLE":
            # Undersized holes → positive compensation (extra clearance) handled at CAD/slicer
            # Track scale inverted vs solid axes for journal visibility
            if abs(s.measured_mm) > 1e-9:
                xy_scales.append(s.measured_mm / s.nominal_mm if abs(s.nominal_mm) > 1e-9 else 1.0)
            if abs(s.nominal_mm) > 1e-9:
                err100.append(abs(s.error_mm) * (100.0 / abs(s.nominal_mm)))
    xy = sum(xy_scales) / len(xy_scales) if xy_scales else 1.0
    z = sum(z_scales) / len(z_scales) if z_scales else 1.0
    mean_err = sum(err100) / len(err100) if err100 else 0.0
    return DimFitResult(xy_scale=xy, z_scale=z, mean_abs_error_100mm=mean_err, samples=len(samples))


def apply_anneal_compensation(print_xy_scale: float, anneal_xy_scale: float) -> float:
    """Combine print scale with expected anneal shrink precompensation."""
    return float(print_xy_scale) * float(anneal_xy_scale)
