"""Read-only stats of every vanilla projectile type, for hd2.attack_output(id):stats() (0.31.2). Read-only, offline.

For each of the 350 ProjectileSettings rows of the pinned datalibrary (the same rows research/projectile-components
checked byte for byte against the live table of a retained mission snapshot) it records the members the Runtime already
names as fields (schemas/player_weapon_fields.json projectile.*, research/projectile-builder REFERENCES):

* flight: pellets per shot (+28), velocity (+32), mass (+36), drag (+40), gravity (+44), lifetime (+52), and the
  projectile-components ballistics members diameter (+24), lifetime variance (+56), penetration slowdown (+64);
* the direct-hit DamageInfo (+60) decoded from the damage table: standard / durable damage, the four armour
  penetration lanes, demolition, stagger, push force (the damage.* field offsets 4..36) and the status slots;
* the impact (+144) and expiry (+156) ExplosionType references.

Explosion names and stats come from research/explosion-identities (the explosion catalogue). Every value is checked
against research/projectile-components where both record it. Output: research/projectile-stats-F5FEE03DCFDB.json.

  py scripts/research_projectile_stats.py
"""
from __future__ import annotations

import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_profile  # noqa: E402
import research_projectile_builder as builder  # noqa: E402

OUTPUT = ROOT / 'research/projectile-stats-F5FEE03DCFDB.json'
COMPONENTS = ROOT / 'research/projectile-components-F5FEE03DCFDB.json'
EXPLOSIONS = ROOT / 'research/explosion-identities-F5FEE03DCFDB.json'
STATUSES = ROOT / 'research/status-effects-F5FEE03DCFDB.json'
ROW, TYPES = 272, 351
FLIGHT = {'diameter': (24, 'f32'), 'pellet_count': (28, 'u32'), 'velocity': (32, 'f32'), 'mass': (36, 'f32'),
    'drag': (40, 'f32'), 'gravity': (44, 'f32'), 'lifetime': (52, 'f32'), 'lifetime_variance': (56, 'f32'),
    'penetration_slowdown': (64, 'f32')}
REFERENCES = {'direct_damage': 60, 'impact_explosion': 144, 'expiry_explosion': 156}
DAMAGE = {'standard_damage': (4, 'i32'), 'durable_damage': (8, 'i32'), 'ap_direct': (12, 'u32'),
    'ap_slight': (16, 'u32'), 'ap_large': (20, 'u32'), 'ap_extreme': (24, 'u32'), 'demolition': (28, 'u32'),
    'stagger': (32, 'u32'), 'push_force': (36, 'u32')}


def value(raw, at, storage):
    if storage == 'f32':
        return round(struct.unpack_from('<f', raw, at)[0], 5)
    return struct.unpack_from('<i' if storage == 'i32' else '<I', raw, at)[0]


def build() -> dict:
    projectiles = builder.settings_rows('generated_projectile_settings.dl_bin', 'ProjectileSettings', ROW)
    damages = builder.settings_rows('generated_damage_settings.dl_bin', 'DamageSettings', 76)
    if sorted(projectiles) != list(range(1, TYPES)):
        raise ValueError('the datalibrary does not hold exactly the vanilla types 1..350')
    status_name = {row['nativeType']: row['semanticId'] for row in
        json.loads(STATUSES.read_text(encoding='utf-8'))['statuses']}
    components = {row['type']: row['components'] for row in json.loads(COMPONENTS.read_text(encoding='utf-8'))['rows']}
    explosions = {e['type']: e for e in json.loads(EXPLOSIONS.read_text(encoding='utf-8'))['explosions']}

    def damage(kind):
        item = damages.get(kind)
        if not kind or not item:
            return None
        raw = item['bytes']
        out = {key: value(raw, at, storage) for key, (at, storage) in DAMAGE.items()}
        out['statuses'] = [{'status': status_name.get(value(raw, 44 + 8 * i, 'u32'), value(raw, 44 + 8 * i, 'u32')),
            'strength': value(raw, 48 + 8 * i, 'f32')} for i in range(4) if value(raw, 44 + 8 * i, 'u32')]
        return out

    def explosion(kind):
        if not kind:
            return None
        item = explosions[kind]
        stats = item['stats']
        d = stats.get('damage')
        out = {'type': kind, 'name': item['name'], 'label': item['label'], 'inner_radius': stats['innerRadius'],
            'outer_radius': stats['outerRadius'], 'shockwave_radius': stats['shockwaveRadius'],
            'shrapnel_count': stats['shrapnelCount'], 'arc': bool(stats['arc']),
            'damage': {'standard_damage': d['standard'], 'durable_damage': d['durable'],
                'ap_direct': d['armorPenetration'][0], 'ap_slight': d['armorPenetration'][1],
                'ap_large': d['armorPenetration'][2], 'ap_extreme': d['armorPenetration'][3],
                'demolition': d['demolition'], 'stagger': d['stagger'], 'push_force': d['pushForce'],
                'statuses': d['statuses']} if d else None}
        # The explosion's own DamageInfo decoded here must agree with the explosion research.
        own = damage(stats.get('damageType'))
        if d and own and any(own[k] != out['damage'][k] for k in DAMAGE):
            raise ValueError(f'explosion {kind}: damage row disagrees with research/explosion-identities')
        return out

    rows = {}
    for kind in range(1, TYPES):
        raw = projectiles[kind]['bytes']
        flight = {key: value(raw, at, storage) for key, (at, storage) in FLIGHT.items()}
        refs = {key: value(raw, at, 'u32') for key, at in REFERENCES.items()}
        ballistics = components[kind]['ballistics']['values']
        for key, research_key in (('diameter', 'diameter'), ('velocity', 'speed'), ('mass', 'mass'), ('drag', 'drag'),
                ('gravity', 'gravity'), ('lifetime_variance', 'lifetime_variance'),
                ('penetration_slowdown', 'penetration_slowdown')):
            if abs(flight[key] - ballistics[research_key]) > 1e-3:
                raise ValueError(f'type {kind}: {key} disagrees with research/projectile-components')
        if refs['direct_damage'] != components[kind]['damage']['values']['direct_damage'] or \
                refs['impact_explosion'] != components[kind]['impact_explosion']['values']['impact_explosion']:
            raise ValueError(f'type {kind}: a reference disagrees with research/projectile-components')
        direct = damage(refs['direct_damage'])
        definition = components[kind]['damage'].get('definition')
        if direct and definition and (direct['standard_damage'], direct['durable_damage']) != (
                definition['standard'], definition['durable']):
            raise ValueError(f'type {kind}: direct damage disagrees with research/projectile-components')
        rows[str(kind)] = {'type': kind, 'flight': flight, 'directDamageType': refs['direct_damage'] or None,
            'directDamage': direct, 'impact': explosion(refs['impact_explosion']),
            'expiry': explosion(refs['expiry_explosion'])}
    return {'schemaVersion': 1, 'build': build_profile.BUILD_ID, 'writes': 0, 'protectionChanges': 0,
        'source': {'datalibrary': 'generated_projectile_settings / damage (pinned)',
            'checkedAgainst': ['research/projectile-components-F5FEE03DCFDB.json',
                'research/explosion-identities-F5FEE03DCFDB.json']},
        'members': {'flight': {k: v[0] for k, v in FLIGHT.items()}, 'references': REFERENCES,
            'damage': {k: v[0] for k, v in DAMAGE.items()}},
        'summary': {'types': len(rows), 'withDirectDamage': sum(1 for r in rows.values() if r['directDamage']),
            'withImpact': sum(1 for r in rows.values() if r['impact']),
            'withExpiry': sum(1 for r in rows.values() if r['expiry'])},
        'rows': rows}


def main():
    result = build()
    OUTPUT.write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(result['summary'], indent=1))


if __name__ == '__main__':
    main()
