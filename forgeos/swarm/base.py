"""Base agent for the film swarm."""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from forgeos.swarm.bus import Message, MessageBus


class BaseAgent(ABC):
    name: str = "base"
    subscriptions: List[str] = []

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self.log = logging.getLogger("swarm.%s" % self.name)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        for topic in self.subscriptions + ["swarm.command", "swarm.shutdown"]:
            bus.subscribe(topic, self._on_message)

    def _on_message(self, msg: Message) -> None:
        if msg.topic == "swarm.shutdown":
            self._stop.set()
            return
        if msg.topic == "swarm.command" and msg.payload.get("target") not in (None, self.name, "*"):
            return
        try:
            self.on_message(msg)
        except Exception as exc:  # noqa: BLE001
            self.emit("swarm.error", {"error": str(exc), "agent": self.name})

    def emit(self, topic: str, payload: Optional[Dict[str, Any]] = None) -> Message:
        return self.bus.emit(topic, self.name, payload or {})

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="agent-%s" % self.name, daemon=True)
        self._thread.start()
        self.emit("swarm.agent.up", {"agent": self.name})

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _loop(self) -> None:
        self.setup()
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001
                self.emit("swarm.error", {"error": str(exc), "agent": self.name, "where": "tick"})
            time.sleep(self.interval_s())

    def interval_s(self) -> float:
        return 1.0

    def setup(self) -> None:
        pass

    def on_message(self, msg: Message) -> None:
        pass

    @abstractmethod
    def tick(self) -> None:
        ...
