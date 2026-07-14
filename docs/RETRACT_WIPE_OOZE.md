# Retraction + nozzle wipe (stop hanging filament)

## Why the tip drools

After a path ends, pressurized melt remains in the Brozzl melt zone.  
If you only travel (or unretract with “extra prime”), a **whisker hangs** and then strings.

## Engineered sequence

```text
1. Wipe  ~1.4 mm backward along last bead  (scrapes tip, tiny E-)
2. Retract 1.15 mm @ 40 mm/s             (pull melt back)
3. Z-hop   0.25 mm
4. Travel  fast
5. Drop Z
6. Unretract 1.15 mm @ 30 mm/s           (NO extra prime)
```

Also:
- **Pressure Advance ~0.032** (smooth 0.03) — less corner pressure / ooze  
- **Nozzle ~213 °C** on PEX — less idle drool than 220+  
- Start macro: prime **2.5 mm** then **`FORGE_TIP_CLEAN`** (full retract)

## Stack defaults (Protopasta HTPLA + Brozzl + PEX)

| Param | Value |
|---|---|
| Retract | 1.15 mm |
| Retract speed | 40 mm/s |
| Unretract speed | 30 mm/s |
| Extra unretract | **0** |
| Wipe | 1.4 mm @ 80 mm/s |
| Z-hop | 0.25 mm |
| PA | 0.032 |

## Macros

```gcode
FORGE_SET_RETRACT LENGTH=1.15 SPEED=40 WIPE=1.4 ZHOP=0.25
FORGE_SET_PA PA=0.032 SMOOTH=0.03
FORGE_TIP_CLEAN
FORGE_RETRACT
FORGE_UNRETRACT
```

## If still hanging

1. `FORGE_SET_RETRACT LENGTH=1.30` (don’t jump past ~1.5 on geared — grind risk)  
2. Drop nozzle 2–3 °C: `FORGE_APPLY_ENV_TARGETS ... NOZ=210`  
3. Dry filament (basement moisture amplifies ooze)  
4. Confirm Z squish (high Z makes strings drag into whiskers)
