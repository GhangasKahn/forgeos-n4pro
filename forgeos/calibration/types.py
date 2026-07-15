"""Calibration type definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CalCategory(str, Enum):
    """When to run a calibration test."""

    ONE_TIME = "one_time"  # After hardware install/change
    PERIODIC = "periodic"  # Weekly / bed change / nozzle swap
    FINE_TUNE = "fine_tune"  # Per material, session, or env bin
    GATE = "gate"  # Zero-trust verification evidence


class CalPhase(str, Enum):
    """Logical grouping for operator runbooks."""

    PREFLIGHT = "preflight"
    THERMAL = "thermal"
    GEOMETRY = "geometry"
    EXTRUSION = "extrusion"
    MOTION = "motion"
    DIMENSIONAL = "dimensional"
    QUALITY = "quality"
    RELIABILITY = "reliability"


@dataclass(frozen=True)
class CalTestDef:
    """Single calibration test definition."""

    id: str
    name: str
    category: CalCategory
    phase: CalPhase
    description: str
    macro: Optional[str] = None
    gcode: tuple = ()
    prerequisites: tuple = ()
    duration_min: float = 5.0
    requires_filament: bool = False
    requires_sensor: Optional[str] = None
    capture_fields: tuple = ()
    pass_criteria: Dict[str, Any] = field(default_factory=dict)
    openneptune_macro: Optional[str] = None
    klipper_commands: tuple = ()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "phase": self.phase.value,
            "description": self.description,
            "macro": self.macro,
            "gcode": list(self.gcode),
            "prerequisites": list(self.prerequisites),
            "duration_min": self.duration_min,
            "requires_filament": self.requires_filament,
            "requires_sensor": self.requires_sensor,
            "capture_fields": list(self.capture_fields),
            "pass_criteria": dict(self.pass_criteria),
            "openneptune_macro": self.openneptune_macro,
            "klipper_commands": list(self.klipper_commands),
        }


@dataclass
class CalMeasurement:
    """Operator or automated measurement for a test."""

    test_id: str
    values: Dict[str, Any]
    notes: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"test_id": self.test_id, "values": self.values, "notes": self.notes}


@dataclass
class CalAnalysis:
    """Analyzed result with pass/fail and evidence."""

    test_id: str
    passed: bool
    summary: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "passed": self.passed,
            "summary": self.summary,
            "evidence": self.evidence,
            "recommendations": self.recommendations,
        }
