# Knife launch and melee authoring (local 0.40.0)

The local Runtime exposes launch tuning on all 23 armory throwables and melee
source tuning for 112 weapons, including dedicated melee weapons and gun bashes.
Use `ThrowableAuthoringCapabilities.json` and `MeleeAuthoringCapabilities.json`
for names, defaults, bounds, shared consumers and available targets.

## Throwing knife

`hd2.throwable('K-2 Throwing Knife'):flight()` exposes:

| Field suffix under `hd2.fields.throwable` | Knife default | Meaning |
| --- | --- | --- |
| `launch_distance_min` | 0.1 | Lower distance calibration in the launch calculation |
| `launch_distance_max` | 20 | Upper distance calibration in the launch calculation |
| `launch_speed_override` | 0 | Positive values bypass the launch curve; 0 restores the curve |
| `forward_strength_bonus` | 0.4 | Added to strength when movement points forward |
| `backward_strength_penalty` | 0.2 | Subtracted from strength when movement points backward |
| `spin_min_x`, `spin_max_x` | -55 | Minimum and maximum angular velocity X |
| `spin_min_y`, `spin_max_y` | 0 | Minimum and maximum angular velocity Y |
| `spin_min_z`, `spin_max_z` | 0 | Minimum and maximum angular velocity Z |

Without a positive speed override, the native launch calculation is:

```text
speed = sqrt(18 * max(0, min_distance + (max_distance - min_distance) * adjusted_strength))
```

Movement adjustments apply when the caller enables them. Strength is not clamped
inside this calculation. For the knife, input strengths 0, 0.5 and 1 produce
approximately 1.34, 13.45 and 18.97 speed units before later physics. These are
calculation examples, not measured trajectories or a mapping from button-hold time.
The distance bounds are calibration parameters, not speed values or guaranteed range.

Spin vectors retain native angular-velocity units and orientation conventions.
The native flags must allow spin, and a zero minimum vector skips spin setup.
For the knife, set both X limits to 0 to remove its authored spin; keep lower and
upper limits consistent when experimenting. The flight target affects future
throws. It does not expose gravity, drag or an in-flight speed/time curve.

```lua
local hd2 = require('mods/skyeshade/hd2runtime')
hd2.patch({id='knife-launch-speed',
    target=hd2.throwable('K-2 Throwing Knife'):flight(),
    field=hd2.fields.throwable.launch_speed_override,
    expect=0, value=50, allow_unverified_effect=true})
```

Existing inventory and `:damage()` controls remain available. This build's knife
defaults are 300 standard / 150 durable damage, penetration 3, demolition 10,
stagger 35, push 5, and inventory counts 10 starting / 20 maximum / 20 from supply.

## Melee weapons and gun bashes

```lua
local names = hd2.melee.names()
local saber = hd2.melee('CQC-2 Saber')
local summary = saber:describe()
local volumes = saber:zones()
local volume = saber:zone(1) -- also :zone('zone_1')

hd2.patch({id='saber-volume', target=volume,
    field=hd2.fields.melee.volume_z, expect=0.85, value=1.5,
    allow_shared=true, allow_unverified_effect=true})
```

Each hit volume exposes `melee.volume_x/y/z`, `melee.offset_x/y/z`, and
`melee.repeat_hit_interval`. Dimensions and offsets follow an animated bone:
absolute reach also depends on the animation and shape, and an individual axis
may not affect every shape. These are native volume parameters; they are not
promised sphere radii, box half-extents or a single maximum reach in metres.
The source template is copied at attack activation, so the next attack uses edits.

Repeat-hit interval 0 retains one-hit-per-activation behavior. The chainsaw uses
0.1 seconds. This field resets hit memory while the attack remains active; it
does not change swing animation speed or the delay before another attack.

Each volume also exposes standard and durable damage, all four penetration
values, demolition force, stagger and push through the usual `damage.*` fields.
Damage definitions are shared with every other attack using the same definition.
Armor passives may further modify damage at runtime.

Dedicated melee weapons additionally expose `melee.stamina_cost` on the root
target. It is a fraction of the stamina bar, not a range value. For example,
the Breaching Hammer defaults to 0.05 per attack. Root targets for gun bashes
have no proven stamina override; use their zones instead.

The 112 entries refer to 15 unique hit-volume templates. Gun-bash geometry is
widely shared, and changing one can affect many guns. `:describe()` and the
editor identify known weapon consumers; `allow_shared=true` is required.
Zone numbers identify reviewed templates, not invented animation or stance names.
The knife has no proven item-local melee override, so its throwable record is
not presented as a unique knife-bash range control.

## Editor and validation

Use **Weapons > Throwables > K-2 Throwing Knife > Flight** for launch controls,
and the **Melee** group on each primary, secondary or support weapon page for
melee geometry, damage and stamina. The separate melee catalogue has been removed.
Existing melee preset keys continue to resolve to their weapon pages.
Apply, Reset, presets and Lua export use the normal editor flows.

The retained-memory validator resolves all 253 flight field instances and all
3,497 melee field instances. It exercises 39 reversible writes, adjacent-byte
preservation, conflicts, altered ownership links, native instruction/template
guards, and public patch/transaction/plan/ensure paths. Editor tests cover apply,
reset, export, shared identities, reopening saved rows and rendering.

This is offline validation. Changed gameplay effects still require in-game
testing; all new fields require `allow_unverified_effect=true`.
