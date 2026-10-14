# Throwable explosions and four status effects (local 0.40.0)

Supported throwable damage targets expose four status slots, each with a status
type and strength. They use the same semantic status names as weapon damage:
`fire`, `gas`, `stun_small`, and so on. Inspect `target:describe().fields` for each
slot's default, allowed values and shared scope. `none` clears a slot.

| Target | Field prefix | Applies to |
| --- | --- | --- |
| `hd2.throwable(name):explosion()` | `explosion.damage.` | The main explosion's damage hits |
| `hd2.throwable('K-2 Throwing Knife'):damage()` | `damage.` | The knife's direct hit |
| `hd2.throwable(name):shrapnel()` | `damage.` | Linked shrapnel damage hits |
| `hd2.throwable('G-7 Pineapple'):bomblets()` | `damage.` | Bomblet direct-hit damage |
| `hd2.throwable('G-7 Pineapple'):bomblets():explosion()` | `explosion.damage.` | Bomblet explosion damage hits |

Append `status_1_type` / `status_1_strength` through `status_4_type` /
`status_4_strength` to the prefix. Twenty-four reviewed damage targets expose
all eight controls. Smoke items without a linked DamageInfo are not given a
fictional damage target, and the shield grenade's unverified explosion stays
read-only. The knife still has no explosion target.

```lua
local hd2 = require('mods/skyeshade/hd2runtime')
hd2.ensure({transaction={
    id='he-four-effects',
    target=hd2.throwable('G-12 High Explosive'):explosion(),
    allow_shared=true,
    allow_unverified_effect=true,
    changes={
        {field='explosion.damage.status_1_type', expect='none', value='fire'},
        {field='explosion.damage.status_1_strength', expect=0, value=1},
        {field='explosion.damage.status_2_type', expect='none', value='gas'},
        {field='explosion.damage.status_2_strength', expect=0, value=1},
        {field='explosion.damage.status_3_type', expect='none', value='stun_small'},
        {field='explosion.damage.status_3_strength', expect=0, value=1},
        {field='explosion.damage.status_4_type', expect='none', value='poison'},
        {field='explosion.damage.status_4_strength', expect=0, value=1},
    },
}})
```

Slots stay packed from 1: slot 4 requires slots 1–3 to hold statuses. A transaction
or one composition-plan phase is checked as a complete resulting set, so all
four can be attached together, regardless of operation order. Clear later slots
first, or clear several together in one transaction. Expected values always
refer to the reviewed native defaults, as with other Runtime fields.

Status strength is an effect parameter, not necessarily duration or damage.
Receiver immunity and the status's own rules still apply. Four assigned slots
do not guarantee four visible or independently stacking effects on every enemy.
These slots belong to the damage hit; they do not create smoke volumes, alter
Thermite's timed attachment pulses, or change every source of a status globally.

Existing named `:status_effect(...)` targets remain available for their original
strength and shared duration. A duration belongs to a global status definition;
swapping a slot's type does not retarget the old named duration control.

## Editor

Open **Weapons > Throwables**, choose the item, and expand the relevant damage
target's **Status** section. Pick Status 1 before Status 2, and continue through
Status 4. Each has its own strength. Presets stage slots in order; Apply waits
for earlier slots; Reset to an originally empty slot also resets later edits.
Lua export combines each target's status edits into one transaction.

Previously saved named-strength keys still resolve, but the editor displays one
strength control per slot. Main explosions, shrapnel and child explosions can
share a DamageInfo row; editing one then affects every consumer of that row.

The **Detonation** section also exposes `throwable.arming_delay` for all 22
explosives, through `hd2.throwable(name):detonation()`. It accepts 0–120 seconds,
retains each item's native default, and does not change detonation mode. Existing
fuse restrictions, explosion radii, damage, penetration, forces, shrapnel counts
and bomblet explosion controls remain in place.

## Validation

All 855 writable throwable fields pass retained-memory baseline, changed-write,
inverse, conflict and bounds checks. Separate scenarios apply four types and
strengths to five damage paths, validate reverse-order plans, clear both existing
Gas statuses together, and reject gaps and changed native status identities.
Editor tests cover staging, apply, dependent reset, export, saved keys and rendering.
These are offline checks; changed gameplay effects have not been tested in game.
