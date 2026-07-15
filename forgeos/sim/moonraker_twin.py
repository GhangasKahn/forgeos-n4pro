"""Neptune 4 Pro digital twin — local Moonraker-compatible HTTP surface.

Zero-trust rule: this is a SIMULATOR. It never claims to be the shop printer.
Labeled state.sim=true on every response. Use only for offline campaign drills.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse


@dataclass
class TwinState:
    """Atomic N4 Pro process state — dual bed, probe Z, mesh, extruder."""

    sim: bool = True
    ready: bool = True
    hostname: str = "znp-k1-sim"
    z_adjust_mm: float = -0.480
    bed_c: float = 25.0
    bed_target_c: float = 0.0
    outer_c: float = 25.0
    outer_target_c: float = 0.0
    nozzle_c: float = 25.0
    nozzle_target_c: float = 0.0
    pressure_advance: float = 0.030
    flow_percent: int = 100
    speed_percent: int = 100
    homed_axes: str = ""
    print_state: str = "standby"
    mesh_matrix: List[List[float]] = field(default_factory=list)
    mesh_profile: str = ""
    gcode_log: List[str] = field(default_factory=list)
    last_error: str = ""

    def ensure_mesh(self, n: int = 7, p2p: float = 0.18) -> None:
        """Synthetic bowl-shaped mesh with known peak-to-peak (CNC-relevant)."""
        if self.mesh_matrix and len(self.mesh_matrix) == n:
            return
        # Bowl: corners high, center low → p2p controlled
        amp = p2p / 2.0
        rows: List[List[float]] = []
        for i in range(n):
            row = []
            for j in range(n):
                # radial bowl on unit square
                u = (i / max(1, n - 1)) * 2 - 1
                v = (j / max(1, n - 1)) * 2 - 1
                z = amp * (u * u + v * v) / 2.0 - amp * 0.5
                row.append(round(z, 4))
            rows.append(row)
        # Force exact p2p
        flat = [v for r in rows for v in r]
        cur = max(flat) - min(flat)
        if cur > 1e-9:
            scale = p2p / cur
            rows = [[round(v * scale, 4) for v in r] for r in rows]
        self.mesh_matrix = rows
        self.mesh_profile = "default"

    def mesh_p2p(self) -> float:
        if not self.mesh_matrix:
            return 0.0
        vals = [v for r in self.mesh_matrix for v in r]
        return max(vals) - min(vals)

    def tick_thermal(self, dt: float = 0.5) -> None:
        """First-order lag toward targets (basement cold start physics)."""
        def approach(cur: float, tgt: float) -> float:
            if tgt <= 0 and cur > 25:
                return cur + (25.0 - cur) * min(1.0, 0.15 * dt)
            return cur + (tgt - cur) * min(1.0, 0.35 * dt)

        self.bed_c = round(approach(self.bed_c, self.bed_target_c if self.bed_target_c > 0 else 25.0), 2)
        self.outer_c = round(approach(self.outer_c, self.outer_target_c if self.outer_target_c > 0 else 25.0), 2)
        self.nozzle_c = round(
            approach(self.nozzle_c, self.nozzle_target_c if self.nozzle_target_c > 0 else 25.0), 2
        )

    def apply_gcode(self, script: str) -> None:
        self.gcode_log.append(script)
        s = script.strip()
        # SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=65
        m = re.search(r"SET_HEATER_TEMPERATURE\s+HEATER=(\S+)\s+TARGET=([0-9.]+)", s, re.I)
        if m:
            heater, tgt = m.group(1).lower(), float(m.group(2))
            if heater == "heater_bed":
                self.bed_target_c = tgt
            elif "outer" in heater or heater == "heater_bed_outer":
                self.outer_target_c = tgt
            elif heater == "extruder":
                self.nozzle_target_c = tgt
            return
        if re.match(r"G28\b", s, re.I):
            self.homed_axes = "xyz"
            return
        if "BED_MESH_CALIBRATE" in s.upper() or "FORGE_MESH" in s.upper():
            self.ensure_mesh(7, 0.18)
            return
        if "BED_MESH_CLEAR" in s.upper():
            self.mesh_matrix = []
            self.mesh_profile = ""
            return
        m = re.search(r"FORGE_SET_Z_ADJUST\s+Z=([-0-9.]+)", s, re.I)
        if m:
            self.z_adjust_mm = float(m.group(1))
            return
        m = re.search(r"SET_GCODE_OFFSET\s+Z=([-0-9.]+)", s, re.I)
        if m:
            self.z_adjust_mm = float(m.group(1))
            return
        m = re.search(r"SET_PRESSURE_ADVANCE\s+.*ADVANCE=([0-9.]+)", s, re.I)
        if m:
            self.pressure_advance = float(m.group(1))
            return
        m = re.search(r"M221\s+S(\d+)", s, re.I)
        if m:
            self.flow_percent = int(m.group(1))
            return
        m = re.search(r"M220\s+S(\d+)", s, re.I)
        if m:
            self.speed_percent = int(m.group(1))
            return

    def objects(self, names: List[str]) -> Dict[str, Any]:
        self.tick_thermal()
        status: Dict[str, Any] = {}
        for name in names:
            if name == "extruder":
                status[name] = {
                    "temperature": self.nozzle_c,
                    "target": self.nozzle_target_c,
                    "power": 0.2 if self.nozzle_target_c > self.nozzle_c else 0.0,
                    "pressure_advance": self.pressure_advance,
                }
            elif name == "heater_bed":
                status[name] = {
                    "temperature": self.bed_c,
                    "target": self.bed_target_c,
                    "power": 0.4 if self.bed_target_c > self.bed_c else 0.0,
                }
            elif name in ("heater_generic heater_bed_outer", "heater_bed_outer"):
                status["heater_generic heater_bed_outer"] = {
                    "temperature": self.outer_c,
                    "target": self.outer_target_c,
                    "power": 0.45 if self.outer_target_c > self.outer_c else 0.0,
                }
            elif name == "toolhead":
                status[name] = {
                    "homed_axes": self.homed_axes,
                    "position": [112.5, 112.5, 5.0 + self.z_adjust_mm, 0.0],
                    "max_velocity": 300,
                    "max_accel": 5000,
                }
            elif name == "print_stats":
                status[name] = {"state": self.print_state, "filename": "", "print_duration": 0}
            elif name == "bed_mesh":
                status[name] = {
                    "profile_name": self.mesh_profile,
                    "probed_matrix": self.mesh_matrix,
                    "mesh_matrix": self.mesh_matrix,
                }
            elif name == "gcode_macro _FORGE_Z":
                status[name] = {"z_adjust": self.z_adjust_mm}
        return status


_STATE = TwinState()
_LOCK = threading.Lock()


def get_state() -> TwinState:
    return _STATE


def reset_state(**kwargs: Any) -> TwinState:
    global _STATE
    with _LOCK:
        _STATE = TwinState(**kwargs)
    return _STATE


class TwinHandler(BaseHTTPRequestHandler):
    server_version = "ForgeOS-N4Pro-Twin/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return  # quiet

    def _json(self, code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-ForgeOS-Sim", "true")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        with _LOCK:
            st = _STATE
            st.tick_thermal()
            if path == "/printer/info":
                self._json(
                    200,
                    {
                        "result": {
                            "state": "ready" if st.ready else "shutdown",
                            "state_message": "ForgeOS digital twin (SIM)",
                            "hostname": st.hostname,
                            "software_version": "forgeos-twin-0.1",
                            "sim": True,
                        }
                    },
                )
                return
            if path.startswith("/printer/objects/query"):
                # /printer/objects/query?extruder&heater_bed&...
                q = parsed.query
                names = [unquote(p) for p in q.split("&") if p]
                self._json(200, {"result": {"status": st.objects(names), "sim": True}})
                return
            if path == "/server/info":
                self._json(200, {"result": {"klippy_connected": True, "klippy_state": "ready", "sim": True}})
                return
            if path == "/health":
                self._json(200, {"ok": True, "sim": True, "mesh_p2p": st.mesh_p2p()})
                return
        self._json(404, {"error": "not found", "sim": True})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        with _LOCK:
            st = _STATE
            if path == "/printer/gcode/script":
                script = qs.get("script", [""])[0]
                st.apply_gcode(script)
                # Fast-forward thermal a bit on heat commands
                for _ in range(6):
                    st.tick_thermal(1.0)
                self._json(200, {"result": "ok", "sim": True, "script": script})
                return
            if path == "/printer/firmware_restart":
                st.ready = True
                self._json(200, {"result": "ok", "sim": True})
                return
            if path in ("/printer/print/pause", "/printer/print/resume", "/printer/print/cancel"):
                self._json(200, {"result": "ok", "sim": True})
                return
        self._json(404, {"error": "not found", "sim": True})


def serve(host: str = "127.0.0.1", port: int = 7125) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), TwinHandler)
    return httpd


def serve_background(host: str = "127.0.0.1", port: int = 7125) -> Tuple[ThreadingHTTPServer, threading.Thread]:
    httpd = serve(host, port)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, t
