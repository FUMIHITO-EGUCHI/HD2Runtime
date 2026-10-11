"""The projectile rows weapons fire through their native ProgrammableAmmo function (ProjectileWeapon +576). Read-only.

While a weapon's ProgrammableAmmo function is on, the projectile fire path (game.dll 0x615940, docs/weapon-feeds.md)
fires ProjectileWeapon +576 instead of the normal projectile when it is non-zero (and +584's entity when that is
non-zero). The AC-8 Autocannon (flak), GR-8 Recoilless Rifle and RL-77 Airburst Rocket Launcher carry a native +576
projectile and no +584 entity (research/weapon-functions). Their +576 projectile could be swapped
(function_ammo.projectile) but its own projectile and damage rows had no field.

This pass reads, through the production resolver against the retained snapshot, the ProjectileSettings row each +576
names and the DamageInfo row it links (+60), with the values the catalogue publishes, and who else names the row
(research/projectile-identities owners: other weapons' +0 / +576 members, Eagle payloads, vehicle guns).

Output: research/programmable-projectiles-F5FEE03DCFDB.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from research_enemy_attacks import resolve_settings  # noqa: E402
from research_ammunition_projectiles import settings_types  # noqa: E402

FUNCTIONS = ROOT / 'research/weapon-functions-F5FEE03DCFDB.json'
IDENTITIES = ROOT / 'research/projectile-identities-F5FEE03DCFDB.json'
OUTPUT = ROOT / 'research/programmable-projectiles-F5FEE03DCFDB.json'


def owner_names(identity, exclude):
    names = set()
    for owner in identity.get('owners') or []:
        for item in owner.get('names') or []:
            if item.get('category') in ('support weapon', 'primary', 'secondary', 'player weapon', 'vehicle weapon') \
                    and item['name'] != exclude:
                names.add(item['name'])
    return sorted(names)


def build():
    functions = json.loads(FUNCTIONS.read_text(encoding='utf-8'))
    identities = {item['type']: item for item in json.loads(IDENTITIES.read_text(encoding='utf-8'))['types']}
    hosts = []
    for weapon in functions['weapons']:
        ammo = weapon.get('functionAmmo') or {}
        if ammo.get('state') == 'native' and ammo.get('projectile') and not ammo.get('entity'):
            hosts.append((weapon['weapon'], ammo['projectile'], dict(ammo, kind=weapon['kind'])))
    rows = {item['type']: item for item in resolve_settings(sorted(identities), [])['projectiles']}
    damage_consumers, damage_projectiles = {}, {}
    for item in rows.values():
        if item.get('settings') and item.get('damage'):
            damage_consumers[item['damage']['type']] = damage_consumers.get(item['damage']['type'], 0) + 1
            damage_projectiles.setdefault(item['damage']['type'], []).append(item['type'])
    projectile_settings, damage_settings = settings_types()
    result = []
    for name, projectile_type, ammo in sorted(hosts):
        row = rows[projectile_type]
        settings, damage = row['settings'], row['damage']
        assert settings and settings['recordType'] == projectile_type, name
        assert damage and damage['settings'], name
        reviewed = ammo.get('settings') or {}
        assert (reviewed.get('group'), reviewed.get('row'), reviewed.get('recordType')) == (
            settings['group'], settings['row'], settings['recordType']), name + ': weapon-functions row differs'
        identity = identities[projectile_type]['identity']
        members = sorted({owner['member'] for owner in identity['owners'] if any(
            item['name'] == name for item in owner.get('names') or [])})
        values = row['values']
        result.append({
            'weapon': name,
            'member': 'ProjectileWeapon +576',
            'selector': {'input': ammo.get('selectorInput'), 'bound': ammo.get('selectorBound')},
            'projectileType': projectile_type,
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
            'ownerMembers': members,
            'sharedWithWeapons': owner_names(identity, name),
            'otherOwners': sum(1 for owner in identity['owners'] if not any(
                item['name'] == name for item in owner.get('names') or [])),
            # Other projectile rows linking the same DamageInfo row, and who fires them: a damage edit reaches them too.
            'damageSharedWith': [{'projectileType': other, 'label': identities[other]['hint'].get('label'),
                'owners': owner_names(identities[other]['identity'], None)}
                for other in sorted(damage_projectiles.get(damage['type'], [])) if other != projectile_type],
        })
    return {'schemaVersion': 1, 'writes': 0, 'protectionChanges': 0, 'fixtureFallback': 'disabled',
        'build': functions.get('build'),
        'source': 'production resolver (scripts/research_enemy_attacks.resolve_settings) on the retained snapshot; '
            'hosts from research/weapon-functions-F5FEE03DCFDB.json, owners from research/projectile-identities',
        'firePath': 'game.dll 0x615940: +576 replaces the fired projectile while the ProgrammableAmmo function is on, '
            'when non-zero (docs/weapon-feeds.md)',
        'summary': {'hosts': [item['weapon'] for item in result],
            'shared': {item['weapon']: item['sharedWithWeapons'] for item in result if item['otherOwners']}},
        'weapons': result}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args(argv)
    report = build()
    OUTPUT.write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report['summary'], indent=1))


if __name__ == '__main__':
    main()
