"""Zero-vision process brain — orchestrates all non-camera adaptive loops.

Turns a stock Neptune 4 Pro into a continuously optimizing system using only
Moonraker telemetry + first-principles models:

  • Dual-bed thermal uniformity (inner/outer)
  • Nozzle thermal track + moisture soft-sensor
  • Pressure advance live nudge (from corner/extrusion proxies when available)
  • Flow / speed / flat-surface motion modes
  • Adaptive state persistence

Vision is optional and never required.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json
import time
from pathlib import Path

from forgeos.adaptive.thermal_dual_bed import DualBedController, DualBedState
from forgeos.adaptive.nozzle_thermal import NozzleThermalController, NozzleState
from forgeos.flat_surface import residual_ridge_proxy_mm
from forgeos.safety import SafetyGate


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


@dataclass
class BrainAction:
    kind: str  # gcode | log
    script: str
    reason: str
    priority: int
    source: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BrainTick:
    ts: float
    mode: str
    quality: Dict[str, float]
    telemetry: Dict[str, Any]
    actions: List[BrainAction]
    state: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "mode": self.mode,
            "quality": self.quality,
            "telemetry": self.telemetry,
            "actions": [a.as_dict() for a in self.actions],
            "state": self.state,
        }


@dataclass
class ZeroVisionState:
    armed: bool = False
    mode: str = "suggest"  # suggest | armed | hold
    z_adjust_mm: float = -0.480
    flow: float = 1.0
    pa: float = 0.032
    pa_smooth: float = 0.03
    speed_factor: float = 1.0
    line_w: float = 0.44
    spacing_ratio: float = 1.0
    layer_h: float = 0.28
    base_bed_c: float = 65.0
    base_nozzle_c: float = 214.0
    ticks: int = 0
    last_apply_ts: float = 0.0
    min_apply_interval_s: float = 2.0
    # quality EMAs
    bed_uniform_ema: float = 0.5
    nozzle_track_ema: float = 0.5
    flat_volume_ema: float = 0.5
    moisture_risk_ema: float = 0.0
    precision_belief: float = 0.5  # composite 0..1 toward "10k class"
    alpha: float = 0.25

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ZeroVisionState":
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        known = set(cls.__dataclass_fields__.keys())  # type: ignore
        return cls(**{k: v for k, v in raw.items() if k in known})


class ZeroVisionBrain:
    """Master zero-vision adaptive controller."""

    def __init__(
        self,
        state: Optional[ZeroVisionState] = None,
        safety: Optional[SafetyGate] = None,
        arm_token: Optional[str] = None,
    ) -> None:
        self.state = state or ZeroVisionState()
        self.safety = safety or SafetyGate()
        self.arm_token = arm_token
        self.bed = DualBedController(
            DualBedState(target_base_c=self.state.base_bed_c)
        )
        self.nozzle = NozzleThermalController(
            NozzleState(base_target_c=self.state.base_nozzle_c)
        )

    def _ema(self, prev: float, x: float) -> float:
        a = _clamp(self.state.alpha, 0.01, 1.0)
        return (1.0 - a) * prev + a * x

    def ingest_status(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Moonraker status dict into flat telemetry."""
        e = status.get("extruder") or {}
        b = status.get("heater_bed") or {}
        o = status.get("heater_generic heater_bed_outer") or status.get(
            "heater_generic heater_bed_outer"
        ) or {}
        # key may vary
        for k, v in status.items():
            if "heater_bed_outer" in k:
                o = v
                break
        ps = status.get("print_stats") or {}
        gm = status.get("gcode_move") or {}
        vs = status.get("virtual_sdcard") or {}
        th = status.get("toolhead") or {}
        fan = status.get("fan") or {}

        origin = gm.get("homing_origin") or [0, 0, 0]
        gpos = gm.get("gcode_position") or [0, 0, 0]
        state = str(ps.get("state") or "standby")
        printing = state.lower() == "printing"

        tele = {
            "print_state": state,
            "printing": printing,
            "filename": str(ps.get("filename") or ""),
            "progress": float(vs.get("progress") or 0.0),
            "z_adjust_mm": float(origin[2] if len(origin) > 2 else 0.0),
            "tool_z_mm": float(gpos[2] if len(gpos) > 2 else 0.0),
            "noz_c": float(e.get("temperature") or 0.0),
            "noz_t": float(e.get("target") or 0.0),
            "noz_power": float(e.get("power") or 0.0),
            "pa_live": float(e.get("pressure_advance") or self.state.pa),
            "bed_c": float(b.get("temperature") or 0.0),
            "bed_t": float(b.get("target") or 0.0),
            "bed_power": float(b.get("power") or 0.0),
            "outer_c": float(o.get("temperature") or 0.0),
            "outer_t": float(o.get("target") or 0.0),
            "outer_power": float(o.get("power") or 0.0),
            "speed_factor": float(gm.get("speed_factor") or 1.0),
            "extrude_factor": float(gm.get("extrude_factor") or 1.0),
            "fan": float(fan.get("speed") or 0.0),
            "homed": str(th.get("homed_axes") or ""),
        }
        return tele

    def plan(self, status: Dict[str, Any], now: Optional[float] = None) -> BrainTick:
        now = time.time() if now is None else now
        st = self.state
        st.ticks += 1
        tele = self.ingest_status(status)

        # Sync beliefs
        st.z_adjust_mm = tele["z_adjust_mm"]
        st.flow = tele["extrude_factor"] if tele["extrude_factor"] > 0 else st.flow
        st.speed_factor = tele["speed_factor"] if tele["speed_factor"] > 0 else st.speed_factor
        if tele["pa_live"] > 0:
            st.pa = tele["pa_live"]
        if tele["bed_t"] > 0:
            st.base_bed_c = tele["bed_t"]
            self.bed.state.target_base_c = tele["bed_t"]
        if tele["noz_t"] > 0:
            st.base_nozzle_c = tele["noz_t"]
            self.nozzle.state.base_target_c = tele["noz_t"]

        # Observe thermal loops
        self.bed.observe(
            tele["bed_c"],
            tele["outer_c"] if tele["outer_c"] > 0 else tele["bed_c"],
            tele["bed_t"],
            tele["outer_t"] if tele["outer_t"] > 0 else tele["bed_t"],
            tele["bed_power"],
            tele["outer_power"],
        )
        # crude volumetric proxy from speed factor * nominal solid Q
        vol = 8.0 * tele["speed_factor"] if tele["printing"] else 0.0
        self.nozzle.observe(
            tele["noz_c"],
            tele["noz_t"],
            tele["noz_power"],
            volumetric_mm3_s=vol,
            is_extruding=tele["printing"] and tele["noz_t"] > 0,
        )

        ridge = residual_ridge_proxy_mm(
            st.line_w, st.layer_h, st.line_w * st.spacing_ratio, st.flow
        )
        flat_vol = _clamp(1.0 - ridge / 0.08, 0.0, 1.0)
        st.flat_volume_ema = self._ema(st.flat_volume_ema, flat_vol)
        st.bed_uniform_ema = self._ema(
            st.bed_uniform_ema, self.bed.state.uniform_score
        )
        st.nozzle_track_ema = self._ema(
            st.nozzle_track_ema, self.nozzle.state.track_score
        )
        st.moisture_risk_ema = self._ema(
            st.moisture_risk_ema, self.nozzle.state.moisture_risk
        )

        # Composite "10k class" belief from zero-vision signals only
        st.precision_belief = _clamp(
            0.30 * st.bed_uniform_ema
            + 0.30 * st.nozzle_track_ema
            + 0.25 * st.flat_volume_ema
            + 0.15 * (1.0 - st.moisture_risk_ema),
            0.0,
            1.0,
        )

        quality = {
            "bed_uniform": st.bed_uniform_ema,
            "nozzle_track": st.nozzle_track_ema,
            "flat_volume": st.flat_volume_ema,
            "moisture_risk": st.moisture_risk_ema,
            "precision_belief": st.precision_belief,
            "ridge_proxy_mm": ridge,
        }

        actions: List[BrainAction] = []

        # Dual bed
        for a in self.bed.plan(
            tele["bed_c"],
            tele["outer_c"] if tele["outer_c"] > 0 else tele["bed_c"],
            printing=tele["printing"],
            base_target=tele["bed_t"] if tele["bed_t"] > 0 else st.base_bed_c,
            now=now,
        ):
            actions.append(
                BrainAction("gcode", a.script, a.reason, a.priority, "dual_bed")
            )

        # Nozzle
        for a in self.nozzle.plan(
            tele["noz_c"],
            tele["noz_t"],
            printing=tele["printing"],
            now=now,
        ):
            actions.append(
                BrainAction("gcode", a.script, a.reason, a.priority, "nozzle")
            )

        # Flat surface motion while printing
        if tele["printing"]:
            if tele["tool_z_mm"] <= 0.45 or tele["progress"] < 0.08:
                actions.append(
                    BrainAction(
                        "gcode",
                        "FORGE_FLAT_SURFACE_MODE ROLE=first",
                        "zero-vision first-layer dynamics",
                        40,
                        "flat",
                    )
                )
            elif tele["progress"] > 0.85:
                actions.append(
                    BrainAction(
                        "gcode",
                        "FORGE_FLAT_SURFACE_MODE ROLE=top",
                        "zero-vision top solid dynamics",
                        40,
                        "flat",
                    )
                )
            else:
                actions.append(
                    BrainAction(
                        "gcode",
                        "FORGE_FLAT_SURFACE_MODE ROLE=solid",
                        "zero-vision solid dynamics",
                        35,
                        "flat",
                    )
                )

        # PA: keep material seed if printer drifted
        if tele["printing"] and tele["noz_t"] > 0:
            if abs(tele["pa_live"] - st.pa) > 0.004 and st.pa > 0:
                actions.append(
                    BrainAction(
                        "gcode",
                        "SET_PRESSURE_ADVANCE ADVANCE=%.4f SMOOTH_TIME=%.3f"
                        % (st.pa, st.pa_smooth),
                        "restore PA to adaptive target",
                        45,
                        "pa",
                    )
                )

        # Flow: only if volume residual implies imbalance (machine-flat doctrine)
        if tele["printing"] and ridge > 0.03 and st.spacing_ratio >= 0.99:
            # over-extrusion ridge with s=w → reduce flow slightly
            new_f = _clamp(st.flow - 0.01, 0.92, 1.08)
            if new_f < st.flow - 0.005:
                actions.append(
                    BrainAction(
                        "gcode",
                        "M221 S%d" % int(round(new_f * 100)),
                        "volume ridge proxy → flow down (no ironing)",
                        55,
                        "flow",
                    )
                )
                st.flow = new_f

        actions.sort(key=lambda a: a.priority, reverse=True)

        mode = "armed" if st.armed else "suggest"
        if st.mode == "hold":
            mode = "hold"

        return BrainTick(
            ts=now,
            mode=mode,
            quality=quality,
            telemetry=tele,
            actions=actions,
            state={
                "zero_vision": st.as_dict(),
                "bed": self.bed.state.as_dict(),
                "nozzle": self.nozzle.state.as_dict(),
            },
        )

    def scripts_to_apply(self, tick: BrainTick) -> List[str]:
        if tick.mode != "armed":
            return []
        # Zero-trust: host token required whenever we actually apply
        self.safety.require_armed("runtime_micro", self.arm_token)
        now = tick.ts
        if now - self.state.last_apply_ts < self.state.min_apply_interval_s:
            return []
        for a in tick.actions:
            if a.kind == "gcode" and a.script.strip():
                # safety clamps for temps in script are already in sub-controllers
                self.state.last_apply_ts = now
                return [a.script]
        return []
