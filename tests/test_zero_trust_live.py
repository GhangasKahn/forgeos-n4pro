"""Tests for zero-trust live campaign (offline layers)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import zero_trust_live as zt  # noqa: E402


def test_layer4_ledger_fails_cnc():
    ok, ev = zt.layer4_evidence_ledger()
    assert ok is False
    assert ev["zero_trust_verdict"] == "FAIL"
    assert ev["worst_abs_error_mm"] >= 0.10
    assert ev["lies_killed"]


def test_score_g3_mean_cnc():
    assert zt.score_g3_mean(100.05)["passed"] is True
    assert zt.score_g3_mean(100.15)["passed"] is False


def test_atom_tcp_localhost_closed():
    atom = zt.atom_tcp("127.0.0.1", 59999, timeout_s=0.5)
    assert atom["connect_ok"] is False
    assert atom["error"] is not None
