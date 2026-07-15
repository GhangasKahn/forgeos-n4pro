"""Gate ledger — CNC promotion only with measured evidence (zero-trust)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from forgeos.gates.verification import GateStatus, gate_g3_accuracy, gate_g4_precision
from forgeos.precision import PrecisionTier, get_band, process_capability


def _tier(name: str) -> PrecisionTier:
    try:
        return PrecisionTier(name)
    except ValueError:
        return PrecisionTier.CNC


@dataclass
class GateRecord:
    gate_id: str
    status: str  # pass | fail | pending | skip | unknown
    detail: str = ""
    evidence_path: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GateLedger:
    """In-memory + on-disk ledger of G0–G7 for a campaign."""

    precision_tier: str = "cnc"
    records: Dict[str, GateRecord] = field(default_factory=dict)

    def set(
        self,
        gate_id: str,
        status: str,
        detail: str = "",
        evidence_path: Optional[str] = None,
        **metrics: Any,
    ) -> GateRecord:
        rec = GateRecord(
            gate_id=gate_id,
            status=status,
            detail=detail,
            evidence_path=evidence_path,
            metrics=metrics,
        )
        self.records[gate_id] = rec
        return rec

    def record_g3(self, mean_mm: float, target_mm: float = 100.0) -> GateRecord:
        err = mean_mm - target_mm
        g = gate_g3_accuracy(err)
        status = "pass" if g.status == GateStatus.PASS else "fail"
        band = get_band(_tier(self.precision_tier))
        return self.set(
            "G3",
            status,
            g.detail,
            mean_mm=mean_mm,
            target_mm=target_mm,
            abs_error_mm=abs(err),
            limit_mm=band.abs_error_max_mm,
        )

    def record_g4(
        self,
        measurements: List[float],
        target_mm: float = 100.0,
    ) -> GateRecord:
        if not measurements:
            return self.set("G4", "fail", "no measurements")
        cap = process_capability(
            measurements,
            nominal_mm=target_mm,
            tier=_tier(self.precision_tier),
        )
        g = gate_g4_precision(cap.span_mm)
        status = "pass" if (g.status == GateStatus.PASS and cap.passed) else "fail"
        band = get_band(_tier(self.precision_tier))
        return self.set(
            "G4",
            status,
            "%s; Cpk=%s" % (g.detail, cap.cpk),
            measurements=list(measurements),
            n=len(measurements),
            span_mm=cap.span_mm,
            cpk=cap.cpk,
            limit_span_mm=band.span_max_mm,
        )

    def record_g2_mesh(self, p2p_mm: float) -> GateRecord:
        band = get_band(_tier(self.precision_tier))
        ok = p2p_mm <= band.mesh_p2p_max_mm
        return self.set(
            "G2",
            "pass" if ok else "fail",
            "mesh p2p=%.3f limit=%.3f" % (p2p_mm, band.mesh_p2p_max_mm),
            p2p_mm=p2p_mm,
            limit_mm=band.mesh_p2p_max_mm,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "precision_tier": self.precision_tier,
            "records": {k: v.as_dict() for k, v in self.records.items()},
            "all_blocking_pass": self.blocking_pass(),
        }

    def blocking_pass(self) -> bool:
        """CNC shop pilot requires G0–G4 pass when present; missing = not pass."""
        needed = ("G0", "G1", "G2", "G3", "G4")
        for g in needed:
            rec = self.records.get(g)
            if rec is None or rec.status != "pass":
                return False
        return True

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2) + "\n")
        return path

    @classmethod
    def load(cls, path: Path) -> "GateLedger":
        data = json.loads(path.read_text())
        led = cls(precision_tier=data.get("precision_tier", "cnc"))
        for k, v in (data.get("records") or {}).items():
            led.records[k] = GateRecord(
                gate_id=v.get("gate_id", k),
                status=v.get("status", "unknown"),
                detail=v.get("detail", ""),
                evidence_path=v.get("evidence_path"),
                metrics=v.get("metrics") or {},
            )
        return led
