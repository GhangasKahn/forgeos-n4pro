"""Minimal Moonraker HTTP client (stdlib only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


class MoonrakerError(Exception):
    pass


class MoonrakerClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 7125, timeout_s: float = 6.0) -> None:
        self.base = "http://%s:%d" % (host, port)
        self.timeout_s = float(timeout_s)

    def _get(self, path: str) -> Dict[str, Any]:
        url = self.base + path
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ConnectionError) as exc:
            raise MoonrakerError("GET %s failed: %s" % (path, exc))

    def _post(self, path: str) -> Dict[str, Any]:
        url = self.base + path
        req = urllib.request.Request(url, method="POST", data=b"")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ConnectionError) as exc:
            raise MoonrakerError("POST %s failed: %s" % (path, exc))

    def printer_info(self) -> Dict[str, Any]:
        return self._get("/printer/info")

    def objects_query(self, object_names: List[str]) -> Dict[str, Any]:
        # Spaces in names like "heater_generic heater_bed_outer" must be encoded
        query = "&".join(urllib.parse.quote(name, safe="") for name in object_names)
        return self._get("/printer/objects/query?" + query)

    def gcode(self, script: str, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        qs = urllib.parse.urlencode({"script": script})
        path = "/printer/gcode/script?" + qs
        if timeout_s is None:
            return self._post(path)
        # temporary timeout override for long waits (heat/mesh)
        old = self.timeout_s
        self.timeout_s = float(timeout_s)
        try:
            return self._post(path)
        finally:
            self.timeout_s = old

    def firmware_restart(self) -> Dict[str, Any]:
        return self._post("/printer/firmware_restart")

    def is_ready(self) -> bool:
        try:
            info = self.printer_info().get("result", {})
            return str(info.get("state", "")).lower() == "ready"
        except MoonrakerError:
            return False
