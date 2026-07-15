"""FORGE_CAL_FULL campaign — uses calibration registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from forgeos.calibration.registry import FULL_CAMPAIGN_SEQUENCE, get_calibration_test
from forgeos.calibration.runner import CalibrationRunner
from forgeos.journal import Journal
from forgeos.safety import SafetyError, SafetyGate


class CalStep(str, Enum):
    """Campaign step ids aligned with calibration registry."""

    IDLE = "idle"
    PID = "pid_all"
    RESONANCE = "input_shaper"
    PROBE_Z = "probe_z_offset"
    SCREWS = "bed_screws_tilt"
    MESH = "mesh_golden"
    ROTATION = "rotation_distance"
    FLOW = "flow_rate"
    PA = "pressure_advance"
    COUPON = "dimensional_accuracy"
    PRECISION = "precision_replicate"
    MEASURE = "measure"
    DONE = "done"
    FAILED = "failed"


# Operator campaign order (skips optional shaper if no sensor — handled at runtime)
STEP_ORDER = [
    CalStep.PID,
    CalStep.RESONANCE,
    CalStep.PROBE_Z,
    CalStep.SCREWS,
    CalStep.MESH,
    CalStep.ROTATION,
    CalStep.FLOW,
    CalStep.PA,
    CalStep.COUPON,
    CalStep.PRECISION,
    CalStep.MEASURE,
    CalStep.DONE,
]


def _step_to_registry_id(step: CalStep) -> str:
    if step == CalStep.PID:
        return "pid_all"
    if step == CalStep.MEASURE:
        return "measure"
    if step == CalStep.DONE:
        return "done"
    if step == CalStep.FAILED:
        return "failed"
    return step.value


@dataclass
class FullCalCampaign:
    journal: Journal
    safety: SafetyGate
    sku: str = "protopasta_htpla"
    step: CalStep = CalStep.IDLE
    evidence: Dict[str, Any] = field(default_factory=dict)
    history: List[str] = field(default_factory=list)
    skip_shaper: bool = True  # default: no ADXL on shop printer yet

    def start(self, arm_token: str) -> None:
        self.safety.require_armed("campaign", arm_token)
        self.step = CalStep.PID
        self.history.append("start")
        self.journal.log_event("cal_start", {"sku": self.sku, "sequence": FULL_CAMPAIGN_SEQUENCE})

    def advance(self, step_ok: bool, evidence: Optional[Dict[str, Any]] = None) -> CalStep:
        if self.step in {CalStep.IDLE, CalStep.DONE, CalStep.FAILED}:
            raise SafetyError("campaign not running")
        if evidence:
            self.evidence.update(evidence)
        self.history.append("%s:%s" % (self.step.value, "ok" if step_ok else "fail"))
        self.journal.log_event(
            "cal_step",
            {"step": self.step.value, "ok": step_ok, "evidence": evidence or {}},
        )
        if not step_ok:
            self.step = CalStep.FAILED
            return self.step
        try:
            idx = STEP_ORDER.index(self.step)
        except ValueError:
            self.step = CalStep.FAILED
            return self.step
        # Advance to next step, auto-skip shaper when no sensor
        next_idx = idx + 1
        while next_idx < len(STEP_ORDER):
            nxt = STEP_ORDER[next_idx]
            if nxt == CalStep.RESONANCE and self.skip_shaper:
                self.history.append("input_shaper:skip")
                self.journal.log_event("cal_step", {"step": "input_shaper", "ok": True, "skipped": True})
                next_idx += 1
                continue
            if nxt == CalStep.DONE:
                self.step = CalStep.DONE
                self.journal.log_event("cal_done", {"sku": self.sku, "evidence": self.evidence})
                return self.step
            self.step = nxt
            return self.step
        self.step = CalStep.DONE
        self.journal.log_event("cal_done", {"sku": self.sku, "evidence": self.evidence})
        return self.step

    def moonraker_scripts_for_step(self) -> List[str]:
        """G-code / macro names for current step."""
        reg_id = _step_to_registry_id(self.step)
        if self.step == CalStep.MEASURE:
            return ["# operator: caliper measure + scripts/import_caliper_csv.py"]
        if self.step in {CalStep.IDLE, CalStep.DONE, CalStep.FAILED}:
            return []
        # Map pid_all to macro
        if reg_id == "pid_all":
            return ["FORGE_PID_ALL"]
        tdef = get_calibration_test(reg_id)
        if tdef and tdef.macro:
            cmds = [tdef.macro]
            cmds.extend([c for c in tdef.klipper_commands if not c.startswith("SAVE")])
            return cmds
        return []

    def runner_plan(self) -> Dict[str, Any]:
        """Offline plan via CalibrationRunner."""
        runner = CalibrationRunner(journal=self.journal, safety=self.safety)
        return runner.plan_report("full")
