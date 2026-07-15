"""Calibration catalog and persistent run state.

The suite deliberately records evidence instead of pretending an interactive,
physical calibration can be made universal or fully automatic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from forgeos.calibration.profile import MachineProfile


VALID_RESULTS = {"pass", "fail", "skipped"}


@dataclass(frozen=True)
class CalibrationTest:
    id: str
    phase: str
    title: str
    procedure: Tuple[str, ...]
    commands: Tuple[str, ...]
    evidence: Tuple[str, ...]
    acceptance: str
    depends_on: Tuple[str, ...] = ()
    cadence: str = "once"
    conditional: bool = False
    invalidated_by: Tuple[str, ...] = ()


def _test(
    id: str,
    phase: str,
    title: str,
    procedure: Sequence[str],
    commands: Sequence[str],
    evidence: Sequence[str],
    acceptance: str,
    depends_on: Sequence[str] = (),
    cadence: str = "once",
    conditional: bool = False,
    invalidated_by: Sequence[str] = (),
) -> CalibrationTest:
    return CalibrationTest(
        id=id,
        phase=phase,
        title=title,
        procedure=tuple(procedure),
        commands=tuple(commands),
        evidence=tuple(evidence),
        acceptance=acceptance,
        depends_on=tuple(depends_on),
        cadence=cadence,
        conditional=conditional,
        invalidated_by=tuple(invalidated_by),
    )


def build_calibration_suite(profile: MachineProfile) -> List[CalibrationTest]:
    """Return the dependency-ordered one-time and per-material test suite."""

    accept = profile.acceptance
    probe_limit = float(profile.probe["repeatability_range_max_mm"])
    return [
        _test(
            "safety-inspection", "one_time", "Electrical and thermal safety inspection",
            ("Power off and unplug.", "Check heater, thermistor, fan, earth, belt and bed-cable routing.", "Install the build plate before any motion."),
            (), ("dated photos", "inspection checklist"),
            "No loose, pinched, scorched or damaged wiring; all fans turn freely.",
            invalidated_by=("wiring or hotend work",),
        ),
        _test(
            "backup-firmware", "one_time", "Back up firmware and identify hardware",
            ("Back up printer.cfg and SAVE_CONFIG.", "Record OpenNept4une version, ZNP-K1 PCB revision and stepper variant."),
            ("opennept4une",), ("configuration archive", "firmware and PCB versions"),
            "Restorable backup exists off-printer and hardware variant is known.",
            ("safety-inspection",), invalidated_by=("firmware migration",),
        ),
        _test(
            "mechanical-frame", "one_time", "Square frame, wheels, belts and toolhead",
            ("Check frame fasteners and X-gantry square.", "Set V-wheel preload without binding.", "Match X/Y belt tension by deflection or frequency; do not chase a generic frequency."),
            (), ("gantry left/right height", "belt method and readings", "wheel inspection"),
            "No play or binding through full travel; gantry side difference <=0.5 mm.",
            ("safety-inspection",), invalidated_by=("frame, belt, wheel or toolhead work",),
        ),
        _test(
            "gantry-level", "one_time", "Synchronize dual-Z gantry",
            ("Power off motors.", "Level both gantry ends to equal-height reference blocks.", "Rotate lead screws together and recheck full travel."),
            (), ("left and right reference heights",),
            "Left/right gantry height difference <=0.2 mm with smooth Z travel.",
            ("mechanical-frame",), invalidated_by=("Z coupler or gantry work",),
        ),
        _test(
            "bed-screws", "one_time", "Tram the four bed screws",
            ("Heat-soak at the normal material bed temperature.", "Run screw tilt repeatedly.", "Avoid fully compressing springs or silicone spacers."),
            ("FORGE_HEAT_DUAL_BED BED=65", "SCREWS_TILT_CALCULATE"),
            ("final screw tilt output",), "All screws within 00:02 adjustment and bed remains mechanically stable.",
            ("gantry-level",), invalidated_by=("bed screw, spacer, plate or gantry change",),
        ),
        _test(
            "extruder-rotation", "one_time", "Calibrate extruder rotation distance",
            ("Remove nozzle back-pressure or extrude slowly hot.", "Measure and command 100 mm filament.", "Compute new distance = old distance * actual / requested; repeat."),
            ("M83", "G1 E100 F60"), ("old/new rotation_distance", "three actual extrusion measurements"),
            "Mean 100 mm extrusion error <=%.2f mm; do not alter X/Y/Z rotation distance from printed-part measurements." % accept["extrusion_error_100mm_max_mm"],
            ("backup-firmware",), invalidated_by=("extruder gears, motor or idler change",),
        ),
        _test(
            "pid-extruder", "one_time", "Tune hotend PID at working temperature",
            ("Fit the normal nozzle and silicone sock.", "Tune at the representative print temperature and save."),
            ("PID_CALIBRATE HEATER=extruder TARGET=214", "SAVE_CONFIG"),
            ("PID values", "five-minute temperature trace"),
            "Stable within +/-%.1f C after settling, without heater faults." % accept["heater_stability_c"],
            ("extruder-rotation",), invalidated_by=("heater, thermistor, hotend, nozzle class or major temperature change",),
        ),
        _test(
            "pid-dual-bed", "one_time", "Tune inner and outer bed PID zones",
            ("Install the normal plate.", "Tune inner then outer zone at working temperature.", "Save only after both complete."),
            ("PID_CALIBRATE HEATER=heater_bed TARGET=65", "PID_CALIBRATE HEATER=heater_bed_outer TARGET=65", "SAVE_CONFIG"),
            ("both PID value sets", "ten-minute temperature trace"),
            "Both zones stable within +/-%.1f C after settling." % accept["heater_stability_c"],
            ("backup-firmware",), invalidated_by=("bed heater, sensor, insulation or plate system change",),
        ),
        _test(
            "probe-repeatability", "one_time", "Verify inductive probe repeatability",
            ("Clean nozzle and plate.", "Run repeatability cold, then after normal bed soak.", "Investigate drift before compensating it."),
            ("G28", "PROBE_ACCURACY SAMPLES=10"),
            ("cold range and standard deviation", "hot range and standard deviation"),
            "Cold and hot ranges each <=%.3f mm." % probe_limit,
            ("pid-dual-bed", "bed-screws"), invalidated_by=("probe mount, nozzle, plate or temperature regime change",),
        ),
        _test(
            "probe-z-offset", "one_time", "Calibrate probe Z offset",
            ("Perform OpenNept4une cold paper calibration.", "ACCEPT, apply to probe and save.", "Discard all old meshes."),
            ("CALIBRATE_PROBE_Z_OFFSET", "Z_OFFSET_APPLY_PROBE", "SAVE_CONFIG"),
            ("saved probe z_offset",), "Paper drag is repeatable and a later first-layer test needs <=0.10 mm total correction.",
            ("probe-repeatability",), invalidated_by=("bed screws, probe, nozzle, hotend or plate change",),
        ),
        _test(
            "axis-twist", "one_time", "Measure axis twist if first-layer slope remains",
            ("Run only after mechanical tramming.", "Enable compensation only when measured twist is repeatable."),
            ("AXIS_TWIST_COMPENSATION_CALIBRATE", "SAVE_CONFIG"),
            ("raw point readings", "before/after first-layer comparison"),
            "Use only when repeatable twist improves the full-bed first layer; otherwise leave disabled.",
            ("probe-z-offset",), conditional=True, invalidated_by=("X rail, probe mount or gantry work",),
        ),
        _test(
            "golden-mesh", "one_time", "Create heat-soaked golden bed mesh",
            ("Heat both zones and soak.", "Home and probe the precision grid.", "Save the profile and its range."),
            ("FORGE_HEAT_DUAL_BED BED=65", "FORGE_BED_SOAK MIN=10", "G28", "FORGE_MESH_PRECISION", "BED_MESH_PROFILE SAVE=default", "SAVE_CONFIG"),
            ("mesh JSON or screenshot", "range and standard deviation"),
            "Range target <=%.2f mm; hard stop >%.2f mm." % (accept["bed_mesh_range_target_mm"], accept["bed_mesh_range_fail_mm"]),
            ("probe-z-offset", "bed-screws"), invalidated_by=("bed, plate, screws, probe Z or gantry change",),
        ),
        _test(
            "input-shaper", "one_time", "Measure X/Y resonance and choose input shaper",
            ("Mount an accelerometer rigidly on the toolhead for X and bed for Y.", "Measure each axis.", "Choose shaper with acceptable smoothing and validate with a ringing print."),
            ("TEST_RESONANCES AXIS=X", "TEST_RESONANCES AXIS=Y", "SHAPER_CALIBRATE", "SAVE_CONFIG"),
            ("X/Y resonance CSV and plots", "chosen shapers/frequencies", "ringing validation print"),
            "No accelerometer errors; selected max acceleration respects smoothing recommendation and has no skipped steps.",
            ("mechanical-frame",), conditional=True, invalidated_by=("belt tension, toolhead mass, bed mass, frame or accelerometer mount change",),
        ),
        _test(
            "filament-dryness", "fine_tuning", "Establish a dry filament baseline",
            ("Dry per filament maker guidance.", "Seal and record spool mass or drying cycle.", "Do not tune stringing with wet material."),
            (), ("material lot/color", "drying cycle", "ambient RH"),
            "No popping, steam or moisture-driven roughness during steady extrusion.",
            ("pid-extruder",), cadence="per spool/lot or moisture event",
        ),
        _test(
            "temperature", "fine_tuning", "Tune nozzle temperature",
            ("Print a temperature tower within the material range.", "Judge layer bonding, overhangs, sheen and stringing.", "Choose the lowest temperature meeting strength and flow needs."),
            (), ("tower gcode and photos", "selected temperature"),
            "Clean bridges/overhangs with required interlayer strength and no under-extrusion.",
            ("filament-dryness", "extruder-rotation"), cadence="per material/nozzle",
        ),
        _test(
            "first-layer", "fine_tuning", "Tune first-layer height and uniformity",
            ("Print a 0.28 mm full-bed patch at 0.44 mm width.", "Baby-step in <=0.02 mm increments.", "Apply and save probe offset only after the whole plate is consistent."),
            ("FORGE_PRINT_START_ENV MESH=0", "Z_OFFSET_APPLY_PROBE", "SAVE_CONFIG"),
            ("five-zone patch photos", "final adjustment"),
            "Lines touch without gaps, ridges or translucent over-squish in all five zones.",
            ("golden-mesh", "temperature"), cadence="after plate/nozzle/Z changes",
        ),
        _test(
            "pressure-advance", "fine_tuning", "Tune pressure advance",
            ("Disable slicer PA override.", "Use Klipper tower or line-pattern method at representative flow.", "Ignore the seam corner and prefer the lower acceptable value."),
            ("SET_VELOCITY_LIMIT SQUARE_CORNER_VELOCITY=1 ACCEL=500", "TUNING_TOWER COMMAND=SET_PRESSURE_ADVANCE PARAMETER=ADVANCE START=0 FACTOR=.005"),
            ("test photos", "selected PA and smooth time", "filament/nozzle/temperature"),
            "Corners are sharp without pre-corner thinning; restore normal limits after test.",
            ("temperature", "input-shaper"), cadence="per material/nozzle/temperature",
        ),
        _test(
            "flow-ratio", "fine_tuning", "Tune per-filament flow ratio",
            ("Print coarse and fine Orca flow coupons.", "Select smooth, closed top surfaces without ridges.", "Do not use flow to compensate Z offset."),
            (), ("coupon photos", "selected flow ratio"),
            "Smooth closed top surface, no nozzle drag, and no visible under-extrusion.",
            ("pressure-advance", "first-layer"), cadence="per material/color/lot",
        ),
        _test(
            "max-volumetric-flow", "fine_tuning", "Measure sustainable volumetric flow",
            ("Run a stepped flow test at selected temperature.", "Find first matte, weak or under-extruded region.", "Set slicer limit to no more than 80 percent of failure flow."),
            (), ("failure flow", "slicer limit", "sample mass or wall measurements"),
            "Chosen limit <=80% of first repeatable quality failure and extruder never skips.",
            ("flow-ratio",), cadence="per material/nozzle/temperature",
        ),
        _test(
            "retraction", "fine_tuning", "Minimize retraction and stringing",
            ("Tune after temperature, PA and drying.", "Sweep direct-drive retraction in small steps.", "Use wipe; add Z-hop only for collision risk."),
            (), ("tower photos", "length/speeds/wipe/Z-hop"),
            "No material strings at normal travel while preserving seam quality and avoiding heat-creep.",
            ("pressure-advance", "filament-dryness"), cadence="per material/nozzle",
        ),
        _test(
            "cooling-bridging", "fine_tuning", "Tune cooling, minimum layer time and bridges",
            ("Print overhang/bridge and small-feature tests.", "Tune normal fan separately from bridge fan.", "Check layer adhesion after cooling changes."),
            (), ("test photos", "fan and layer-time settings"),
            "Bridges and overhangs meet geometry needs without brittle or weak layer bonding.",
            ("temperature", "flow-ratio"), cadence="per material/part class",
        ),
        _test(
            "dimensional", "fine_tuning", "Calibrate dimensional and hole compensation",
            ("Print three 100 mm bars plus a cube and hole coupon.", "Measure only after cooling 24 hours.", "Apply slicer shrinkage/hole compensation, not X/Y rotation-distance hacks."),
            (), ("caliper CSV", "mean/error/span", "slicer compensation"),
            "|mean error| <=%.2f mm/100 mm and three-part span <=%.2f mm." % (accept["dimensional_error_100mm_max_mm"], accept["repeatability_span_3x_max_mm"]),
            ("flow-ratio", "cooling-bridging"), cadence="per material/part class",
        ),
        _test(
            "speed-acceleration", "fine_tuning", "Validate speed and acceleration quality limits",
            ("Run ringing and feature-quality coupons from conservative limits upward.", "Respect machine/profile and input-shaper ceilings.", "Stop at the first quality regression or skipped step."),
            (), ("speed/accel matrix", "photos", "cycle times"),
            "Selected limits pass ringing, layer registration and corner tests with zero skipped steps.",
            ("max-volumetric-flow", "dimensional", "input-shaper"), cadence="after mass or motion changes",
        ),
        _test(
            "repeatability", "fine_tuning", "Production repeatability gate",
            ("Print the same reference coupon three times from cold starts.", "Record environment and cycle time.", "Measure blind and retain all samples."),
            (), ("three measurement sets", "environment", "failure observations"),
            "All three pass dimensional and visual gates; span <=%.2f mm." % accept["repeatability_span_3x_max_mm"],
            ("speed-acceleration",), cadence="before promoting a profile",
        ),
        _test(
            "anneal", "fine_tuning", "Characterize annealing compensation",
            ("Print and measure sacrificial coupons.", "Anneal with support media and controlled cooling.", "Remeasure X/Y/Z and holes; never assume published shrinkage."),
            (), ("before/after measurements", "oven trace", "derived scales"),
            "Three coupons produce repeatable scale factors without unacceptable warp.",
            ("repeatability",), cadence="per material/anneal recipe", conditional=True,
        ),
    ]


@dataclass
class CalibrationRun:
    machine_model: str
    created_at: str
    results: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def create(cls, profile: MachineProfile) -> "CalibrationRun":
        return cls(profile.model, datetime.now(timezone.utc).isoformat())

    @classmethod
    def load(cls, path: Path) -> "CalibrationRun":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            machine_model=str(data["machine_model"]),
            created_at=str(data["created_at"]),
            results=dict(data.get("results", {})),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)

    def record(
        self,
        test: CalibrationTest,
        result: str,
        evidence: Optional[Dict[str, Any]] = None,
        tests: Optional[Sequence[CalibrationTest]] = None,
    ) -> None:
        result = result.lower()
        if result not in VALID_RESULTS:
            raise ValueError("result must be pass, fail or skipped")
        if result == "skipped" and not test.conditional:
            raise ValueError("%s is not conditional and may not be skipped" % test.id)
        if result == "pass" and tests is not None:
            by_id = {item.id: item for item in tests}
            unknown = [dep for dep in test.depends_on if dep not in by_id]
            if unknown:
                raise ValueError("unknown dependencies: %s" % ", ".join(unknown))
            blocked = [
                dep for dep in test.depends_on
                if self.results.get(dep, {}).get("result") not in {"pass", "skipped"}
            ]
            if blocked:
                raise ValueError("blocked by incomplete dependencies: %s" % ", ".join(blocked))
        self.results[test.id] = {
            "result": result,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "evidence": evidence or {},
        }

    def next_tests(self, tests: Sequence[CalibrationTest]) -> List[CalibrationTest]:
        ready: List[CalibrationTest] = []
        for test in tests:
            if test.id in self.results:
                continue
            if all(self.results.get(dep, {}).get("result") in {"pass", "skipped"} for dep in test.depends_on):
                ready.append(test)
        return ready

    def summary(self, tests: Sequence[CalibrationTest]) -> Dict[str, int]:
        counts = {"pass": 0, "fail": 0, "skipped": 0, "pending": 0}
        for test in tests:
            result = self.results.get(test.id, {}).get("result", "pending")
            counts[result] += 1
        return counts
