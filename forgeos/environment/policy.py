"""Phase policies: before / during / after under ambient + enclosure conditions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from forgeos.environment.models import (
    REFERENCE_RH,
    REFERENCE_TEMP_C,
    AmbientReading,
    EnclosureMode,
    Phase,
)
from forgeos.materials import MaterialPack
from forgeos.sensors.moisture_soft_sensor import MoistureEstimate


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


@dataclass
class PhasePlan:
    phase: Phase
    nozzle_temp_c: float
    bed_temp_c: float
    bed_soak_min: float
    first_layer_speed_factor: float
    part_fan_percent: int
    speed_factor: float
    flow_factor: float
    max_volumetric_factor: float
    mesh_mode: str  # balanced | precision
    cool_down_style: str  # passive | staged | hold_warm
    moisture_risk_hint: float
    gcode: List[str] = field(default_factory=list)
    rationale: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "nozzle_temp_c": self.nozzle_temp_c,
            "bed_temp_c": self.bed_temp_c,
            "bed_soak_min": self.bed_soak_min,
            "first_layer_speed_factor": self.first_layer_speed_factor,
            "part_fan_percent": self.part_fan_percent,
            "speed_factor": self.speed_factor,
            "flow_factor": self.flow_factor,
            "max_volumetric_factor": self.max_volumetric_factor,
            "mesh_mode": self.mesh_mode,
            "cool_down_style": self.cool_down_style,
            "moisture_risk_hint": self.moisture_risk_hint,
            "gcode": list(self.gcode),
            "rationale": list(self.rationale),
        }


@dataclass
class EnvironmentPolicy:
    """Derive process plans from ambient + material + optional moisture estimate."""

    material: MaterialPack
    ambient: AmbientReading
    moisture: Optional[MoistureEstimate] = None

    def _base_temps(self) -> tuple:
        noz = float(self.material.nozzle_default_c)
        bed = float(self.material.bed_default_c)
        return noz, bed

    def _cold_stress(self) -> float:
        # 0 at ref, grows as ambient colder than 22C
        return _clamp((REFERENCE_TEMP_C - float(self.ambient.temperature_c)) / 12.0, 0.0, 1.5)

    def _humid_stress(self) -> float:
        return _clamp((float(self.ambient.rh_percent) - REFERENCE_RH) / 40.0, 0.0, 1.5)

    def _hot_stress(self) -> float:
        return _clamp((float(self.ambient.temperature_c) - 26.0) / 10.0, 0.0, 1.5)

    def _enclosure_chamber_boost(self) -> float:
        if self.ambient.enclosure == EnclosureMode.ENCLOSED:
            return 1.0
        if self.ambient.enclosure == EnclosureMode.DOOR_AJAR:
            return 0.5
        return 0.0

    def ambient_moisture_prior(self) -> float:
        """Prior risk that filament is damp given shop RH (not a measurement)."""
        rh = float(self.ambient.rh_percent)
        # Basements often 55-75% RH → elevated prior
        prior = _clamp((rh - 45.0) / 40.0, 0.0, 1.0)
        if self.moisture is not None:
            return _clamp(0.4 * prior + 0.6 * float(self.moisture.risk), 0.0, 1.0)
        return prior

    def plan(self, phase: Phase) -> PhasePlan:
        if phase == Phase.BEFORE:
            return self._plan_before()
        if phase == Phase.DURING:
            return self._plan_during()
        return self._plan_after()

    def plan_all(self) -> Dict[str, PhasePlan]:
        return {
            Phase.BEFORE.value: self._plan_before(),
            Phase.DURING.value: self._plan_during(),
            Phase.AFTER.value: self._plan_after(),
        }

    def _plan_before(self) -> PhasePlan:
        noz, bed = self._base_temps()
        cold = self._cold_stress()
        humid = self._humid_stress()
        enc = self._enclosure_chamber_boost()
        mprior = self.ambient_moisture_prior()
        rationale = [
            "bin=%s" % self.ambient.environment_bin().value,
            "cold_stress=%.2f humid_stress=%.2f enclosure=%.1f" % (cold, humid, enc),
            "moisture_prior=%.2f" % mprior,
        ]

        # Cold basement: hotter bed + longer soak for adhesion / dual-zone equalize
        bed = bed + 3.0 * cold + 1.0 * humid
        bed = _clamp(bed, self.material.bed_temp_range_c[0], self.material.bed_temp_range_c[1])
        # Slight nozzle bump if humid (helps fusion / residual moisture)
        noz = noz + 2.0 * mprior + 1.0 * cold
        noz = _clamp(noz, self.material.nozzle_temp_range_c[0], self.material.nozzle_temp_range_c[1])

        soak = 3.0 + 4.0 * cold + 1.5 * humid
        if enc >= 1.0:
            soak *= 0.85  # enclosure reduces draft losses; still soak dual bed
            rationale.append("enclosure: slightly shorter soak")
        if self.ambient.draft_level > 0.4 and enc < 0.5:
            soak += 2.0
            rationale.append("drafty open setup: extra soak")

        soak = _clamp(soak, 2.0, 15.0)
        mesh = "precision" if cold > 0.6 or humid > 0.6 else "balanced"
        fl_speed = _clamp(1.0 - 0.35 * cold - 0.10 * humid, 0.55, 1.0)

        gcode = [
            'RESPOND MSG="ForgeOS ENV BEFORE bin=%s T=%.1fC RH=%.0f%% enc=%s"'
            % (
                self.ambient.environment_bin().value,
                self.ambient.temperature_c,
                self.ambient.rh_percent,
                self.ambient.enclosure.value,
            ),
            "FORGE_PREFLIGHT",
            "FORGE_HEAT_DUAL_BED BED=%.1f" % bed,
            "FORGE_BED_SOAK MIN=%.2f" % soak,
            "G28",
            "FORGE_MESH_PRECISION" if mesh == "precision" else "FORGE_MESH_BALANCED",
            "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=%.1f" % noz,
            "TEMPERATURE_WAIT SENSOR=extruder MINIMUM=%.1f MAXIMUM=%.1f" % (noz - 2.0, noz + 5.0),
        ]
        if mprior >= 0.45:
            gcode.append('RESPOND MSG="High RH prior — prefer dry box; moisture soft-sensor armed for DURING"')

        return PhasePlan(
            phase=Phase.BEFORE,
            nozzle_temp_c=noz,
            bed_temp_c=bed,
            bed_soak_min=soak,
            first_layer_speed_factor=fl_speed,
            part_fan_percent=0,
            speed_factor=1.0,
            flow_factor=1.0,
            max_volumetric_factor=_clamp(1.0 - 0.15 * mprior, 0.7, 1.0),
            mesh_mode=mesh,
            cool_down_style="staged",
            moisture_risk_hint=mprior,
            gcode=gcode,
            rationale=rationale,
        )

    def _plan_during(self) -> PhasePlan:
        noz, bed = self._base_temps()
        cold = self._cold_stress()
        humid = self._humid_stress()
        hot = self._hot_stress()
        enc = self._enclosure_chamber_boost()
        mprior = self.ambient_moisture_prior()
        rationale = ["during homeostasis tracking"]

        noz = noz + 2.0 * mprior + 1.0 * cold - 1.0 * hot
        noz = _clamp(noz, self.material.nozzle_temp_range_c[0], self.material.nozzle_temp_range_c[1])
        bed = bed + 2.0 * cold
        bed = _clamp(bed, self.material.bed_temp_range_c[0], self.material.bed_temp_range_c[1])

        # Part cooling: open cold basement often wants more fan for detail after L1;
        # enclosure holds heat → more fan for HTPLA detail; very cold open → moderate fan
        if enc >= 1.0:
            fan = int(_clamp(55 + 15 * hot - 10 * cold, 20, 80))
            rationale.append("enclosed: active part cooling for HTPLA detail")
        else:
            fan = int(_clamp(40 + 10 * hot + 5 * humid, 15, 70))
            rationale.append("open: moderate part cooling")

        speed = _clamp(1.0 - 0.12 * cold - 0.20 * mprior - 0.08 * self.ambient.draft_level, 0.6, 1.05)
        if enc >= 1.0 and cold > 0.3:
            speed = min(1.05, speed + 0.05)  # enclosure recovers some speed budget
            rationale.append("enclosure speed recovery")

        flow = _clamp(1.0 + 0.02 * mprior, 0.95, 1.05)
        vol = _clamp(1.0 - 0.20 * mprior - 0.10 * cold, 0.65, 1.0)

        if self.moisture is not None and self.moisture.level in {"moderate", "severe"}:
            speed *= 0.85 if self.moisture.level == "moderate" else 0.70
            noz = min(self.material.nozzle_temp_range_c[1], noz + (4.0 if self.moisture.level == "moderate" else 7.0))
            rationale.append("moisture soft-sensor %s active" % self.moisture.level)

        gcode = [
            "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=%.1f" % noz,
            "SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=%.1f" % bed,
            "SET_HEATER_TEMPERATURE HEATER=heater_bed_outer TARGET=%.1f" % bed,
            "M106 S%d" % int(round(fan * 255 / 100.0)),
            "M221 S%d" % int(round(flow * 100.0)),
            'RESPOND MSG="ENV DURING speed*=%.2f fan=%d%% moisture_prior=%.2f"' % (speed, fan, mprior),
        ]

        return PhasePlan(
            phase=Phase.DURING,
            nozzle_temp_c=noz,
            bed_temp_c=bed,
            bed_soak_min=0.0,
            first_layer_speed_factor=_clamp(1.0 - 0.3 * cold, 0.55, 1.0),
            part_fan_percent=fan,
            speed_factor=speed,
            flow_factor=flow,
            max_volumetric_factor=vol,
            mesh_mode="balanced",
            cool_down_style="staged",
            moisture_risk_hint=mprior,
            gcode=gcode,
            rationale=rationale,
        )

    def _plan_after(self) -> PhasePlan:
        cold = self._cold_stress()
        enc = self._enclosure_chamber_boost()
        noz, bed = self._base_temps()
        rationale = []

        # Cold basement shock-cool warps parts / cracks CF — stage cool-down
        if cold > 0.5 and enc < 0.5:
            style = "staged"
            rationale.append("cold open basement: staged cool-down")
            gcode = [
                "M104 S0",
                "M106 S0",
                # Hold bed warm briefly so part doesn't snap-cool
                "SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=%.1f" % max(40.0, bed - 15.0),
                "SET_HEATER_TEMPERATURE HEATER=heater_bed_outer TARGET=%.1f" % max(40.0, bed - 15.0),
                "G4 P120000",
                "SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=0",
                "SET_HEATER_TEMPERATURE HEATER=heater_bed_outer TARGET=0",
                "BED_MESH_CLEAR",
                'RESPOND MSG="ENV AFTER staged cool — leave part on bed until near ambient"',
            ]
        elif enc >= 1.0:
            style = "hold_warm"
            rationale.append("enclosure: slow passive cool with door closed initially")
            gcode = [
                "M104 S0",
                "M106 S0",
                "SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=0",
                "SET_HEATER_TEMPERATURE HEATER=heater_bed_outer TARGET=0",
                "BED_MESH_CLEAR",
                'RESPOND MSG="ENV AFTER enclosure cool — open door only after bed <40C if warping"',
            ]
        else:
            style = "passive"
            gcode = [
                "M104 S0",
                "M106 S0",
                "SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=0",
                "SET_HEATER_TEMPERATURE HEATER=heater_bed_outer TARGET=0",
                "BED_MESH_CLEAR",
                'RESPOND MSG="ENV AFTER passive cool"',
            ]

        return PhasePlan(
            phase=Phase.AFTER,
            nozzle_temp_c=0.0,
            bed_temp_c=0.0,
            bed_soak_min=0.0,
            first_layer_speed_factor=1.0,
            part_fan_percent=0,
            speed_factor=1.0,
            flow_factor=1.0,
            max_volumetric_factor=1.0,
            mesh_mode="balanced",
            cool_down_style=style,
            moisture_risk_hint=self.ambient_moisture_prior(),
            gcode=gcode,
            rationale=rationale,
        )
