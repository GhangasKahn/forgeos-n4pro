"""Vision event schema — Jetson → journal / MQTT / operator UI."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import time


@dataclass
class VisionEvent:
    type: str  # first_layer_score | spaghetti | thermal_map | whisker | calib_step
    severity: str  # info | warn | critical
    scores: Dict[str, float] = field(default_factory=dict)
    labels: List[str] = field(default_factory=list)
    suggestion: Optional[str] = None  # e.g. FORGE_BABY_DOWN
    cameras: List[str] = field(default_factory=list)
    ts: float = field(default_factory=time.time)
    meta: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)
