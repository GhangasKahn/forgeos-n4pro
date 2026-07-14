"""Film swarm orchestrator — boots agents and keeps them talking."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import List, Optional

from forgeos.swarm.agents import (
    AdbAgent,
    ArchiveAgent,
    CaptureAgent,
    CommsAgent,
    DirectorAgent,
    OpticsAgent,
    PrinterSenseAgent,
)
from forgeos.swarm.base import BaseAgent
from forgeos.swarm.bus import MessageBus

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "film_swarm"

log = logging.getLogger("swarm.orch")


class FilmSwarm:
    def __init__(
        self,
        phone_url: str = "http://192.168.1.250:8080",
        moonraker: str = "http://192.168.1.178:7125",
        adb_serial: Optional[str] = None,
    ) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        self.bus = MessageBus(log_path=OUT / "bus.jsonl")
        self.agents: List[BaseAgent] = [
            CommsAgent(self.bus),
            CaptureAgent(self.bus, phone_url),
            OpticsAgent(self.bus, phone_url),
            AdbAgent(self.bus, serial=adb_serial),
            PrinterSenseAgent(self.bus, moonraker=moonraker),
            ArchiveAgent(self.bus),
            DirectorAgent(self.bus),
        ]
        self.phone_url = phone_url

    def start(self) -> None:
        log.info("Starting film swarm (%d agents) phone=%s", len(self.agents), self.phone_url)
        for a in self.agents:
            a.start()
            time.sleep(0.05)
        self.bus.emit(
            "swarm.started",
            "orchestrator",
            {"agents": [a.name for a in self.agents], "phone": self.phone_url},
        )

    def stop(self) -> None:
        self.bus.emit("swarm.shutdown", "orchestrator", {})
        for a in self.agents:
            a.stop()
        log.info("swarm stopped")

    def command(self, cmd: str, **payload) -> None:
        self.bus.emit("swarm.command", "orchestrator", {"cmd": cmd, "target": "*", **payload})

    def run_forever(self) -> None:
        self.start()
        try:
            while True:
                time.sleep(1.0)
                # heartbeat file
                (OUT / "SWARM_LIVE").write_text(
                    "OK %s agents=%s\n"
                    % (time.strftime("%H:%M:%S"), ",".join(a.name for a in self.agents)),
                    encoding="utf-8",
                )
        except KeyboardInterrupt:
            self.stop()
