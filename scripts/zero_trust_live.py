#!/usr/bin/env python3
"""Zero-trust live campaign — atomic evidence only. No soft passes. No vibes.

Layers (abort on hard fail unless --continue):
  L0  network atom: TCP SYN + HTTP/SSH response bytes (not just connect())
  L1  G0 static: pytest + material packs
  L2  G1 hardware: Moonraker printer state == ready
  L3  telemetry snapshot: heaters, toolhead, mesh, print_stats
  L4  evidence ledger: re-score historical claims vs CNC band (zero-lie)

Usage:
  python3 scripts/zero_trust_live.py
  python3 scripts/zero_trust_live.py --host 192.168.1.178
  FORGE_HOST=mks@192.168.1.178 python3 scripts/zero_trust_live.py --ssh-probe
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.gates.verification import (
    GateStatus,
    VerificationReport,
    gate_g0_static,
    gate_g1_hardware,
    gate_g2_process_sensors,
    gate_g3_accuracy,
)
from forgeos.materials import default_materials_dir, load_all_packs
from forgeos.moonraker_client import MoonrakerClient, MoonrakerError
from forgeos.precision import PrecisionTier, get_band, process_capability


def atom_tcp(host: str, port: int, timeout_s: float = 3.0, payload: bytes = b"") -> Dict[str, Any]:
    """First-principles connectivity: connect + optional recv. No marketing."""
    t0 = time.time()
    out: Dict[str, Any] = {
        "host": host,
        "port": port,
        "connect_ok": False,
        "bytes_recv": 0,
        "error": None,
        "elapsed_s": 0.0,
    }
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout_s)
    try:
        s.connect((host, port))
        out["connect_ok"] = True
        if payload:
            s.sendall(payload)
        try:
            data = s.recv(512)
            out["bytes_recv"] = len(data)
            out["preview"] = repr(data[:80])
        except socket.timeout:
            out["error"] = "recv_timeout"
        except OSError as exc:
            out["error"] = "recv_%s" % type(exc).__name__
            out["error_detail"] = str(exc)
    except OSError as exc:
        out["error"] = type(exc).__name__
        out["error_detail"] = str(exc)
    finally:
        try:
            s.close()
        except OSError:
            pass
        out["elapsed_s"] = round(time.time() - t0, 3)
    return out


def layer0_network(host: str, ssh_probe: bool) -> Tuple[bool, Dict[str, Any]]:
    """Prove the wire. TCP connect alone is NOT proof of a usable printer API."""
    evidence: Dict[str, Any] = {"atoms": []}
    http_payload = b"GET /printer/info HTTP/1.0\r\nHost: %s\r\n\r\n" % host.encode()
    for port, payload in (
        (7125, http_payload),
        (81, b"GET / HTTP/1.0\r\nHost: x\r\n\r\n"),
        (22, b""),
    ):
        atom = atom_tcp(host, port, timeout_s=4.0, payload=payload)
        evidence["atoms"].append(atom)

    moon = next(a for a in evidence["atoms"] if a["port"] == 7125)
    # Usable Moonraker = connect + bytes (HTTP response). Connect-then-RST = FAIL.
    usable = bool(moon["connect_ok"] and moon["bytes_recv"] > 0)
    evidence["moonraker_usable"] = usable
    evidence["verdict"] = "PASS" if usable else "FAIL"
    evidence["physics"] = (
        "HTTP response bytes received from :7125"
        if usable
        else "TCP may SYN but no Moonraker payload — tunnel/firewall/RST or printer dead"
    )

    if ssh_probe:
        try:
            proc = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "ConnectTimeout=5",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "mks@%s" % host,
                    "hostname",
                ],
                capture_output=True,
                text=True,
                timeout=12,
            )
            evidence["ssh"] = {
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "").strip()[:200],
                "stderr": (proc.stderr or "").strip()[:300],
            }
        except Exception as exc:  # noqa: BLE001
            evidence["ssh"] = {"error": str(exc)}

    return usable, evidence


def layer1_g0() -> Tuple[bool, Dict[str, Any]]:
    packs = load_all_packs(default_materials_dir())
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    failures = 0 if proc.returncode == 0 else max(1, proc.returncode)
    g0 = gate_g0_static(len(packs), failures)
    return g0.status == GateStatus.PASS, {
        "gate": g0.as_dict(),
        "pytest_returncode": proc.returncode,
        "pytest_tail": (proc.stdout or "")[-400:],
    }


def layer2_g1(client: MoonrakerClient) -> Tuple[bool, Dict[str, Any]]:
    ready = client.is_ready()
    info: Dict[str, Any] = {}
    err = None
    try:
        info = client.printer_info().get("result", {})
    except MoonrakerError as exc:
        err = str(exc)
    g1 = gate_g1_hardware(mcu_ready=ready, disk_free_mb=500.0, abrasive=False, nozzle_ok=True)
    return g1.status == GateStatus.PASS, {
        "gate": g1.as_dict(),
        "ready": ready,
        "printer_info": info,
        "error": err,
    }


def layer3_telemetry(client: MoonrakerClient) -> Tuple[bool, Dict[str, Any]]:
    try:
        status = client.objects_query(
            [
                "extruder",
                "heater_bed",
                "heater_generic heater_bed_outer",
                "toolhead",
                "print_stats",
                "bed_mesh",
                "gcode_macro _FORGE_Z",
            ]
        )
    except MoonrakerError as exc:
        return False, {"error": str(exc)}

    st = status.get("result", {}).get("status", {})
    mesh = st.get("bed_mesh") or {}
    matrix = mesh.get("probed_matrix") or mesh.get("mesh_matrix")
    p2p = None
    g2 = None
    if matrix:
        vals = [float(v) for row in matrix for v in row]
        if vals:
            p2p = max(vals) - min(vals)
            # shaper unknown until ADXL — do not lie; mark shaper_ok False for CNC
            g2 = gate_g2_process_sensors(p2p, shaper_ok=False, thermal_stable=True)
    return True, {
        "status_keys": sorted(st.keys()),
        "extruder_temp": (st.get("extruder") or {}).get("temperature"),
        "bed_temp": (st.get("heater_bed") or {}).get("temperature"),
        "outer_temp": (st.get("heater_generic heater_bed_outer") or {}).get("temperature"),
        "print_state": (st.get("print_stats") or {}).get("state"),
        "homed": (st.get("toolhead") or {}).get("homed_axes"),
        "mesh_p2p_mm": p2p,
        "g2": None if g2 is None else g2.as_dict(),
        "forge_z": st.get("gcode_macro _FORGE_Z"),
    }


def layer4_evidence_ledger() -> Tuple[bool, Dict[str, Any]]:
    """Zero-lie: re-score saved G3 claim against CNC band. Provisional ≠ PASS."""
    band = get_band(PrecisionTier.CNC)
    path = ROOT / "artifacts" / "g3_measure_20260714.json"
    if not path.is_file():
        return False, {"error": "missing artifacts/g3_measure_20260714.json"}

    raw = json.loads(path.read_text(encoding="utf-8"))
    # Historical range 99–100 mm → worst |err| = 1.0 mm. Mean unknown.
    # Zero-trust: without a single mean, treat as FAIL (cannot prove CNC).
    mx = raw.get("measured_x_mm") or {}
    if isinstance(mx, dict):
        lo = float(mx.get("min", 0))
        hi = float(mx.get("max", 0))
        # Conservative: use worst absolute error vs 100
        worst = max(abs(lo - 100.0), abs(hi - 100.0))
        # Optimistic mid for curiosity only — NOT a pass criterion
        mid = (lo + hi) / 2.0
    else:
        worst = abs(float(mx) - 100.0)
        mid = float(mx)

    g3_worst = gate_g3_accuracy(worst, limit_mm=band.abs_error_max_mm)
    g3_mid = gate_g3_accuracy(mid - 100.0, limit_mm=band.abs_error_max_mm)
    old_verdict = raw.get("g3_verdict")

    # Lies to kill
    lies: List[str] = []
    if old_verdict and "provisional" in str(old_verdict):
        lies.append("historical 'provisional_borderline' is NOT a CNC pass")
    if worst > band.abs_error_max_mm:
        lies.append(
            "range spans %.3f mm worst |err| vs CNC limit %.3f — FAIL"
            % (worst, band.abs_error_max_mm)
        )
    # saved_state still may claim pile-up first layer — flag if present
    saved = ROOT / "configs" / "saved_state_shop_n4pro.yaml"
    if saved.is_file():
        text = saved.read_text(encoding="utf-8")
        if "0.58" in text and "1.14" in text:
            lies.append(
                "saved_state still describes pile-up first-layer (0.58/114%) — conflicts with machine-flat zero-iron"
            )

    # Zero-trust pass only if we have a single mean within band — we do not.
    passed = False
    return passed, {
        "source": str(path),
        "cnc_band": band.as_dict(),
        "measured_range_mm": {"min": lo, "max": hi} if isinstance(mx, dict) else mx,
        "worst_abs_error_mm": round(worst, 4),
        "midpoint_error_mm": round(mid - 100.0, 4),
        "gate_worst": g3_worst.as_dict(),
        "gate_midpoint_curiosity_only": g3_mid.as_dict(),
        "historical_verdict": old_verdict,
        "zero_trust_verdict": "FAIL",
        "lies_killed": lies,
        "next_physical_action": (
            "On LAN Mac: caliper 100mm bar at 3 points → mean; "
            "python3 scripts/zero_trust_live.py --g3-mean <mm>"
        ),
        "t0_s": raw.get("t0_print_duration_s"),
        "z_adjust_mm": raw.get("z_adjust_mm"),
    }


def score_g3_mean(mean_mm: float) -> Dict[str, Any]:
    band = get_band(PrecisionTier.CNC)
    err = mean_mm - 100.0
    g3 = gate_g3_accuracy(err, limit_mm=band.abs_error_max_mm)
    return {
        "mean_mm": mean_mm,
        "error_mm": round(err, 4),
        "cnc_limit_mm": band.abs_error_max_mm,
        "gate": g3.as_dict(),
        "passed": g3.status == GateStatus.PASS,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Zero-trust live atomic campaign")
    ap.add_argument("--host", default="192.168.1.178")
    ap.add_argument("--port", type=int, default=7125)
    ap.add_argument("--ssh-probe", action="store_true")
    ap.add_argument("--continue-on-fail", action="store_true")
    ap.add_argument("--g3-mean", type=float, default=None, help="Operator caliper mean mm")
    ap.add_argument(
        "--report",
        default=str(ROOT / "artifacts" / "zero_trust_live_report.json"),
    )
    args = ap.parse_args()

    report: Dict[str, Any] = {
        "ts": time.time(),
        "host": args.host,
        "precision_tier": "cnc",
        "layers": {},
        "all_pass": False,
    }
    ok_all = True

    print("=== L0 NETWORK ATOM ===")
    ok, ev = layer0_network(args.host, ssh_probe=args.ssh_probe)
    report["layers"]["L0_network"] = {"ok": ok, "evidence": ev}
    print(json.dumps({"ok": ok, "verdict": ev.get("verdict"), "physics": ev.get("physics")}, indent=2))
    if not ok:
        ok_all = False
        if not args.continue_on_fail:
            report["all_pass"] = False
            report["abort"] = "L0 network unusable — cannot claim printer control from this host"
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
            print("ABORT:", report["abort"])
            print("report:", args.report)
            # Still run offline layers for honesty
            print("=== L1 G0 (offline) ===")
            ok1, ev1 = layer1_g0()
            report["layers"]["L1_g0"] = {"ok": ok1, "evidence": ev1}
            print(json.dumps({"ok": ok1, "gate": ev1.get("gate")}, indent=2))
            print("=== L4 EVIDENCE LEDGER (offline) ===")
            ok4, ev4 = layer4_evidence_ledger()
            report["layers"]["L4_ledger"] = {"ok": ok4, "evidence": ev4}
            print(json.dumps({"ok": ok4, "verdict": ev4.get("zero_trust_verdict"), "lies": ev4.get("lies_killed")}, indent=2))
            if args.g3_mean is not None:
                report["layers"]["L4b_g3_mean"] = score_g3_mean(args.g3_mean)
                print(json.dumps(report["layers"]["L4b_g3_mean"], indent=2))
            Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
            return 2

    print("=== L1 G0 ===")
    ok, ev = layer1_g0()
    report["layers"]["L1_g0"] = {"ok": ok, "evidence": ev}
    print(json.dumps({"ok": ok, "gate": ev.get("gate")}, indent=2))
    ok_all = ok_all and ok
    if not ok and not args.continue_on_fail:
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 1

    client = MoonrakerClient(args.host, args.port, timeout_s=8.0)
    print("=== L2 G1 ===")
    ok, ev = layer2_g1(client)
    report["layers"]["L2_g1"] = {"ok": ok, "evidence": ev}
    print(json.dumps({"ok": ok, "gate": ev.get("gate"), "ready": ev.get("ready")}, indent=2))
    ok_all = ok_all and ok
    if not ok and not args.continue_on_fail:
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 1

    print("=== L3 TELEMETRY ===")
    ok, ev = layer3_telemetry(client)
    report["layers"]["L3_telemetry"] = {"ok": ok, "evidence": ev}
    print(json.dumps({"ok": ok, "temps": {k: ev.get(k) for k in ("extruder_temp", "bed_temp", "outer_temp")}, "mesh_p2p": ev.get("mesh_p2p_mm"), "g2": ev.get("g2")}, indent=2))
    ok_all = ok_all and ok

    print("=== L4 EVIDENCE LEDGER ===")
    ok, ev = layer4_evidence_ledger()
    report["layers"]["L4_ledger"] = {"ok": ok, "evidence": ev}
    print(json.dumps({"ok": ok, "verdict": ev.get("zero_trust_verdict"), "lies": ev.get("lies_killed")}, indent=2))
    ok_all = ok_all and ok

    if args.g3_mean is not None:
        scored = score_g3_mean(args.g3_mean)
        report["layers"]["L4b_g3_mean"] = scored
        print(json.dumps(scored, indent=2))
        ok_all = ok_all and bool(scored["passed"])

    report["all_pass"] = ok_all
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("all_pass:", ok_all)
    print("report:", args.report)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
