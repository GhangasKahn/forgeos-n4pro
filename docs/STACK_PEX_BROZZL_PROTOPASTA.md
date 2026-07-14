# Optimized stack: Wham Bam PEX + Brozzl Ni-Cu + Protopasta

Your shop-preferred stack for the Neptune 4 Pro.

## Hardware

| Component | Choice | Why it matters |
|---|---|---|
| **Surface** | Wham Bam **PEX** flex sheet | Strong PLA/HTPLA adhesion when clean; flex-release when cool; no glue needed |
| **Nozzle** | **[Brozzl Plated Copper 0.4 mm](https://www.brozzl.com/products/plated-copper-nozzles/)** | Copper core = very high heat transfer; plating = durability/release; **soft core** — not for CF |
| **Filament** | **Protopasta HTPLA** (primary) | Semi-crystalline HTPLA; best interlayer fusion when printed hot enough; optional anneal |

## Material science (short)

### Protopasta HTPLA
- Engineered PLA that can be **annealed** (~110 °C) for higher heat resistance  
- Wants **hotter melt** than bargain PLA (shop seed **215 °C** on Brozzl)  
- **Moisture** → stringing, zits, weak walls (basement RH is a real factor)  
- Dimensional change after anneal → use scale compensation after G6

### Wham Bam PEX
- Powder-coat style PEI-ish behavior: **clean + correct temp + Z squish**  
- HTPLA bed seed on PEX: **65 °C** (range 60–70)  
- Too cool → lift; too hot → grip/release issues  
- Clean with **IPA** (or mild soap). Avoid acetone on coating  
- Remove part by **flexing when cool** (~&lt;40 °C), don’t pry hot  

### Brozzl Plated Copper 0.4 mm
Product: [brozzl.com plated copper nozzles](https://www.brozzl.com/products/plated-copper-nozzles/)

- **Copper core** → excellent thermal conductivity (melt responds faster / “runs hotter” at the same set-point than brass)  
- **Plating** → better surface durability/release than bare copper; still **not** hardened steel  
- Implication for Protopasta HTPLA: seed nozzle **~3 °C cooler** than brass-era profiles to cut stringing + hanging whiskers  
- Slightly **longer retract** bias (melt zone stays soft longer)  
- **Not abrasive-rated** → HTPLA-CF requires **hardened ≥0.5 mm** (preflight enforces)  

## Resolved process seeds (basement ~14 °C)

From `python3 scripts/print_stack_profile.py`:

| Param | HTPLA + PEX + Brozzl 0.4 |
|---|---|
| Bed | **65 °C** (dual zones) |
| Nozzle | **~210–213 °C** on plated copper (copper runs hot; raise toward 215–218 only if layers weak) |
| Soak | **~5–7 min** cold shop |
| First layer | **0.28 mm**, **18 mm/s**, flow **~1.06**, fan **0** |
| Retract | **~0.9 mm** @ 35 mm/s |
| PA seed | **~0.028** (×0.95 Brozzl bias → ~0.027) |
| Brim | **on** for coupons/jigs |
| Glue | **off** on clean PEX |
| Z seed | **−0.10 mm** live adjust (babystep from there) |

## Console setup

```gcode
FORGE_SET_SURFACE TYPE=pex NAME="WhamBam PEX"
FORGE_SET_NOZZLE TYPE=brozzl_plated_copper DIA=0.4
FORGE_SET_MATERIAL SKU=protopasta_htpla
FORGE_SET_Z_ADJUST Z=-0.10
FORGE_APPLY_ENV_TARGETS BED=65 NOZ=212 SOAK=6
FORGE_SET_RETRACT LENGTH=1.20 SPEED=40 WIPE=1.4 ZHOP=0.25
FORGE_SET_PA PA=0.032 SMOOTH=0.03
FORGE_PREFLIGHT
```

## First-layer checklist on PEX

1. IPA-clean sheet  
2. `FORGE_SET_Z_ADJUST` then **Z-tune square**  
3. Lines should be **squished and stuck**, not round beads  
4. `FORGE_BABY_DOWN` if high/stringy; `FORGE_BABY_UP` if scraping  
5. Then G3 bar v2 / production prints  

## CF exception

Protopasta **HTPLA-CF** + Brozzl Ni-Cu = **refuse**. Swap to hardened nozzle first.
