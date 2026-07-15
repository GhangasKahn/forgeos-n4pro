from forgeos.gates.verification import (
    ZeroTrustSuite,
    gate_g0_static,
    gate_g1_hardware,
    gate_g2_process_sensors,
    gate_g3_accuracy,
    gate_g4_precision,
    gate_g5_speed,
    gate_g6_anneal,
    gate_g7_reliability,
    GateStatus,
)


def test_production_ready_requires_full_chain():
    suite = ZeroTrustSuite()
    suite.register(lambda: gate_g0_static(2, 0))
    suite.register(lambda: gate_g1_hardware(True, 500, False, True))
    suite.register(lambda: gate_g2_process_sensors(0.15, True, True))
    suite.register(lambda: gate_g3_accuracy(0.08))
    suite.register(lambda: gate_g4_precision(0.04))
    suite.register(lambda: gate_g5_speed(700, 1000, 0.25))
    report = suite.run()
    assert report.production_ready() is True


def test_speed_without_accuracy_not_ready():
    suite = ZeroTrustSuite()
    suite.register(lambda: gate_g0_static(2, 0))
    suite.register(lambda: gate_g1_hardware(True, 500, False, True))
    suite.register(lambda: gate_g2_process_sensors(0.15, True, True))
    suite.register(lambda: gate_g3_accuracy(0.40))  # fail
    suite.register(lambda: gate_g4_precision(0.04))
    suite.register(lambda: gate_g5_speed(500, 1000, 0.25))
    report = suite.run(stop_on_fail=True)
    assert report.production_ready() is False
    assert any(r.gate_id == "G3" and r.status == GateStatus.FAIL for r in report.results)


def test_g7_and_g6():
    assert gate_g6_anneal(0.08).status == GateStatus.PASS
    assert gate_g7_reliability(0, 10, 2.5).status == GateStatus.PASS
    assert gate_g7_reliability(1, 10, 2.5).status == GateStatus.FAIL


def test_cnc_g3_g4_defaults():
    assert gate_g3_accuracy(0.10).status == GateStatus.PASS
    assert gate_g3_accuracy(0.11).status == GateStatus.FAIL
    assert gate_g4_precision(0.05).status == GateStatus.PASS
    assert gate_g4_precision(0.06).status == GateStatus.FAIL
    assert gate_g2_process_sensors(0.25, True, True).status == GateStatus.PASS
    assert gate_g2_process_sensors(0.26, True, True).status == GateStatus.FAIL
