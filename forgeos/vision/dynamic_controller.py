"""Real-time multi-objective dynamic controller (ML policy layer).

Maps live features + adaptive state → gcode actions every tick.
Objectives: flatness (zero ironing) × adhesion Z × thermal track × speed.

Actions are rate-limited and envelope-clamped. When not armed, actions are
suggestions only (still fully dynamic — state updates every tick).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import time

from forgeos.vision.adaptive_state import AdaptiveState
from forgeos.vision.scorers.first_layer import FirstLayerResult
from forgeos.vision.telemetry_features import TelemetryFeatures


@dataclass
class DynamicAction:
    kind: str  # gcode | pause | log
    script: str
    reason: str
    priority: int = 0  # higher first

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "script": self.script,
            "reason": self.reason,
            "priority": self.priority,
        }


@dataclass
class ControlTick:
    ts: float
    features: Dict[str, Any]
    quality: Dict[str, float]
    actions: List[DynamicAction]
    state_snapshot: Dict[str, Any]
    mode: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "features": self.features,
            "quality": self.quality,
            "actions": [a.as_dict() for a in self.actions],
            "state": self.state_snapshot,
            "mode": self.mode,
        }


class DynamicController:
    """Fully dynamic real-time policy."""

    def __init__(self, state: Optional[AdaptiveState] = None) -> None:
        self.state = state or AdaptiveState()

    def fuse_vision(
        self,
        tele: TelemetryFeatures,
        vision: Optional[FirstLayerResult] = None,
    ) -> Dict[str, float]:
        """Fuse camera scorer with telemetry into live quality vector."""
        flat = tele.flat_volume_score
        rib = max(0.0, min(1.0, 1.0 - flat))
        # Telemetry proxy for coverage: heat-ready printing near bed → assume material
        cov = 0.7 if (tele.printing and tele.heat_ready) else 0.3
        cov = 0.5 * cov + 0.5 * tele.flat_volume_score
        # prefer vision when present
        if vision is not None:
            flat = 0.35 * flat + 0.65 * float(vision.score)
            rib = float(vision.metrics.get("rib_score", rib))
            cov = float(vision.metrics.get("coverage", cov))
            self.state.observe_quality(
                flat_score=float(vision.score),
                rib_score=rib,
                coverage=cov,
                thermal_uniform=tele.thermal_track_score,
            )
        else:
            self.state.observe_quality(
                flat_score=flat,
                rib_score=rib,
                coverage=cov,
                thermal_uniform=tele.thermal_track_score,
            )
        # sync Z belief from printer
        self.state.z_adjust_mm = tele.z_adjust_mm
        self.state.flow = tele.extrude_factor if tele.extrude_factor > 0 else self.state.flow
        return {
            "flat": self.state.flat_score_ema,
            "rib": self.state.rib_score_ema,
            "coverage": self.state.coverage_ema,
            "thermal": self.state.thermal_uniform_ema,
            "ridge_proxy_mm": tele.ridge_proxy_mm,
        }

    def plan(
        self,
        tele: TelemetryFeatures,
        vision: Optional[FirstLayerResult] = None,
        now: Optional[float] = None,
    ) -> ControlTick:
        now = time.time() if now is None else now
        q = self.fuse_vision(tele, vision)
        actions: List[DynamicAction] = []

        # Always keep flat surface motion profile warm while printing
        if tele.printing:
            if tele.first_layer_window or tele.tool_z_mm <= 0.45:
                actions.append(
                    DynamicAction(
                        "gcode",
                        "FORGE_FLAT_SURFACE_MODE ROLE=first",
                        "RT first-layer flat dynamics",
                        priority=10,
                    )
                )
            elif tele.progress > 0.02:
                role = "top" if tele.progress > 0.85 else "solid"
                actions.append(
                    DynamicAction(
                        "gcode",
                        "FORGE_FLAT_SURFACE_MODE ROLE=%s" % role,
                        "RT solid/top flat dynamics",
                        priority=8,
                    )
                )
            else:
                actions.append(
                    DynamicAction(
                        "log",
                        "",
                        "RT warm-up/mesh — adaptive state updating",
                        priority=1,
                    )
                )

        # First-layer Z + flow policy (machine-flat, zero ironing)
        if tele.printing and tele.first_layer_window:
            if vision is not None and vision.suggestion == "FORGE_BABY_UP":
                actions.append(
                    DynamicAction("gcode", "FORGE_BABY_UP", "vision empty/scrape", 100)
                )
            elif vision is not None and vision.suggestion == "FORGE_BABY_DOWN":
                actions.append(
                    DynamicAction("gcode", "FORGE_BABY_DOWN", "vision high Z", 100)
                )
            elif vision is not None and vision.suggestion == "INCREASE_FLOW_OR_BABY_DOWN":
                # Prefer tiny flow nudge over pile-up spacing (zero ironing doctrine)
                new_f = self.state.clamp_flow(self.state.flow + self.state.max_flow_step)
                if abs(new_f - self.state.flow) > 1e-6:
                    pct = int(round(new_f * 100))
                    actions.append(
                        DynamicAction(
                            "gcode",
                            "M221 S%d" % pct,
                            "ribbed → flow nudge (not ironing/pile-up)",
                            90,
                        )
                    )
                    self.state.flow = new_f
                else:
                    actions.append(
                        DynamicAction(
                            "gcode", "FORGE_BABY_DOWN", "ribbed → Z closer", 85
                        )
                    )
            elif q["rib"] > 0.55 and q["coverage"] > 0.4:
                # telemetry-only rib belief
                new_f = self.state.clamp_flow(self.state.flow + 0.01)
                actions.append(
                    DynamicAction(
                        "gcode",
                        "M221 S%d" % int(round(new_f * 100)),
                        "tele rib EMA high → slight flow",
                        50,
                    )
                )
                self.state.flow = new_f
            elif q["coverage"] < 0.2 and tele.tool_z_mm < 0.5:
                actions.append(
                    DynamicAction("gcode", "FORGE_BABY_UP", "tele low coverage", 80)
                )

        # Thermal track: if nozzle lagging target during print, hold speed
        if tele.printing and tele.nozzle_target_c > 0 and tele.nozzle_c < tele.nozzle_target_c - 8:
            actions.append(
                DynamicAction(
                    "gcode",
                    "M220 S80",
                    "nozzle lag → temporary slowdown",
                    40,
                )
            )
        elif tele.printing and tele.thermal_track_score > 0.85 and tele.speed_factor < 0.99:
            actions.append(
                DynamicAction(
                    "gcode",
                    "M220 S100",
                    "thermal recovered → restore speed",
                    30,
                )
            )

        # Sort by priority desc
        actions.sort(key=lambda a: a.priority, reverse=True)

        # Rate-limit apply set
        if not self.state.can_apply(now):
            actions = [
                DynamicAction("log", "", "rate-limit hold: " + a.reason, a.priority)
                if a.kind == "gcode"
                else a
                for a in actions
            ]

        mode = "armed" if self.state.armed else "suggest"
        if self.state.mode == "hold":
            mode = "hold"
            actions = [
                DynamicAction("log", "", "HOLD: " + a.reason, a.priority) for a in actions
            ]

        return ControlTick(
            ts=now,
            features=tele.as_dict(),
            quality=q,
            actions=actions,
            state_snapshot=self.state.as_dict(),
            mode=mode,
        )

    def scripts_to_apply(self, tick: ControlTick) -> List[str]:
        """If armed, return gcode scripts to execute this tick (max 1 high-pri)."""
        if tick.mode != "armed":
            return []
        if not self.state.can_apply(tick.ts):
            return []
        for a in tick.actions:
            if a.kind == "gcode" and a.script:
                self.state.mark_applied(a.script, tick.ts)
                return [a.script]
        return []
