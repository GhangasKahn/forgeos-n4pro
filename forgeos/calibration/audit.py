"""Static consistency checks between machine truth and Klipper configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, List

from forgeos.calibration.profile import MachineProfile


@dataclass(frozen=True)
class AuditFinding:
    level: str
    message: str


def _parse_sections(text: str) -> Dict[str, Dict[str, str]]:
    sections: Dict[str, Dict[str, str]] = {}
    current = ""
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        match = re.fullmatch(r"\[([^\]]+)\]", line)
        if match:
            current = match.group(1).strip()
            sections.setdefault(current, {})
            continue
        if current and ":" in line:
            key, value = line.split(":", 1)
            sections[current][key.strip()] = value.strip()
    return sections


def audit_klipper_base(profile: MachineProfile, config_path: Path) -> List[AuditFinding]:
    if not config_path.is_file():
        return [AuditFinding("error", "Klipper base not found: %s" % config_path)]
    sections = _parse_sections(config_path.read_text(encoding="utf-8"))
    findings: List[AuditFinding] = []
    expected = {
        ("printer", "max_velocity"): profile.motion["max_velocity_mm_s"],
        ("printer", "max_accel"): profile.motion["max_accel_mm_s2"],
        ("printer", "max_z_velocity"): profile.motion["max_z_velocity_mm_s"],
        ("printer", "max_z_accel"): profile.motion["max_z_accel_mm_s2"],
        ("probe", "x_offset"): profile.probe["offset_xy_mm"][0],
        ("probe", "y_offset"): profile.probe["offset_xy_mm"][1],
    }
    for (section, key), wanted in expected.items():
        actual = sections.get(section, {}).get(key)
        if actual is None:
            findings.append(AuditFinding("error", "[%s] missing %s" % (section, key)))
            continue
        try:
            if abs(float(actual) - float(wanted)) > 1e-6:
                findings.append(
                    AuditFinding("error", "[%s] %s=%s, profile requires %s" % (section, key, actual, wanted))
                )
        except ValueError:
            findings.append(AuditFinding("error", "[%s] %s is not numeric: %s" % (section, key, actual)))
    required = ("heater_bed", "heater_generic heater_bed_outer", "probe", "bed_mesh", "safe_z_home")
    for section in required:
        if section not in sections:
            findings.append(AuditFinding("error", "required section missing: [%s]" % section))
    z_offset = sections.get("probe", {}).get("z_offset")
    if z_offset is not None:
        findings.append(
            AuditFinding(
                "warning",
                "[probe] z_offset is a seed only; use PROBE_CALIBRATE/SAVE_CONFIG on the physical printer",
            )
        )
    return findings
