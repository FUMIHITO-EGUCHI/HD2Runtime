"""Generate the payload options: every explosion a projectile payload field accepts, grouped by source family, and
what each payload field may not take (0.31.2; docs/explosions.md "Payload options").

A payload field (terminal.<role>.<phase>.explosion of a primary, secondary or support weapon, the attack outputs'
projectile.impact_explosion / expiry_explosion) takes, besides its own explosion and none, any catalogued explosion
whose package is known (the explosion catalogue's `payload`: the package is loaded before the write, or it is the
mission effects package, resident in every mission). This generator publishes that set once, with what an editor needs
to list it: the source group (weapons, support weapons, grenades, orbitals, eagles, hellbombs, sentries, mines,
vehicles, backpacks, enemies, other), the label, what the explosion leaves (a lingering status field, fire, shrapnel,
an arc), its damage and radius, warnings (very large blasts) and the acknowledgements. Per payload field it lists the
explosions it refuses: those whose shrapnel chain releases the written row again (RECURSIVE_COMPOSITION; the write
path re-proves this live).

Inputs (read-only): domains/explosion_catalogue.lua (payload, package, owners), research/explosion-identities (each
row's status and fire templates, shrapnel projectile), research/projectile-stats (each row's impact and expiry
explosion: the chain), domains/player_weapon_authoring.lua and domains/support_weapon_authoring.lua (the payload
fields), domains/status_catalog.lua (status names).

Outputs: domains/payload_options.lua (runtime: api/payload_options.lua) and sdk/PayloadOptions.json (contract
hd2runtime.payload_options.v1; semantic names only, no raw ids).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from reference_format import lua  # noqa: E402
from lua_offline import execute  # noqa: E402

EXPLOSIONS = ROOT / 'research/explosion-identities-F5FEE03DCFDB.json'
STATS = ROOT / 'research/projectile-stats-F5FEE03DCFDB.json'
LUA_OUTPUT = ROOT / 'domains/payload_options.lua'
JSON_OUTPUT = ROOT / 'sdk/PayloadOptions.json'
CONTRACT = 'hd2runtime.payload_options.v1'

GROUPS = (
    ('weapon', 'Primary and secondary weapons'),
    ('support_weapon', 'Support weapons'),
    ('throwable', 'Grenades and throwables'),
    ('orbital', 'Orbital strikes'),
    ('eagle', 'Eagle strikes'),
    ('hellbomb', 'Hellbombs'),
    ('sentry', 'Sentries and emplacements'),
    ('mine', 'Mines'),
    ('vehicle', 'Vehicles and exosuits'),
    ('backpack', 'Backpacks'),
    ('enemy', 'Enemies'),
    ('other', 'Other (world objects)'),
)
# Warnings an editor shows next to an option (codes in each option's `warnings`).
WARNINGS = {
    'very_large': 'A very large blast (2000 damage or more, or an outer radius of 20 m or more): it can kill the '
        'shooter and teammates nearby.',
    'lingering_field': 'Leaves a lingering status field (gas, EMS, smoke...). The game holds at most 4096 of them and '
        'does not check the count: avoid it on fast-firing weapons.',
    'fire': 'Leaves fire on the ground.',
    'shrapnel': 'Releases shrapnel or bomblets (projectiles of their own).',
    'arc': 'Releases an electric arc.',
    'no_damage': 'Deals no damage itself (its effect is a status field, smoke or a push).',
}
VERY_LARGE_DAMAGE = 2000
VERY_LARGE_RADIUS = 20.0
ACKNOWLEDGEMENTS = ['allow_unverified_reference', 'allow_unverified_effect']
RECURSIVE = ('RECURSIVE_COMPOSITION: its shrapnel chain releases the projectile this field writes, which would then '
    'spawn itself')


def lua_data() -> dict:
    """The payload fields of the generated weapon domains, the explosion catalogue and the status names."""
    modules = {name: (ROOT / ('domains/' + name + '.lua')).read_text(encoding='utf-8') for name in
        ('explosion_catalogue', 'player_weapon_authoring', 'support_weapon_authoring', 'status_catalog')}
    source = ''.join('local %s=(function()\n%s\nend)()\n' % (name, body) for name, body in modules.items())
    source += 'local json=(function()\n%s\nend)()\n' % (ROOT / 'primary_mapper/json.lua').read_text(encoding='utf-8')
    source += r'''
local fields={}
local function collect(kind,db)
 for name,weapon in pairs(db.weapons)do
  for _,f in ipairs(weapon.fields or{})do
   if f.type=='explosion_reference'then
    fields[#fields+1]={kind=kind,weapon=name,field=f.semanticFieldId,role=f.referenceRole,phase=f.referencePhase,
     row=f.backing.recordType,current=f.currentDefault.explosionType,editable=f.editable==true
      and not weapon.ordinaryWritesBlocked,shared=f.affectsMultipleWeapons==true,
     acknowledgement=f.acknowledgement or json.null}
   end
  end
 end
end
collect('player_weapon',player_weapon_authoring)
collect('support_weapon',support_weapon_authoring)
local explosions={}
for id,e in pairs(explosion_catalogue.explosions)do
 explosions[id]={type=e.type,label=e.label,family=e.family,payload=e.payload==true,shared=e.shared==true,
  mission=e.package and e.package.mission==true or false,via=e.package and e.package.via or json.null,
  owners=e.owners,values=e.values,shrapnel=e.shrapnel==true,arc=e.arc==true,damage=e.damage~=nil}
end
local statuses={}
for t,id in pairs(status_catalog.byType)do statuses[tostring(t)]=id end
return json.encode({fields=fields,explosions=explosions,order=explosion_catalogue.order,statuses=statuses})'''
    return json.loads(execute(source.encode()))


def owner_name(entry) -> str:
    return entry['label'].split(' (')[0]


def group_of(name: str, entry: dict) -> str:
    family = entry['family']
    owner = owner_name(entry)
    if 'Hellbomb' in owner:
        return 'hellbomb'
    if family in ('weapon', 'support_weapon', 'throwable', 'backpack', 'vehicle', 'enemy'):
        return family
    if family == 'entity':
        return 'other'
    assert family == 'stratagem', name
    if owner.startswith('Orbital'):
        return 'orbital'
    if owner.startswith('Eagle'):
        return 'eagle'
    if owner.startswith(('A/', 'E/')):
        return 'sentry'
    if owner.startswith('MD-'):
        return 'mine'
    if owner.startswith(('EXO-', 'M-10', 'TD-', 'FRV')):
        return 'vehicle'
    raise AssertionError('unclassified stratagem explosion: ' + name)


def chains(research: dict, stats: dict) -> dict:
    """{explosion type: projectile types its shrapnel chain releases} (bounded, like the live check)."""
    shrapnel = {item['type']: item['stats']['shrapnelProjectile'] for item in research['explosions']}
    terminal = {int(key): [row[phase]['type'] for phase in ('impact', 'expiry') if row.get(phase)]
        for key, row in stats['rows'].items()}
    out = {}
    for start in shrapnel:
        seen, queue, released = set(), [start], set()
        while queue:
            current = queue.pop()
            if not current or current in seen:
                continue
            seen.add(current)
            assert len(seen) <= 64, 'explosion chain longer than reviewed: ' + str(start)
            projectile = shrapnel.get(current) or 0
            if projectile:
                released.add(projectile)
                queue.extend(terminal.get(projectile, []))
        out[start] = sorted(released)
    return out


def build() -> tuple[dict, dict]:
    research = json.loads(EXPLOSIONS.read_text(encoding='utf-8'))
    stats = json.loads(STATS.read_text(encoding='utf-8'))
    if research['writes'] or stats['writes']:
        raise ValueError('the payload option sources must be read-only')
    data = lua_data()
    rows = {item['type']: item for item in research['explosions']}
    released = chains(research, stats)
    group_index = {key: index for index, (key, _) in enumerate(GROUPS)}
    options, runtime_options = [], {}
    for name in data['order']:
        entry = data['explosions'][name]
        if not entry['payload']:
            continue
        row = rows[entry['type']]['stats']
        values = entry['values']
        damage = values[4] if entry['damage'] else 0
        durable = values[5] if entry['damage'] else 0
        outer = values[1]
        statuses = [data['statuses'].get(str(status), 'status ' + str(status))
            for status in (row['damage'] or {}).get('statuses') or []] if row.get('damage') else []
        warnings = []
        if max(damage, durable) >= VERY_LARGE_DAMAGE or outer >= VERY_LARGE_RADIUS:
            warnings.append('very_large')
        if row['statusTemplate']:
            warnings.append('lingering_field')
        if row['fireTemplate']:
            warnings.append('fire')
        if row['shrapnelCount'] and row['shrapnelProjectile']:
            warnings.append('shrapnel')
        if row['arc']:
            warnings.append('arc')
        if not damage and not durable:
            warnings.append('no_damage')
        group = group_of(name, entry)
        item = {'name': name, 'label': entry['label'], 'owner': owner_name(entry), 'group': group,
            'family': entry['family'], 'damage': damage, 'durableDamage': durable,
            'innerRadius': values[0], 'outerRadius': outer, 'statuses': statuses,
            'lingeringField': bool(row['statusTemplate']), 'fire': bool(row['fireTemplate']),
            'shrapnel': bool(row['shrapnelCount'] and row['shrapnelProjectile']), 'arc': bool(row['arc']),
            'warnings': warnings, 'sharedRow': entry['shared'],
            'package': {'mission': entry['mission'], 'loadedByRuntime': not entry['mission'], 'via': entry['via']},
            'acknowledgements': list(ACKNOWLEDGEMENTS)}
        options.append(item)
        runtime_options[name] = dict(item, releases=released.get(entry['type'], []))
    options.sort(key=lambda item: (group_index[item['group']], item['label'].lower(), item['name']))
    order = [item['name'] for item in options]
    by_type = {data['explosions'][name]['type']: name for name in data['explosions']}
    fields, runtime_fields = [], {}
    for field in sorted(data['fields'], key=lambda f: (f['kind'], f['weapon'], f['field'])):
        excluded = [{'name': name, 'reason': RECURSIVE} for name in order
            if field['row'] in runtime_options[name]['releases']]
        key = field['kind'] + ':' + field['weapon'] + ':' + field['field']
        current = by_type.get(field['current']) if field['current'] else None
        public = {'resource': field['kind'], 'weapon': field['weapon'], 'field': field['field'],
            'apiField': 'hd2.fields.terminal.explosion', 'role': field['role'], 'phase': field['phase'],
            'current': current, 'editable': field['editable'], 'shared': field['shared'],
            'acknowledgements': {
                'own': sorted(set(filter(None, [field.get('acknowledgement'),
                    'allow_shared' if field['shared'] else None]))),
                'catalogue': sorted(set(filter(None, [field.get('acknowledgement'),
                    'allow_shared' if field['shared'] else None] + ACKNOWLEDGEMENTS)))},
            'excluded': excluded}
        fields.append(public)
        runtime_fields[key] = {'excluded': {item['name']: item['reason'] for item in excluded}}
    counts = {}
    for item in options:
        counts[item['group']] = counts.get(item['group'], 0) + 1
    groups = [{'id': key, 'label': label, 'count': counts.get(key, 0)} for key, label in GROUPS]
    summary = {'options': len(options), 'byGroup': {key: counts.get(key, 0) for key, _ in GROUPS},
        'missionPackage': sum(item['package']['mission'] for item in options),
        'veryLarge': sum('very_large' in item['warnings'] for item in options),
        'lingeringField': sum(item['lingeringField'] for item in options),
        'payloadFields': len(fields),
        'payloadFieldsByResource': {kind: sum(f['resource'] == kind for f in fields)
            for kind in ('player_weapon', 'support_weapon')},
        'recursiveExclusions': sum(len(f['excluded']) for f in fields)}
    runtime = {'groups': [{'id': key, 'label': label} for key, label in GROUPS], 'order': order,
        'options': runtime_options, 'fields': runtime_fields, 'warnings': WARNINGS, 'recursive': RECURSIVE,
        'summary': summary}
    public = {'contract': CONTRACT, 'schemaVersion': 1, 'build': research['build'],
        'hd2RuntimeVersion': (ROOT / 'VERSION').read_text().strip(),
        'source': 'domains/explosion_catalogue.lua, research/explosion-identities, research/projectile-stats '
            '(scripts/generate_payload_options.py)',
        'model': [
            'A payload field takes its own explosion (terminal:explosion()), none (terminal:no_explosion()) or any '
            'option below as hd2.explosion(name).',
            'An option is a catalogued explosion whose package is known: Runtime loads that package before the write '
            '(the operation waits, waiting_for_assets) or, for the mission effects package, needs none (resident in '
            'every mission). A package that cannot be loaded within 90 s rejects the operation with ASSET_UNAVAILABLE '
            'and the row keeps its value.',
            'Every option needs allow_unverified_reference and allow_unverified_effect (no catalogued payload is '
            'live-tested), plus the field\'s own acknowledgements (fields[].acknowledgements.catalogue).',
            'A field refuses an option whose shrapnel chain releases the row it writes (fields[].excluded); the write '
            'path re-proves the chain live.',
            'The option\'s explosion row is only referenced: its own values stay those of its owner, and editing them '
            '(hd2.explosion(name)) changes every owner.'],
        'groups': groups, 'warnings': WARNINGS, 'summary': summary, 'options': options, 'fields': fields,
        'safety': {'rawIds': False, 'writes': 0}}
    return runtime, public


def outputs() -> dict:
    runtime, public = build()
    return {LUA_OUTPUT: '-- Generated by scripts/generate_payload_options.py; do not edit.\nreturn ' + lua(runtime) + '\n',
        JSON_OUTPUT: json.dumps(public, indent=2) + '\n'}


def generate(check=False):
    stale = []
    for path, body in outputs().items():
        if not path.exists() or path.read_text(encoding='utf-8') != body:
            stale.append(path)
            if not check:
                path.write_text(body, encoding='utf-8', newline='\n')
    if check and stale:
        raise RuntimeError('Stale payload option outputs: ' + ', '.join(str(path) for path in stale))
    return stale


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(', '.join(str(path.relative_to(ROOT)) for path in generate(args.check)) or 'up to date')
