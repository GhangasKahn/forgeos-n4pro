; FORGE_EXTRUDE_CAL — mark filament at 120 mm above entry; command 100 mm
M83
G92 E0
M104 S214
TEMPERATURE_WAIT SENSOR=extruder MINIMUM=212 MAXIMUM=219
G1 E100.00 F60
M104 S0
RESPOND MSG="Measure remaining mark distance; actual = 120 - leftover"
