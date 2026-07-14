"""Adaptive nozzle thermal control — zero vision.

Uses extruder temperature, target, heater power, and estimated volumetric load
to keep melt stable (precision) while allowing higher speed (throughput).

Policies:
  - Droop under load → raise target slightly (clamped) or cut speed
  - High power + still drooping → moisture or flow too high → speed derate
  - Stable track → restore speed factor / slight cool for stringing control
  - Integrate soft moisture risk for HTPLA basement shop
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import time

from forgeos.sensors.moisture_soft_sensor import (
    ExtrusionThermalSample,
    MoistureSoftSensor,
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _ema(prev: float, x: float, a: float) -> float:
    a = _clamp(a, 0.01, 1.0)
    return (1.0 - a) * prev + a * x


@dataclass
class NozzleState:
    base_target_c: float = 214.0
    cmd_target_c: float = 214.0
    droop_ema_c: float = 0.0
    power_ema: float = 0.0
    track_score: float = 0.5  # 1 = on target
    moisture_risk: float = 0.0
    speed_factor: float = 1.0
    samples: int = 0
    last_adjust_ts: float = 0.0

    nozzle_min_c: float = 200.0
    nozzle_max_c: float = 230.0
    max_step_c: float = 2.0
    hold_band_c: float = 2.0
    min_adjust_interval_s: float = 6.0
    alpha: float = 0.25

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NozzleAction:
    script: str
    reason: str
    priority: int = 60

    def as_dict(self) -> Dict[str, Any]:
        return {"script": self.script, "reason": self.reason, "priority": self.priority}


class NozzleThermalController:
    def __init__(
        self,
        state: Optional[NozzleState] = None,
        moisture: Optional[MoistureSoftSensor] = None,
    ) -> None:
        self.state = state or NozzleState()
        self.moisture = moisture or MoistureSoftSensor()

    def observe(
        self,
        temp_c: float,
        target_c: float,
        power: float = 0.0,
        volumetric_mm3_s: float = 0.0,
        is_extruding: bool = False,
    ) -> None:
        st = self.state
        st.samples += 1
        if target_c > 0:
            droop = float(target_c) - float(temp_c)
            st.droop_ema_c = _ema(st.droop_ema_c, droop, st.alpha)
            st.track_score = _clamp(1.0 - abs(droop) / 12.0, 0.0, 1.0)
            st.cmd_target_c = float(target_c)
        st.power_ema = _ema(st.power_ema, power, st.alpha)

        est = self.moisture.observe(
            ExtrusionThermalSample(
                temperature_c=temp_c,
                target_c=target_c if target_c > 0 else st.base_target_c,
                heater_power=power,
                volumetric_flow_mm3_s=volumetric_mm3_s,
                is_extruding=is_extruding,
            )
        )
        st.moisture_risk = float(est.risk)

    def plan(
        self,
        temp_c: float,
        target_c: float,
        *,
        printing: bool,
        now: Optional[float] = None,
    ) -> List[NozzleAction]:
        now = time.time() if now is None else now
        st = self.state
        actions: List[NozzleAction] = []
        if not printing or target_c <= 0:
            return actions
        if now - st.last_adjust_ts < st.min_adjust_interval_s:
            return actions

        scripts: List[str] = []
        reasons: List[str] = []

        # 1) Droop: raise nozzle a step (clamped) OR slow down
        if st.droop_ema_c > 3.0:
            new_t = _clamp(
                st.cmd_target_c + min(st.max_step_c, st.droop_ema_c * 0.5),
                st.nozzle_min_c,
                st.nozzle_max_c,
            )
            if new_t > st.cmd_target_c + 0.4:
                scripts.append(
                    "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=%.1f" % new_t
                )
                st.cmd_target_c = new_t
                reasons.append("droop_ema=%.1f→noz %.1f" % (st.droop_ema_c, new_t))
            # also derate speed if power already high
            if st.power_ema > 0.85:
                sf = _clamp(st.speed_factor - 0.05, 0.60, 1.0)
                if sf < st.speed_factor - 0.01:
                    st.speed_factor = sf
                    scripts.append("M220 S%d" % int(round(sf * 100)))
                    reasons.append("high_power+droop→speed %.0f%%" % (sf * 100))

        # 2) Moisture risk: safer speed, slight temp bump
        if st.moisture_risk > 0.55:
            sf = _clamp(st.speed_factor - 0.08, 0.55, 1.0)
            if sf < st.speed_factor - 0.01:
                st.speed_factor = sf
                scripts.append("M220 S%d" % int(round(sf * 100)))
                reasons.append("moisture_risk=%.2f→speed" % st.moisture_risk)
            if st.moisture_risk > 0.7:
                new_t = _clamp(st.cmd_target_c + 1.0, st.nozzle_min_c, st.nozzle_max_c)
                if new_t > st.cmd_target_c + 0.3:
                    scripts.append(
                        "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=%.1f" % new_t
                    )
                    st.cmd_target_c = new_t
                    reasons.append("wet_risk temp bump")

        # 3) Recover when tracking well
        if st.track_score > 0.9 and st.droop_ema_c < 1.5 and st.moisture_risk < 0.35:
            if st.speed_factor < 0.99:
                sf = _clamp(st.speed_factor + 0.05, 0.60, 1.0)
                st.speed_factor = sf
                scripts.append("M220 S%d" % int(round(sf * 100)))
                reasons.append("thermal_stable→speed restore %.0f%%" % (sf * 100))
            # drift target back toward base if we raised it
            if st.cmd_target_c > st.base_target_c + 0.5:
                new_t = max(st.base_target_c, st.cmd_target_c - 1.0)
                scripts.append(
                    "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=%.1f" % new_t
                )
                st.cmd_target_c = new_t
                reasons.append("anneal nozzle toward base %.1f" % new_t)

        if scripts:
            st.last_adjust_ts = now
            actions.append(
                NozzleAction(
                    script="\n".join(scripts),
                    reason="; ".join(reasons) if reasons else "nozzle adapt",
                    priority=75,
                )
            )
        return actions
