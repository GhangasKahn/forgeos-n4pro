"""Retraction + nozzle wipe kinematics for ooze control.

Target stack: Protopasta HTPLA + Brozzl Ni-Cu + geared Neptune 4 Pro extruder.

Problem: melt pressure stays in the melt zone after a path ends → filament
drools into a hanging whisker on travels / idle.

Strategy (order matters):
  1) Short wipe along the last extrusion direction (scrapes tip on plastic)
  2) Retract (pull melt back)
  3) Small Z-hop
  4) Travel
  5) Drop Z
  6) Unretract (no extra prime by default — extra prime re-creates the hang)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
import math


@dataclass(frozen=True)
class RetractWipeProfile:
    retract_mm: float = 1.15
    unretract_mm: float = 1.15  # match retract; no extra
    retract_speed_mm_s: float = 40.0
    unretract_speed_mm_s: float = 30.0
    wipe_mm: float = 1.4
    wipe_speed_mm_s: float = 80.0
    z_hop_mm: float = 0.25
    z_hop_speed_mm_s: float = 10.0
    travel_speed_mm_s: float = 250.0
    # If True, wipe uses extrusion at near-zero (coast); False = pure XY wipe while retracted=false then retract
    wipe_before_retract: bool = True
    pressure_advance: float = 0.032
    pressure_advance_smooth_time: float = 0.03

    def as_dict(self):
        return self.__dict__.copy()


# HTPLA + Brozzl Ni-Cu + N4 Pro geared (52:10 class)
HTPLA_BROZZL = RetractWipeProfile()

# Slightly less retract for CF (stiffer, more grind risk) — hardened path
HTPLA_CF = RetractWipeProfile(
    retract_mm=0.95,
    unretract_mm=0.95,
    retract_speed_mm_s=32.0,
    wipe_mm=1.0,
    pressure_advance=0.028,
)


def _f(mm_s: float) -> int:
    return int(round(mm_s * 60.0))


def unit_vector(dx: float, dy: float) -> Tuple[float, float]:
    n = math.hypot(dx, dy)
    if n < 1e-9:
        return 1.0, 0.0
    return dx / n, dy / n


def gcode_wipe_retract(
    x: float,
    y: float,
    z: float,
    last_dx: float,
    last_dy: float,
    profile: RetractWipeProfile = HTPLA_BROZZL,
    comment: str = "wipe+retract",
) -> List[str]:
    """Emit wipe along reverse of last move, then retract, then hop."""
    ux, uy = unit_vector(last_dx, last_dy)
    # wipe backward along path (tip rubs on just-laid plastic)
    wx = x - ux * profile.wipe_mm
    wy = y - uy * profile.wipe_mm
    lines = ["; %s" % comment]
    if profile.wipe_before_retract and profile.wipe_mm > 0:
        # slight negative E during wipe (mini-retract while wiping)
        wipe_e = -min(0.12, profile.retract_mm * 0.08)
        lines.append(
            "G1 X%.4f Y%.4f E%.5f F%d"
            % (wx, wy, wipe_e, _f(profile.wipe_speed_mm_s))
        )
        x, y = wx, wy
    lines.append(
        "G1 E-%.3f F%d" % (profile.retract_mm, _f(profile.retract_speed_mm_s))
    )
    if profile.z_hop_mm > 0:
        lines.append(
            "G0 Z%.3f F%d" % (z + profile.z_hop_mm, _f(profile.z_hop_speed_mm_s))
        )
    return lines


def gcode_travel_unretract(
    x: float,
    y: float,
    z: float,
    profile: RetractWipeProfile = HTPLA_BROZZL,
    comment: str = "travel+unretract",
) -> List[str]:
    lines = ["; %s" % comment]
    lines.append("G0 X%.4f Y%.4f F%d" % (x, y, _f(profile.travel_speed_mm_s)))
    lines.append("G0 Z%.3f F%d" % (z, _f(profile.z_hop_speed_mm_s)))
    lines.append(
        "G1 E%.3f F%d" % (profile.unretract_mm, _f(profile.unretract_speed_mm_s))
    )
    return lines


def gcode_apply_pa(profile: RetractWipeProfile = HTPLA_BROZZL) -> List[str]:
    return [
        "SET_PRESSURE_ADVANCE ADVANCE=%.4f SMOOTH_TIME=%.3f"
        % (profile.pressure_advance, profile.pressure_advance_smooth_time),
    ]
