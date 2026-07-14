"""Load environment YAML profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from forgeos.environment.models import AmbientReading, EnclosureMode, EnvironmentProfile


class EnvironmentLoadError(Exception):
    pass


def load_environment_profile(path: Path) -> EnvironmentProfile:
    path = Path(path)
    if not path.is_file():
        raise EnvironmentLoadError("missing profile: %s" % path)
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise EnvironmentLoadError("profile must be mapping")
    amb = data.get("ambient") or {}
    enc_raw = str(amb.get("enclosure", "open")).lower()
    try:
        enc = EnclosureMode(enc_raw)
    except ValueError:
        enc = EnclosureMode.OPEN
    reading = AmbientReading(
        temperature_c=float(amb.get("temperature_c", 22.0)),
        rh_percent=float(amb.get("rh_percent", 40.0)),
        enclosure=enc,
        chamber_temperature_c=(
            float(amb["chamber_temperature_c"])
            if amb.get("chamber_temperature_c") is not None
            else None
        ),
        draft_level=float(amb.get("draft_level", 0.0)),
        source=str(amb.get("source", "profile")),
        notes=str(amb.get("notes", "")),
    )
    return EnvironmentProfile(
        name=str(data.get("name", path.stem)),
        description=str(data.get("description", "")),
        tags=[str(t) for t in list(data.get("tags", []))],
        ambient=reading,
    )


def load_all_profiles(directory: Path) -> Dict[str, EnvironmentProfile]:
    directory = Path(directory)
    out: Dict[str, EnvironmentProfile] = {}
    for p in sorted(directory.glob("*.yaml")):
        prof = load_environment_profile(p)
        out[prof.name] = prof
    return out


def default_environments_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "environments"
