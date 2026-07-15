"""Moonraker HTTP client (stdlib only) — query, gcode, upload, print control."""

from __future__ import annotations

import json
import mimetypes
import os
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class MoonrakerError(Exception):
    pass


class MoonrakerClient:
    """Minimal but complete client for ForgeOS live ops."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7125, timeout_s: float = 6.0) -> None:
        self.host = host
        self.port = int(port)
        self.base = "http://%s:%d" % (host, port)
        self.timeout_s = float(timeout_s)

    def _get(self, path: str, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        url = self.base + path
        t = self.timeout_s if timeout_s is None else float(timeout_s)
        try:
            with urllib.request.urlopen(url, timeout=t) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ConnectionError) as exc:
            raise MoonrakerError("GET %s failed: %s" % (path, exc))

    def _post(self, path: str, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        url = self.base + path
        t = self.timeout_s if timeout_s is None else float(timeout_s)
        req = urllib.request.Request(url, method="POST", data=b"")
        try:
            with urllib.request.urlopen(req, timeout=t) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ConnectionError) as exc:
            raise MoonrakerError("POST %s failed: %s" % (path, exc))

    def printer_info(self) -> Dict[str, Any]:
        return self._get("/printer/info")

    def objects_query(self, object_names: List[str]) -> Dict[str, Any]:
        query = "&".join(urllib.parse.quote(name, safe="") for name in object_names)
        return self._get("/printer/objects/query?" + query)

    def status(self, *object_names: str) -> Dict[str, Any]:
        """Return result.status for the given objects."""
        names = list(object_names) if object_names else [
            "print_stats",
            "toolhead",
            "gcode_move",
            "heater_bed",
            "extruder",
            "virtual_sdcard",
        ]
        return self.objects_query(names).get("result", {}).get("status", {})

    def gcode(self, script: str, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        qs = urllib.parse.urlencode({"script": script})
        path = "/printer/gcode/script?" + qs
        return self._post(path, timeout_s=timeout_s)

    def firmware_restart(self) -> Dict[str, Any]:
        return self._post("/printer/firmware_restart", timeout_s=30.0)

    def restart(self) -> Dict[str, Any]:
        return self._post("/printer/restart", timeout_s=30.0)

    def is_ready(self) -> bool:
        try:
            info = self.printer_info().get("result", {})
            return str(info.get("state", "")).lower() == "ready"
        except MoonrakerError:
            return False

    def print_start(self, filename: str) -> Dict[str, Any]:
        """Start a gcode already present under Moonraker gcodes root."""
        qs = urllib.parse.urlencode({"filename": filename})
        return self._post("/printer/print/start?" + qs, timeout_s=30.0)

    def print_pause(self) -> Dict[str, Any]:
        return self._post("/printer/print/pause")

    def print_resume(self) -> Dict[str, Any]:
        return self._post("/printer/print/resume")

    def print_cancel(self) -> Dict[str, Any]:
        return self._post("/printer/print/cancel")

    def upload_gcode(
        self,
        local_path: Union[str, Path],
        remote_name: Optional[str] = None,
        root: str = "gcodes",
        start_print: bool = False,
        timeout_s: float = 120.0,
    ) -> Dict[str, Any]:
        """Multipart upload to Moonraker server/files/upload."""
        path = Path(local_path)
        if not path.is_file():
            raise MoonrakerError("upload file missing: %s" % path)
        name = remote_name or path.name
        boundary = "----ForgeOS%s" % uuid.uuid4().hex
        body = bytearray()

        def add_field(field: str, value: str) -> None:
            body.extend(("--%s\r\n" % boundary).encode())
            body.extend(('Content-Disposition: form-data; name="%s"\r\n\r\n' % field).encode())
            body.extend(value.encode())
            body.extend(b"\r\n")

        add_field("root", root)
        add_field("print", "true" if start_print else "false")
        data = path.read_bytes()
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        body.extend(("--%s\r\n" % boundary).encode())
        body.extend(
            (
                'Content-Disposition: form-data; name="file"; filename="%s"\r\n'
                "Content-Type: %s\r\n\r\n" % (name, ctype)
            ).encode()
        )
        body.extend(data)
        body.extend(b"\r\n")
        body.extend(("--%s--\r\n" % boundary).encode())

        req = urllib.request.Request(
            self.base + "/server/files/upload",
            data=bytes(body),
            method="POST",
            headers={
                "Content-Type": "multipart/form-data; boundary=%s" % boundary,
                "Content-Length": str(len(body)),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ConnectionError) as exc:
            raise MoonrakerError("upload failed: %s" % exc)

    def print_snapshot(self) -> Dict[str, Any]:
        """Compact print + thermal + Z snapshot for evidence."""
        st = self.status(
            "print_stats",
            "display_status",
            "virtual_sdcard",
            "heater_bed",
            "extruder",
            "gcode_move",
            "toolhead",
        )
        ps = st.get("print_stats") or {}
        hb = st.get("heater_bed") or {}
        ex = st.get("extruder") or {}
        gm = st.get("gcode_move") or {}
        vs = st.get("virtual_sdcard") or {}
        origin = gm.get("homing_origin") or [None, None, None, None]
        return {
            "state": ps.get("state"),
            "filename": ps.get("filename"),
            "message": ps.get("message"),
            "print_duration": ps.get("print_duration"),
            "progress": (st.get("display_status") or {}).get("progress"),
            "vs_progress": vs.get("progress"),
            "bed_c": hb.get("temperature"),
            "bed_target": hb.get("target"),
            "noz_c": ex.get("temperature"),
            "noz_target": ex.get("target"),
            "homing_origin_z": origin[2] if len(origin) > 2 else None,
            "homed_axes": (st.get("toolhead") or {}).get("homed_axes"),
        }

    def wait_print_terminal(
        self,
        poll_s: float = 15.0,
        max_wait_s: float = 3600.0,
        terminal: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Poll until print state is complete/error/cancelled or timeout."""
        done = set(terminal or ["complete", "error", "cancelled"])
        t0 = time.time()
        last: Dict[str, Any] = {}
        while True:
            last = self.print_snapshot()
            st = str(last.get("state") or "").lower()
            if st in done:
                last["elapsed_s"] = round(time.time() - t0, 1)
                last["terminal"] = True
                return last
            if time.time() - t0 >= max_wait_s:
                last["elapsed_s"] = round(time.time() - t0, 1)
                last["terminal"] = False
                last["timeout"] = True
                return last
            time.sleep(poll_s)

    def has_object(self, name: str) -> bool:
        """True if object is registered (e.g. adxl345, axis_twist_compensation)."""
        try:
            q = self.objects_query([name])
            st = q.get("result", {}).get("status", {})
            return name in st
        except MoonrakerError:
            return False

    @classmethod
    def from_url(cls, url: str, timeout_s: float = 6.0) -> "MoonrakerClient":
        """Parse http://host:port into client."""
        u = urllib.parse.urlparse(url if "://" in url else "http://%s" % url)
        host = u.hostname or "127.0.0.1"
        port = u.port or 7125
        return cls(host=host, port=port, timeout_s=timeout_s)
