# Explosion-created arcs

HD2Runtime 0.40.0 exposes the GL-52 De-Escalator and G-31 Arc grenade's electric attacks separately from their radial explosion damage.

Both expose arc velocity, range, spread distance and angle (including first-shot values), maximum chain length, maximum split, standard/durable damage, four armor penetration values, demolition, stagger, push force, and their linked stun strength/duration. The grenade arc also exposes all four damage status type/strength pairs.

```lua
local gl_arc = hd2.support_weapon('GL-52 De-Escalator'):attack('primary_impact_arc')
local grenade_arc = hd2.throwable('G-31 Arc'):explosion():arc()

hd2.patch {
    id = 'grenade-arc-range', target = grenade_arc,
    field = hd2.fields.arc.range, expect = 10, value = 20,
    allow_shared = true, allow_unverified_effect = true,
}
```

`hd2.throwable('G-31 Arc'):arc()` is an alias for the grenade target above. Use `damage.standard_damage` on the arc target to edit electric hit damage; the explosion's `explosion.damage.standard_damage` controls the separate radial hit.

The De-Escalator's stun target is `:attack('primary_impact_arc_status_37')`. The grenade's is `:arc():status_effect('arc-stun-small')`. Both accept `status.strength` and `status.duration`. Duration edits change the shared Stun Small definition, including other weapons that use it. Replacing an arc's status slot does not retarget the original Stun Small duration control; its guarded owner link must still be present.

The editor lists these under Support Weapons / GL-52 De-Escalator and Throwables / G-31 Arc. Arc damage, radial explosion damage, and status controls have separate sections. Apply, reset, and Lua export use the same guarded API paths.

All these settings require shared-definition and unverified-effect acknowledgements. Native ownership, changed writes, inverses, and broken-link rejection were tested against retained memory; changed gameplay has not been tested in game. These controls do not expose targeting filters or self-hit toggles, whose semantics have not been established for this path. Chain length and split are native limits, not a guaranteed number of enemies hit.
