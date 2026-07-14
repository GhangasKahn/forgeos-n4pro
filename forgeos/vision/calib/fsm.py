"""Vision-assisted calibration FSM (Z / first-layer), Jetson-side.

Suggest-only by default; auto-apply only when armed and within envelopes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from forgeos.vision.events import VisionEvent
from forgeos.vision.scorers.first_layer import FirstLayerResult


class CalibState(str, Enum):
    IDLE = "idle"
    WAIT_FIRST_LAYER = "wait_first_layer"
    SCORING = "scoring"
    ADJUST = "adjust"
    CONVERGED = "converged"
    FAILED = "failed"


@dataclass
class VisionCalibFSM:
    armed: bool = False
    max_steps: int = 8
    max_total_z_mm: float = 0.15
    step_mm: float = 0.02
    good_score: float = 0.8
    state: CalibState = CalibState.IDLE
    steps: int = 0
    z_delta_applied: float = 0.0
    history: List[VisionEvent] = field(default_factory=list)

    def arm(self) -> None:
        self.armed = True
        self.state = CalibState.WAIT_FIRST_LAYER
        self.steps = 0
        self.z_delta_applied = 0.0

    def disarm(self) -> None:
        self.armed = False
        self.state = CalibState.IDLE

    def on_first_layer_result(self, result: FirstLayerResult) -> VisionEvent:
        self.state = CalibState.SCORING
        suggestion = result.suggestion
        apply_cmd = None

        if result.score >= self.good_score and "good_sheet" in result.labels:
            self.state = CalibState.CONVERGED
            suggestion = None
        elif self.steps >= self.max_steps:
            self.state = CalibState.FAILED
        elif suggestion == "FORGE_BABY_UP" and abs(self.z_delta_applied + self.step_mm) <= self.max_total_z_mm:
            apply_cmd = "FORGE_BABY_UP"
            self.z_delta_applied += self.step_mm
            self.steps += 1
            self.state = CalibState.ADJUST
        elif suggestion in ("FORGE_BABY_DOWN", "INCREASE_FLOW_OR_BABY_DOWN"):
            if abs(self.z_delta_applied - self.step_mm) <= self.max_total_z_mm:
                apply_cmd = "FORGE_BABY_DOWN"
                self.z_delta_applied -= self.step_mm
                self.steps += 1
                self.state = CalibState.ADJUST

        # Only auto-apply when armed; still report suggestion always
        event = VisionEvent(
            type="first_layer_score",
            severity="info" if result.score >= self.good_score else "warn",
            scores={"first_layer": result.score},
            labels=list(result.labels),
            suggestion=apply_cmd if self.armed else suggestion,
            cameras=["cam_nozzle", "cam_oblique"],
            meta={
                "armed": self.armed,
                "state": self.state.value,
                "steps": self.steps,
                "z_delta_applied": self.z_delta_applied,
                "metrics": result.metrics,
                "would_apply": apply_cmd if self.armed else None,
            },
        )
        self.history.append(event)
        return event
