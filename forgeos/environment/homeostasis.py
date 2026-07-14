"""Self-annealing environmental homeostasis.

The controller keeps a memory of successful process set-points per environment bin
and slowly anneals live parameters toward the stable attractor for the current shop
conditions (basement cold/humid, enclosure on/off, etc.).

This is control-theoretic "annealing", not polymer oven annealing — though AFTER
phase still cooperates with HTPLA heat-treat workflow separately.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional
import math
import time

from forgeos.environment.models import AmbientReading, EnvironmentBin, Phase
from forgeos.environment.policy import EnvironmentPolicy, PhasePlan
from forgeos.materials import MaterialPack
from forgeos.sensors.moisture_soft_sensor import MoistureEstimate


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


@dataclass
class HomeostasisState:
    """Learned attractor for one environment bin."""

    env_bin: str
    samples: int = 0
    nozzle_temp_c: float = 215.0
    bed_temp_c: float = 60.0
    bed_soak_min: float = 3.0
    speed_factor: float = 1.0
    flow_factor: float = 1.0
    part_fan_percent: float = 40.0
    quality_ema: float = 0.5
    updated_at: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HomeostasisController:
    """EMA memory + slow anneal toward bin-local optima."""

    material: MaterialPack
    ambient: AmbientReading
    memory: Dict[str, HomeostasisState] = field(default_factory=dict)
    # Anneal rates (lower = slower, more stable)
    learn_alpha: float = 0.12
    apply_blend: float = 0.35  # how hard policy pulls toward memory each plan
    moisture: Optional[MoistureEstimate] = None

    def bin_key(self) -> str:
        b = self.ambient.environment_bin().value
        enc = self.ambient.enclosure.value
        return "%s|%s|%s" % (b, enc, self.material.sku)

    def get_state(self) -> HomeostasisState:
        key = self.bin_key()
        if key not in self.memory:
            pol = EnvironmentPolicy(self.material, self.ambient, self.moisture)
            before = pol.plan(Phase.BEFORE)
            during = pol.plan(Phase.DURING)
            self.memory[key] = HomeostasisState(
                env_bin=key,
                nozzle_temp_c=during.nozzle_temp_c,
                bed_temp_c=before.bed_temp_c,
                bed_soak_min=before.bed_soak_min,
                speed_factor=during.speed_factor,
                flow_factor=during.flow_factor,
                part_fan_percent=float(during.part_fan_percent),
            )
        return self.memory[key]

    def plan_phase(self, phase: Phase) -> PhasePlan:
        """Policy plan blended toward learned homeostasis for this environment."""
        pol = EnvironmentPolicy(self.material, self.ambient, self.moisture)
        plan = pol.plan(phase)
        st = self.get_state()
        if st.samples <= 0:
            return plan

        b = _clamp(self.apply_blend, 0.0, 1.0)
        # Blend continuous knobs toward memory (self-anneal to attractor)
        if phase == Phase.BEFORE:
            plan.bed_temp_c = (1 - b) * plan.bed_temp_c + b * st.bed_temp_c
            plan.bed_soak_min = (1 - b) * plan.bed_soak_min + b * st.bed_soak_min
            plan.nozzle_temp_c = (1 - b) * plan.nozzle_temp_c + b * st.nozzle_temp_c
            plan.rationale = list(plan.rationale) + [
                "homeostasis_blend=%.2f samples=%d" % (b, st.samples)
            ]
            # rebuild key gcode temps/soak
            plan.gcode = [
                g
                for g in plan.gcode
                if not g.startswith("FORGE_HEAT_DUAL_BED")
                and not g.startswith("FORGE_BED_SOAK")
                and not g.startswith("SET_HEATER_TEMPERATURE HEATER=extruder")
            ]
            # insert adjusted commands after PREFLIGHT if present
            inject = [
                "FORGE_HEAT_DUAL_BED BED=%.1f" % plan.bed_temp_c,
                "FORGE_BED_SOAK MIN=%.2f" % plan.bed_soak_min,
                "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=%.1f" % plan.nozzle_temp_c,
            ]
            out = []
            injected = False
            for g in plan.gcode:
                out.append(g)
                if (not injected) and ("FORGE_PREFLIGHT" in g or g.startswith("G28")):
                    out.extend(inject)
                    injected = True
            if not injected:
                out = inject + out
            plan.gcode = out
        elif phase == Phase.DURING:
            plan.nozzle_temp_c = (1 - b) * plan.nozzle_temp_c + b * st.nozzle_temp_c
            plan.bed_temp_c = (1 - b) * plan.bed_temp_c + b * st.bed_temp_c
            plan.speed_factor = (1 - b) * plan.speed_factor + b * st.speed_factor
            plan.flow_factor = (1 - b) * plan.flow_factor + b * st.flow_factor
            plan.part_fan_percent = int(
                round((1 - b) * plan.part_fan_percent + b * st.part_fan_percent)
            )
            plan.rationale = list(plan.rationale) + [
                "homeostasis_blend=%.2f samples=%d q_ema=%.2f" % (b, st.samples, st.quality_ema)
            ]
            plan.gcode = [
                "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=%.1f" % plan.nozzle_temp_c,
                "SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=%.1f" % plan.bed_temp_c,
                "SET_HEATER_TEMPERATURE HEATER=heater_bed_outer TARGET=%.1f" % plan.bed_temp_c,
                "M106 S%d" % int(round(plan.part_fan_percent * 255 / 100.0)),
                "M221 S%d" % int(round(plan.flow_factor * 100.0)),
                'RESPOND MSG="ENV DURING homeo speed*=%.2f fan=%d"'
                % (plan.speed_factor, plan.part_fan_percent),
            ]
        # AFTER: keep structural cool-down policy; memory less critical
        return plan

    def observe_outcome(
        self,
        quality_score: float,
        nozzle_temp_c: float,
        bed_temp_c: float,
        bed_soak_min: float,
        speed_factor: float,
        flow_factor: float,
        part_fan_percent: float,
        success: bool = True,
    ) -> HomeostasisState:
        """Update bin memory. Failed prints pull away slightly; success anneals in."""
        st = self.get_state()
        q = _clamp(quality_score, 0.0, 1.0)
        a = self.learn_alpha if success else self.learn_alpha * 0.35
        if not success:
            # On failure, decay quality and nudge toward safer (slower, hotter bed if cold)
            st.quality_ema = (1 - a) * st.quality_ema + a * q
            st.speed_factor = _clamp(st.speed_factor * 0.97, 0.55, 1.1)
            st.bed_soak_min = _clamp(st.bed_soak_min + 0.25, 2.0, 15.0)
            st.samples += 1
            st.updated_at = time.time()
            return st

        def ema(old: float, new: float) -> float:
            return (1 - a) * old + a * new

        st.nozzle_temp_c = ema(st.nozzle_temp_c, nozzle_temp_c)
        st.bed_temp_c = ema(st.bed_temp_c, bed_temp_c)
        st.bed_soak_min = ema(st.bed_soak_min, bed_soak_min)
        st.speed_factor = ema(st.speed_factor, speed_factor)
        st.flow_factor = ema(st.flow_factor, flow_factor)
        st.part_fan_percent = ema(st.part_fan_percent, part_fan_percent)
        st.quality_ema = ema(st.quality_ema, q)
        st.samples += 1
        st.updated_at = time.time()
        return st

    def distance_from_homeostasis(self, plan: PhasePlan) -> float:
        """Scalar stress: how far current plan is from learned attractor (0 = settled)."""
        st = self.get_state()
        if st.samples <= 0:
            return 1.0
        terms = [
            abs(plan.nozzle_temp_c - st.nozzle_temp_c) / 15.0,
            abs(plan.bed_temp_c - st.bed_temp_c) / 15.0,
            abs(plan.speed_factor - st.speed_factor) / 0.4,
            abs(plan.flow_factor - st.flow_factor) / 0.1,
        ]
        return _clamp(math.sqrt(sum(t * t for t in terms) / len(terms)), 0.0, 2.0)

    def export_memory(self) -> Dict[str, Any]:
        return {k: v.as_dict() for k, v in self.memory.items()}

    def import_memory(self, raw: Dict[str, Any]) -> None:
        for k, v in raw.items():
            self.memory[k] = HomeostasisState(
                env_bin=str(v.get("env_bin", k)),
                samples=int(v.get("samples", 0)),
                nozzle_temp_c=float(v.get("nozzle_temp_c", 215)),
                bed_temp_c=float(v.get("bed_temp_c", 60)),
                bed_soak_min=float(v.get("bed_soak_min", 3)),
                speed_factor=float(v.get("speed_factor", 1)),
                flow_factor=float(v.get("flow_factor", 1)),
                part_fan_percent=float(v.get("part_fan_percent", 40)),
                quality_ema=float(v.get("quality_ema", 0.5)),
                updated_at=float(v.get("updated_at", time.time())),
            )
