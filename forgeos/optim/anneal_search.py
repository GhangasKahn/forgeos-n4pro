"""Simulated annealing over a continuous parameter dict (between prints only)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class AnnealSearch:
    bounds: Dict[str, Tuple[float, float]]
    objective: Callable[[Dict[str, float]], float]
    t0: float = 1.0
    t_min: float = 1e-3
    cooling: float = 0.92
    steps_per_temp: int = 8
    rng: random.Random = field(default_factory=random.Random)

    def _clip(self, params: Dict[str, float]) -> Dict[str, float]:
        out = {}
        for k, v in params.items():
            lo, hi = self.bounds[k]
            out[k] = max(lo, min(hi, float(v)))
        return out

    def _neighbor(self, params: Dict[str, float], t: float) -> Dict[str, float]:
        out = dict(params)
        key = self.rng.choice(list(self.bounds.keys()))
        lo, hi = self.bounds[key]
        scale = (hi - lo) * max(t, 0.05)
        out[key] = out[key] + self.rng.uniform(-scale, scale)
        return self._clip(out)

    def run(self, start: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        if start is None:
            current = {k: 0.5 * (lo + hi) for k, (lo, hi) in self.bounds.items()}
        else:
            current = self._clip(start)
        current_y = float(self.objective(current))
        best = dict(current)
        best_y = current_y
        t = self.t0
        while t > self.t_min:
            for _ in range(self.steps_per_temp):
                cand = self._neighbor(current, t)
                y = float(self.objective(cand))
                delta = y - current_y
                if delta >= 0 or self.rng.random() < math.exp(delta / max(t, 1e-9)):
                    current, current_y = cand, y
                    if y > best_y:
                        best, best_y = dict(cand), y
            t *= self.cooling
        return best
