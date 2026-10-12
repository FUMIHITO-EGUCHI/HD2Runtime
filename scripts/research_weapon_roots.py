"""The real roots of the seven player weapons the stat-fingerprint mapper resolves to two roots (DUPLICATE).

Each weapon's catalogue entry lists two candidate roots that tie on every compared stat; the first was picked by hash
order. This research proves which root is the weapon a player carries, from three kinds of evidence:
  * equipped_snapshot: a retained snapshot with the weapon equipped; the player's inventory slot holds an entity of
    exactly this root (research_player_equipment.observe). LAS-5 Scythe, LAS-7 Dagger (2026-10-08 T162919Z),
    SMG-37 Defender, CQC-73 Entrenchment Tool (T163453Z);
  * underbarrel: the other root is a host weapon's underbarrel (research/underbarrel-weapons catalogCorrections).
    GP-31 Grenade Pistol, P-72 Crisper;
  * call_in_rack: the other root is the one a support weapon's call-in rack attaches (research/support-weapon-coverage
    deliveredRoot), and the kept root's resource path names the weapon. CQC-42 Machete.

0.31.3: player weapons the reviewed catalogue never named (`additions`). The catalogue's identities come from a
published-stat dataset; a weapon it has no entry for is not catalogued even when the snapshot mapper already captured
its root as another weapon's candidate. The game's own armory names it: the loadout weapon table entry of an armory item
holds the entity resource (+8), and the armory title is that resource's EncyclopediaEntry prefix + name
(research/weapon-name-text-ids, research_weapon_name_text.py; the same path resolves all 80 catalogued weapons to their
catalogue roots, the seven proven roots included). An addition must be such an armory entry of the primary (1) or
secondary (3) category, its root a catalogued candidate no weapon uses, and its LoadoutPackage slot the same as the
armory category. LAS-22 Shear (laser_rifle_charge), the LAS-5 Scythe's dropped root.

Writes research/weapon-roots-F5FEE03DCFDB.json; scripts/generate_weapon_authoring.py applies it to the catalogue
(resources = [the proven root], resolution UNIQUE; additions become their own UNIQUE entries). Read-only on the
snapshots.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'research/weapon-roots-F5FEE03DCFDB.json'
UNDERBARREL = ROOT / 'research/underbarrel-weapons-F5FEE03DCFDB.json'
SUPPORT_COVERAGE = ROOT / 'research/support-weapon-coverage-F5FEE03DCFDB.json'
CATALOG = ROOT / 'schemas/player_weapon_authoring_catalog.json'
GAME_NAMES = ROOT / 'research/weapon-name-text-ids-F5FEE03DCFDB.json'
# Armory (loadout weapon table) categories of the two player weapon slots: every catalogued primary is in category 1,
# every catalogued secondary in category 3 (checked below).
ARMORY_SLOT = {1: 'primary', 3: 'secondary'}
# Reviewed additions: the armory's name of the weapon -> its catalogue grouping. The grouping is the published-stat
# dataset's category; a weapon it has no entry for takes the one of its designation family and implementation family
# in the catalogue (every LAS primary: the LAS-5 Scythe, LAS-12 Sai, LAS-13 Trident, LAS-16 Sickle are Energy-Based).
ADDITIONS = {'LAS-22 Shear': {'category': 'Energy-Based', 'categoryBasis': 'no published-stat entry; the grouping of '
    'every LAS primary in the catalogue (LAS-5 Scythe, LAS-12 Sai, LAS-13 Trident, LAS-16 Sickle, LAS-17 '
    'Double-Edge Sickle: Energy-Based)'}}

# Snapshot -> {slot: weapon}: what the user equipped for the capture.
SNAPSHOTS = {
    'F5FEE03DCFDB-20261008T162919Z-weapon-roots-scythe-dagger.hd2snap':
        {'primary': 'LAS-5 Scythe', 'secondary': 'LAS-7 Dagger'},
    'F5FEE03DCFDB-20261008T163453Z-weapon-roots-defender-etool.hd2snap':
        {'primary': 'SMG-37 Defender', 'secondary': 'CQC-73 Entrenchment Tool'},
}
# What each dropped root is (the reviewed identification, for the record).
DROPPED_IS = {
    'LAS-5 Scythe': ('laser_rifle_charge: the LAS-22 Shear (its armory entry; its heat matches no published Scythe '
        'value), catalogued on its own since 0.31.3 (additions)'),
    'LAS-7 Dagger': 'a non-loadout beam entity (its 2000 heat is the source of the old 2000-vs-100 disagreement)',
    'SMG-37 Defender': 'the SEAF SMG (seaf_smg package, foley_seafs banks)',
    'CQC-73 Entrenchment Tool': 'the world/support shovel (survival_shovel, the CQC-72 support weapon)',
}


def equipped():
    import research_player_equipment as equipment
    items = equipment.catalog()
    out = []
    for snapshot, slots in SNAPSHOTS.items():
        observation = equipment.observe(snapshot, items)
        player = observation['players'][0]
        for slot, weapon in slots.items():
            seen = player['slots'][slot]
            if seen['name'] != weapon:
                raise ValueError('%s: the %s slot holds %r, not %s' % (snapshot, slot, seen['name'], weapon))
            out.append({'weapon': weapon, 'provenRoot': '0x' + seen['type'],
                'evidence': {'kind': 'equipped_snapshot', 'snapshot': snapshot, 'slot': slot,
                    'entity': seen['entity'], 'entityType': '0x' + seen['type']}})
    return out


def underbarrel():
    data = json.loads(UNDERBARREL.read_text(encoding='utf-8'))
    out = []
    for item in data['catalogCorrections']:
        (kept,) = item['keptRoots']
        out.append({'weapon': item['weapon'], 'provenRoot': kept, 'droppedRoots': [item['dropRoot']],
            'droppedIs': 'the %s underbarrel' % ', '.join(item['underbarrelOf']),
            'evidence': {'kind': 'underbarrel', 'source': UNDERBARREL.name, 'underbarrelOf': item['underbarrelOf']}})
    return out


def machete():
    data = json.loads(SUPPORT_COVERAGE.read_text(encoding='utf-8'))
    found = []

    def walk(value, name):
        if isinstance(value, dict):
            paths = (value.get('structuralConfirmation') or {}).get('paths') or {}
            if '0x792D5D2A340FD6E6' in paths and value.get('deliveredRoot') == '0x5F3EC9BDA2BD8553':
                found.append((name, paths))
            for key, item in value.items():
                walk(item, key)
        elif isinstance(value, list):
            for item in value:
                walk(item, name)
    walk(data, None)
    hammer = found[0][1] if len(found) == 1 and found[0][0] == 'CQC-20 Breaching Hammer' else None
    if not hammer or not hammer['0x792D5D2A340FD6E6'].endswith('/machete/machete') \
            or not hammer['0x5F3EC9BDA2BD8553'].endswith('/sledge_hammer/sledge_hammer'):
        raise ValueError('the CQC-20 Breaching Hammer call-in rack evidence changed')
    return [{'weapon': 'CQC-42 Machete', 'provenRoot': '0x792D5D2A340FD6E6', 'droppedRoots': ['0x5F3EC9BDA2BD8553'],
        'droppedIs': 'the CQC-20 Breaching Hammer (sledge_hammer), the root its call-in rack attaches',
        'evidence': {'kind': 'call_in_rack', 'source': SUPPORT_COVERAGE.name, 'paths': hammer}}]


def additions(source):
    """The armory's player weapons the catalogue never named, whose root the catalogue holds as a candidate."""
    names = json.loads(GAME_NAMES.read_text(encoding='utf-8'))
    armory = {}
    for item in names['armory']:
        armory.setdefault(item['resource'], []).append(item)
    weapons = [w for w in source['weapons'] if w['name'] not in ADDITIONS]
    # The method: the armory entry of every catalogued weapon holds its catalogue root, in its slot's category.
    for weapon in weapons:
        (root,) = weapon['resources']
        entries = armory.get(root) or []
        if not entries or any(ARMORY_SLOT.get(e['category']) != weapon['slot'] for e in entries):
            raise ValueError('%s: the armory does not hold %s in the %s category' % (weapon['name'], root,
                weapon['slot']))
    used = {r for w in weapons for r in w['resources']}
    found = []
    for root, candidate in sorted(source['candidates'].items()):
        if root in used:
            continue
        for entry in armory.get(root) or []:
            slot = ARMORY_SLOT.get(entry['category'])
            if not slot or not entry.get('composedName'):
                continue
            seen = candidate['resolvedFields'].get('weapon_slot')
            if seen != slot:
                raise ValueError('%s: LoadoutPackage slot %r, armory category %s' % (root, seen, entry['category']))
            found.append({'weapon': entry['composedName'], 'root': root, 'slot': slot,
                **ADDITIONS.get(entry['composedName'], {}),
                'candidateOf': sorted(w['name'] for w in weapons if root in (w.get('candidateRoots') or [])),
                'evidence': {'kind': 'armory_entry', 'source': GAME_NAMES.name, 'armoryCategory': entry['category'],
                    'itemId': entry['itemId'], 'encyclopediaRecord': entry['record'],
                    'entityPath': entry['entityPath'], 'composedName': entry['composedName'],
                    'loadoutSlot': seen,
                    'methodCheck': 'the armory entry of each of the %d catalogued weapons holds its catalogue root '
                        'in its slot\'s category (the seven proven roots included)' % len(weapons)}})
    if sorted(item['weapon'] for item in found) != sorted(ADDITIONS):
        raise ValueError('reviewed additions %r, armory candidates %r' % (sorted(ADDITIONS),
            sorted(item['weapon'] for item in found)))
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.parse_args()
    source = json.loads(CATALOG.read_text(encoding='utf-8'))
    catalog = {w['name']: w for w in source['weapons']}
    rows = underbarrel() + equipped() + machete()
    for row in rows:
        entry = catalog[row['weapon']]
        roots = entry.get('candidateRoots') or entry['resources']
        if row['provenRoot'] not in roots or len(roots) != 2:
            raise ValueError('%s: %s is not one of its two candidate roots %r' % (row['weapon'], row['provenRoot'],
                roots))
        row.setdefault('droppedRoots', [r for r in roots if r != row['provenRoot']])
        if 'droppedIs' not in row:
            row['droppedIs'] = DROPPED_IS[row['weapon']]
    rows.sort(key=lambda r: r['weapon'])
    value = {'schemaVersion': 1, 'gameFingerprint': 'F5FEE03DCFDB',
        'scope': 'The real root of each player weapon the stat-fingerprint mapper resolves to two roots (DUPLICATE). '
            'Applied by scripts/generate_weapon_authoring.py: resources = [provenRoot], resolution UNIQUE. '
            'additions (0.31.3): armory player weapons the catalogue never named, catalogued on their own root.',
        'corrections': rows, 'additions': additions(source)}
    OUTPUT.write_text(json.dumps(value, indent=2) + '\n', newline='\n')
    print('wrote %s (%d weapons, %d additions)' % (OUTPUT.relative_to(ROOT), len(rows), len(value['additions'])))


if __name__ == '__main__':
    main()
