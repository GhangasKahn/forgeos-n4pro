"""Moonraker control bus — shared by adaptive brain and optional vision loop.

Moved out of forgeos.vision so zero-vision control has no camera dependency.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List


class MoonrakerBus:
    def __init__(self, base_url: str = "http://192.168.1.178:7125", timeout_s: float = 10.0) -> None:
        self.base = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def _get(self, path: str) -> Dict[str, Any]:
        with urllib.request.urlopen(self.base + path, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, path: str) -> Dict[str, Any]:
        req = urllib.request.Request(self.base + path, method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def printer_info(self) -> Dict[str, Any]:
        return self._get("/printer/info").get("result", {})

    def objects_query(self, names: List[str]) -> Dict[str, Any]:
        q = "&".join(urllib.parse.quote(n, safe="") for n in names)
        return self._get("/printer/objects/query?" + q).get("result", {}).get("status", {})

    def gcode(self, script: str) -> Dict[str, Any]:
        qs = urllib.parse.urlencode({"script": script})
        return self._post("/printer/gcode/script?" + qs)

    def pause(self) -> Dict[str, Any]:
        return self._post("/printer/print/pause")

    def resume(self) -> Dict[str, Any]:
        return self._post("/printer/print/resume")

    def cancel(self) -> Dict[str, Any]:
        return self._post("/printer/print/cancel")

    def baby_down(self) -> Dict[str, Any]:
        return self.gcode("FORGE_BABY_DOWN")

    def baby_up(self) -> Dict[str, Any]:
        return self.gcode("FORGE_BABY_UP")

    def apply_dynamic(self, script: str) -> Dict[str, Any]:
        return self.gcode(script)

    def set_flow_percent(self, percent: int) -> Dict[str, Any]:
        return self.gcode("M221 S%d" % int(percent))

    def set_speed_percent(self, percent: int) -> Dict[str, Any]:
        return self.gcode("M220 S%d" % int(percent))

    def flat_mode(self, role: str = "solid") -> Dict[str, Any]:
        return self.gcode("FORGE_FLAT_SURFACE_MODE ROLE=%s" % role)

    def set_z_adjust(self, z_mm: float) -> Dict[str, Any]:
        return self.gcode("FORGE_SET_Z_ADJUST Z=%.3f" % float(z_mm))

    def is_printing(self) -> bool:
        try:
            st = self.objects_query(["print_stats"])
            return str(st.get("print_stats", {}).get("state", "")).lower() == "printing"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
            return False
