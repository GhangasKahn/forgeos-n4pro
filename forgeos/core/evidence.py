"""Evidence writers — every live claim must leave a disk artifact."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"


def _ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def write_evidence(
    name: str,
    payload: Dict[str, Any],
    *,
    directory: Optional[Union[str, Path]] = None,
    stamp: bool = True,
) -> Path:
    """Write JSON evidence under artifacts/. Returns path written."""
    d = Path(directory) if directory else ARTIFACTS
    d.mkdir(parents=True, exist_ok=True)
    if stamp and not name.endswith(".json"):
        fname = "%s_%s.json" % (name, _ts())
    elif stamp and name.endswith(".json") and "_" not in Path(name).stem[-15:]:
        stem = Path(name).stem
        fname = "%s_%s.json" % (stem, _ts())
    else:
        fname = name if name.endswith(".json") else name + ".json"
    path = d / fname
    body = dict(payload)
    body.setdefault("written_at", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    path.write_text(json.dumps(body, indent=2, sort_keys=False) + "\n")
    return path


def append_jsonl(
    name: str,
    record: Dict[str, Any],
    *,
    directory: Optional[Union[str, Path]] = None,
) -> Path:
    """Append one JSON line to artifacts/<name>.jsonl (or absolute name)."""
    d = Path(directory) if directory else ARTIFACTS
    d.mkdir(parents=True, exist_ok=True)
    fname = name if name.endswith(".jsonl") else name + ".jsonl"
    path = d / fname
    rec = dict(record)
    rec.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    with path.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return path
