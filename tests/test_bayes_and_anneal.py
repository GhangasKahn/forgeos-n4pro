from forgeos.optim.anneal_search import AnnealSearch
from forgeos.optim.bayes_1d import Bayes1D


def test_bayes_1d_finds_peak():
    bo = Bayes1D(lo=0.0, hi=1.0, kappa=1.2)
    # synthetic peak near 0.7
    for _ in range(12):
        x = bo.ask()
        y = 1.0 - (x - 0.7) ** 2
        bo.tell(x, y)
    best = bo.best()
    assert best is not None
    assert abs(best.x - 0.7) < 0.25


def test_anneal_search_maximizes():
    def obj(p):
        # peak at x=2, y=3
        return -((p["x"] - 2) ** 2 + (p["y"] - 3) ** 2)

    sa = AnnealSearch(
        bounds={"x": (0.0, 5.0), "y": (0.0, 5.0)},
        objective=obj,
        t0=1.0,
        t_min=1e-3,
        cooling=0.85,
        steps_per_temp=10,
    )
    best = sa.run({"x": 0.5, "y": 0.5})
    assert abs(best["x"] - 2.0) < 0.75
    assert abs(best["y"] - 3.0) < 0.75
