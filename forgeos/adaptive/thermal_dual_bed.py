"""Adaptive dual-bed control (inner + outer) — zero vision.

Neptune 4 Pro has heater_bed + heater_generic heater_bed_outer. Equal set-points
do not mean equal physics: outer zone has more perimeter loss in a cold basement.

Controller goals (precision/accuracy of first layer and dimensional stability):
  1) Hold both zones near target within tight band (default ±0.8 °C)
  2) Minimize |T_inner - T_outer| (delta drives mesh drift / warpage)
  3) Boost the colder zone slightly without exceeding safety envelope
  4) Learn outer bias EMA for basement open-shop (homeostasis)

Actions: SET_HEATER_TEMPERATURE on each zone independently (small steps).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
import time


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _ema(prev: float, x: float, a: float) -> float:
    a = _clamp(a, 0.01, 1.0)
    return (1.0 - a) * prev + a * x


@dataclass
class DualBedState:
    target_base_c: float = 65.0
    inner_target_c: float = 65.0
    outer_target_c: float = 65.0
    # Learned: outer often needs +0.5..+3 C in cold basement
    outer_bias_c: float = 1.0
    inner_bias_c: float = 0.0
    delta_ema_c: float = 0.0  # outer - inner actual
    power_inner_ema: float = 0.0
    power_outer_ema: float = 0.0
    uniform_score: float = 0.5  # 1 = perfect match
    samples: int = 0
    last_adjust_ts: float = 0.0

    # envelopes
    bed_min_c: float = 50.0
    bed_max_c: float = 72.0
    max_step_c: float = 0.5
    max_zone_delta_c: float = 4.0  # |outer_target - inner_target|
    hold_band_c: float = 0.8
    min_adjust_interval_s: float = 8.0
    alpha: float = 0.2

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DualBedAction:
    script: str
    reason: str
    priority: int = 50

    def as_dict(self) -> Dict[str, Any]:
        return {"script": self.script, "reason": self.reason, "priority": self.priority}


class DualBedController:
    def __init__(self, state: Optional[DualBedState] = None) -> None:
        self.state = state or DualBedState()

    def observe(
        self,
        inner_c: float,
        outer_c: float,
        inner_target: float,
        outer_target: float,
        inner_power: float = 0.0,
        outer_power: float = 0.0,
    ) -> None:
        st = self.state
        st.samples += 1
        delta = float(outer_c) - float(inner_c)
        st.delta_ema_c = _ema(st.delta_ema_c, delta, st.alpha)
        st.power_inner_ema = _ema(st.power_inner_ema, inner_power, st.alpha)
        st.power_outer_ema = _ema(st.power_outer_ema, outer_power, st.alpha)
        # uniformity: 0 delta → 1.0; 3C delta → ~0
        st.uniform_score = _clamp(1.0 - abs(st.delta_ema_c) / 3.0, 0.0, 1.0)
        # track commanded if printer already has targets
        if inner_target > 0:
            st.inner_target_c = float(inner_target)
        if outer_target > 0:
            st.outer_target_c = float(outer_target)

    def plan(
        self,
        inner_c: float,
        outer_c: float,
        *,
        printing: bool,
        base_target: Optional[float] = None,
        now: Optional[float] = None,
    ) -> List[DualBedAction]:
        now = time.time() if now is None else now
        st = self.state
        if base_target is not None and base_target > 0:
            st.target_base_c = float(base_target)

        actions: List[DualBedAction] = []
        if st.target_base_c <= 0 and not printing:
            return actions

        # Desired targets: base + biases, clamped, limited zone delta
        inner_des = _clamp(
            st.target_base_c + st.inner_bias_c, st.bed_min_c, st.bed_max_c
        )
        outer_des = _clamp(
            st.target_base_c + st.outer_bias_c, st.bed_min_c, st.bed_max_c
        )
        if outer_des - inner_des > st.max_zone_delta_c:
            outer_des = inner_des + st.max_zone_delta_c
        if inner_des - outer_des > st.max_zone_delta_c:
            inner_des = outer_des + st.max_zone_delta_c

        # Learn bias: if outer is colder than inner while both commanded equal-ish
        if abs(outer_c - inner_c) > 0.6:
            if outer_c < inner_c - 0.6:
                st.outer_bias_c = _clamp(st.outer_bias_c + 0.05, 0.0, st.max_zone_delta_c)
            elif inner_c < outer_c - 0.6:
                st.outer_bias_c = _clamp(st.outer_bias_c - 0.03, 0.0, st.max_zone_delta_c)

        if now - st.last_adjust_ts < st.min_adjust_interval_s:
            return actions

        # Step targets toward desired if actual lagging or delta high
        def step_toward(current_cmd: float, desired: float) -> float:
            d = desired - current_cmd
            if abs(d) < 0.15:
                return current_cmd
            return current_cmd + _clamp(d, -st.max_step_c, st.max_step_c)

        new_inner = step_toward(st.inner_target_c if st.inner_target_c > 0 else st.target_base_c, inner_des)
        new_outer = step_toward(st.outer_target_c if st.outer_target_c > 0 else st.target_base_c, outer_des)

        # If actual outer cold vs target, nudge outer up
        if outer_c < st.target_base_c - st.hold_band_c:
            new_outer = _clamp(new_outer + st.max_step_c, st.bed_min_c, st.bed_max_c)
        if inner_c < st.target_base_c - st.hold_band_c:
            new_inner = _clamp(new_inner + st.max_step_c, st.bed_min_c, st.bed_max_c)

        # Avoid fighting if already very close
        changed = False
        scripts = []
        if abs(new_inner - (st.inner_target_c or 0)) >= 0.2 or (
            abs(inner_c - new_inner) > st.hold_band_c and new_inner > 0
        ):
            scripts.append(
                "SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=%.1f" % new_inner
            )
            st.inner_target_c = new_inner
            changed = True
        if abs(new_outer - (st.outer_target_c or 0)) >= 0.2 or (
            abs(outer_c - new_outer) > st.hold_band_c and new_outer > 0
        ):
            scripts.append(
                "SET_HEATER_TEMPERATURE HEATER=heater_bed_outer TARGET=%.1f" % new_outer
            )
            st.outer_target_c = new_outer
            changed = True

        if changed and scripts:
            st.last_adjust_ts = now
            actions.append(
                DualBedAction(
                    script="\n".join(scripts),
                    reason="dual-bed adapt inner=%.1f outer=%.1f bias_o=%.2f dEMA=%.2f uni=%.2f"
                    % (
                        st.inner_target_c,
                        st.outer_target_c,
                        st.outer_bias_c,
                        st.delta_ema_c,
                        st.uniform_score,
                    ),
                    priority=70,
                )
            )
        return actions
