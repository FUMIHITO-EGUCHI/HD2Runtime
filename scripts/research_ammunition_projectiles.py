"""The projectile rows that INDIRECT weapons fire through their default ammunition. Read-only.

An INDIRECT weapon (research/active-projectile-sources: the default ammunition item's entity delta patches
ProjectileWeapon +0 when the weapon is built) fires the ammunition's projectile, not its base member. For four of the
six the two are the same row, so the reviewed weapon catalogue already resolves their projectile and damage rows from
the base member. The P-2 Peacemaker and the P-19 Redeemer have a base member of 0: their catalogue attack graph was empty
and no projectile or damage field was published, although the Runtime write path already resolves projectile rows
through the proven ammunition delta (domains/player_weapon_writes.lua projectile_for_candidate).

This pass reads, through the production resolver against the retained snapshot, the ProjectileSettings row each
ammunition delta names and the DamageInfo row that row links (+60), with the values the catalogue publishes, and who
else uses them:
  * baseConsumers: weapons whose base ProjectileWeapon +0 names the same projectile row;
  * ammunitionItems: every ammunition item whose delta patches that row, with the weapons it is the default of and the
    weapons that list it (sharedWithWeapons of the ammunition source);
  * damageProjectileConsumers: how many ProjectileSettings rows (of every catalogued projectile type) link the damage
    row.

Output: research/ammunition-projectiles-F5FEE03DCFDB.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from research_enemy_attacks import resolve_settings  # noqa: E402

ACTIVE = ROOT / 'research/active-projectile-sources-F5FEE03DCFDB.json'
IDENTITIES = ROOT / 'research/projectile-identities-F5FEE03DCFDB.json'
CATALOG = ROOT / 'schemas/player_weapon_authoring_catalog.json'
OUTPUT = ROOT / 'research/ammunition-projectiles-F5FEE03DCFDB.json'


def settings_types():
    """The settings type hash of ProjectileSettings and DamageInfo rows, as the reviewed catalogue names them."""
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    projectile, damage = set(), set()
    for candidate in catalog['candidates'].values():
        for attack in candidate.get('attacks') or []:
            if attack.get('projectileSettings'):
                projectile.add(attack['projectileSettings']['settingsType'])
            if attack.get('damageInfo') and attack.get('kind') == 'Projectile':
                damage.add(attack['damageInfo']['settingsType'])
    assert len(projectile) == 1 and len(damage) == 1, (projectile, damage)
    return projectile.pop(), damage.pop()


def build():
    active = json.loads(ACTIVE.read_text(encoding='utf-8'))
    weapons = {item['weapon']: item for item in active['weapons']}
    indirect = sorted(name for name, item in weapons.items() if item['status'] == 'INDIRECT')
    types = sorted({item['type'] for item in json.loads(IDENTITIES.read_text(encoding='utf-8'))['types']})
    rows = {item['type']: item for item in resolve_settings(types, [])['projectiles']}
    projectile_settings, damage_settings = settings_types()
    damage_consumers = {}
    for item in rows.values():
        if item.get('settings') and item.get('damage'):
            damage_consumers[item['damage']['type']] = damage_consumers.get(item['damage']['type'], 0) + 1
    result = []
    for name in indirect:
        entry = weapons[name]
        patches = [(custom['item'], patch) for custom in entry['defaultCustomization']
            for patch in custom['projectilePatches']
            if patch['component'] == 'ProjectileWeaponComponentData' and patch['offset'] == 0]
        if len(patches) != 1:
            continue    # the SG-20 Halt's rounds member is classified on its own (not a ProjectileWeapon +0 delta)
        item_name, patch = patches[0]
        projectile_type = patch['value']
        row = rows[projectile_type]
        settings, damage = row['settings'], row['damage']
        assert settings and settings['recordType'] == projectile_type, name
        assert damage and damage['settings'], name
        values = row['values']
        items = [{'item': item['item'], 'defaultOf': item['defaultOf'], 'unlockListedBy': item['unlockListedBy']}
            for item in active['ammunitionItems']
            if any(p['component'] == 'ProjectileWeaponComponentData' and p['offset'] == 0
                and p['value'] == projectile_type for p in item['projectilePatches'])]
        result.append({
            'weapon': name,
            'ammunitionItem': item_name,
            'baseProjectileType': entry['base']['projType'],
            'projectileType': projectile_type,
            'baseIsAmmunitionRow': entry['base']['projType'] == projectile_type,
            'projectileSettings': dict(settings, settingsType=projectile_settings),
            'damageInfo': dict(damage['settings'], settingsType=damage_settings,
                projectileConsumerCount=damage_consumers.get(damage['type'], 0)),
            'resolvedFields': {
                'projectile_velocity': values['velocity'], 'projectile_mass': values['mass'],
                'drag': values['drag'], 'gravity': values['gravity'], 'pellet_count': values['pellet_count'],
                'damage_type': damage['type'], **damage['values']},
            'lifetime': values['lifetime'],
            'penetrationSlowdown': values['penetration_slowdown'],
            'explosions': {phase: item['type'] for phase, item in sorted((row.get('explosions') or {}).items())},
            'baseConsumers': sorted(other for other, item in weapons.items()
                if other != name and item['base']['projType'] == projectile_type),
            'ammunitionItems': items,
        })
    gap = [item['weapon'] for item in result if not item['baseIsAmmunitionRow']]
    return {'schemaVersion': 1, 'writes': 0, 'protectionChanges': 0, 'fixtureFallback': 'disabled',
        'build': active.get('build'),
        'source': 'production resolver (scripts/research_enemy_attacks.resolve_settings) on the retained snapshot; '
            'ammunition deltas from research/active-projectile-sources-F5FEE03DCFDB.json',
        'summary': {'indirectWeapons': len(result), 'baseDiffersFromAmmunition': gap,
            'projectileTypesRead': len(rows)},
        'weapons': result}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args(argv)
    report = build()
    OUTPUT.write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report['summary'], indent=1))


if __name__ == '__main__':
    main()
