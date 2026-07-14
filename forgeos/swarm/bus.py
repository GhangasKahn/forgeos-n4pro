"""Inter-agent message bus — in-process pub/sub + durable event log."""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional


@dataclass
class Message:
    topic: str
    sender: str
    payload: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: float = field(default_factory=time.time)
    reply_to: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


Handler = Callable[[Message], None]


class MessageBus:
    """Thread-safe pub/sub with optional JSONL persistence."""

    def __init__(self, log_path: Optional[Path] = None, history: int = 500) -> None:
        self._lock = threading.RLock()
        self._subs: Dict[str, List[Handler]] = defaultdict(list)
        self._history: Deque[Message] = deque(maxlen=history)
        self._log_path = log_path
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)

    def subscribe(self, topic: str, handler: Handler) -> None:
        with self._lock:
            self._subs[topic].append(handler)
            # wildcard
            if topic != "*":
                pass

    def publish(self, msg: Message) -> None:
        with self._lock:
            self._history.append(msg)
            handlers = list(self._subs.get(msg.topic, []))
            handlers += list(self._subs.get("*", []))
            log_path = self._log_path
        if log_path:
            try:
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(msg.as_dict()) + "\n")
            except Exception:
                pass
        for h in handlers:
            try:
                h(msg)
            except Exception as exc:  # noqa: BLE001
                # don't kill swarm on one bad handler
                err = Message(
                    topic="swarm.error",
                    sender="bus",
                    payload={"error": str(exc), "from": msg.sender, "topic": msg.topic},
                )
                with self._lock:
                    self._history.append(err)

    def emit(
        self,
        topic: str,
        sender: str,
        payload: Optional[Dict[str, Any]] = None,
        reply_to: Optional[str] = None,
    ) -> Message:
        msg = Message(topic=topic, sender=sender, payload=payload or {}, reply_to=reply_to)
        self.publish(msg)
        return msg

    def recent(self, n: int = 20, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._history)
        if topic:
            items = [m for m in items if m.topic == topic]
        return [m.as_dict() for m in items[-n:]]
