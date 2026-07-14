"""Filament moisture soft-sensor from hotend thermal load.

IMPORTANT
---------
This does **not** measure absolute water % in the spool. Without a dryer RH probe
or lab moisture analyzer, we only estimate a **risk score** from physics proxies:

  1) Hotend temperature droop under extrusion (target - actual)
  2) Heater power fraction while extruding (if Klipper reports it)
  3) Optional: short-term temperature variance (steam "sputter" signature)

Why temp drops can correlate with moisture
------------------------------------------
Cold filament always steals heat. Wet filament also spends energy boiling water
(latent heat ~2250 J/g). That extra thermal load often shows up as:
  - larger steady-state droop at the same volumetric flow
  - higher average heater duty cycle to hold set-point
  - noisier melt temperature / inconsistent extrusion

Confounders (zero-trust: always listed)
---------------------------------------
High flow, bad PID, partial clog, wrong thermistor, aggressive part-cooling,
color/CF fillers, ambient drafts, first-layer fan, and poor seating of the
sensor all mimic "wet" signatures. So automation is **conservative**: derate
speed / slightly raise temp / optional tiny flow trim — never invent a fake RH%.

Baseline learning
-----------------
Call ``observe`` during a known-dry reference extrusion (or first good session).
Later sessions are scored relative to that baseline at similar flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _ema(prev: Optional[float], value: float, alpha: float) -> float:
    if prev is None:
        return float(value)
    a = _clamp(alpha, 0.01, 1.0)
    return a * float(value) + (1.0 - a) * float(prev)


@dataclass
class ExtrusionThermalSample:
    """One telemetry tick while the toolhead is extruding (or idle reference)."""

    temperature_c: float
    target_c: float
    # Klipper extruder.power is typically 0..1 PWM duty when available
    heater_power: Optional[float] = None
    # mm^3/s estimated from slicer/runtime (0 if idle)
    volumetric_flow_mm3_s: float = 0.0
    # True when filament is moving into the hotend
    is_extruding: bool = False
    # Optional operator label for baseline learning
    known_dry: bool = False


@dataclass
class MoistureEstimate:
    """Soft estimate — risk in [0, 1], not % water."""

    risk: float
    level: str  # dry | mild | moderate | severe
    temp_droop_c: float
    power: Optional[float]
    flow_mm3_s: float
    droop_excess_c: float
    power_excess: float
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "risk": self.risk,
            "level": self.level,
            "temp_droop_c": self.temp_droop_c,
            "power": self.power,
            "flow_mm3_s": self.flow_mm3_s,
            "droop_excess_c": self.droop_excess_c,
            "power_excess": self.power_excess,
            "notes": list(self.notes),
        }


@dataclass
class MoistureResponse:
    """Safe automated compensations derived from risk (still must pass SafetyGate)."""

    risk: float
    level: str
    nozzle_temp_delta_c: float
    flow_multiplier: float  # 1.0 = unchanged; slight bump if under-extrusion likely
    speed_derate: float  # multiply outer/infill speeds (e.g. 0.85)
    max_volumetric_derate: float
    pause_recommended: bool
    gcode: List[str]
    rationale: List[str]

    def as_dict(self) -> Dict[str, object]:
        return {
            "risk": self.risk,
            "level": self.level,
            "nozzle_temp_delta_c": self.nozzle_temp_delta_c,
            "flow_multiplier": self.flow_multiplier,
            "speed_derate": self.speed_derate,
            "max_volumetric_derate": self.max_volumetric_derate,
            "pause_recommended": self.pause_recommended,
            "gcode": list(self.gcode),
            "rationale": list(self.rationale),
        }


@dataclass
class MoistureSoftSensor:
    """Online EMA soft-sensor for filament moisture risk."""

    # How fast EMA tracks (higher = snappier)
    alpha: float = 0.15
    # Minimum flow to treat as "loaded extrusion"
    min_flow_mm3_s: float = 1.0
    # Baseline stats learned from known-dry extrusion
    baseline_droop_c: Optional[float] = None
    baseline_power: Optional[float] = None
    baseline_flow_mm3_s: Optional[float] = None
    # Live EMA
    ema_droop_c: Optional[float] = None
    ema_power: Optional[float] = None
    ema_flow: Optional[float] = None
    # For variance proxy (steam sputter)
    _droop_history: List[float] = field(default_factory=list)
    history_len: int = 30

    def reset_live(self) -> None:
        self.ema_droop_c = None
        self.ema_power = None
        self.ema_flow = None
        self._droop_history = []

    def observe(self, sample: ExtrusionThermalSample) -> MoistureEstimate:
        droop = float(sample.target_c) - float(sample.temperature_c)
        # Ignore negative droop (overshoot) for moisture load model
        droop_pos = max(0.0, droop)

        if sample.is_extruding and sample.volumetric_flow_mm3_s >= self.min_flow_mm3_s:
            self.ema_droop_c = _ema(self.ema_droop_c, droop_pos, self.alpha)
            self.ema_flow = _ema(self.ema_flow, sample.volumetric_flow_mm3_s, self.alpha)
            if sample.heater_power is not None:
                p = _clamp(sample.heater_power, 0.0, 1.0)
                self.ema_power = _ema(self.ema_power, p, self.alpha)
            self._droop_history.append(droop_pos)
            if len(self._droop_history) > self.history_len:
                self._droop_history.pop(0)

            if sample.known_dry:
                self._update_baseline()

        return self.estimate(
            temperature_c=sample.temperature_c,
            target_c=sample.target_c,
            heater_power=sample.heater_power,
            volumetric_flow_mm3_s=sample.volumetric_flow_mm3_s,
        )

    def _update_baseline(self) -> None:
        if self.ema_droop_c is None:
            return
        # Slow baseline adapt when labeled dry
        b_alpha = 0.05
        self.baseline_droop_c = _ema(self.baseline_droop_c, self.ema_droop_c, b_alpha)
        if self.ema_power is not None:
            self.baseline_power = _ema(self.baseline_power, self.ema_power, b_alpha)
        if self.ema_flow is not None:
            self.baseline_flow_mm3_s = _ema(self.baseline_flow_mm3_s, self.ema_flow, b_alpha)

    def _droop_std(self) -> float:
        if len(self._droop_history) < 5:
            return 0.0
        mean = sum(self._droop_history) / float(len(self._droop_history))
        var = sum((x - mean) ** 2 for x in self._droop_history) / float(len(self._droop_history))
        return math.sqrt(var)

    def estimate(
        self,
        temperature_c: float,
        target_c: float,
        heater_power: Optional[float] = None,
        volumetric_flow_mm3_s: float = 0.0,
    ) -> MoistureEstimate:
        droop = max(0.0, float(target_c) - float(temperature_c))
        notes: List[str] = []

        # Prefer EMA if we have it
        d = self.ema_droop_c if self.ema_droop_c is not None else droop
        p = self.ema_power if self.ema_power is not None else heater_power
        flow = self.ema_flow if self.ema_flow is not None else volumetric_flow_mm3_s

        # Normalize droop excess vs baseline; if no baseline, use absolute heuristics
        if self.baseline_droop_c is not None:
            # Scale mild expectation with flow ratio
            flow_scale = 1.0
            if self.baseline_flow_mm3_s and self.baseline_flow_mm3_s > 0.1 and flow:
                flow_scale = _clamp(float(flow) / float(self.baseline_flow_mm3_s), 0.5, 2.0)
            expected = float(self.baseline_droop_c) * flow_scale
            droop_excess = max(0.0, float(d) - expected)
            notes.append("baseline_droop=%.2fC expected=%.2fC" % (self.baseline_droop_c, expected))
        else:
            # Absolute: dry HTPLA at moderate flow often holds within ~1-3C if PID is good
            expected = 2.0
            droop_excess = max(0.0, float(d) - expected)
            notes.append("no_dry_baseline_using_absolute_heuristic")

        if p is not None and self.baseline_power is not None:
            power_excess = max(0.0, float(p) - float(self.baseline_power) * 1.05)
        elif p is not None:
            # heater sitting high under load is suspicious
            power_excess = max(0.0, float(p) - 0.55)
            notes.append("no_power_baseline")
        else:
            power_excess = 0.0
            notes.append("heater_power_unavailable")

        # Variance / sputter contribution
        std = self._droop_std()
        sputter = _clamp((std - 0.4) / 1.5, 0.0, 1.0)
        if std > 0.4:
            notes.append("temp_droop_std=%.2fC (possible steam sputter)" % std)

        # Fuse into risk 0..1
        # ~2C excess droop or ~0.25 power excess ≈ significant
        r_droop = _clamp(droop_excess / 3.0, 0.0, 1.0)
        r_power = _clamp(power_excess / 0.30, 0.0, 1.0)
        risk = _clamp(0.55 * r_droop + 0.30 * r_power + 0.15 * sputter, 0.0, 1.0)

        if risk < 0.20:
            level = "dry"
        elif risk < 0.40:
            level = "mild"
        elif risk < 0.70:
            level = "moderate"
        else:
            level = "severe"

        if flow and flow < self.min_flow_mm3_s:
            notes.append("low_or_zero_flow_estimate_less_reliable")

        return MoistureEstimate(
            risk=risk,
            level=level,
            temp_droop_c=float(d),
            power=None if p is None else float(p),
            flow_mm3_s=float(flow or 0.0),
            droop_excess_c=float(droop_excess),
            power_excess=float(power_excess),
            notes=notes,
        )


def recommend_response(
    estimate: MoistureEstimate,
    base_nozzle_c: float,
    base_flow_multiplier: float = 1.0,
    nozzle_temp_max_c: float = 240.0,
) -> MoistureResponse:
    """Map risk → conservative automation.

    Design choices:
    - Prefer **slowing down** (more melt residence time) over dumping more plastic.
    - Small **+temp** helps drive off residual moisture in the melt zone.
    - Tiny **+flow** only at moderate risk (classic wet under-extrusion); never huge.
    - Severe → pause recommendation (operator should dry spool).
    """
    risk = float(estimate.risk)
    level = estimate.level
    rationale: List[str] = [
        "soft_sensor_not_absolute_moisture",
        "level=%s risk=%.2f" % (level, risk),
    ]

    if level == "dry":
        return MoistureResponse(
            risk=risk,
            level=level,
            nozzle_temp_delta_c=0.0,
            flow_multiplier=base_flow_multiplier,
            speed_derate=1.0,
            max_volumetric_derate=1.0,
            pause_recommended=False,
            gcode=[],
            rationale=rationale + ["no_action"],
        )

    if level == "mild":
        d_temp = 3.0
        flow_m = base_flow_multiplier * 1.00
        speed = 0.92
        vol = 0.95
        pause = False
        rationale.append("mild: slight speed derate + small temp bump")
    elif level == "moderate":
        d_temp = 6.0
        flow_m = base_flow_multiplier * 1.03  # tiny under-extrusion compensation
        speed = 0.80
        vol = 0.85
        pause = False
        rationale.append("moderate: slow down hard, +temp, tiny +flow")
    else:  # severe
        d_temp = 8.0
        flow_m = base_flow_multiplier * 1.02
        speed = 0.65
        vol = 0.70
        pause = True
        rationale.append("severe: pause recommended — dry the spool")

    new_temp = min(float(nozzle_temp_max_c), float(base_nozzle_c) + d_temp)
    actual_delta = new_temp - float(base_nozzle_c)
    flow_pct = int(round(flow_m * 100.0))

    gcode = [
        "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=%.1f" % new_temp,
        "M221 S%d" % flow_pct,
        # Volumetric limit is slicer/Klipper max_extrude_cross_section related;
        # expose SET_VELOCITY_LIMIT as optional motion derate helper:
        "SET_VELOCITY_LIMIT VELOCITY=%.1f" % (300.0 * speed),
    ]
    if pause:
        gcode.append("PAUSE")
        gcode.append('RESPOND MSG="ForgeOS moisture risk SEVERE — dry filament and resume"')
    else:
        gcode.append(
            'RESPOND MSG="ForgeOS moisture risk %s (%.2f): temp%+.0fC flow=%d%% speed*=%.2f"'
            % (level, risk, actual_delta, flow_pct, speed)
        )

    return MoistureResponse(
        risk=risk,
        level=level,
        nozzle_temp_delta_c=actual_delta,
        flow_multiplier=flow_m,
        speed_derate=speed,
        max_volumetric_derate=vol,
        pause_recommended=pause,
        gcode=gcode,
        rationale=rationale,
    )


def estimate_flow_mm3_s(
    filament_diameter_mm: float,
    extrusion_speed_mm_s: float,
) -> float:
    """Volumetric flow from filament feed speed (not nozzle speed)."""
    r = float(filament_diameter_mm) / 2.0
    area = math.pi * r * r
    return max(0.0, area * float(extrusion_speed_mm_s))
