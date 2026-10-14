# Enemy, structure and spawn controls (0.40.0)

`hd2.enemy(name)` and `hd2.structure(name)` now include the expanded native
catalogue. Existing names still work; new named entities also accept their full
content path. `hd2.enemies({kind='structure', faction='illuminate'})` lists names.
Unnamed entries remain build-specific identities, not identified enemy species.

Descriptions also expose `displayName`, `fullDisplayName`, `gameName` (when available), `nameSource`,
and an optional `variantLabel`. These are English presentation labels recovered
from game text, reviewed objective context, or readable resource/model names.
They do not rename `name`, `className`, semantic IDs, aliases, or patch targets.
For example, `hd2.enemy('illuminate_dropship'):describe().displayName` is
`Warp Ship`; the target still uses `illuminate_dropship`. The game can reuse one
name for several variants, so display labels are not lookup keys.

Roster metadata includes the same presentation labels. Composition groups retain
their existing `candidates` and add parallel `candidateNames` for display.
Missing identities stay explicitly unidentified; model-derived labels do not
prove a specific enemy variant. These labels do not depend on live localization.

Use `hd2.enemies({component='HiveMind'})` or `{component='Bughole'}` to find
director and breach-controller entities even when their original paths are unknown.

All new controls are offline-proven and require `allow_unverified_effect=true`.
Shared component records, attack settings, and director targets also require
`allow_shared=true`. Use `:describe()` for the exact baseline, range, editability,
scope and lifecycle. The standard patch, transaction and ensure contracts apply.

```lua
local hd2 = require('mods/skyeshade/hd2runtime')
hd2.patch({id='larger-chargers', target=hd2.enemy('Charger'),
    field=hd2.fields.unit.scale_min, expect=1, value=1.5,
    allow_unverified_effect=true})

hd2.transaction({id='landed-ship-spawns', target=hd2.structure('il_spawner_ship'),
    allow_unverified_effect=true, changes={
        {field=hd2.fields.spawner.queue_limit, expect=4, value=8},
        {field=hd2.fields.spawner.batch_size, expect=2, value=4},
        {field=hd2.fields.spawner.release_delay, expect=4, value=6},
    }})

hd2.patch({id='jammer-range', target=hd2.structure('cy_stratagem_blocker'),
    field=hd2.fields.jammer.radius, expect=150, value=75,
    allow_unverified_effect=true})
```

## Entity fields and lifecycle

* `unit.scale_min`: uniform creation-time scale. Existing units are not resized.
  Physics, navigation clearance and hit geometry still need gameplay tests.
  `unit.scale_max` is an inspection lead, not a proven random-scale control.
* `spawner.*`: queue cap, batch/minimum counts, initial delay, refill/release
  delays, serialized delay, variance and alternate-roster selection. Queue/batch
  edits stay within 16 entries. These are pending selections, not living-enemy
  limits or a finite lifetime stock. Group hashes remain inspection-only.
* `hive.*`: progress, player-count and conditional multipliers on HiveMind
  entities. Player suffixes `_1` through `_4` mean player counts; progress
  suffixes `_1` through `_5` are the authored progress factors. Clock-rate
  multipliers speed countdowns up; duration multipliers lengthen them.
* `transport.*`: carrier grid dimensions and passenger footprints. Carrier
  dimensions support reductions up to their authored size; larger allocations
  are not proven. The flying Illuminate transport has 5 by 3 cells, not a fixed
  15 passengers. `:describe().transport` includes footprint-based bounds.
* `shield.*`: health, armor, radius and recharge controls. Radius zero selects
  actor geometry on the traced path. Landed ship mounted shields are distinct
  from the ship body and its door shield; `:describe().mountedEntities` lists
  known mounted target names.
* `jammer.radius`: a positive 3D radius. Zero/negative native values bypass the
  distance test, so new nonpositive writes are rejected. Set
  `jammer.initially_enabled` to 0 to change initialization; it does not switch
  off an already-existing jammer's independent enabled state.
* `breach.emission_radius`: the mapped bug-hole emission radius.
* Main/zone health, armor, durability, explosion share and death flags are
  available wherever mapped. Native sentinel values stay visible and read-only.
  Other recovered health/behavior aliases remain read-only when semantics are
  incomplete. Existing instances may hold private settings copies.
* Dev9 adds `entity.health_change_rate`, `entity.health_change_rate_disabled`,
  `entity.regeneration_cooldown`, `entity.regeneration_segments`,
  `entity.regeneration_change_rate`, and `entity.zone_bleedout_change_rate`.
  Rates integrate over elapsed time. The regeneration rate applies within an
  incomplete health segment; the disabled flag initializes instance state.
  Apply before new spawns; existing private copies and segment state may retain
  previous values. Unproven reward, mass and enum meanings remain read-only.

Zone selectors accept stable `zone_<slot>` IDs, numeric slots, or unambiguous
observed names. Duplicate names require a slot. Constructed spellings and hash
collisions are available in `nameCandidates`; they do not silently select a zone.

`:attacks()` includes the existing mounted weapon slots and `mapped_<n>` typed
references, including recursive mounts and arc/beam-to-damage links. Every mount,
component and settings link is re-read before writing. A reference can belong to
an ability that normal gameplay never executes. Shared rows can affect other
enemies, structures or player equipment.

## Difficulty, rosters and compositions

```lua
local difficulty = hd2.enemies.difficulty(10)
hd2.patch({id='difficulty-budget', target=difficulty,
    field=hd2.fields.difficulty.encounter_points, expect=600, value=450,
    allow_shared=true, allow_unverified_effect=true})

local compositions = hd2.enemies.compositions({faction='terminids', family=4})
local target = hd2.enemies.composition(compositions[1].id)
-- Inspect target:describe().fields before choosing expected values.

local rosters = hd2.enemies.rosters() -- all 191 rows across five rosters
local row = hd2.enemies.roster(rosters[1].id)
```

Source spawn writes require **Ship state**. They affect subsequent installation
or compilation, and do not rebuild a mission's already-compiled compositions.
Use an ensure if registration happens before the ship is ready.

`difficulty.*` exposes encounter/guardforce budgets and shared spawner cooldown.
`spawn.weight_1` through `_10` are absolute difficulty weights on one roster row.
`composition.*` exposes selection weight, cost multiplier, tech/player bounds,
populated group counts, authored override weights and bug-hole schedule timing.
Groups retain their enemy candidates. Family numbers identify eight authored
tables. The reviewed consumers are now labeled for patrol, map guard and reinforcement
roles; other families remain unresolved. Emission timing
is proven for bug holes, not every delivery mechanism.

`hd2.enemies.spawn_weight` retains its existing primary-roster multiplier API.
Zero weights suppress normal picks, but native positive-weight bypasses,
fallbacks, queued selections and directly authored squads remain. Neither API
claims a global enemy blacklist. Do not combine an absolute roster writer and
a multiplier writer on the same bytes; conflicts are rejected.

## Spawn tuning recipes (0.40.0)

These helpers return recipes; they do not write or run a background update loop.
Submit their transactions through `hd2.ensure`, or stage them in the Editor.
All multipliers accept 0.1 through 5 and calculate from reviewed defaults each
time, so applying 2x twice remains 2x. Apply aboard the ship before launch.

| Recipe | Native control | Meaning |
| --- | --- | --- |
| `spawn_multiplier(faction, n, 'patrol')` | Ordinary patrol composition counts | Group size; rounded whole enemies, up to the supported field limit |
| `spawn_multiplier(faction, n, 'reinforcement')` | Reinforcement composition counts | Breaches and faction transports; capacity still limits deliveries |
| `spawn_multiplier(faction, n, 'map')` | Map guard composition cost divided by n | Effective budget; native 999 fill limits stay intact, so this is not an exact count scale |
| `patrol_frequency(faction, n)` | Patrol clock player factors across authored faction modes | Faster scheduling at larger multipliers; caps and other gates remain |
| `difficulty_multiplier(level, 'encounter_budget', n)` | Difficulty encounter budget | More or less budget for director selections |
| `difficulty_multiplier(level, 'map_budget', n)` | Difficulty guardforce budget | Map guard budget for just that difficulty |
| `difficulty_multiplier(level, 'spawner_frequency', n)` | Shared spawner cooldown divided by n | 2x halves the cooldown for that difficulty; not the patrol clock |

Faction is `terminids`, `automatons`, or `illuminate`. Difficulty is 1 through 10.
Omitting the spawn channel keeps the earlier behavior: all editable composition
counts, including other families. Existing presets keep their canonical fields.
The separate shortcuts do not reset edits to those other families.

```lua
local recipe = hd2.enemies.spawn_multiplier('terminids', 2, 'reinforcement')
for _,transaction in ipairs(recipe.transactions) do
    hd2.ensure({transaction=transaction})
end
```

The Editor uses sliders under Enemy Overview and Mission Difficulty. Release a
slider to prepare changes incrementally, review Changes, then Apply. Slider
positions are preparation choices, while the normal field rows show actual
staged/applied values. The 1x button restores the selected channel to defaults.
All changes use the usual preset, export and reset paths. Closing the editor
cancels an unreleased slider; explicit preparation already started can finish.

Each count-scaled composition is capped at **32 enemies total across its groups**.
This protects a fixed native squad-spawn queue: exceeding it can corrupt the queue
count and crash the game. Recipes preserve the requested mix using proportional
integer allocation and report `cappedCompositions` and `maxCompositionCount`.
The Editor reports when this cap is reached. Manual writes and older presets
must also satisfy the total; Runtime rechecks current values immediately before
preparing writes, so separate operations cannot bypass it. Patrol frequency is
independent and can increase encounters without increasing a squad beyond 32.
The `all` count recipe covers patrol and reinforcement only; map guards retain
their separate budget control and unresolved composition families are excluded.

These controls do not promise an exact multiplier on enemies in play. Mission
scripts, eligibility, transport capacity, population caps, special spawn families
and private mode copies still apply. Faction map cost and difficulty map budget
both affect map guards, so their effects can combine. More enemies can cost more
performance; the new controls do not raise native capacity limits.

Difficulty descriptions include English `metadata.displayName` and
`metadata.iconName` for `hd2.resources.game_icon('difficulty', iconName)`.
Composition metadata names the reviewed consumer (`patrol`, `reinforcement`,
`map`), or `unresolved`. Roster descriptions include `metadata.faction`.

## Structure destruction

`:describe().demolition` reports the model association and three ordered stage
requirements. `hd2.enemies.destruction_models()` covers all 1,641 models, including
those without a gameplay entity. Embedded model references are marked separately
from direct Unit associations.

```lua
local demolition = hd2.enemies.demolition_template('OrbitalBombardment')
hd2.patch({id='bombardment-demolition', target=demolition,
    field=hd2.fields.demolition.force, expect=50, value=45,
    allow_shared=true, allow_unverified_effect=true})
```

This edits the **shared required strength**, affecting every referencing stage.
It does not edit one weapon's damage or create a private per-structure threshold.
`none` and `Count` templates are read-only. New force values are bounded to
1â€“255 because the traced incoming force is narrowed to a byte. Stages are
ordered: an earlier unmet Script/250 gate can prevent reaching a later 60 stage.

See `EnemyControlCapabilities.json` and `EnemyDirectorCapabilities.json` for the
complete authoring catalogue. Runtime ownership checks, byte-conflict checks and
rollback protect writes; snapshot tests do not establish live gameplay effects.


## Spawn-picker compatibility (RC8)

When Pick your bots/bugs/squids is loaded (`PickYourBots` or legacy
`AllAutomatonReplace` runtime object), it owns rosters, compositions, difficulty
spawn budgets/cooldowns, HiveMind tuning and native spawner tuning. This remains
true while its internal options are disabled: the mod can enable them later.
HD2Runtime refuses overlapping preparations and checks prepared transactions again
at commit, returning `SPAWN_SYSTEM_OWNED` before memory reads or writes. Mixed
transactions are refused as a whole. Inverse plans preserve that ownership scope;
they cannot restore bytes over the picker. The older spawn-weight override API is
also suspended/refused while the picker is loaded.

Enemy health, damage, size, transport geometry, breach geometry, demolition and
mission timers remain independent. The editor crosses out overlapping fields,
retains saved/imported values as pending, and offers **OPEN SPAWN PICKER**. An
intentional compatibility block does not create a false interrupted-application
warning. Disabling the picker in the mod pack takes effect on a fresh game start.
Already-applied Runtime spawn changes are not blindly reverted when a picker is
introduced late; restart with the desired mod selection to establish clean ownership.

`hd2.enemies.spawn_compatibility()` returns ownership status.
`hd2.enemies.spawn_control_reason(target, field)` checks a canonical descriptor.
`hd2.enemies.open_spawn_picker(before_open)` opens its GUI on a user action; the
optional callback closes the caller's menu after finding a supported opener.
The downloaded 1.6.0 Ship Preview Test7 uses a bounded callback-upvalue adapter to
exercise its normal GUI opening path, restoring its panel-local binding immediately.
No foreign settings, files, native input hooks or OS key injection are changed.
A future public `open_settings` bridge takes precedence; unknown GUI layouts fail
with a message directing the player to the picker's own binding/F9 fallback.


RC9 follows callback wrappers without depending on a short fixed list of upvalue
names. Discovery remains bounded and click-only, including named callback slots in
private tables. The installed pack's `previous_update` / `game_update` wrappers and
profiler-wrapped panel pumps are covered. Each open request logs success or its
failure reason; foreign callback functions are never executed during discovery.
