"""Executable calibration campaign runner (dry-run or live Moonraker)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import json
import time

from forgeos.calibration.patterns import (
    generate_extrude_cal_script,
    generate_first_layer_patch,
    generate_flow_shell,
    generate_pa_fine_tower,
    generate_pa_tower,
    write_pattern,
)
from forgeos.calibration.promote import CalRecipe, promote_recipe
from forgeos.calibration.protocol import (
    CalPlan,
    CalStepDef,
    CalSuite,
    OperatorMode,
    build_plan,
)
from forgeos.campaigns.dimensional_fit import DimSample, fit_scales
from forgeos.journal import Journal
from forgeos.moonraker_client import MoonrakerClient, MoonrakerError
from forgeos.safety import SafetyError, SafetyGate


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_OPERATOR = "waiting_operator"


@dataclass
class StepResult:
    step_id: str
    status: StepStatus
    detail: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    macros_run: List[str] = field(default_factory=list)
    gcode_path: Optional[str] = None
    ts: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "status": self.status.value,
            "detail": self.detail,
            "evidence": self.evidence,
            "macros_run": self.macros_run,
            "gcode_path": self.gcode_path,
            "ts": self.ts,
        }


@dataclass
class CampaignReport:
    suite: str
    sku: str
    dry_run: bool
    results: List[StepResult] = field(default_factory=list)
    recipe: Optional[CalRecipe] = None
    failed: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "suite": self.suite,
            "sku": self.sku,
            "dry_run": self.dry_run,
            "failed": self.failed,
            "results": [r.as_dict() for r in self.results],
            "recipe": self.recipe.as_dict() if self.recipe else None,
        }


class CalibrationRunner:
    """Drive one-time / fine-tune / full calibration plans.

    ``dry_run=True`` (default): plan macros + write gcode artifacts, no Moonraker.
    ``execute=True``: send AUTO macros via Moonraker (requires campaign arm token).
    Interactive/measure steps always pause for operator evidence via ``advance`` /
    ``submit_evidence``.
    """

    def __init__(
        self,
        journal: Journal,
        safety: SafetyGate,
        client: Optional[MoonrakerClient] = None,
        artifacts_dir: Optional[Path] = None,
        recipe: Optional[CalRecipe] = None,
    ) -> None:
        self.journal = journal
        self.safety = safety
        self.client = client
        self.artifacts_dir = Path(artifacts_dir or Path("artifacts") / "calibration")
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.recipe = recipe or CalRecipe()
        self.plan: Optional[CalPlan] = None
        self._arm_token: Optional[str] = None
        self._idx: int = -1
        self._results: List[StepResult] = []
        self._capabilities: Set[str] = set()
        self._dry_run: bool = True
        self._execute: bool = False

    @property
    def current_step(self) -> Optional[CalStepDef]:
        if self.plan is None or self._idx < 0 or self._idx >= len(self.plan.steps):
            return None
        return self.plan.steps[self._idx]

    def start(
        self,
        suite: CalSuite = CalSuite.FULL,
        arm_token: Optional[str] = None,
        *,
        dry_run: bool = True,
        execute: bool = False,
        has_adxl: bool = False,
        include_optional: bool = True,
        sku: str = "protopasta_htpla",
    ) -> CalPlan:
        if execute and not dry_run:
            if arm_token is None:
                raise SafetyError("live calibration requires campaign arm token")
            self.safety.require_armed("campaign", arm_token)
            self._arm_token = arm_token
            if self.client is None:
                raise SafetyError("live calibration requires MoonrakerClient")
        self._dry_run = dry_run
        self._execute = bool(execute and not dry_run)
        self._capabilities = set()
        if has_adxl:
            self._capabilities.add("adxl")
        self.recipe.sku = sku
        self.plan = build_plan(
            suite=suite,
            sku=sku,
            has_adxl=has_adxl,
            include_optional=include_optional,
        )
        self._idx = 0
        self._results = []
        self.journal.log_event(
            "cal_campaign_start",
            {
                "suite": suite.value,
                "sku": sku,
                "dry_run": self._dry_run,
                "execute": self._execute,
                "steps": [s.id for s in self.plan.steps],
            },
        )
        return self.plan

    def _should_skip(self, step: CalStepDef) -> Optional[str]:
        for need in step.skip_without:
            if need not in self._capabilities:
                return "missing capability: %s" % need
        return None

    def _write_step_gcode(self, step: CalStepDef) -> Optional[str]:
        r = self.recipe
        path = self.artifacts_dir / ("forgeos_cal_%s.gcode" % step.id)
        content: Optional[str] = None
        if step.id in {"flow", "flow_fine"}:
            content = generate_flow_shell(
                bed=r.bed_c,
                nozzle=r.nozzle_c,
                soak=min(r.soak_min, 3.0),
                line_w=0.44,
                flow=r.flow,
                pa=0.0 if step.id == "flow" else r.pressure_advance,
            )
        elif step.id == "pressure_advance":
            content = generate_pa_tower(
                bed=r.bed_c,
                nozzle=r.nozzle_c,
                soak=min(r.soak_min, 3.0),
            )
        elif step.id == "pa_fine":
            content = generate_pa_fine_tower(
                seed_pa=r.pressure_advance,
                bed=r.bed_c,
                nozzle=r.nozzle_c,
                soak=min(r.soak_min, 3.0),
            )
        elif step.id in {"first_layer", "flat_fine"}:
            content = generate_first_layer_patch(
                bed=r.bed_c,
                nozzle=r.nozzle_c,
                soak=r.soak_min,
                pa=r.pressure_advance,
                flow=r.flow,
            )
        elif step.id == "rotation_distance":
            content = generate_extrude_cal_script(hotend_c=r.nozzle_c)
        elif step.id in {"coupon", "g4_precision"}:
            # Prefer existing G3 generator artifact path note
            path = self.artifacts_dir / "forgeos_cal_coupon_README.txt"
            path.write_text(
                "Print artifacts/gcodes/forgeos_g3_htpla_100mm_bar*.gcode "
                "or: python3 scripts/generate_g3_bar_gcode.py --use-stack\n",
                encoding="utf-8",
            )
            return str(path)
        if content is not None:
            write_pattern(str(path), content)
            return str(path)
        return None

    def _run_macros(self, macros: List[str], step: CalStepDef) -> List[str]:
        ran: List[str] = []
        if not self._execute or self.client is None:
            return list(macros)
        # Expand parametric macros with recipe values
        for m in macros:
            script = m
            if m == "FORGE_HEAT_DUAL_BED":
                script = "FORGE_HEAT_DUAL_BED BED=%.1f" % self.recipe.bed_c
            elif m == "FORGE_BED_SOAK":
                script = "FORGE_BED_SOAK MIN=%.2f" % self.recipe.soak_min
            elif m == "FORGE_APPLY_CAL_RESULT":
                script = (
                    "FORGE_APPLY_CAL_RESULT PA=%.4f FLOW=%.0f Z=%.3f RETRACT=%.2f"
                    % (
                        self.recipe.pressure_advance,
                        self.recipe.flow * 100.0,
                        self.recipe.z_adjust_mm,
                        self.recipe.retract_mm,
                    )
                )
            try:
                # Interactive macros: fire and return (operator finishes)
                if step.operator == OperatorMode.INTERACTIVE:
                    self.client.gcode(script, timeout_s=15.0)
                elif step.id == "pid":
                    self.client.run_script_and_wait(script, timeout_s=2400.0, gcode_timeout_s=20.0)
                elif step.id == "mesh":
                    self.client.run_script_and_wait(script, timeout_s=900.0, gcode_timeout_s=20.0)
                else:
                    self.client.gcode(script, timeout_s=60.0)
                ran.append(script)
            except MoonrakerError as exc:
                raise SafetyError("macro failed %s: %s" % (script, exc))
        return ran

    def run_current(self, auto_pass_dry: bool = True) -> StepResult:
        step = self.current_step
        if step is None:
            raise SafetyError("no current calibration step")
        skip = self._should_skip(step)
        if skip:
            result = StepResult(step.id, StepStatus.SKIPPED, skip)
            self._results.append(result)
            self.journal.log_event("cal_step", result.as_dict())
            return result

        gcode_path = self._write_step_gcode(step)
        macros_run: List[str] = []
        detail = step.description

        if self._execute and step.operator == OperatorMode.AUTO:
            macros_run = self._run_macros(list(step.macros), step)
            if step.id == "mesh" and self.client:
                p2p = self.client.mesh_peak_to_peak()
                if p2p is not None:
                    self.recipe.mesh_p2p_mm = p2p
            if step.id == "promote":
                promote_recipe(self.journal, self.recipe)
            result = StepResult(
                step.id,
                StepStatus.PASSED,
                detail="auto executed",
                evidence={"mesh_p2p_mm": self.recipe.mesh_p2p_mm},
                macros_run=macros_run,
                gcode_path=gcode_path,
            )
        elif step.operator in {OperatorMode.INTERACTIVE, OperatorMode.MEASURE}:
            macros_run = self._run_macros(list(step.macros), step) if self._execute else list(step.macros)
            result = StepResult(
                step.id,
                StepStatus.WAITING_OPERATOR,
                detail=detail,
                macros_run=macros_run,
                gcode_path=gcode_path,
            )
        elif self._dry_run and auto_pass_dry:
            result = StepResult(
                step.id,
                StepStatus.PASSED,
                detail="dry-run planned: %s" % ", ".join(step.macros) if step.macros else "dry-run",
                macros_run=list(step.macros),
                gcode_path=gcode_path,
                evidence={"dry_run": True},
            )
        else:
            result = StepResult(
                step.id,
                StepStatus.WAITING_OPERATOR,
                detail=detail,
                macros_run=list(step.macros),
                gcode_path=gcode_path,
            )

        self._results.append(result)
        self.journal.log_event("cal_step", result.as_dict())
        return result

    def submit_evidence(self, evidence: Dict[str, Any], ok: bool = True) -> StepResult:
        """Complete a WAITING_OPERATOR step with operator measurements."""
        if not self._results:
            raise SafetyError("no step to submit evidence for")
        last = self._results[-1]
        if last.status not in {StepStatus.WAITING_OPERATOR, StepStatus.RUNNING}:
            raise SafetyError("current result not waiting for evidence")
        step = self.current_step
        if step is None:
            raise SafetyError("no current step")

        # Apply known evidence keys into recipe
        if "pressure_advance" in evidence:
            self.recipe.pressure_advance = float(evidence["pressure_advance"])
        if "pa_height_mm" in evidence:
            from forgeos.calibration.math_cal import compute_pressure_advance

            pr = compute_pressure_advance(float(evidence["pa_height_mm"]))
            self.recipe.pressure_advance = pr.pressure_advance
            evidence["pressure_advance"] = pr.pressure_advance
        if "flow" in evidence:
            self.recipe.flow = float(evidence["flow"])
        if "wall_mm" in evidence:
            from forgeos.calibration.math_cal import compute_flow_multiplier

            fr = compute_flow_multiplier(float(evidence["wall_mm"]), current_flow=self.recipe.flow)
            self.recipe.flow = fr.new_flow
            evidence["flow"] = fr.new_flow
        if "z_adjust_mm" in evidence:
            self.recipe.z_adjust_mm = float(evidence["z_adjust_mm"])
        if "retract_mm" in evidence:
            self.recipe.retract_mm = float(evidence["retract_mm"])
        if "wipe_mm" in evidence:
            self.recipe.wipe_mm = float(evidence["wipe_mm"])
        if "z_hop_mm" in evidence:
            self.recipe.z_hop_mm = float(evidence["z_hop_mm"])
        if "nozzle_c" in evidence:
            self.recipe.nozzle_c = float(evidence["nozzle_c"])
        if "rotation_distance" in evidence:
            self.recipe.rotation_distance = float(evidence["rotation_distance"])
        if "actual_mm" in evidence and "commanded_mm" in evidence and "current_rd" in evidence:
            from forgeos.calibration.math_cal import compute_rotation_distance

            rd = compute_rotation_distance(
                float(evidence["current_rd"]),
                commanded_mm=float(evidence["commanded_mm"]),
                actual_mm=float(evidence["actual_mm"]),
            )
            self.recipe.rotation_distance = rd.new_rotation_distance
            evidence["rotation_distance"] = rd.new_rotation_distance
        if "abs_error_100mm" in evidence:
            self.recipe.abs_error_100mm = float(evidence["abs_error_100mm"])
        if "samples" in evidence:
            samples = [
                DimSample(axis=s["axis"], nominal_mm=float(s["nominal_mm"]), measured_mm=float(s["measured_mm"]))
                for s in evidence["samples"]
            ]
            fit = fit_scales(samples)
            self.recipe.abs_error_100mm = fit.mean_abs_error_100mm
            evidence["xy_scale"] = fit.xy_scale
            evidence["abs_error_100mm"] = fit.mean_abs_error_100mm

        last.evidence.update(evidence)
        last.status = StepStatus.PASSED if ok else StepStatus.FAILED
        last.detail = "operator evidence accepted" if ok else "operator evidence FAIL"
        last.ts = time.time()
        self.journal.log_event("cal_step_evidence", last.as_dict())
        if not ok:
            raise SafetyError("calibration step failed: %s" % step.id)
        return last

    def advance(self) -> Optional[CalStepDef]:
        if self.plan is None:
            raise SafetyError("campaign not started")
        if self._results:
            last = self._results[-1]
            if last.status == StepStatus.WAITING_OPERATOR:
                raise SafetyError("submit_evidence before advance")
            if last.status == StepStatus.FAILED:
                return None
        self._idx += 1
        if self._idx >= len(self.plan.steps):
            self.journal.log_event("cal_campaign_done", {"sku": self.recipe.sku, "results": len(self._results)})
            return None
        return self.current_step

    def run_all_dry(self) -> CampaignReport:
        """Plan every step (dry-run), auto-pass non-interactive; leave interactive as planned PASS."""
        if self.plan is None:
            self.start(CalSuite.FULL, dry_run=True)
        assert self.plan is not None
        report = CampaignReport(suite=self.plan.suite.value, sku=self.recipe.sku, dry_run=True)
        while self.current_step is not None:
            result = self.run_current(auto_pass_dry=True)
            # In dry-run, convert WAITING to PASSED for plan completeness
            if result.status == StepStatus.WAITING_OPERATOR:
                result.status = StepStatus.PASSED
                result.detail = "dry-run operator step planned"
            report.results.append(result)
            if result.status == StepStatus.FAILED:
                report.failed = True
                break
            nxt = self.advance()
            if nxt is None and self._idx >= len(self.plan.steps):
                break
        report.recipe = self.recipe
        return report

    def write_report(self, report: CampaignReport, path: Optional[Path] = None) -> Path:
        out = Path(path or (self.artifacts_dir / "cal_campaign_report.json"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.as_dict(), indent=2) + "\n", encoding="utf-8")
        return out
