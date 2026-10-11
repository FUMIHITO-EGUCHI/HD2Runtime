"""The direct-hit damage of the missile a support weapon spawns per shot (0.31.1: FAF-14 Spear, MLS-4X Commando,
StA-X3 W.A.S.P. Launcher; research/wasp-rocket-F5FEE03DCFDB.json).

Such a weapon spawns a SeekingMissile entity per shot (ProjectileWeapon +40). The missile carries the shot's projectile
row, ProjectileWeapon +0 (the shooter's spawn info +0x424), as its hit row: the DamageInfo row it links (+60) is the
direct hit, and its impact explosion (+144) is the explosion the catalogue already resolves as `primary_impact`. The
missile flies by its own SeekingMissile record (missile.*), so the row's flight members (speed, mass, drag, gravity) are
not used by the missile and are not offered here.

The reviewed catalogue left the primary projectile branch PARTIAL because its drag and gravity differ from the scraped
catalog (they are unused by a unit-driven projectile), so no direct-hit field was published although every damage
member matched exactly. This module publishes only the damage fields of that branch, on the row the write path already
resolves for the impact explosion (ProjectileWeapon +0), and only where:
  * the weapon spawns a missile through +40 whose carried type is its ProjectileWeapon +0 (research/wasp-rocket);
  * the branch mismatches nothing but drag / gravity and matches every damage member;
  * the catalogue attack fires exactly that carried projectile type.
Every field needs allow_unverified_effect: no live test has shown a direct-hit edit change a missile in play.
"""
from __future__ import annotations

import missile_fields

DAMAGE = {'standard_damage', 'durable_damage', 'ap_direct', 'ap_slight', 'ap_large', 'ap_extreme', 'demolition',
    'stagger', 'push_force'}
UNUSED_BY_MISSILE = {'drag', 'gravity'}
REASON = ('The direct hit of the missile this weapon spawns per shot: the missile carries this projectile row '
    '(ProjectileWeapon +0) and deals its damage when it hits (research/wasp-rocket-F5FEE03DCFDB.json); no live test has '
    'yet shown an edit of it in play.')
MULTIPLAYER = ('The shooter decides the missile\'s impact (research/projectile-homing), so the direct hit follows the '
    'shooter\'s row.')


def hit_attack(weapon, candidate):
    """(attack, branch, spawn) of the weapon's missile direct hit, or None."""
    if not candidate:
        return None
    spawned = [item for item in missile_fields.spawns(candidate['resourceHash']) if item['member'] == 40]
    if len(spawned) != 1:
        return None
    missile = spawned[0]['missile']
    if not str(missile.get('projectileTypeSource', '')).endswith('(ProjectileWeapon +0)'):
        return None
    found = None
    for branch in weapon['attackGraph']:
        match = branch.get('runtimeMatch') or {}
        if branch['kind'] != 'Projectile' or branch.get('state') != 'PARTIAL':
            continue
        mismatched = set(match.get('mismatchedFields') or [])
        if not mismatched or not mismatched <= UNUSED_BY_MISSILE or not DAMAGE <= set(match.get('matchedFields') or []):
            continue
        role = match.get('runtimeAttackRole')
        attack = next((item for item in candidate['attacks'] if item['role'] == role and item['kind'] == 'Projectile'),
            None)
        if attack and attack.get('damageInfo') and attack['projectileType'] == missile['projectileType']:
            assert found is None, weapon['name'] + ': two missile hit branches'
            found = (attack, branch, spawned[0])
    return found


def annotate(fields, hit):
    """Gate and describe the direct-hit fields damage_fields() just built for the hit attack."""
    attack, branch, spawn = hit
    for field in fields:
        field['acknowledgement'] = 'allow_unverified_effect'
        field['acknowledgementReason'] = REASON
        field.pop('liveEvidence', None)
        field['missileHit'] = {'catalogBranch': branch['name'], 'projectileType': attack['projectileType'],
            'carriedBy': spawn['missile']['resource'], 'member': 'ProjectileWeapon +0',
            'unusedByMissile': sorted(UNUSED_BY_MISSILE),
            'research': 'research/wasp-rocket-F5FEE03DCFDB.json'}
        field['multiplayer'] = MULTIPLAYER
