"""Online adaptive state — fully dynamic, real-time EMA memory.

All knobs the ML / control loop is allowed to move live. Updated every tick;
persisted optionally for warm-start across restarts.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional
import json
import time
from pathlib import Path


def ema(prev: float, x: float, alpha: float) -> float:
    a = max(0.0, min(1.0, alpha))
    return (1.0 - a) * prev + a * x


@dataclass
class AdaptiveState:
    """Live process + quality estimates (updated in real time)."""

    # Process knobs (commanded / believed)
    z_adjust_mm: float = -0.480
    flow: float = 1.00
    spacing_ratio: float = 1.00
    pressure_advance: float = 0.032
    solid_speed_factor: float = 1.0  # multiplies solid pack speed via M220-like intent
    first_layer_speed_factor: float = 1.0

    # Quality EMAs (0..1 good)
    flat_score_ema: float = 0.5
    rib_score_ema: float = 0.0
    coverage_ema: float = 0.5
    thermal_uniform_ema: float = 0.5
    dimensional_belief_mm: float = 100.0  # believed finished X on 100mm bar

    # Control bookkeeping
    ticks: int = 0
    last_apply_ts: float = 0.0
    last_suggestion: str = ""
    armed: bool = False
    mode: str = "suggest"  # suggest | armed | hold
    alpha: float = 0.25  # EMA rate (higher = more real-time reactive)

    # Envelopes (hard limits — never auto-exceed)
    z_min_mm: float = -0.80
    z_max_mm: float = 0.20
    flow_min: float = 0.92
    flow_max: float = 1.08
    pa_min: float = 0.010
    pa_max: float = 0.080
    max_z_step_mm: float = 0.02
    max_flow_step: float = 0.02
    min_apply_interval_s: float = 1.5

    meta: Dict[str, Any] = field(default_factory=dict)

    def observe_quality(
        self,
        *,
        flat_score: Optional[float] = None,
        rib_score: Optional[float] = None,
        coverage: Optional[float] = None,
        thermal_uniform: Optional[float] = None,
    ) -> None:
        a = self.alpha
        if flat_score is not None:
            self.flat_score_ema = ema(self.flat_score_ema, flat_score, a)
        if rib_score is not None:
            self.rib_score_ema = ema(self.rib_score_ema, rib_score, a)
        if coverage is not None:
            self.coverage_ema = ema(self.coverage_ema, coverage, a)
        if thermal_uniform is not None:
            self.thermal_uniform_ema = ema(self.thermal_uniform_ema, thermal_uniform, a)
        self.ticks += 1

    def clamp_z(self, z: float) -> float:
        return max(self.z_min_mm, min(self.z_max_mm, z))

    def clamp_flow(self, f: float) -> float:
        return max(self.flow_min, min(self.flow_max, f))

    def clamp_pa(self, pa: float) -> float:
        return max(self.pa_min, min(self.pa_max, pa))

    def can_apply(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return (now - self.last_apply_ts) >= self.min_apply_interval_s

    def mark_applied(self, suggestion: str, now: Optional[float] = None) -> None:
        self.last_apply_ts = time.time() if now is None else now
        self.last_suggestion = suggestion

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "AdaptiveState":
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
        return cls(**{k: v for k, v in raw.items() if k in known})
