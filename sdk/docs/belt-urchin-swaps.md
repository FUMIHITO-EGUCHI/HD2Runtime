# Belt-fed shotgun and Urchin plasma pulses

These controls are available in the local 0.40.0 Runtime and 0.10.0 editor.

In **Support Weapons → GL-28 Belt-Fed Grenade Launcher → Projectile / Swap**, choose **SG-225 Breaker** for a shotgun projectile. The launcher retains its own firing rate, handling and backpack ammunition. Apply the swap before calling in a fresh weapon: the projectile reference is copied when the weapon is built.

In **Throwables → G-109 Urchin → Pulse payload**, choose **PLAS-45 Epoch (impact)** for the small plasma explosion. The other reviewed option, **PLAS-45 Epoch (charge 2 expiry)**, supplies the charged plasma explosion. Reset restores the original stun payloads.

The Urchin control replaces both shared explosion definitions used by its repeating and final discharges. It copies the reviewed effect, sound, radii and damage links, preserving each recipient definition's identity. It applies to all Urchins using those definitions and keeps the native sticky/repeat logic. It does not change repeat timing or count. The ordinary Urchin explosion controls describe its original payload and can conflict with an active replacement. Donor definitions must remain at their reviewed values when copied; unrelated edits are rejected rather than silently overwritten.

```lua
local source = hd2.support_weapon('GL-28 Belt-Fed Grenade Launcher'):projectile_source()
hd2.ensure { patch = {
    id = 'belt-shotgun', target = source.target, field = source.field,
    expect = source.expect, value = hd2.attack_output('SG-225 Breaker'),
    allow_shared = true, allow_unverified_effect = true, allow_unverified_reference = true,
} }

hd2.ensure { patch = {
    id = 'sticky-plasma', target = hd2.throwable('G-109 Urchin'):pulse(),
    field = hd2.fields.throwable.pulse_explosion,
    expect = hd2.explosion('throwable/g109_urchin/detonation'),
    value = hd2.explosion('support_weapon/plas45_epoch/impact'),
    allow_shared = true, allow_unverified_effect = true, allow_unverified_reference = true,
} }
```

The small Epoch effect belongs to the mission effects package. The charged effect's package is loaded through the normal asset gate before writes. No executable instructions are patched. The guarded write plan covers both Urchin definitions and rolls both back on a recoverable write failure.

Native ownership, changed writes, restoration, conflict rejection, and editor apply/reset/export were tested offline against retained memory. Changed gameplay, including multiplayer behavior, still needs an in-game test.
