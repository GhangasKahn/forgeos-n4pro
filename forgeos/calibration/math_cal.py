"""Calibration math for Neptune 4 Pro / Klipper / OpenNeptune workflows.

Formulas match Klipper docs + OpenNept4une operator practice:
- rotation_distance (extruder)
- flow multiplier from single-wall thickness
- pressure advance from TUNING_TOWER height
- mesh peak-to-peak gate helpers
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence


@dataclass
class RotationDistanceResult:
    old_rotation_distance: float
    commanded_mm: float
    actual_mm: float
    new_rotation_distance: float

    @property
    def error_pct(self) -> float:
        if self.commanded_mm <= 0:
            return 0.0
        return 100.0 * (self.actual_mm - self.commanded_mm) / self.commanded_mm


def compute_rotation_distance(
    current_rd: float,
    commanded_mm: float = 100.0,
    actual_mm: float = 100.0,
) -> RotationDistanceResult:
    """Klipper: new_rd = current_rd * (actual / commanded).

    Under-extrusion (actual < commanded) → lower rotation_distance.
    """
    if commanded_mm <= 0 or actual_mm <= 0 or current_rd <= 0:
        raise ValueError("rotation_distance inputs must be positive")
    new_rd = float(current_rd) * (float(actual_mm) / float(commanded_mm))
    return RotationDistanceResult(
        old_rotation_distance=float(current_rd),
        commanded_mm=float(commanded_mm),
        actual_mm=float(actual_mm),
        new_rotation_distance=round(new_rd, 5),
    )


@dataclass
class FlowResult:
    current_flow: float
    expected_wall_mm: float
    measured_wall_mm: float
    new_flow: float
    perimeters: int

    @property
    def error_pct(self) -> float:
        if self.expected_wall_mm <= 0:
            return 0.0
        return 100.0 * (self.measured_wall_mm - self.expected_wall_mm) / self.expected_wall_mm


def compute_flow_multiplier(
    measured_wall_mm: float,
    line_width_mm: float = 0.44,
    perimeters: int = 1,
    current_flow: float = 1.0,
) -> FlowResult:
    """new_flow = current * expected / measured (Slic3rPE / Orca single-wall method)."""
    expected = float(line_width_mm) * int(perimeters)
    if measured_wall_mm <= 0 or expected <= 0:
        raise ValueError("wall thickness / line width must be positive")
    new_flow = float(current_flow) * (expected / float(measured_wall_mm))
    # Clamp to sane filament band — god-tier still stays near 1.0 after RD is right
    new_flow = max(0.85, min(1.15, new_flow))
    return FlowResult(
        current_flow=float(current_flow),
        expected_wall_mm=expected,
        measured_wall_mm=float(measured_wall_mm),
        new_flow=round(new_flow, 4),
        perimeters=int(perimeters),
    )


@dataclass
class PressureAdvanceResult:
    start: float
    factor: float
    measured_height_mm: float
    pressure_advance: float


def compute_pressure_advance(
    measured_height_mm: float,
    start: float = 0.0,
    factor: float = 0.005,
) -> PressureAdvanceResult:
    """PA = start + measured_height * factor (Klipper TUNING_TOWER).

    Direct-drive (N4 Pro geared): factor 0.005 is standard.
    Typical DD PA band: ~0.02–0.08.
    """
    if measured_height_mm < 0:
        raise ValueError("height must be >= 0")
    pa = float(start) + float(measured_height_mm) * float(factor)
    pa = max(0.0, min(1.0, pa))
    return PressureAdvanceResult(
        start=float(start),
        factor=float(factor),
        measured_height_mm=float(measured_height_mm),
        pressure_advance=round(pa, 5),
    )


def mesh_peak_to_peak(matrix: Sequence[Sequence[float]]) -> float:
    vals: List[float] = []
    for row in matrix:
        for v in row:
            vals.append(float(v))
    if not vals:
        return 0.0
    return max(vals) - min(vals)


def dimensional_error_100mm(nominal_mm: float, measured_mm: float) -> float:
    """Signed error normalized to a 100 mm span (positive = oversized)."""
    if abs(nominal_mm) < 1e-9:
        return 0.0
    return (float(measured_mm) - float(nominal_mm)) * (100.0 / abs(float(nominal_mm)))


def precision_span(measurements_mm: Iterable[float]) -> float:
    vals = [float(v) for v in measurements_mm]
    if not vals:
        return 0.0
    return max(vals) - min(vals)


def suggest_z_nudge_from_first_layer(
    *,
    under_squish: bool = False,
    over_squish: bool = False,
    ribs: bool = False,
    step_mm: float = 0.02,
) -> float:
    """Heuristic Z baby-step suggestion (mm, SET_GCODE_OFFSET / FORGE_SET_Z sense).

    Positive nudge raises nozzle (less squish). Negative lowers (more squish).
    """
    if under_squish and over_squish:
        return 0.0
    if over_squish or ribs:
        return abs(step_mm)  # raise
    if under_squish:
        return -abs(step_mm)  # lower
    return 0.0


# Neptune 4 Pro / OpenNeptune reference bands (shop targets)
N4PRO_MESH_P2P_GOOD_MM = 0.25
N4PRO_MESH_P2P_MAX_MM = 0.80
N4PRO_PA_DD_TYPICAL = (0.020, 0.060)
N4PRO_FLOW_TYPICAL = (0.92, 1.08)
N4PRO_ZHOP_MM = (0.25, 0.60)
N4PRO_RETRACT_DD_MM = (0.8, 1.5)
