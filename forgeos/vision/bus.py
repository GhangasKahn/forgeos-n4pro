"""Moonraker bridge used by Jetson vision / adaptive services.

Thin compatibility wrapper around :class:`forgeos.moonraker_client.MoonrakerClient`.
Prefer importing ``MoonrakerClient`` directly in new code.
"""

from __future__ import annotations

from typing import Any, Dict, List

from forgeos.moonraker_client import MoonrakerClient, MoonrakerError


class MoonrakerBus(MoonrakerClient):
    """Legacy name kept so adaptive/vision imports keep working."""

    def __init__(self, base_url: str = "http://192.168.1.178:7125", timeout_s: float = 10.0) -> None:
        super().__init__(base_url=base_url, timeout_s=timeout_s)

    def printer_info(self) -> Dict[str, Any]:  # type: ignore[override]
        return self.printer_info_result()

    def objects_query(self, names: List[str]) -> Dict[str, Any]:  # type: ignore[override]
        return self.objects_status(names)


__all__ = ["MoonrakerBus", "MoonrakerClient", "MoonrakerError"]
