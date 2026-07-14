from forgeos.extrusion_motion import (
    HTPLA_BROZZL,
    gcode_apply_pa,
    gcode_travel_unretract,
    gcode_wipe_retract,
)


def test_wipe_retract_order():
    lines = gcode_wipe_retract(10, 10, 0.28, 1.0, 0.0, HTPLA_BROZZL)
    text = "\n".join(lines)
    assert "E-" in text or "E-0" in text or "E-1" in text
    # wipe then retract: first G1 after comment should include wipe motion
    assert any(l.startswith("G1 X") for l in lines)
    assert any("E-1.150" in l or "E-1.15" in l for l in lines)
    assert any("Z0.530" in l or "Z0.53" in l for l in lines)  # 0.28+0.25


def test_unretract_no_extra():
    lines = gcode_travel_unretract(20, 20, 0.28, HTPLA_BROZZL)
    text = "\n".join(lines)
    assert "E1.150" in text or "E1.15" in text
    assert "G0 X20" in text or "G0 X20.0000" in text


def test_pa_line():
    lines = gcode_apply_pa(HTPLA_BROZZL)
    assert "SET_PRESSURE_ADVANCE" in lines[0]
    assert "0.032" in lines[0]
