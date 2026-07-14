#!/usr/bin/env python3
"""Patch printer.cfg [probe] + [bed_mesh] for fast accurate mesh.

Run ON the printer host (or via ssh):
  python3 scripts/patch_mesh_speed_printer.py /home/mks/printer_data/config/printer.cfg

Creates .bak alongside. Does not touch #*# SAVE_CONFIG block values except
leaving them alone (profile points stay).
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path


PROBE_REPLACEMENTS = {
    r"(?m)^(speed:\s*)[0-9.]+(\s*)$": r"\g<1>10.0\2",
    r"(?m)^(samples:\s*)[0-9]+(\s*)$": r"\g<1>2\2",
    r"(?m)^(sample_retract_dist:\s*)[0-9.]+(\s*)$": r"\g<1>2.0\2",
    r"(?m)^(samples_tolerance:\s*)[0-9.]+(\s*)$": r"\g<1>0.035\2",
    r"(?m)^(samples_tolerance_retries:\s*)[0-9]+(\s*)$": r"\g<1>2\2",
}

MESH_REPLACEMENTS = {
    r"(?m)^(speed:\s*)[0-9.]+(\s*)$": r"\g<1>200\2",
    r"(?m)^(horizontal_move_z:\s*)[0-9.]+(\s*)$": r"\g<1>3\2",
    r"(?m)^(probe_count:\s*)[0-9,\s]+$": r"probe_count: 7, 7",
}


def patch_section(text: str, section: str, rules: dict) -> str:
    # Only patch before SAVE_CONFIG marker
    if "#*#" in text:
        head, tail = text.split("#*#", 1)
        tail = "#*#" + tail
    else:
        head, tail = text, ""

    pat = re.compile(
        r"(\[" + re.escape(section) + r"\][^\[]*)",
        re.DOTALL | re.IGNORECASE,
    )

    def sub_block(m: re.Match) -> str:
        block = m.group(1)
        for rp, repl in rules.items():
            block = re.sub(rp, repl, block)
        # inject lift_speed if probe and missing
        if section == "probe" and "lift_speed" not in block:
            block = block.rstrip() + "\nlift_speed: 15.0\n"
        return block

    new_head, n = pat.subn(sub_block, head, count=1)
    if n != 1:
        raise SystemExit("section [%s] not found or multiple" % section)
    return new_head + tail


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "printer.cfg")
    raw = path.read_text(encoding="utf-8", errors="replace")
    bak = path.with_suffix(path.suffix + ".bak_mesh_speed")
    shutil.copy2(path, bak)
    out = patch_section(raw, "probe", PROBE_REPLACEMENTS)
    out = patch_section(out, "bed_mesh", MESH_REPLACEMENTS)
    path.write_text(out, encoding="utf-8")
    print("patched", path)
    print("backup ", bak)
    print("probe: speed 10, samples 2, retract 2, tol 0.035")
    print("mesh:  speed 200, hop Z 3, default count 7x7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
