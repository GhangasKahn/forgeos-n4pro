"""Calibration orchestration — offline planning and live Moonraker execution."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from forgeos.calibration.analysis import analyze_measurement
from forgeos.calibration.registry import (
    CALIBRATION_CATALOG,
    FULL_CAMPAIGN_SEQUENCE,
    FINE_TUNE_SEQUENCE,
    ONE_TIME_SEQUENCE,
    get_calibration_test,
)
from forgeos.calibration.types import CalAnalysis, CalCategory, CalMeasurement, CalTestDef
from forgeos.journal import Journal
from forgeos.moonraker_client import MoonrakerClient, MoonrakerError
from forgeos.safety import SafetyError, SafetyGate


@dataclass
class CalStepResult:
    """Result of one calibration step."""

    test_id: str
    status: str  # pending, running, ok, fail, skip
    detail: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    analysis: Optional[CalAnalysis] = None
    duration_s: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        d = {
            "test_id": self.test_id,
            "status": self.status,
            "detail": self.detail,
            "evidence": self.evidence,
            "duration_s": round(self.duration_s, 2),
        }
        if self.analysis:
            d["analysis"] = self.analysis.as_dict()
        return d


class CalibrationRunner:
    """Run calibration tests offline (plan/analyze) or live via Moonraker."""

    def __init__(
        self,
        journal: Optional[Journal] = None,
        safety: Optional[SafetyGate] = None,
        client: Optional[MoonrakerClient] = None,
    ) -> None:
        self.journal = journal
        self.safety = safety or SafetyGate()
        self.client = client
        self.results: List[CalStepResult] = []
        self._armed = False

    def arm(self, token: str, purpose: str = "campaign") -> None:
        self.safety.require_armed(purpose, token)
        self._armed = True

    def plan_sequence(self, mode: str = "full") -> List[CalTestDef]:
        """Return ordered test definitions for a mode."""
        if mode == "one_time":
            ids = ONE_TIME_SEQUENCE
        elif mode == "fine_tune":
            ids = FINE_TUNE_SEQUENCE
        elif mode == "full":
            ids = FULL_CAMPAIGN_SEQUENCE
        else:
            raise ValueError("unknown mode: %s" % mode)
        out: List[CalTestDef] = []
        for tid in ids:
            t = get_calibration_test(tid)
            if t:
                # Skip sensor-required tests when no sensor configured
                if t.requires_sensor == "adxl345" and mode != "one_time":
                    continue
                out.append(t)
        return out

    def plan_report(self, mode: str = "full") -> Dict[str, Any]:
        """Offline plan with durations and prerequisites."""
        seq = self.plan_sequence(mode)
        total_min = sum(t.duration_min for t in seq)
        return {
            "mode": mode,
            "test_count": len(seq),
            "estimated_duration_min": round(total_min, 1),
            "tests": [t.as_dict() for t in seq],
        }

    def record_measurement(self, test_id: str, values: Dict[str, Any], notes: str = "") -> CalStepResult:
        """Analyze operator measurements and journal."""
        analysis = analyze_measurement(test_id, values)
        result = CalStepResult(
            test_id=test_id,
            status="ok" if analysis.passed else "fail",
            detail=analysis.summary,
            evidence=analysis.evidence,
            analysis=analysis,
        )
        self.results.append(result)
        if self.journal:
            self.journal.log_event(
                "cal_measurement",
                {
                    "test_id": test_id,
                    "values": values,
                    "notes": notes,
                    "passed": analysis.passed,
                    "summary": analysis.summary,
                },
            )
        return result

    def run_live_step(
        self,
        test: CalTestDef,
        dry_run: bool = False,
        command_timeout_s: float = 600.0,
    ) -> CalStepResult:
        """Execute klipper commands for one test via Moonraker."""
        if test.requires_sensor and not dry_run:
            return CalStepResult(
                test.id,
                "skip",
                "requires sensor: %s" % test.requires_sensor,
                evidence={"requires_sensor": test.requires_sensor},
            )
        t0 = time.time()
        log: List[Dict[str, Any]] = []
        if dry_run:
            for cmd in test.klipper_commands or (test.macro and [test.macro] or []):
                log.append({"cmd": cmd, "dry_run": True})
            return CalStepResult(
                test.id,
                "ok",
                "dry_run %d commands" % len(log),
                evidence={"commands": log},
                duration_s=time.time() - t0,
            )
        if not self.client:
            return CalStepResult(test.id, "fail", "no Moonraker client")
        if not self.client.is_ready():
            return CalStepResult(test.id, "fail", "printer not ready")
        commands = list(test.klipper_commands)
        if test.macro and test.macro not in commands:
            commands.insert(0, test.macro)
        for cmd in commands:
            if cmd.startswith("#") or cmd.startswith(";"):
                continue
            try:
                resp = self.client.gcode(cmd, timeout_s=command_timeout_s)
                log.append({"cmd": cmd, "ok": True, "result": resp.get("result")})
            except MoonrakerError as exc:
                log.append({"cmd": cmd, "ok": False, "error": str(exc)})
                result = CalStepResult(
                    test.id,
                    "fail",
                    "gcode failed: %s" % cmd,
                    evidence={"log": log},
                    duration_s=time.time() - t0,
                )
                self.results.append(result)
                if self.journal:
                    self.journal.log_event("cal_live_fail", result.as_dict())
                return result
        evidence: Dict[str, Any] = {"log": log}
        # Auto-capture mesh if applicable
        if test.id in ("mesh_golden", "mesh_balanced", "mesh_fast"):
            evidence.update(self._capture_mesh())
        result = CalStepResult(
            test.id,
            "ok",
            "executed %d commands" % len(log),
            evidence=evidence,
            duration_s=time.time() - t0,
        )
        self.results.append(result)
        if self.journal:
            self.journal.log_event("cal_live_ok", result.as_dict())
        return result

    def _capture_mesh(self) -> Dict[str, Any]:
        if not self.client:
            return {}
        try:
            obj = self.client.objects_query(["bed_mesh"])
            bm = obj.get("result", {}).get("status", {}).get("bed_mesh", {})
            matrix = bm.get("probed_matrix") or bm.get("mesh_matrix")
            if matrix:
                from forgeos.calibration.analysis import analyze_mesh_matrix

                analysis = analyze_mesh_matrix(matrix)
                return {"mesh": bm, "analysis": analysis.as_dict()}
        except MoonrakerError:
            pass
        return {}

    def run_live_sequence(
        self,
        mode: str = "one_time",
        dry_run: bool = False,
        stop_on_fail: bool = True,
    ) -> Dict[str, Any]:
        """Run full sequence against printer."""
        if not dry_run and not self._armed:
            raise SafetyError("live calibration requires arm token")
        seq = self.plan_sequence(mode)
        for test in seq:
            result = self.run_live_step(test, dry_run=dry_run)
            if stop_on_fail and result.status == "fail":
                break
        return self.summary()

    def summary(self) -> Dict[str, Any]:
        passed = sum(1 for r in self.results if r.status == "ok")
        failed = sum(1 for r in self.results if r.status == "fail")
        skipped = sum(1 for r in self.results if r.status == "skip")
        return {
            "steps": [r.as_dict() for r in self.results],
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "all_ok": failed == 0,
        }

    def write_report(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.summary(), indent=2), encoding="utf-8")


def merge_pid_steps(tests: List[CalTestDef]) -> List[CalTestDef]:
    """Collapse PID trio into FORGE_PID_ALL for campaign compatibility."""
    pid_ids = {"pid_extruder", "pid_bed_inner", "pid_bed_outer"}
    out: List[CalTestDef] = []
    pid_seen = False
    for t in tests:
        if t.id in pid_ids:
            if not pid_seen:
                out.append(
                    CalTestDef(
                        id="pid_all",
                        name="PID tune all heaters",
                        category=CalCategory.ONE_TIME,
                        phase=t.phase,
                        description="Nozzle + inner + outer bed PID in one session.",
                        macro="FORGE_PID_ALL",
                        klipper_commands=(
                            "PID_CALIBRATE HEATER=extruder TARGET=220",
                            "PID_CALIBRATE HEATER=heater_bed TARGET=65",
                            "PID_CALIBRATE HEATER=heater_bed_outer TARGET=65",
                            "SAVE_CONFIG",
                        ),
                        duration_min=40.0,
                    )
                )
                pid_seen = True
            continue
        out.append(t)
    return out
