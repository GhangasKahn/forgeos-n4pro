"""Core evidence + gate ledger + gcode dispatch (mechanics-only)."""

from pathlib import Path

from forgeos.calibration.gcodes import gcode_for_test_id
from forgeos.calibration.ledger import GateLedger
from forgeos.calibration.runner import CalibrationRunner
from forgeos.core.evidence import append_jsonl, write_evidence
from forgeos.moonraker_client import MoonrakerClient


def test_write_evidence(tmp_path: Path) -> None:
    p = write_evidence("unit_test", {"ok": True}, directory=tmp_path, stamp=False)
    assert p.exists()
    assert "ok" in p.read_text()


def test_append_jsonl(tmp_path: Path) -> None:
    p = append_jsonl("log", {"event": "a"}, directory=tmp_path)
    append_jsonl("log", {"event": "b"}, directory=tmp_path)
    lines = p.read_text().strip().splitlines()
    assert len(lines) == 2


def test_ledger_g3_pass() -> None:
    led = GateLedger(precision_tier="cnc")
    r = led.record_g3(99.97)
    assert r.status == "pass"
    assert r.metrics["abs_error_mm"] <= 0.10


def test_ledger_g3_fail() -> None:
    led = GateLedger()
    r = led.record_g3(99.0)  # 1 mm error
    assert r.status == "fail"


def test_ledger_g4_pass() -> None:
    led = GateLedger()
    r = led.record_g4([100.01, 99.99, 100.00])
    assert r.status == "pass"


def test_ledger_g2_mesh() -> None:
    led = GateLedger()
    assert led.record_g2_mesh(0.195).status == "pass"
    assert led.record_g2_mesh(0.40).status == "fail"


def test_cnc_close_plan() -> None:
    r = CalibrationRunner()
    plan = r.plan_report("cnc_close")
    assert plan["test_count"] == 3
    ids = [t["id"] for t in plan["tests"]]
    assert ids == ["mesh_fast", "dimensional_accuracy", "precision_replicate"]


def test_gcode_for_flow_and_fl() -> None:
    flow = gcode_for_test_id("flow_rate", first_speed_mm_s=18)
    assert "ForgeOS single-wall" in flow
    fl = gcode_for_test_id("first_layer_squish", first_speed_mm_s=18)
    assert "first-layer" in fl.lower() or "squish" in fl.lower()
    assert "F1080" in fl  # 18 mm/s * 60


def test_moonraker_from_url() -> None:
    c = MoonrakerClient.from_url("http://192.168.1.178:7125")
    assert c.host == "192.168.1.178"
    assert c.port == 7125
