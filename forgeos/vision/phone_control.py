"""Remote control for Android IP Webcam (camera features only).

With IP Webcam running we can drive torch/focus/quality/zoom-ish settings
over HTTP — no ADB required.

We cannot fully control Android (launch apps, unlock, change Wi‑Fi) unless
you enable Wireless debugging + ADB and authorize this Mac once.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class PhoneControl:
    base_url: str
    timeout_s: float = 3.0

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    def _get(self, path: str) -> str:
        url = self.base_url + path
        req = urllib.request.Request(url, headers={"User-Agent": "ForgeOS-PhoneControl/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _ok(self, path: str) -> bool:
        try:
            body = self._get(path)
            return "Ok" in body or "ok" in body.lower() or body.strip() != ""
        except Exception:
            return False

    def status(self) -> Dict[str, Any]:
        import json

        try:
            raw = self._get("/status.json")
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def torch(self, on: bool = True) -> bool:
        return self._ok("/enabletorch" if on else "/disabletorch")

    def focus(self, on: bool = True) -> bool:
        # IP Webcam: /focus triggers AF; /nofocus may lock
        return self._ok("/focus" if on else "/nofocus")

    def quality(self, percent: int = 70) -> bool:
        percent = max(1, min(100, int(percent)))
        return self._ok("/settings/quality?set=%d" % percent)

    def orientation(self, mode: str = "landscape") -> bool:
        mode = mode if mode in ("landscape", "portrait") else "landscape"
        return self._ok("/settings/orientation?set=%s" % mode)

    def night_vision(self, on: bool = False) -> bool:
        # some builds: /settings/night_vision?set=on|off
        return self._ok("/settings/night_vision?set=%s" % ("on" if on else "off"))

    def exposure_lock(self, on: bool = False) -> bool:
        return self._ok(
            "/settings/exposure_lock?set=%s" % ("on" if on else "off")
        )

    def whitebalance_lock(self, on: bool = False) -> bool:
        return self._ok(
            "/settings/whitebalance_lock?set=%s" % ("on" if on else "off")
        )

    def front_camera(self, on: bool = False) -> bool:
        # ffc = front facing camera
        return self._ok("/settings/ffc?set=%s" % ("on" if on else "off"))

    def optimize_for_bed(self) -> Dict[str, bool]:
        """Preset for printing: rear cam, decent quality, AF, torch off by default."""
        return {
            "rear_cam": self.front_camera(False),
            "quality70": self.quality(70),
            "focus": self.focus(True),
            "torch_off": self.torch(False),
            "landscape": self.orientation("landscape"),
        }
