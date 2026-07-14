from forgeos.optim.multi_objective import (
    ObjectiveWeights,
    ParetoArchive,
    RecipeCandidate,
    score_observation,
)
from forgeos.optim.quality_score import PillarObservation


def test_feasible_score():
    obs = PillarObservation(
        duration_s=800,
        baseline_s=1000,
        abs_error_100mm=0.08,
        precision_span_mm=0.04,
        first_layer_ok=True,
        delam=False,
        elephant_foot_mm=0.05,
    )
    r = score_observation(obs)
    assert r.feasible
    assert 0.0 < r.j <= 1.0


def test_fast_but_wrong_is_fail():
    obs = PillarObservation(
        duration_s=400,
        baseline_s=1000,
        abs_error_100mm=0.35,
        precision_span_mm=0.02,
        first_layer_ok=True,
        delam=False,
    )
    r = score_observation(obs)
    assert not r.feasible
    assert r.j == 0.0
    assert "accuracy_fail" in r.reasons


def test_quality_fail_delam():
    obs = PillarObservation(
        duration_s=900,
        baseline_s=1000,
        abs_error_100mm=0.05,
        precision_span_mm=0.03,
        first_layer_ok=True,
        delam=True,
    )
    r = score_observation(obs)
    assert not r.feasible


def test_pareto_prefers_non_dominated():
    arch = ParetoArchive()
    a = score_observation(
        PillarObservation(900, 1000, 0.05, 0.03, True, False)
    )
    b = score_observation(
        PillarObservation(700, 1000, 0.08, 0.04, True, False)
    )
    assert arch.add(RecipeCandidate("balanced", "htpla", {}, a))
    assert arch.add(RecipeCandidate("fast", "htpla", {}, b))
    assert arch.best_for("max_speed_feasible").name == "fast"
    assert arch.best_for("max_accuracy").name == "balanced"
