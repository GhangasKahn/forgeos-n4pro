"""Unified Moonraker HTTP client (stdlib only).

Single spine for guardian, adaptive, vision, and calibration runners.
Status helpers unwrap Moonraker's ``result`` / ``status`` envelopes.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Union


class MoonrakerError(Exception):
    pass


class MoonrakerClient:
    """HTTP client for Moonraker / Klipper.

    Construct with ``host``+``port`` or a full ``base_url``.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7125,
        timeout_s: float = 10.0,
        base_url: Optional[str] = None,
    ) -> None:
        if base_url:
            self.base = base_url.rstrip("/")
        else:
            self.base = "http://%s:%d" % (host, port)
        self.timeout_s = float(timeout_s)

    @classmethod
    def from_url(cls, url: str, timeout_s: float = 10.0) -> "MoonrakerClient":
        return cls(base_url=url, timeout_s=timeout_s)

    def _get(self, path: str, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        url = self.base + path
        to = self.timeout_s if timeout_s is None else float(timeout_s)
        try:
            with urllib.request.urlopen(url, timeout=to) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise MoonrakerError("GET %s failed: %s" % (path, exc))

    def _post(self, path: str, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        url = self.base + path
        to = self.timeout_s if timeout_s is None else float(timeout_s)
        req = urllib.request.Request(url, method="POST", data=b"")
        try:
            with urllib.request.urlopen(req, timeout=to) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise MoonrakerError("POST %s failed: %s" % (path, exc))

    # ---- raw API ---------------------------------------------------------

    def printer_info(self) -> Dict[str, Any]:
        return self._get("/printer/info")

    def printer_info_result(self) -> Dict[str, Any]:
        return dict(self.printer_info().get("result") or {})

    def objects_query(self, object_names: List[str]) -> Dict[str, Any]:
        # Spaces in names like "heater_generic heater_bed_outer" must be encoded
        query = "&".join(urllib.parse.quote(name, safe="") for name in object_names)
        return self._get("/printer/objects/query?" + query)

    def objects_status(self, object_names: List[str]) -> Dict[str, Any]:
        """Unwrapped ``result.status`` map keyed by object name."""
        raw = self.objects_query(object_names)
        return dict((raw.get("result") or {}).get("status") or {})

    def gcode(self, script: str, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        qs = urllib.parse.urlencode({"script": script})
        path = "/printer/gcode/script?" + qs
        return self._post(path, timeout_s=timeout_s)

    def firmware_restart(self) -> Dict[str, Any]:
        return self._post("/printer/firmware_restart")

    def pause(self) -> Dict[str, Any]:
        return self._post("/printer/print/pause")

    def resume(self) -> Dict[str, Any]:
        return self._post("/printer/print/resume")

    def cancel(self) -> Dict[str, Any]:
        return self._post("/printer/print/cancel")

    def print_start(self, filename: str) -> Dict[str, Any]:
        qs = urllib.parse.urlencode({"filename": filename})
        return self._post("/printer/print/start?" + qs)

    # ---- readiness / status ----------------------------------------------

    def is_ready(self) -> bool:
        try:
            return str(self.printer_info_result().get("state", "")).lower() == "ready"
        except MoonrakerError:
            return False

    def print_state(self) -> str:
        try:
            st = self.objects_status(["print_stats"])
            return str(st.get("print_stats", {}).get("state", "") or "").lower()
        except MoonrakerError:
            return "unknown"

    def is_printing(self) -> bool:
        return self.print_state() == "printing"

    def idle_timeout_state(self) -> str:
        try:
            st = self.objects_status(["idle_timeout"])
            return str(st.get("idle_timeout", {}).get("state", "") or "").lower()
        except MoonrakerError:
            return "unknown"

    def temps(self) -> Dict[str, float]:
        """Common thermal snapshot for N4 Pro dual-bed."""
        names = ["extruder", "heater_bed", "heater_generic heater_bed_outer"]
        try:
            st = self.objects_status(names)
        except MoonrakerError:
            return {}
        out: Dict[str, float] = {}
        if "extruder" in st:
            out["extruder"] = float(st["extruder"].get("temperature") or 0)
            out["extruder_target"] = float(st["extruder"].get("target") or 0)
        if "heater_bed" in st:
            out["bed"] = float(st["heater_bed"].get("temperature") or 0)
            out["bed_target"] = float(st["heater_bed"].get("target") or 0)
        outer = st.get("heater_generic heater_bed_outer") or {}
        if outer:
            out["bed_outer"] = float(outer.get("temperature") or 0)
            out["bed_outer_target"] = float(outer.get("target") or 0)
        return out

    def mesh_peak_to_peak(self) -> Optional[float]:
        try:
            st = self.objects_status(["bed_mesh"])
            mesh = st.get("bed_mesh") or {}
            probed = mesh.get("probed_matrix") or mesh.get("mesh_matrix")
            if not probed:
                return None
            vals: List[float] = []
            for row in probed:
                for v in row:
                    vals.append(float(v))
            if not vals:
                return None
            return max(vals) - min(vals)
        except (MoonrakerError, TypeError, ValueError):
            return None

    def forge_armed_autotune(self) -> bool:
        try:
            st = self.objects_status(["gcode_macro _FORGE_STATE"])
            var = st.get("gcode_macro _FORGE_STATE") or {}
            return int(var.get("armed_autotune") or 0) == 1
        except (MoonrakerError, TypeError, ValueError):
            return False

    # ---- wait helpers ----------------------------------------------------

    def wait_until(
        self,
        predicate: Callable[[], bool],
        timeout_s: float = 600.0,
        poll_s: float = 1.0,
        label: str = "condition",
    ) -> bool:
        deadline = time.time() + float(timeout_s)
        while time.time() < deadline:
            try:
                if predicate():
                    return True
            except MoonrakerError:
                pass
            time.sleep(float(poll_s))
        raise MoonrakerError("timeout waiting for %s (%.0fs)" % (label, timeout_s))

    def wait_ready(self, timeout_s: float = 120.0) -> bool:
        return self.wait_until(self.is_ready, timeout_s=timeout_s, label="printer ready")

    def wait_temps(
        self,
        extruder: Optional[float] = None,
        bed: Optional[float] = None,
        bed_outer: Optional[float] = None,
        tol: float = 2.5,
        timeout_s: float = 900.0,
    ) -> Dict[str, float]:
        def _ok() -> bool:
            t = self.temps()
            if extruder is not None and abs(t.get("extruder", -999) - extruder) > tol:
                return False
            if bed is not None and abs(t.get("bed", -999) - bed) > tol:
                return False
            if bed_outer is not None and abs(t.get("bed_outer", -999) - bed_outer) > (tol + 1.0):
                return False
            return True

        self.wait_until(_ok, timeout_s=timeout_s, poll_s=2.0, label="temperatures")
        return self.temps()

    def wait_idle(self, timeout_s: float = 3600.0, poll_s: float = 2.0) -> bool:
        """Wait until not printing / not busy (idle_timeout Idle or Ready)."""

        def _idle() -> bool:
            if self.is_printing():
                return False
            state = self.idle_timeout_state()
            if state in {"idle", "ready", ""}:
                # empty → treat as idle if not printing
                return not self.is_printing()
            if state == "printing":
                return False
            # "Ready" / other — require not printing
            return not self.is_printing()

        return self.wait_until(_idle, timeout_s=timeout_s, poll_s=poll_s, label="idle")

    def run_script_and_wait(
        self,
        script: str,
        timeout_s: float = 1800.0,
        gcode_timeout_s: float = 30.0,
        poll_s: float = 2.0,
    ) -> Dict[str, Any]:
        """Fire a gcode script then wait until the printer returns to idle.

        Long macros (PID, mesh) often hold the HTTP request; use a short
        gcode timeout and poll idle state instead of blocking forever.
        """
        try:
            self.gcode(script, timeout_s=gcode_timeout_s)
        except MoonrakerError as exc:
            # Request may time out while Klipper keeps running the macro — continue polling
            if "timed out" not in str(exc).lower() and "timeout" not in str(exc).lower():
                raise
        self.wait_idle(timeout_s=timeout_s, poll_s=poll_s)
        return {"ok": True, "script": script}

    # ---- convenience forge helpers (used by adaptive / vision) -----------

    def baby_down(self) -> Dict[str, Any]:
        return self.gcode("FORGE_BABY_DOWN")

    def baby_up(self) -> Dict[str, Any]:
        return self.gcode("FORGE_BABY_UP")

    def set_flow_percent(self, percent: int) -> Dict[str, Any]:
        return self.gcode("M221 S%d" % int(percent))

    def set_speed_percent(self, percent: int) -> Dict[str, Any]:
        return self.gcode("M220 S%d" % int(percent))

    def flat_mode(self, role: str = "solid") -> Dict[str, Any]:
        return self.gcode("FORGE_FLAT_SURFACE_MODE ROLE=%s" % role)

    def set_z_adjust(self, z_mm: float) -> Dict[str, Any]:
        return self.gcode("FORGE_SET_Z_ADJUST Z=%.3f" % float(z_mm))

    def apply_dynamic(self, script: str) -> Dict[str, Any]:
        return self.gcode(script)


# Backward-compatible alias used by vision / adaptive code
MoonrakerBus = MoonrakerClient
