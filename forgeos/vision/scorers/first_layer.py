"""First-layer scorer (v0 classical placeholders → swap for TensorRT later).

v0 is intentionally simple so Jetson integration works before heavy models:
- brightness / texture heuristics as stand-ins
- returns structured scores the calib FSM can consume
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import math


@dataclass
class FirstLayerResult:
    score: float  # 0..1 good
    labels: Tuple[str, ...]
    suggestion: Optional[str]
    metrics: Dict[str, float]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "labels": list(self.labels),
            "suggestion": self.suggestion,
            "metrics": dict(self.metrics),
        }


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def score_first_layer_features(
    mean_luma: float,
    row_variance: float,
    edge_energy: float,
    coverage: float,
) -> FirstLayerResult:
    """Heuristic model until CNN/TensorRT is trained on shop images.

    Parameters are normalized loosely:
      mean_luma: 0..255
      row_variance: variance of row means (high → ribs)
      edge_energy: high → texture/ribs or scrape
      coverage: 0..1 fraction that looks like filament vs bare bed
    """
    labels = []
    suggestion = None

    if coverage < 0.15:
        labels.append("empty_or_scrape")
        return FirstLayerResult(
            score=0.05,
            labels=tuple(labels),
            suggestion="FORGE_BABY_UP",
            metrics={
                "mean_luma": mean_luma,
                "row_variance": row_variance,
                "edge_energy": edge_energy,
                "coverage": coverage,
            },
        )

    # ribs: high row variance with decent coverage
    rib_score = _clamp01((row_variance - 20.0) / 80.0)
    if rib_score > 0.45:
        labels.append("ribbed_rows")
        suggestion = "INCREASE_FLOW_OR_BABY_DOWN"

    # high Z: low coverage edges, round beads → moderate coverage + high edge
    high_z = coverage < 0.55 and edge_energy > 40
    if high_z:
        labels.append("possible_high_z")
        suggestion = "FORGE_BABY_DOWN"

    # good flat sheet: high coverage, low row variance
    flat = _clamp01(1.0 - rib_score) * _clamp01(coverage)
    score = flat
    if not labels:
        labels = ("good_sheet",)
        suggestion = None
        score = max(score, 0.75)

    return FirstLayerResult(
        score=_clamp01(score),
        labels=tuple(labels),
        suggestion=suggestion,
        metrics={
            "mean_luma": mean_luma,
            "row_variance": row_variance,
            "edge_energy": edge_energy,
            "coverage": coverage,
            "rib_score": rib_score,
        },
    )


def score_from_gray_rows(rows_mean: list, coverage: float = 0.7) -> FirstLayerResult:
    """Convenience when you already reduced a frame to per-row means."""
    if not rows_mean:
        return score_first_layer_features(0, 0, 0, 0)
    mean = sum(rows_mean) / len(rows_mean)
    var = sum((x - mean) ** 2 for x in rows_mean) / max(1, len(rows_mean))
    # crude edge energy: mean abs diff
    edge = 0.0
    for i in range(1, len(rows_mean)):
        edge += abs(rows_mean[i] - rows_mean[i - 1])
    edge /= max(1, len(rows_mean) - 1)
    return score_first_layer_features(mean, var, edge * 3.0, coverage)
