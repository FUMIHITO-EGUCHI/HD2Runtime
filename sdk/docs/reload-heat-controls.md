# Reload and Double-Edge Sickle controls (local 0.40.0)

Every reloadable firearm in the primary/secondary catalogue has a control: 57 use
`reload.duration` on `hd2.weapon(name)`, and 17 use the existing
`attachment.reload_duration` on `hd2.weapon(name):magazine_attachment()`.
The Blitzer has no reload ability; it and the six melee entries have no editable reload. The editor places the applicable control
under Ammunition on each weapon's page.

For a base reload override, zero preserves native ability timing. Positive seconds
rescale the reload ability. This is not a separate tactical/empty reload timer:
partial reloads, interrupted stages and repeated shell insertions follow their
own animation events. Armor reload bonuses still multiply the resulting speed.
Customization can retain a private copy; rebuild/re-equip the weapon after editing.

```lua
local gun = hd2.weapon('P-4 Senator')
session.patch {
    id = 'senator-reload', target = gun,
    field = hd2.fields.reload.duration, expect = 2.799999952316284, value = 1.25,
    allow_unverified_effect = true,
}

-- A magazine-owned reload: this definition is shared by its users.
session.patch {
    id = 'liberator-reload',
    target = hd2.weapon('AR-23 Liberator'):magazine_attachment(),
    field = hd2.fields.attachment.reload_duration, expect = 3, value = 1.5,
    allow_shared = true, allow_unverified_effect = true,
}
```

The default-magazine row affects that magazine definition. Select a different
magazine under Magazines to tune its reload too. The base override is read-only
where the default magazine replaces it.

LAS-17 Double-Edge Sickle adds 89 controls to its existing heat controls:

- Maximum heat fire-rate multiplier and curve exponent. The multiplier is
  `1 + (maximum - 1) * (heat / capacity)^exponent`.
- Cold/hot cooling multipliers, overheat release threshold, the charging/overheated
  cooling rate and its prevention switch, and four wind-up charge controls.
- Each of the three heat levels' projectile velocity, mass, drag, gravity,
  lifetime, penetration slowdown and pellet count.
- Each level's direct damage, durable damage, four penetration values,
  demolition, stagger and push force.
- The same nine values on each level's self-damage row, plus self-status duration.

Level thresholds, wielder status selection (including `none`), heat per shot,
capacity, base cooling and the overheat lock remain available. The new level
fields use `heat.level_N.projectile.*`, `heat.level_N.damage.*`,
`heat.level_N.self_damage.*`, and `heat.level_N.self_status_duration` on the
weapon target. Settings edits require `allow_shared=true`; every new control
requires `allow_unverified_effect=true`. These are shared definitions, and source
selectors are rechecked before writing. They do not follow a replaced selector
to an unrelated definition.

```lua
session.patch {
    id = 'sickle-ramp', target = hd2.weapon('LAS-17 Double-Edge Sickle'),
    field = hd2.fields.heat.fire_rate_multiplier_max,
    expect = 1.100000023841858, value = 2,
    allow_unverified_effect = true,
}
```

These changes were tested against retained memory and in the editor simulator,
not in a running game. Unidentified heat members and asset references are not
editable controls.

**Throwing-knife explosions remain unavailable.** K-2 uses a physical sticky
entity rather than the projectile path that supports explosion references. It
has no ExplosiveComponent, and its native attachment ability callback requires
an ability instance it does not own. No working explosion selector has been added
for the knife. Its existing direct-hit statuses remain available.

The Arbitrator, One-Two and Stoker underbarrels now expose their own
`reload.duration` through `hd2.weapon('<host> / underbarrel')`. The Editor places
these under **Underbarrel Weapon**, with the main reload in **Ammo & Magazine**.
Arbitrator labels distinguish AR mode from underbarrel. Zero uses native ability
timing; positive seconds rescale that ability, and staged reloads can differ from
the full magazine duration. Rebuild/re-equip after editing component values.
