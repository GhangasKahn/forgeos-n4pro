from forgeos.sensors.moisture_soft_sensor import (
    ExtrusionThermalSample,
    MoistureSoftSensor,
    estimate_flow_mm3_s,
    recommend_response,
)


def test_flow_estimate():
    # 1.75 mm filament at 5 mm/s feed ≈ 12 mm^3/s
    q = estimate_flow_mm3_s(1.75, 5.0)
    assert 11.0 < q < 13.0


def test_dry_baseline_then_wet_risk_rises():
    s = MoistureSoftSensor(alpha=0.4)
    # Learn dry: small droop, modest power
    for _ in range(15):
        s.observe(
            ExtrusionThermalSample(
                temperature_c=214.5,
                target_c=215.0,
                heater_power=0.40,
                volumetric_flow_mm3_s=8.0,
                is_extruding=True,
                known_dry=True,
            )
        )
    dry = s.estimate(214.5, 215.0, 0.40, 8.0)
    assert dry.level in {"dry", "mild"}
    assert dry.risk < 0.35

    # Wet-like: bigger droop + higher heater power
    s.reset_live()
    for _ in range(15):
        s.observe(
            ExtrusionThermalSample(
                temperature_c=210.0,
                target_c=215.0,
                heater_power=0.78,
                volumetric_flow_mm3_s=8.0,
                is_extruding=True,
                known_dry=False,
            )
        )
    wet = s.estimate(210.0, 215.0, 0.78, 8.0)
    assert wet.risk > dry.risk
    assert wet.level in {"moderate", "severe", "mild"}


def test_recommend_severe_pauses():
    from forgeos.sensors.moisture_soft_sensor import MoistureEstimate

    est = MoistureEstimate(
        risk=0.85,
        level="severe",
        temp_droop_c=5.0,
        power=0.9,
        flow_mm3_s=8.0,
        droop_excess_c=3.0,
        power_excess=0.3,
    )
    resp = recommend_response(est, base_nozzle_c=215.0)
    assert resp.pause_recommended is True
    assert any("PAUSE" in g for g in resp.gcode)
    assert resp.speed_derate < 1.0
    assert resp.nozzle_temp_delta_c > 0


def test_recommend_dry_noop():
    from forgeos.sensors.moisture_soft_sensor import MoistureEstimate

    est = MoistureEstimate(
        risk=0.05,
        level="dry",
        temp_droop_c=1.0,
        power=0.4,
        flow_mm3_s=8.0,
        droop_excess_c=0.0,
        power_excess=0.0,
    )
    resp = recommend_response(est, base_nozzle_c=215.0)
    assert resp.gcode == []
    assert resp.flow_multiplier == 1.0
