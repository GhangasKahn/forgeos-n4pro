"""Tiny pure-Python 1D Bayesian-ish optimizer (no numpy required).

Uses a simple GP-lite with RBF-ish heuristic via inverse-distance weighting
and upper confidence bound exploration. Good enough for PA / temp linesearch
on a 1GB SBC.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Observation1D:
    x: float
    y: float


@dataclass
class Bayes1D:
    lo: float
    hi: float
    kappa: float = 1.5
    observations: List[Observation1D] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)

    def tell(self, x: float, y: float) -> None:
        x = min(self.hi, max(self.lo, float(x)))
        self.observations.append(Observation1D(x=x, y=float(y)))

    def _predict(self, x: float) -> Tuple[float, float]:
        if not self.observations:
            mid = 0.5 * (self.lo + self.hi)
            return mid, (self.hi - self.lo)
        # inverse distance weighted mean + spread
        num = 0.0
        den = 0.0
        for obs in self.observations:
            d = abs(x - obs.x) + 1e-6
            w = 1.0 / (d * d)
            num += w * obs.y
            den += w
        mean = num / den
        # uncertainty grows with distance to nearest point
        nearest = min(abs(x - o.x) for o in self.observations)
        span = max(self.hi - self.lo, 1e-6)
        std = (nearest / span) * (1.0 + abs(mean) * 0.1) + 0.05
        return mean, std

    def ask(self, n_candidates: int = 32) -> float:
        best_x = 0.5 * (self.lo + self.hi)
        best_acq = -1e18
        for i in range(n_candidates):
            if i == 0 and self.observations:
                # also re-check around best so far
                x = max(self.observations, key=lambda o: o.y).x
            else:
                x = self.rng.uniform(self.lo, self.hi)
            mean, std = self._predict(x)
            acq = mean + self.kappa * std
            if acq > best_acq:
                best_acq = acq
                best_x = x
        return best_x

    def best(self) -> Optional[Observation1D]:
        if not self.observations:
            return None
        return max(self.observations, key=lambda o: o.y)
