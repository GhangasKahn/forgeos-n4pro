from forgeos.vision.scorers.first_layer import score_first_layer_features, score_from_gray_rows
from forgeos.vision.scorers.thermal_map import analyze_thermal_grid
from forgeos.vision.calib.fsm import VisionCalibFSM, CalibState


def test_empty_bed_suggests_baby_up():
    r = score_first_layer_features(mean_luma=200, row_variance=5, edge_energy=5, coverage=0.05)
    assert "empty_or_scrape" in r.labels
    assert r.suggestion == "FORGE_BABY_UP"


def test_ribbed_detected():
    rows = [100 + (i % 2) * 40 for i in range(30)]
    r = score_from_gray_rows(rows, coverage=0.8)
    assert r.metrics["rib_score"] > 0.3


def test_thermal_uniform():
    grid = [[65.0 + 0.2 * (r % 3) for _ in range(8)] for r in range(8)]
    t = analyze_thermal_grid(grid, target_c=65, max_p2p_c=4)
    assert t.uniform is True


def test_thermal_cold_corner():
    grid = [[65.0] * 8 for _ in range(8)]
    for r in range(4):
        for c in range(4):
            grid[r][c] = 58.0
    t = analyze_thermal_grid(grid, target_c=65, max_p2p_c=3)
    assert t.uniform is False
    assert t.cold_quadrant == "nw"


def test_fsm_suggest_only_when_disarmed():
    fsm = VisionCalibFSM(armed=False)
    from forgeos.vision.scorers.first_layer import FirstLayerResult

    r = FirstLayerResult(0.2, ("possible_high_z",), "FORGE_BABY_DOWN", {})
    ev = fsm.on_first_layer_result(r)
    assert ev.meta["would_apply"] is None
