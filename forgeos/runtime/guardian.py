"""Protective runtime guardian — reliability floor under all four pillars.

Does NOT spam logs. State-change logging only.
"""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from forgeos.journal import Journal
from forgeos.moonraker_client import MoonrakerClient, MoonrakerError


@dataclass
class GuardianConfig:
    host: str = "127.0.0.1"
    port: int = 7125
    interval_s: float = 10.0
    min_disk_free_mb: float = 200.0
    journal_path: str = "artifacts/forgeos_journal.sqlite3"


class ForgeGuardian:
    def __init__(self, config: Optional[GuardianConfig] = None, journal: Optional[Journal] = None) -> None:
        self.config = config or GuardianConfig()
        self.client = MoonrakerClient(self.config.host, self.config.port)
        self.journal = journal or Journal(self.config.journal_path)
        self.log = logging.getLogger("forgeos.guardian")
        self._last_state: Optional[str] = None
        self._last_disk_warn = False

    def poll_once(self) -> Dict[str, Any]:
        disk = shutil.disk_usage("/")
        free_mb = disk.free / (1024.0 * 1024.0)
        ready = False
        state = "unreachable"
        try:
            info = self.client.printer_info().get("result", {})
            state = str(info.get("state", "unknown")).lower()
            ready = state == "ready"
        except MoonrakerError as exc:
            state = "error:%s" % exc

        result = {
            "state": state,
            "ready": ready,
            "disk_free_mb": round(free_mb, 1),
            "action": "ok",
        }

        if free_mb < self.config.min_disk_free_mb:
            result["action"] = "disk_low"
            if not self._last_disk_warn:
                self.log.warning("disk_free_mb=%.1f below %.1f", free_mb, self.config.min_disk_free_mb)
                self.journal.log_event("guardian_disk_low", result)
                self._last_disk_warn = True
        else:
            self._last_disk_warn = False

        if state != self._last_state:
            self.log.info("printer state %s -> %s", self._last_state, state)
            self.journal.log_event("guardian_state", result)
            self._last_state = state

        return result

    def run_forever(self) -> None:
        self.log.info("forgeos guardian starting config=%s", self.config)
        self.journal.log_event("guardian_start", {"config": self.config.__dict__})
        while True:
            try:
                self.poll_once()
            except Exception as exc:  # pragma: no cover
                self.log.exception("guardian poll error: %s", exc)
                self.journal.log_event("guardian_error", {"error": str(exc)})
            time.sleep(self.config.interval_s)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    ForgeGuardian().run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
