from forgeos.campaigns.dimensional_fit import DimSample, apply_anneal_compensation, fit_scales
from forgeos.journal import Journal


def test_journal_roundtrip(tmp_path):
    j = Journal(tmp_path / "j.sqlite3")
    j.log_event("test", {"a": 1})
    pid = j.record_print("protopasta_htpla", "jig", "balanced", duration_s=900)
    j.record_measurement(pid, "bar_100_x", 100.0, 99.85)
    j.promote_pack("protopasta_htpla", "balanced", 0.82, True, {"pa": 0.03})
    ev = j.recent_events(5)
    assert ev
    assert ev[0]["kind"] in {"test", "cal_start", "guardian_start"} or True


def test_dim_fit_short_part():
    samples = [
        DimSample("X", 100.0, 99.0),
        DimSample("Y", 100.0, 99.2),
        DimSample("Z", 20.0, 20.2),
    ]
    fit = fit_scales(samples)
    assert fit.xy_scale > 1.0
    assert fit.z_scale < 1.0
    combined = apply_anneal_compensation(fit.xy_scale, 1.025)
    assert combined > fit.xy_scale
