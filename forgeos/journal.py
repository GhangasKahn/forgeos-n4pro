"""SQLite experiment journal — every change and measurement is recorded."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    sku TEXT NOT NULL,
    part_class TEXT,
    recipe TEXT,
    duration_s REAL,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    print_id INTEGER,
    metric TEXT NOT NULL,
    nominal_mm REAL,
    measured_mm REAL,
    error_mm REAL,
    FOREIGN KEY(print_id) REFERENCES prints(id)
);
CREATE TABLE IF NOT EXISTS pack_promotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    sku TEXT NOT NULL,
    recipe TEXT NOT NULL,
    j_score REAL,
    feasible INTEGER NOT NULL,
    payload TEXT NOT NULL
);
"""


@dataclass
class Journal:
    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def log_event(self, kind: str, payload: Dict[str, Any]) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO events(ts, kind, payload) VALUES (?, ?, ?)",
                (time.time(), kind, json.dumps(payload, sort_keys=True)),
            )
            return int(cur.lastrowid)

    def record_print(
        self,
        sku: str,
        part_class: str,
        recipe: str,
        duration_s: Optional[float] = None,
        notes: str = "",
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO prints(ts, sku, part_class, recipe, duration_s, notes) VALUES (?,?,?,?,?,?)",
                (time.time(), sku, part_class, recipe, duration_s, notes),
            )
            return int(cur.lastrowid)

    def record_measurement(
        self,
        print_id: Optional[int],
        metric: str,
        nominal_mm: float,
        measured_mm: float,
    ) -> int:
        err = float(measured_mm) - float(nominal_mm)
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO measurements(ts, print_id, metric, nominal_mm, measured_mm, error_mm) VALUES (?,?,?,?,?,?)",
                (time.time(), print_id, metric, float(nominal_mm), float(measured_mm), err),
            )
            return int(cur.lastrowid)

    def promote_pack(
        self,
        sku: str,
        recipe: str,
        j_score: float,
        feasible: bool,
        payload: Dict[str, Any],
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO pack_promotions(ts, sku, recipe, j_score, feasible, payload) VALUES (?,?,?,?,?,?)",
                (
                    time.time(),
                    sku,
                    recipe,
                    float(j_score),
                    1 if feasible else 0,
                    json.dumps(payload, sort_keys=True),
                ),
            )
            return int(cur.lastrowid)

    def recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, ts, kind, payload FROM events ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "ts": r["ts"],
                    "kind": r["kind"],
                    "payload": json.loads(r["payload"]),
                }
            )
        return out
