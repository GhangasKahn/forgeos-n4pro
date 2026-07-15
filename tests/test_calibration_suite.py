import json
from pathlib import Path

import pytest

from forgeos.calibration.audit import audit_klipper_base
from forgeos.calibration.profile import ProfileError, load_machine_profile
from forgeos.calibration.suite import CalibrationRun, build_calibration_suite


ROOT = Path(__file__).resolve().parents[1]


def test_machine_profile_is_valid_and_conservative():
    profile = load_machine_profile()
    assert profile.model == "Elegoo Neptune 4 Pro"
    assert profile.motion["max_velocity_mm_s"] == 300
    assert profile.motion["max_accel_mm_s2"] == 5000
    assert profile.acceptance["dimensional_error_100mm_max_mm"] == 0.20


def test_invalid_profile_fails_closed(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("schema_version: 1\nmachine: {}\n", encoding="utf-8")
    with pytest.raises(ProfileError):
        load_machine_profile(path)


def test_suite_ids_and_dependencies_are_valid():
    tests = build_calibration_suite(load_machine_profile())
    ids = [test.id for test in tests]
    assert len(tests) >= 20
    assert len(ids) == len(set(ids))
    positions = {test_id: index for index, test_id in enumerate(ids)}
    for test in tests:
        for dependency in test.depends_on:
            assert dependency in positions
            assert positions[dependency] < positions[test.id]
        assert test.procedure
        assert test.evidence
        assert test.acceptance


def test_run_enforces_dependencies_and_skip_policy(tmp_path):
    profile = load_machine_profile()
    tests = build_calibration_suite(profile)
    by_id = {test.id: test for test in tests}
    run = CalibrationRun.create(profile)

    with pytest.raises(ValueError, match="incomplete dependencies"):
        run.record(by_id["backup-firmware"], "pass", tests=tests)
    with pytest.raises(ValueError, match="not conditional"):
        run.record(by_id["safety-inspection"], "skipped", tests=tests)

    run.record(by_id["safety-inspection"], "pass", {"photos": "inspection.zip"}, tests)
    run.record(by_id["backup-firmware"], "pass", {"archive": "printer-config.tgz"}, tests)
    run.record(by_id["mechanical-frame"], "pass", tests=tests)
    run.record(by_id["gantry-level"], "pass", tests=tests)
    run.record(by_id["bed-screws"], "pass", tests=tests)
    run.record(by_id["extruder-rotation"], "pass", tests=tests)
    run.record(by_id["pid-extruder"], "pass", tests=tests)
    run.record(by_id["pid-dual-bed"], "pass", tests=tests)
    run.record(by_id["probe-repeatability"], "pass", tests=tests)
    run.record(by_id["probe-z-offset"], "pass", tests=tests)
    run.record(by_id["axis-twist"], "skipped", {"reason": "no measured twist"}, tests)
    run.record(by_id["golden-mesh"], "pass", tests=tests)
    run.record(by_id["input-shaper"], "skipped", {"reason": "accelerometer not installed"}, tests)
    assert "filament-dryness" in {item.id for item in run.next_tests(tests)}

    path = tmp_path / "run.json"
    run.save(path)
    loaded = CalibrationRun.load(path)
    assert loaded.results["safety-inspection"]["result"] == "pass"
    assert json.loads(path.read_text())["machine_model"] == profile.model


def test_klipper_base_matches_machine_profile():
    findings = audit_klipper_base(
        load_machine_profile(),
        ROOT / "klipper" / "base" / "printer_n4pro.cfg",
    )
    assert not [finding for finding in findings if finding.level == "error"]
    assert any("z_offset" in finding.message for finding in findings)
