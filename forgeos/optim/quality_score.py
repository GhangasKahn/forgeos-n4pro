"""Quality / pillar scoring primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def accuracy_score(abs_error_100mm: float, fail_mm: float = 0.20, perfect_mm: float = 0.02) -> float:
    """1.0 at <=perfect, 0.0 at >=fail, linear between."""
    e = abs(float(abs_error_100mm))
    if e >= fail_mm:
        return 0.0
    if e <= perfect_mm:
        return 1.0
    return clamp01(1.0 - (e - perfect_mm) / (fail_mm - perfect_mm))


def precision_score(span_mm: float, fail_mm: float = 0.10, perfect_mm: float = 0.02) -> float:
    s = abs(float(span_mm))
    if s >= fail_mm:
        return 0.0
    if s <= perfect_mm:
        return 1.0
    return clamp01(1.0 - (s - perfect_mm) / (fail_mm - perfect_mm))


def time_score(duration_s: float, baseline_s: float) -> float:
    """Higher is better. 1.0 at 2x faster than baseline, 0.5 at baseline, approaches 0 if much slower."""
    if baseline_s <= 0 or duration_s <= 0:
        return 0.0
    ratio = float(baseline_s) / float(duration_s)  # >1 means faster
    # map ratio 0.5..2.0 -> 0..1
    return clamp01((ratio - 0.5) / 1.5)


def quality_score(
    first_layer_ok: bool,
    delam: bool,
    elephant_foot_mm: float = 0.0,
    surface_ok: bool = True,
) -> float:
    if not first_layer_ok or delam:
        return 0.0
    score = 1.0
    if not surface_ok:
        score *= 0.7
    # soft penalty for elephant foot above 0.05 mm, hard-ish at 0.15
    ef = max(0.0, float(elephant_foot_mm))
    if ef > 0.15:
        return 0.0
    if ef > 0.05:
        score *= clamp01(1.0 - (ef - 0.05) / 0.10)
    return clamp01(score)


@dataclass
class PillarObservation:
    duration_s: float
    baseline_s: float
    abs_error_100mm: float
    precision_span_mm: float
    first_layer_ok: bool
    delam: bool
    elephant_foot_mm: float = 0.0
    surface_ok: bool = True
