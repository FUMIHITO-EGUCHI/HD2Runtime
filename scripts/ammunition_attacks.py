"""The fired attack of an INDIRECT weapon whose base ProjectileWeapon +0 is 0 (0.31.1: P-2 Peacemaker, P-19 Redeemer).

Such a weapon fires only its default ammunition's projectile (research/active-projectile-sources: the ammunition
delta patches ProjectileWeapon +0 when the weapon is built), so the reviewed catalogue, built from the base member,
gave it no attack and published no projectile or damage field. The Runtime write path already resolves every
projectile, damage and terminal row of an ammunition weapon through its re-proven ammunition delta
(domains/player_weapon_writes.lua projectile_for_candidate), so these weapons get the same `primary` attack the other
four INDIRECT weapons have, built from the ammunition row research/ammunition-projectiles reads (whose method matches
the reviewed catalogue exactly on the four weapons it already covered).

Used by scripts/generate_weapon_composition.py (the attack graph) and scripts/generate_weapon_authoring.py (the
projectile and damage fields). The attack's reference member is not swapped here: the ammunition is the source
(weapon:projectile_source() names weapon:ammunition()).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / 'research/ammunition-projectiles-F5FEE03DCFDB.json'
CATALOG = ROOT / 'schemas/player_weapon_authoring_catalog.json'

UNVERIFIED = ('The weapon fires its default ammunition\'s projectile row (the ammunition delta patches ProjectileWeapon '
    '+0 at weapon build; its base member is 0) and the write re-proves that delta, but no live test has yet shown an '
    'edit of this row changing the weapon in play.')
_CACHE = {}


def _load():
    if 'weapons' not in _CACHE:
        report = json.loads(RESEARCH.read_text(encoding='utf-8'))
        _CACHE['weapons'] = {item['weapon']: item for item in report['weapons'] if not item['baseIsAmmunitionRow']}
    return _CACHE['weapons']


def weapons():
    """Names of the weapons that get an ammunition attack."""
    return sorted(_load())


def entry(name):
    return _load().get(name)


def ammunition_source(name):
    """The reviewed ammunition source of the weapon (scripts/generate_attack_outputs.py active_sources)."""
    if 'ammunition' not in _CACHE:
        from generate_attack_outputs import active_sources
        _CACHE['ammunition'] = active_sources()[2]
    return _CACHE['ammunition'][name]


def authoring_attack(name):
    """The attack in the shape of a reviewed catalogue candidate attack (schemas/player_weapon_authoring_catalog.json),
    or None."""
    item = entry(name)
    if not item:
        return None
    return {'kind': 'Projectile', 'role': 'primary', 'sources': ['primary'],
        'projectileType': item['projectileType'], 'projectileSettings': dict(item['projectileSettings']),
        'damageInfo': dict(item['damageInfo']), 'resolvedFields': dict(item['resolvedFields']),
        'statusEffects': {}, 'ammunitionSource': item['ammunitionItem']}


def _projectile_weapon(name):
    """The weapon's own ProjectileWeaponComponentData ownership identity in the reviewed catalogue."""
    if 'catalog' not in _CACHE:
        _CACHE['catalog'] = json.loads(CATALOG.read_text(encoding='utf-8'))
    catalog = _CACHE['catalog']
    weapon = next(item for item in catalog['weapons'] if item['name'] == name)
    assert len(weapon['resources']) == 1, name + ': an ammunition attack needs one reviewed root'
    return catalog['candidates'][weapon['resources'][0]]['ownership']['ProjectileWeaponComponentData']


def projectile_member(name):
    """The +52 lifetime and +64 penetration slowdown of the ammunition row, in the shape of a
    research/player-projectile-members branch (which reads only the reviewed catalogue's attacks), or None."""
    item = entry(name)
    if not item:
        return None
    settings = item['projectileSettings']
    return {'prefix': 'projectile', 'recordType': settings['recordType'], 'group': settings['group'],
        'row': settings['row'], 'resolved': True, 'lifetime': item['lifetime'],
        'penetrationSlowdown': item['penetrationSlowdown']}


def composition_attack(name):
    """The attack in the shape of a reviewed composition attack (schemas/player_weapon_composition_catalog.json),
    or None."""
    item = entry(name)
    if not item:
        return None
    projectile_weapon = _projectile_weapon(name)
    settings = dict(item['projectileSettings'])
    assert not item['explosions'], name + ': an ammunition row with terminal explosions needs reviewed terminal actions'
    return {'role': 'primary', 'aliases': ['primary'], 'projectileType': item['projectileType'],
        'projectileSettings': settings, 'compatibilityClass': ammunition_source(name)['compatibilityClass'],
        'projectileObject': {'identity': dict(settings), 'consumers': [],
            'scalarWriteScope': 'shared_projectile_definition', 'weaponLocalOverrideProven': False},
        'residency': None,
        'targetBacking': {'component': 'ProjectileWeaponComponentData', 'offset': 0, 'width': 4, 'storage': 'u32',
            'recordIndex': projectile_weapon['recordIndex'], 'indexRow': projectile_weapon['indexRow'],
            'ownerCount': projectile_weapon['ownerCount'], 'uniqueOwner': projectile_weapon['uniqueOwner']},
        'sourceIdentityResolvable': True, 'targetOwnershipProven': True, 'writableReferenceSwap': False,
        'reason': None, 'activeSource': 'ammunition', 'ammunitionItem': item['ammunitionItem'],
        'terminalActions': [], 'explosions': []}


def annotate(weapons_value):
    """Gate the projectile and damage fields of the ammunition rows (allow_unverified_effect until a live test) and name
    the weapons that may equip the same ammunition (sharedWithWeapons of the ammunition source)."""
    for weapon in weapons_value:
        item = entry(weapon['name'])
        if not item:
            continue
        rows = {('projectile', item['projectileSettings']['row'], item['projectileType']),
            ('damage', item['damageInfo']['row'], item['damageInfo']['recordType'])}
        for field in weapon['fields']:
            backing = field.get('backing') or {}
            if backing.get('kind') != 'settings' or (backing.get('settings'), backing.get('row'),
                    backing.get('recordType')) not in rows:
                continue
            field['ammunitionSource'] = item['ammunitionItem']
            field['sharedWithWeapons'] = sorted(set(field.get('sharedWithWeapons') or []) | set(
                ammunition_source(weapon['name'])['sharedWithWeapons']))
            if field.get('sharedWithWeapons'):
                field['affectsMultipleWeapons'] = True
            if field.get('editable'):
                field['acknowledgement'] = 'allow_unverified_effect'
                field['acknowledgementReason'] = UNVERIFIED
                field.pop('liveEvidence', None)
