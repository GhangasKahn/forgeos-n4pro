"""Constrained multi-objective score: SPEED x PRECISION x ACCURACY x QUALITY."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from forgeos.optim.quality_score import (
    PillarObservation,
    accuracy_score,
    precision_score,
    quality_score,
    time_score,
)
from forgeos.safety import SafetyEnvelopes


@dataclass
class ObjectiveWeights:
    # CNC-first: accuracy + precision outweigh speed
    accuracy: float = 0.35
    precision: float = 0.30
    quality: float = 0.20
    time: float = 0.15

    def normalized(self) -> "ObjectiveWeights":
        s = self.accuracy + self.precision + self.quality + self.time
        if s <= 0:
            return ObjectiveWeights()
        return ObjectiveWeights(
            accuracy=self.accuracy / s,
            precision=self.precision / s,
            quality=self.quality / s,
            time=self.time / s,
        )


@dataclass
class ScoreResult:
    j: float
    feasible: bool
    time_s: float
    accuracy_s: float
    precision_s: float
    quality_s: float
    reasons: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def score_observation(
    obs: PillarObservation,
    weights: Optional[ObjectiveWeights] = None,
    envelopes: Optional[SafetyEnvelopes] = None,
) -> ScoreResult:
    """Hard constraints first; soft weighted J only if feasible."""
    env = envelopes or SafetyEnvelopes()
    w = (weights or ObjectiveWeights()).normalized()
    reasons: List[str] = []

    a = accuracy_score(obs.abs_error_100mm, fail_mm=env.dim_error_100mm_fail_mm)
    p = precision_score(obs.precision_span_mm, fail_mm=env.precision_span_3x_fail_mm)
    q = quality_score(
        first_layer_ok=obs.first_layer_ok,
        delam=obs.delam,
        elephant_foot_mm=obs.elephant_foot_mm,
        surface_ok=obs.surface_ok,
    )
    t = time_score(obs.duration_s, obs.baseline_s)

    feasible = True
    if abs(obs.abs_error_100mm) > env.dim_error_100mm_fail_mm:
        feasible = False
        reasons.append("accuracy_fail")
    if obs.precision_span_mm > env.precision_span_3x_fail_mm:
        feasible = False
        reasons.append("precision_fail")
    if q <= 0.0:
        feasible = False
        reasons.append("quality_fail")

    if not feasible:
        return ScoreResult(
            j=0.0,
            feasible=False,
            time_s=t,
            accuracy_s=a,
            precision_s=p,
            quality_s=q,
            reasons=reasons,
        )

    j = w.accuracy * a + w.precision * p + w.quality * q + w.time * t
    return ScoreResult(
        j=j,
        feasible=True,
        time_s=t,
        accuracy_s=a,
        precision_s=p,
        quality_s=q,
        reasons=reasons,
    )


@dataclass
class RecipeCandidate:
    name: str
    sku: str
    params: Dict[str, float]
    score: ScoreResult


class ParetoArchive:
    """Keep non-dominated feasible recipes (maximize J and time_s, minimize |error| via accuracy_s)."""

    def __init__(self) -> None:
        self.candidates: List[RecipeCandidate] = []

    def _dominates(self, a: ScoreResult, b: ScoreResult) -> bool:
        """a dominates b if a is >= on all maximized metrics and > on at least one."""
        if not a.feasible:
            return False
        if not b.feasible:
            return True
        ge_all = (
            a.j >= b.j
            and a.time_s >= b.time_s
            and a.accuracy_s >= b.accuracy_s
            and a.precision_s >= b.precision_s
            and a.quality_s >= b.quality_s
        )
        gt_one = (
            a.j > b.j
            or a.time_s > b.time_s
            or a.accuracy_s > b.accuracy_s
            or a.precision_s > b.precision_s
            or a.quality_s > b.quality_s
        )
        return ge_all and gt_one

    def add(self, candidate: RecipeCandidate) -> bool:
        if not candidate.score.feasible:
            return False
        # remove dominated
        kept: List[RecipeCandidate] = []
        for c in self.candidates:
            if self._dominates(candidate.score, c.score):
                continue
            if self._dominates(c.score, candidate.score):
                return False
            kept.append(c)
        kept.append(candidate)
        self.candidates = kept
        return True

    def best_for(self, mode: str) -> Optional[RecipeCandidate]:
        if not self.candidates:
            return None
        if mode == "max_speed_feasible":
            return max(self.candidates, key=lambda c: (c.score.time_s, c.score.j))
        if mode == "max_accuracy":
            return max(self.candidates, key=lambda c: (c.score.accuracy_s, c.score.precision_s, c.score.j))
        # balanced
        return max(self.candidates, key=lambda c: c.score.j)
