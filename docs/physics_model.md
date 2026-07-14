# Physics model (N4 Pro + Protopasta)

## Machine
- Cartesian bed-slinger style kinematics on Makerbase ZNP-K1
- Dual bed heaters: center + outer ring → gradient if soak skipped
- Inductive probe with XY offset → mesh only as good as mechanical truth + samples
- TMC2209 drivers: stealthchop quiet vs spreadcycle torque/speed tradeoff

## Speed without losing accuracy
- Input shaper raises **usable** accel (not marketing max)
- Pressure advance cleans corners at higher outer-wall speed
- Role-based velocity: spend time on mating faces; sprint infill/travel
- Volumetric flow ceiling is material-limited (CF lower)

## Accuracy stack
1. Mechanical: belts, eccentric nuts, probe Z, mesh
2. Thermal: dual-bed soak before mesh and first layer
3. Extrusion: flow + PA + density
4. Material process: anneal shrink compensation for HTPLA

## Quality
- Interlayer fusion: nozzle temp window for HTPLA (hotter than commodity PLA)
- First layer: soak + Z offset + slow first layer
- Abrasive wear: hardened nozzle mandatory for CF
