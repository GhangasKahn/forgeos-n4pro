"""Zero-trust multi-verification gate protocol.

Nothing is "ready for public / production use" until independent gates pass.
Design inspired by high-reliability process control, not marketing checklists.

Gate levels:
  G0  unit / static (code + material packs)
  G1  hardware preflight (nozzle, MCU ready, disk)
  G2  thermal / mesh / shaper instrumentation
  G3  dimensional coupon (accuracy)
  G4  precision replicate (3x)
  G5  speed regression vs baseline with gates held
  G6  anneal process (HTPLA) if claimed
  G7  reliability soak (time + log growth + MCU stability)

Public/production release requires G0–G5 minimum; G6 if anneal advertised; G7 for unattended claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import time


class GateStatus(str, Enum):
    PENDING = "pending"
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class GateResult:
    gate_id: str
    name: str
    status: GateStatus
    detail: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class VerificationReport:
    results: List[GateResult] = field(default_factory=list)

    def add(self, result: GateResult) -> None:
        self.results.append(result)

    def passed(self, required: Optional[List[str]] = None) -> bool:
        by_id = {r.gate_id: r for r in self.results}
        if required is None:
            return all(r.status == GateStatus.PASS for r in self.results if r.status != GateStatus.SKIP)
        for gid in required:
            r = by_id.get(gid)
            if r is None or r.status != GateStatus.PASS:
                return False
        return True

    def production_ready(self, anneal_claimed: bool = False, unattended_claimed: bool = False) -> bool:
        required = ["G0", "G1", "G2", "G3", "G4", "G5"]
        if anneal_claimed:
            required.append("G6")
        if unattended_claimed:
            required.append("G7")
        return self.passed(required)

    def summary(self) -> Dict[str, Any]:
        return {
            "gates": [r.as_dict() for r in self.results],
            "all_pass": self.passed(),
            "production_ready": self.production_ready(),
        }


GateFn = Callable[[], GateResult]


class ZeroTrustSuite:
    """Run ordered gates; abort chain on hard fail if stop_on_fail."""

    def __init__(self) -> None:
        self._gates: List[GateFn] = []

    def register(self, fn: GateFn) -> None:
        self._gates.append(fn)

    def run(self, stop_on_fail: bool = True) -> VerificationReport:
        report = VerificationReport()
        for fn in self._gates:
            result = fn()
            report.add(result)
            if stop_on_fail and result.status == GateStatus.FAIL:
                break
        return report


def gate_g0_static(material_count: int, test_failures: int) -> GateResult:
    if test_failures != 0:
        return GateResult("G0", "static_unit", GateStatus.FAIL, "pytest failures=%d" % test_failures)
    if material_count < 1:
        return GateResult("G0", "static_unit", GateStatus.FAIL, "no material packs")
    return GateResult(
        "G0",
        "static_unit",
        GateStatus.PASS,
        "materials=%d tests_ok" % material_count,
        {"material_count": material_count},
    )


def gate_g1_hardware(mcu_ready: bool, disk_free_mb: float, abrasive: bool, nozzle_ok: bool) -> GateResult:
    if not mcu_ready:
        return GateResult("G1", "hardware_preflight", GateStatus.FAIL, "MCU/printer not ready")
    if disk_free_mb < 200:
        return GateResult("G1", "hardware_preflight", GateStatus.FAIL, "disk_free_mb=%.1f" % disk_free_mb)
    if abrasive and not nozzle_ok:
        return GateResult("G1", "hardware_preflight", GateStatus.FAIL, "abrasive without hardened nozzle")
    return GateResult(
        "G1",
        "hardware_preflight",
        GateStatus.PASS,
        "ready disk_free_mb=%.1f" % disk_free_mb,
        {"disk_free_mb": disk_free_mb},
    )


def gate_g2_process_sensors(mesh_peak_to_peak_mm: float, shaper_ok: bool, thermal_stable: bool) -> GateResult:
    if mesh_peak_to_peak_mm > 0.8:
        return GateResult("G2", "mesh_shaper_thermal", GateStatus.FAIL, "mesh p2p too high")
    if not shaper_ok:
        return GateResult("G2", "mesh_shaper_thermal", GateStatus.FAIL, "shaper not validated")
    if not thermal_stable:
        return GateResult("G2", "mesh_shaper_thermal", GateStatus.FAIL, "thermal unstable")
    return GateResult(
        "G2",
        "mesh_shaper_thermal",
        GateStatus.PASS,
        "mesh_p2p=%.3f" % mesh_peak_to_peak_mm,
        {"mesh_peak_to_peak_mm": mesh_peak_to_peak_mm},
    )


def gate_g3_accuracy(abs_error_100mm: float, limit_mm: float = 0.20) -> GateResult:
    if abs(abs_error_100mm) > limit_mm:
        return GateResult(
            "G3",
            "dimensional_accuracy",
            GateStatus.FAIL,
            "|err|=%.3f > %.3f" % (abs(abs_error_100mm), limit_mm),
            {"abs_error_100mm": abs_error_100mm},
        )
    return GateResult(
        "G3",
        "dimensional_accuracy",
        GateStatus.PASS,
        "|err|=%.3f" % abs(abs_error_100mm),
        {"abs_error_100mm": abs_error_100mm},
    )


def gate_g4_precision(span_mm: float, limit_mm: float = 0.10) -> GateResult:
    if span_mm > limit_mm:
        return GateResult(
            "G4",
            "precision_replicate",
            GateStatus.FAIL,
            "span=%.3f > %.3f" % (span_mm, limit_mm),
            {"span_mm": span_mm},
        )
    return GateResult(
        "G4",
        "precision_replicate",
        GateStatus.PASS,
        "span=%.3f" % span_mm,
        {"span_mm": span_mm},
    )


def gate_g5_speed(duration_s: float, baseline_s: float, min_improvement: float = 0.25) -> GateResult:
    if baseline_s <= 0 or duration_s <= 0:
        return GateResult("G5", "speed_vs_baseline", GateStatus.FAIL, "invalid durations")
    improvement = (baseline_s - duration_s) / baseline_s
    if improvement < min_improvement:
        return GateResult(
            "G5",
            "speed_vs_baseline",
            GateStatus.FAIL,
            "improvement=%.1f%% < %.0f%%" % (100 * improvement, 100 * min_improvement),
            {"duration_s": duration_s, "baseline_s": baseline_s, "improvement": improvement},
        )
    return GateResult(
        "G5",
        "speed_vs_baseline",
        GateStatus.PASS,
        "improvement=%.1f%%" % (100 * improvement),
        {"duration_s": duration_s, "baseline_s": baseline_s, "improvement": improvement},
    )


def gate_g6_anneal(post_err_mm: float, limit_mm: float = 0.20) -> GateResult:
    if abs(post_err_mm) > limit_mm:
        return GateResult(
            "G6",
            "anneal_dimensional",
            GateStatus.FAIL,
            "post_anneal |err|=%.3f" % abs(post_err_mm),
        )
    return GateResult(
        "G6",
        "anneal_dimensional",
        GateStatus.PASS,
        "post_anneal |err|=%.3f" % abs(post_err_mm),
        {"post_err_mm": post_err_mm},
    )


def gate_g7_reliability(mcu_losses: int, log_growth_mb_per_day: float, soak_hours: float) -> GateResult:
    if mcu_losses > 0:
        return GateResult("G7", "reliability_soak", GateStatus.FAIL, "mcu_losses=%d" % mcu_losses)
    if log_growth_mb_per_day > 50:
        return GateResult("G7", "reliability_soak", GateStatus.FAIL, "log growth too high")
    if soak_hours < 2.0:
        return GateResult("G7", "reliability_soak", GateStatus.FAIL, "soak too short")
    return GateResult(
        "G7",
        "reliability_soak",
        GateStatus.PASS,
        "soak_h=%.1f log_mb_day=%.1f" % (soak_hours, log_growth_mb_per_day),
        {"soak_hours": soak_hours, "log_growth_mb_per_day": log_growth_mb_per_day},
    )
