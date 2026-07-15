"""FORGE_CAL_FULL campaign state machine — bridges to calibration protocol.

Prefer ``forgeos.calibration.runner.CalibrationRunner`` for executable campaigns.
This module keeps the legacy step enum used by existing unit tests and docs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from forgeos.calibration.protocol import CalSuite, build_plan
from forgeos.journal import Journal
from forgeos.safety import SafetyError, SafetyGate


class CalStep(str, Enum):
    IDLE = "idle"
    PID = "pid"
    RESONANCE = "resonance"
    PROBE_Z = "probe_z"
    MESH = "mesh"
    FLOW = "flow"
    PA = "pressure_advance"
    COUPON = "coupon_print"
    MEASURE = "measure"
    DONE = "done"
    FAILED = "failed"


# Legacy order (subset of onetime; RD/first_layer/retract live in full protocol)
STEP_ORDER = [
    CalStep.PID,
    CalStep.RESONANCE,
    CalStep.PROBE_Z,
    CalStep.MESH,
    CalStep.FLOW,
    CalStep.PA,
    CalStep.COUPON,
    CalStep.MEASURE,
    CalStep.DONE,
]


@dataclass
class FullCalCampaign:
    journal: Journal
    safety: SafetyGate
    sku: str = "protopasta_htpla"
    step: CalStep = CalStep.IDLE
    evidence: Dict[str, Any] = field(default_factory=dict)
    history: List[str] = field(default_factory=list)

    def start(self, arm_token: str) -> None:
        self.safety.require_armed("campaign", arm_token)
        self.step = CalStep.PID
        self.history.append("start")
        self.journal.log_event("cal_start", {"sku": self.sku})

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
        if idx + 1 >= len(STEP_ORDER):
            self.step = CalStep.DONE
        else:
            self.step = STEP_ORDER[idx + 1]
        if self.step == CalStep.DONE:
            self.journal.log_event("cal_done", {"sku": self.sku, "evidence": self.evidence})
        return self.step

    def moonraker_scripts_for_step(self) -> List[str]:
        """G-code / macro names operators or automation should run for current step."""
        mapping = {
            CalStep.PID: ["FORGE_PID_ALL"],
            CalStep.RESONANCE: ["FORGE_SHAPER_CAL"],
            CalStep.PROBE_Z: ["FORGE_PROBE_CAL"],
            CalStep.MESH: ["FORGE_MESH_PRECISION"],
            CalStep.FLOW: ["FORGE_FLOW_CAL"],
            CalStep.PA: ["FORGE_PA_CAL"],
            CalStep.COUPON: ["FORGE_PRINT_COUPON"],
            CalStep.MEASURE: ["# operator: import caliper CSV / enter dims"],
        }
        return list(mapping.get(self.step, []))

    def full_protocol_plan(self, has_adxl: bool = False):
        """Return the expanded OpenNeptune-grade onetime+finetune plan."""
        return build_plan(suite=CalSuite.FULL, sku=self.sku, has_adxl=has_adxl)
