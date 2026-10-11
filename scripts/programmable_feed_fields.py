"""Projectile and damage fields of the projectile a support weapon fires through its native ProgrammableAmmo function
(0.31.1: AC-8 Autocannon flak, GR-8 Recoilless Rifle, RL-77 Airburst Rocket Launcher;
research/programmable-projectiles-F5FEE03DCFDB.json).

While the weapon's ProgrammableAmmo function is on, the projectile fire path fires ProjectileWeapon +576 instead of the
normal projectile (game.dll 0x615940, docs/weapon-feeds.md). The +576 projectile could be swapped
(function_ammo.projectile, feed('programmable')) but its own row had no field. These fields edit that row through the
role `programmable` (support_weapon(name):attack('programmable'):projectile()): every write reads the weapon's +576 again
(domains/player_weapon_writes.lua function_projectile), so a swapped or emptied function projectile is refused, never
written through.

The row is read whenever the function fires it (like any projectile row), but no live test has shown an edit of a
ProgrammableAmmo row change a shot in play: every field needs allow_unverified_effect, and allow_shared (a projectile
row may be fired by other weapons; its DamageInfo row may be linked by other projectiles).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / 'research/programmable-projectiles-F5FEE03DCFDB.json'
ROLE = 'programmable'
UNVERIFIED = ('The projectile this weapon fires while its ProgrammableAmmo function is on (ProjectileWeapon +576, re-read '
    'on every write); no live test has yet shown an edit of this row change a shot in play.')

_CACHE = {}


def entry(name):
    if 'weapons' not in _CACHE:
        _CACHE['weapons'] = {item['weapon']: item for item in
            json.loads(RESEARCH.read_text(encoding='utf-8'))['weapons']}
    return _CACHE['weapons'].get(name)


def attack(item):
    """The attack in the shape of a reviewed support catalogue attack."""
    return {'kind': 'Projectile', 'role': ROLE, 'projectileType': item['projectileType'],
        'projectileSettings': dict(item['projectileSettings']), 'damageInfo': dict(item['damageInfo']),
        'resolvedFields': dict(item['resolvedFields']), 'statusEffects': {}}


def members(item):
    """(suffix, value, offset, storage) of the projectile row's published members."""
    values = item['resolvedFields']
    out = [('velocity', values['projectile_velocity'], 32, 'f32'), ('mass', values['projectile_mass'], 36, 'f32'),
        ('drag', values['drag'], 40, 'f32'), ('gravity', values['gravity'], 44, 'f32'),
        ('pellet_count', values['pellet_count'], 28, 'u32'),
        ('penetration_slowdown', item['penetrationSlowdown'], 64, 'f32')]
    if item['lifetime']:
        # 0 is the no-explicit-lifetime state; a non-zero value would add a limit rather than tune one.
        out.append(('lifetime', item['lifetime'], 52, 'f32'))
    return out


def annotate(fields, item):
    """Gate the fields and name who else fires the row or links its damage."""
    damage_shared = sorted({owner for other in item['damageSharedWith'] for owner in other['owners']})
    for field in fields:
        damage = field['semanticFieldId'].startswith('damage.')
        shared = set(item['sharedWithWeapons']) | (set(damage_shared) if damage else set())
        shared.discard(field['target']['weapon'])
        field['sharedWithWeapons'] = sorted(set(field.get('sharedWithWeapons') or []) | shared)
        field['affectsMultipleWeapons'] = True
        field['acknowledgement'] = 'allow_unverified_effect'
        field['acknowledgementReason'] = UNVERIFIED
        field.pop('liveEvidence', None)
        field['programmableFeed'] = {'member': item['member'], 'feed': 'programmable',
            'selectorInput': item['selector']['input'],
            'sharedRow': bool(item['sharedWithWeapons']) or bool(damage and item['damageSharedWith']),
            'research': 'research/programmable-projectiles-F5FEE03DCFDB.json'}
