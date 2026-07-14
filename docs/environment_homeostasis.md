# Environmental capability & homeostasis

Your Neptune lives in a **basement**: cold, often humid, drafts, optional enclosure.  
ForgeOS treats that as a first-class control domain — not “PLA defaults from a 22 °C lab.”

## What “self-anneal to homeostasis” means

Two different “anneals”:

| Kind | Meaning in ForgeOS |
|---|---|
| **Process anneal** | HTPLA oven heat-treat after print (material science) |
| **Control anneal** | Parameters slowly settle toward a stable attractor for *this* environment bin |

Homeostasis = for the current **(temp bin × RH bin × enclosure × material)**, settings stop thrashing and converge on what has produced good quality scores.

## Inputs

| Input | How you provide it |
|---|---|
| Ambient °C | `$10 thermo-hygrometer` → `FORGE_SET_AMBIENT TEMP=14 RH=65` or YAML profile |
| RH % | same |
| Enclosure | `FORGE_SET_ENCLOSURE MODE=open\|ajar\|enclosed` |
| Draft | optional 0..1 |
| Filament moisture risk | soft-sensor (nozzle droop/power) + RH prior |
| Chamber °C | optional later (sensor) |

No enclosure sensor required. Profiles cover open vs enclosed basements.

## Phases

### BEFORE (pre-print)
- Dual-bed heat with **environment-scaled soak** (cold/humid → longer)
- Slightly higher bed for adhesion in cold shops
- Precision mesh when cold/humid stress high
- Slower first-layer speed factor
- Moisture prior warning if RH high

### DURING (print)
- Nozzle/bed/fan/flow/speed factors from ambient + enclosure + moisture soft-sensor
- Enclosure can **recover speed** vs open cold draft
- Open humid basement → more conservative volumetric flow

### AFTER (cool-down)
- **Cold open basement:** staged cool (hold bed ~45 °C 2 min) to reduce snap-warp / CF stress
- **Enclosed:** passive cool, open door only after bed cools if warping
- Mild shops: simple passive off

## Environment bins

`cold_dry · cold_humid · mild · warm_dry · warm_humid · hot`  
combined with `open|ajar|enclosed` and material SKU → homeostasis memory key.

Basement default profile: **~14 °C / 65 % RH / open** → typically `cold_humid|open|protopasta_htpla`.

## Learning loop

```text
plan BEFORE/DURING from physics policy
  → blend toward memory for this bin (homeostasis)
  → print
  → score quality
  → EMA-update memory (success anneals in; failure slows + lengthens soak)
```

Over N successful basement prints, soak/temps/speeds **self-stabilize** without you retuning every day.

## Files

| Path | Role |
|---|---|
| `forgeos/environment/policy.py` | before/during/after physics policy |
| `forgeos/environment/homeostasis.py` | self-annealing memory |
| `environments/*.yaml` | basement / garage profiles |
| `klipper/overlays/forge_environment.cfg` | macros |
| `scripts/env_plan.py` | print a session plan on your Mac |

## Operator quick start

```gcode
FORGE_SET_AMBIENT TEMP=14 RH=65 DRAFT=0.3
FORGE_SET_ENCLOSURE MODE=open
FORGE_APPLY_ENV_TARGETS BED=63 NOZ=217 SOAK=7
FORGE_PRINT_START_ENV
```

Or generate targets from Python:

```bash
python3 scripts/env_plan.py --profile environments/basement_default.yaml
```

## Zero-trust note

Environment automation still cannot violate safety envelopes or dimensional gates.  
A humid cold day that needs slower prints **fails G5 speed claims** until gates re-pass — honesty over marketing.
