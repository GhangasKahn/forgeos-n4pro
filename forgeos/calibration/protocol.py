"""Calibration protocol catalog — one-time machine setup + fine-tune quality loop.

Ordered for Neptune 4 Pro + OpenNept4une + ForgeOS stack (Wham Bam PEX /
Brozzl plated copper 0.4 / Protopasta HTPLA).

Order is non-negotiable for god-tier results:
  mechanical → thermal → mesh/Z → extruder RD → flow → shaper → PA → retract → dims → promote
Fine-tune loops only after one-time baseline is locked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence


class CalSuite(str, Enum):
    ONETIME = "onetime"  # machine + filament baseline (do once / after hardware change)
    FINETUNE = "finetune"  # god-tier quality iteration
    FULL = "full"  # onetime then finetune


class CalTier(str, Enum):
    MACHINE = "machine"  # once per hardware change
    FILAMENT = "filament"  # once per filament/spool brand
    QUALITY = "quality"  # iterative fine tune
    GATE = "gate"  # verification coupon / promote


class OperatorMode(str, Enum):
    AUTO = "auto"  # host can drive via Moonraker
    INTERACTIVE = "interactive"  # needs paper test / SAVE_CONFIG accept
    MEASURE = "measure"  # needs caliper / micrometer input
    OPTIONAL = "optional"  # skip if sensor missing


@dataclass(frozen=True)
class CalStepDef:
    id: str
    name: str
    tier: CalTier
    suite: CalSuite
    operator: OperatorMode
    macros: tuple = ()
    description: str = ""
    skip_without: tuple = ()  # e.g. ("adxl",)
    evidence_keys: tuple = ()
    pass_hint: str = ""


# ---- One-time calibration (OpenNeptune + Klipper engineering order) ------

ONETIME_STEPS: Sequence[CalStepDef] = (
    CalStepDef(
        id="preflight",
        name="Hardware preflight",
        tier=CalTier.MACHINE,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.AUTO,
        macros=("FORGE_PREFLIGHT",),
        description="MCU ready, material/nozzle policy, dual-bed object present.",
        evidence_keys=("mcu_ready", "disk_free_mb"),
        pass_hint="G1 green",
    ),
    CalStepDef(
        id="bed_screws",
        name="Bed screw tilt (OpenNeptune)",
        tier=CalTier.MACHINE,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.INTERACTIVE,
        macros=("FORGE_BED_SCREWS_TUNE",),
        description=(
            "BED_LEVEL_SCREWS_TUNE / SCREWS_TILT_CALCULATE. Do not over-compress springs "
            "(center-high mesh). Re-run probe Z after any screw change."
        ),
        evidence_keys=("screws_adjusted",),
        pass_hint="Probe deltas within ~0.05 mm after retries",
    ),
    CalStepDef(
        id="probe_z",
        name="Probe Z-offset (cold paper)",
        tier=CalTier.MACHINE,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.INTERACTIVE,
        macros=("FORGE_PROBE_CAL",),
        description=(
            "CALIBRATE_PROBE_Z_OFFSET cold with paper. Accept → SAVE_CONFIG. "
            "Larger saved z_offset moves nozzle closer to bed (Klipper/OpenNeptune)."
        ),
        evidence_keys=("z_offset",),
        pass_hint="Paper drag at center; Fluidd homing_origin Z stable",
    ),
    CalStepDef(
        id="rotation_distance",
        name="Extruder rotation_distance",
        tier=CalTier.MACHINE,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.MEASURE,
        macros=("FORGE_EXTRUDE_CAL",),
        description=(
            "Mark 120 mm, command 100 mm slow extrusion, measure actual. "
            "new_rd = old_rd * actual/commanded. Foundation for all flow/PA work."
        ),
        evidence_keys=("rotation_distance", "actual_mm", "commanded_mm"),
        pass_hint="|error| ≤ 1% on 100 mm mark",
    ),
    CalStepDef(
        id="pid",
        name="PID: nozzle + dual bed (N4 Pro)",
        tier=CalTier.MACHINE,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.AUTO,
        macros=("FORGE_PID_ALL",),
        description=(
            "PID_CALIBRATE extruder @220, heater_bed @60/65, heater_bed_outer @60 "
            "(OpenNeptune PID_TUNE_OUTER_BED equivalent). SAVE_CONFIG."
        ),
        evidence_keys=("pid_extruder", "pid_bed", "pid_bed_outer"),
        pass_hint="Temps settle ±1 °C without oscillation",
    ),
    CalStepDef(
        id="resonance",
        name="Input shaper (ADXL/Beacon)",
        tier=CalTier.MACHINE,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.OPTIONAL,
        macros=("FORGE_SHAPER_CAL",),
        description="SHAPER_CALIBRATE if accelerometer present; else skip and mark shaper_ok=false for G2 soft.",
        skip_without=("adxl",),
        evidence_keys=("shaper_x", "shaper_y", "shaper_ok"),
        pass_hint="Belt rings gone at target accel; SAVE_CONFIG",
    ),
    CalStepDef(
        id="mesh",
        name="Dual-bed soak + precision mesh",
        tier=CalTier.MACHINE,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.AUTO,
        macros=("FORGE_HEAT_DUAL_BED", "FORGE_BED_SOAK", "FORGE_MESH_PRECISION"),
        description=(
            "Heat both zones, soak for basement thermal equalization, run precision mesh. "
            "Target p2p ≤ 0.25 mm good / ≤ 0.80 mm hard fail (G2)."
        ),
        evidence_keys=("mesh_p2p_mm", "soak_min"),
        pass_hint="mesh_p2p ≤ 0.25 mm preferred",
    ),
    CalStepDef(
        id="first_layer",
        name="First-layer squish (PEX)",
        tier=CalTier.FILAMENT,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.INTERACTIVE,
        macros=("FORGE_FIRST_LAYER_CAL",),
        description=(
            "Print first-layer patch on clean Wham Bam PEX. Baby-step Z; "
            "Z_OFFSET_APPLY_PROBE + SAVE_CONFIG when loved. Machine-flat: s=w, no ironing."
        ),
        evidence_keys=("z_adjust_mm", "first_layer_ok"),
        pass_hint="Even squish, no ribs, no empty lanes",
    ),
    CalStepDef(
        id="flow",
        name="Flow multiplier (single-wall)",
        tier=CalTier.FILAMENT,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.MEASURE,
        macros=("FORGE_FLOW_CAL",),
        description=(
            "Print single-wall shell; measure wall with caliper/micrometer. "
            "new_flow = current * expected / measured. Do AFTER rotation_distance."
        ),
        evidence_keys=("flow", "wall_mm"),
        pass_hint="Wall within ±0.02 mm of line_width × perimeters",
    ),
    CalStepDef(
        id="pressure_advance",
        name="Pressure advance (TUNING_TOWER)",
        tier=CalTier.FILAMENT,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.MEASURE,
        macros=("FORGE_PA_CAL",),
        description=(
            "Direct-drive: TUNING_TOWER START=0 FACTOR=0.005. Measure height of sharpest "
            "corners → PA = height * 0.005. Set in filament start gcode (OpenNeptune practice)."
        ),
        evidence_keys=("pressure_advance", "pa_height_mm"),
        pass_hint="Sharp corners without leading under-extrusion; typical DD 0.02–0.06",
    ),
    CalStepDef(
        id="retract",
        name="Retract / wipe / z-hop",
        tier=CalTier.FILAMENT,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.MEASURE,
        macros=("FORGE_RETRACT_CAL",),
        description=(
            "Stringing tower with firmware retract temporarily disabled in slicer while "
            "tuning. N4 Pro geared + Brozzl: start ~1.15–1.20 mm @ 40 mm/s, wipe 1.4, zhop 0.25."
        ),
        evidence_keys=("retract_mm", "wipe_mm", "z_hop_mm"),
        pass_hint="No whiskers on travels; no scars from excess z-hop",
    ),
    CalStepDef(
        id="coupon",
        name="Dimensional coupon (100 mm bar)",
        tier=CalTier.GATE,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.AUTO,
        macros=("FORGE_PRINT_COUPON",),
        description="Print ForgeOS G3 100 mm bar (machine-flat pack). Journal print id.",
        evidence_keys=("print_id", "duration_s"),
        pass_hint="Clean first layer + complete bar",
    ),
    CalStepDef(
        id="measure",
        name="Caliper measure → G3",
        tier=CalTier.GATE,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.MEASURE,
        macros=(),
        description="Import caliper CSV; |err|≤0.20 mm / 100 mm (aim 0.15).",
        evidence_keys=("abs_error_100mm", "xy_scale"),
        pass_hint="G3 PASS",
    ),
    CalStepDef(
        id="promote",
        name="Promote recipe → saved_state",
        tier=CalTier.GATE,
        suite=CalSuite.ONETIME,
        operator=OperatorMode.AUTO,
        macros=("FORGE_APPLY_CAL_RESULT",),
        description="Write PA/flow/Z/retract into journal promotion + configs/saved_state.",
        evidence_keys=("promoted", "recipe"),
        pass_hint="restore_saved_state.py reapplies knobs",
    ),
)


# ---- Fine-tune (god-tier quality loop) -----------------------------------

FINETUNE_STEPS: Sequence[CalStepDef] = (
    CalStepDef(
        id="temp_fine",
        name="Nozzle temp fine (±5 °C)",
        tier=CalTier.QUALITY,
        suite=CalSuite.FINETUNE,
        operator=OperatorMode.MEASURE,
        macros=("FORGE_TEMP_TOWER",),
        description="HTPLA on plated copper: bias cooler if stringing; hotter if layer bonds weak.",
        evidence_keys=("nozzle_c",),
        pass_hint="Best surface + interlayer for this spool",
    ),
    CalStepDef(
        id="pa_fine",
        name="PA fine band (±0.005)",
        tier=CalTier.QUALITY,
        suite=CalSuite.FINETUNE,
        operator=OperatorMode.MEASURE,
        macros=("FORGE_PA_FINE",),
        description="Narrow TUNING_TOWER around seed PA for corner perfection at production accel.",
        evidence_keys=("pressure_advance",),
        pass_hint="Corners crisp at outer-wall speed",
    ),
    CalStepDef(
        id="flow_fine",
        name="Flow fine (±2%)",
        tier=CalTier.QUALITY,
        suite=CalSuite.FINETUNE,
        operator=OperatorMode.MEASURE,
        macros=("FORGE_FLOW_FINE",),
        description="Re-measure single-wall after PA/temp settle; lock flow for dim accuracy.",
        evidence_keys=("flow",),
        pass_hint="Wall error ≤ 0.02 mm",
    ),
    CalStepDef(
        id="flat_fine",
        name="Machine-flat first layer",
        tier=CalTier.QUALITY,
        suite=CalSuite.FINETUNE,
        operator=OperatorMode.INTERACTIVE,
        macros=("FORGE_FIRST_LAYER_CAL",),
        description="s=w, flow=1.0 volume balance, zero ironing. See MACHINE_FLAT_ZERO_IRON.md.",
        evidence_keys=("first_layer_ok", "line_width_mm"),
        pass_hint="Optical flat, no pile-up ribs",
    ),
    CalStepDef(
        id="g4_precision",
        name="G4 precision ×3",
        tier=CalTier.GATE,
        suite=CalSuite.FINETUNE,
        operator=OperatorMode.MEASURE,
        macros=("FORGE_PRINT_COUPON",),
        description="Three identical 100 mm bars; span ≤ 0.10 mm.",
        evidence_keys=("span_mm",),
        pass_hint="G4 PASS",
    ),
    CalStepDef(
        id="g5_speed",
        name="Speed with gates held",
        tier=CalTier.GATE,
        suite=CalSuite.FINETUNE,
        operator=OperatorMode.MEASURE,
        macros=(),
        description="Raise role speeds ≥25% vs T0 baseline while G3/G4/quality still green.",
        evidence_keys=("duration_s", "baseline_s", "improvement"),
        pass_hint="G5 PASS",
    ),
    CalStepDef(
        id="anneal_optional",
        name="Anneal compensation (HTPLA claim)",
        tier=CalTier.GATE,
        suite=CalSuite.FINETUNE,
        operator=OperatorMode.OPTIONAL,
        macros=(),
        description="Post-anneal remeasure → update anneal xy scale (G6).",
        evidence_keys=("post_anneal_err_mm",),
        pass_hint="G6 PASS if anneal advertised",
    ),
)


def steps_for_suite(suite: CalSuite, include_optional: bool = True) -> List[CalStepDef]:
    if suite == CalSuite.ONETIME:
        steps = list(ONETIME_STEPS)
    elif suite == CalSuite.FINETUNE:
        steps = list(FINETUNE_STEPS)
    elif suite == CalSuite.FULL:
        steps = list(ONETIME_STEPS) + list(FINETUNE_STEPS)
    else:
        raise ValueError("unknown suite: %s" % suite)
    if not include_optional:
        steps = [s for s in steps if s.operator != OperatorMode.OPTIONAL]
    return steps


def step_by_id(step_id: str) -> Optional[CalStepDef]:
    for s in list(ONETIME_STEPS) + list(FINETUNE_STEPS):
        if s.id == step_id:
            return s
    return None


@dataclass
class CalPlan:
    suite: CalSuite
    steps: List[CalStepDef] = field(default_factory=list)
    sku: str = "protopasta_htpla"
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict:
        return {
            "suite": self.suite.value,
            "sku": self.sku,
            "notes": list(self.notes),
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "tier": s.tier.value,
                    "operator": s.operator.value,
                    "macros": list(s.macros),
                    "description": s.description,
                    "pass_hint": s.pass_hint,
                    "skip_without": list(s.skip_without),
                }
                for s in self.steps
            ],
        }


def build_plan(
    suite: CalSuite = CalSuite.FULL,
    sku: str = "protopasta_htpla",
    has_adxl: bool = False,
    include_optional: bool = True,
) -> CalPlan:
    steps = steps_for_suite(suite, include_optional=include_optional)
    notes = [
        "N4 Pro dual-bed: always PID + heat both heater_bed and heater_bed_outer.",
        "OpenNeptune: PA lives in filament start gcode; printer.cfg is fallback only.",
        "Order: RD → flow → (shaper) → PA. Never PA before flow.",
    ]
    if not has_adxl:
        notes.append("No ADXL flagged — resonance step will soft-skip unless forced.")
        # keep step but runner marks skip
    return CalPlan(suite=suite, steps=steps, sku=sku, notes=notes)
