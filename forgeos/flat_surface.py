"""Machine-flat solid surfaces WITHOUT ironing — first principles.

Goal
----
A fingernail dragged across the surface must not catch ridges or drop into
valleys. That is a **geometric + volumetric** problem, not a cosmetic "ironing"
problem. Ironing is explicitly rejected: it is a second pass that hides bad
first-pass volume, costs time, and blurs dimensional accuracy.

Physics (zero-trust model)
--------------------------
1. Ideal rectangular cell between two line centers:
      cell_area = spacing * layer_height
   Deposited filament cross-section commanded:
      e_area = line_width * layer_height * flow
   For a level plane (no ridge, no valley):
      e_area == cell_area  ⇒  flow * line_width == spacing
   Machine-flat default: spacing = line_width, flow = 1.0
   (or flow = spacing / line_width if you deliberately change either).

2. Real beads are stadium/ellipse under nozzle squish. Residual peak-to-valley
   after correct volume is dominated by:
   - Z error (first layer) — wrong gap → wrong squish aspect ratio
   - Pressure lag (uncalibrated PA) — fat/thin at speed changes → texture
   - Direction reversals — V-grooves at row joins (use MONOTONIC fill)
   - Over-extrusion → ridges; under-extrusion → valleys
   - Vibration / ringing → wavy texture (input shaper + lower solid SCV)

3. Fingernail threshold (engineering proxy, not ISO):
   peak-to-valley ≲ 0.02–0.03 mm is typically "glass" to a nail.
   We target residual_ridge_score < 1.0 on that scale.

4. High speed (Klipper):
   volumetric_rate Q = line_width * layer_height * speed_mm_s
   Q ≤ Q_max_hotend (Brozzl plated copper + HTPLA ~12 mm³/s seed)
   PA must hold at that Q; else bead width modulates and ridges reappear.
   Solid surfaces: moderate square_corner_velocity, solid-specific accel,
   long monotonic strokes (few corners).

References for method (not copied code):
- Volume balance / extrusion width literature (slicer solid infill)
- Klipper Pressure Advance + input shaper for constant bead width at speed
- Monotonic solid fill (Prusa/Orca style) to remove reverse-direction valleys
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import math


FILAMENT_D_MM = 1.75
FILAMENT_AREA = math.pi * (FILAMENT_D_MM / 2.0) ** 2

# Fingernail / "machine flat" residual proxy (mm peak-to-valley target)
NAIL_PV_TARGET_MM = 0.025


@dataclass(frozen=True)
class FlatGeometry:
    """One solid surface recipe (first layer or upper solid)."""

    line_width_mm: float
    layer_height_mm: float
    spacing_mm: float
    flow: float
    speed_mm_s: float
    accel_mm_s2: float
    square_corner_velocity_mm_s: float
    pressure_advance: float
    pressure_advance_smooth_time: float = 0.03
    monotonic: bool = True
    fan_percent: int = 0
    role: str = "solid"  # first_layer | solid | top_solid

    @property
    def spacing_ratio(self) -> float:
        return self.spacing_mm / self.line_width_mm if self.line_width_mm else 0.0

    @property
    def volumetric_mm3_s(self) -> float:
        return self.line_width_mm * self.layer_height_mm * self.speed_mm_s * self.flow

    def e_per_mm(self) -> float:
        """Filament mm per mm of XY travel."""
        return (
            self.line_width_mm * self.layer_height_mm * self.flow
        ) / FILAMENT_AREA


@dataclass(frozen=True)
class FlatBalanceReport:
    """Zero-trust check that geometry can be flat without ironing."""

    cell_area_mm2: float
    e_area_mm2: float
    area_error_frac: float
    residual_ridge_proxy_mm: float
    nail_ok: bool
    volumetric_mm3_s: float
    q_max_mm3_s: float
    speed_ok: bool
    notes: Tuple[str, ...]

    def as_dict(self) -> Dict:
        return asdict(self)


def balance_flow_for_spacing(
    line_width_mm: float, spacing_mm: float
) -> float:
    """flow such that e_area == cell_area (perfect rectangular pack)."""
    if line_width_mm <= 0:
        raise ValueError("line_width_mm must be > 0")
    return spacing_mm / line_width_mm


def spacing_for_flow(line_width_mm: float, flow: float) -> float:
    """spacing that matches a chosen flow at rectangular pack."""
    return line_width_mm * flow


def residual_ridge_proxy_mm(
    line_width_mm: float,
    layer_height_mm: float,
    spacing_mm: float,
    flow: float,
) -> float:
    """Crude peak-to-valley proxy from volume mismatch only.

    excess fraction of cell volume becomes a triangular ridge of height h:
      0.5 * spacing * h ≈ |e_area - cell|  ⇒  h ≈ 2 * |err| / spacing
    (order-of-magnitude; real bead shape differs).
    """
    cell = spacing_mm * layer_height_mm
    e_area = line_width_mm * layer_height_mm * flow
    if spacing_mm <= 1e-9:
        return 999.0
    return abs(e_area - cell) * 2.0 / spacing_mm


def max_speed_for_q(
    line_width_mm: float,
    layer_height_mm: float,
    flow: float,
    q_max_mm3_s: float,
) -> float:
    denom = line_width_mm * layer_height_mm * flow
    if denom <= 1e-12:
        return 0.0
    return q_max_mm3_s / denom


def evaluate_geometry(
    geo: FlatGeometry,
    q_max_mm3_s: float = 12.0,
    nail_pv_mm: float = NAIL_PV_TARGET_MM,
) -> FlatBalanceReport:
    cell = geo.spacing_mm * geo.layer_height_mm
    e_area = geo.line_width_mm * geo.layer_height_mm * geo.flow
    err = (e_area - cell) / cell if cell else 999.0
    ridge = residual_ridge_proxy_mm(
        geo.line_width_mm, geo.layer_height_mm, geo.spacing_mm, geo.flow
    )
    q = geo.volumetric_mm3_s
    notes: List[str] = []
    if abs(err) > 0.02:
        notes.append(
            "area_error>2%% — ridges/valleys likely; set flow=spacing/line_w"
        )
    if not geo.monotonic:
        notes.append("non-monotonic fill adds reverse-direction V-grooves")
    if q > q_max_mm3_s * 1.02:
        notes.append("Q exceeds hotend budget — underextrude/texture at speed")
    if geo.square_corner_velocity_mm_s > 8.0 and geo.role in (
        "solid",
        "top_solid",
        "first_layer",
    ):
        notes.append("high SCV on solids can corner-bulge; prefer 2–5 mm/s")
    if ridge <= nail_pv_mm and abs(err) <= 0.02:
        notes.append("volume balanced within nail proxy")
    return FlatBalanceReport(
        cell_area_mm2=cell,
        e_area_mm2=e_area,
        area_error_frac=err,
        residual_ridge_proxy_mm=ridge,
        nail_ok=ridge <= nail_pv_mm and abs(err) <= 0.025,
        volumetric_mm3_s=q,
        q_max_mm3_s=q_max_mm3_s,
        speed_ok=q <= q_max_mm3_s * 1.02,
        notes=tuple(notes),
    )


def machine_flat_pack(
    nozzle_d_mm: float = 0.4,
    *,
    first_h: float = 0.28,
    solid_h: float = 0.20,
    q_max_mm3_s: float = 12.0,
    pa: float = 0.032,
    pa_smooth: float = 0.03,
    # line width ~ 1.05–1.15× nozzle is stable; wider needs more Q for same speed
    line_width_mm: Optional[float] = None,
    first_speed_mm_s: float = 30.0,
    solid_speed_mm_s: float = 120.0,
    top_speed_mm_s: float = 80.0,
) -> Dict[str, FlatGeometry]:
    """God-tier pack: spacing = line_w, flow = 1.0, monotonic, Q-limited speeds.

    Zero ironing. First layer slower for adhesion; solids exploit Klipper speed
    up to volumetric limit.
    """
    lw = line_width_mm if line_width_mm is not None else round(nozzle_d_mm * 1.10, 3)
    # Perfect rectangular balance
    sp = lw
    flow = 1.0

    def clamp_speed(h: float, want: float) -> float:
        vmax = max_speed_for_q(lw, h, flow, q_max_mm3_s)
        # 92% of Q_max leaves margin for PA / acceleration peaks
        return min(want, vmax * 0.92)

    first = FlatGeometry(
        line_width_mm=lw,
        layer_height_mm=first_h,
        spacing_mm=sp,
        flow=flow,
        speed_mm_s=clamp_speed(first_h, first_speed_mm_s),
        accel_mm_s2=2500.0,
        square_corner_velocity_mm_s=3.0,
        pressure_advance=pa,
        pressure_advance_smooth_time=pa_smooth,
        monotonic=True,
        fan_percent=0,
        role="first_layer",
    )
    solid = FlatGeometry(
        line_width_mm=lw,
        layer_height_mm=solid_h,
        spacing_mm=sp,
        flow=flow,
        speed_mm_s=clamp_speed(solid_h, solid_speed_mm_s),
        accel_mm_s2=5000.0,
        square_corner_velocity_mm_s=5.0,
        pressure_advance=pa,
        pressure_advance_smooth_time=pa_smooth,
        monotonic=True,
        fan_percent=40,
        role="solid",
    )
    top = FlatGeometry(
        line_width_mm=lw,
        layer_height_mm=solid_h,
        spacing_mm=sp,
        flow=flow,
        speed_mm_s=clamp_speed(solid_h, top_speed_mm_s),
        accel_mm_s2=3500.0,
        square_corner_velocity_mm_s=3.0,
        pressure_advance=pa,
        pressure_advance_smooth_time=pa_smooth,
        monotonic=True,
        fan_percent=60,
        role="top_solid",
    )
    return {"first_layer": first, "solid": solid, "top_solid": top}


def gcode_set_motion_for_flat(geo: FlatGeometry) -> List[str]:
    """Klipper velocity limits tuned for this solid role."""
    return [
        "SET_VELOCITY_LIMIT VELOCITY=%.1f ACCEL=%.0f SQUARE_CORNER_VELOCITY=%.1f"
        % (max(geo.speed_mm_s * 1.15, 50.0), geo.accel_mm_s2, geo.square_corner_velocity_mm_s),
        "SET_PRESSURE_ADVANCE ADVANCE=%.4f SMOOTH_TIME=%.3f"
        % (geo.pressure_advance, geo.pressure_advance_smooth_time),
        "M106 S%d" % int(round(255 * geo.fan_percent / 100.0)),
        "M221 S%d" % int(round(geo.flow * 100)),
    ]


def e_for_distance(dist_mm: float, geo: FlatGeometry) -> float:
    return dist_mm * geo.e_per_mm()


def monotonic_row_ys(
    y0: float,
    y1: float,
    spacing_mm: float,
    line_width_mm: float,
) -> List[float]:
    """Y centers for rows inset by half line width, step = spacing."""
    y_start = y0 + line_width_mm * 0.5
    y_end = y1 - line_width_mm * 0.5
    if y_end < y_start:
        return [(y0 + y1) * 0.5]
    ys = []
    y = y_start
    # ensure last row lands near y_end (no large edge gap)
    while y < y_end - 1e-9:
        ys.append(round(y, 4))
        y += spacing_mm
    # snap/add final row
    if not ys or abs(ys[-1] - y_end) > spacing_mm * 0.35:
        ys.append(round(y_end, 4))
    else:
        ys[-1] = round(y_end, 4)
    return ys


def pack_reports(
    pack: Dict[str, FlatGeometry], q_max: float = 12.0
) -> Dict[str, FlatBalanceReport]:
    return {k: evaluate_geometry(v, q_max_mm3_s=q_max) for k, v in pack.items()}
