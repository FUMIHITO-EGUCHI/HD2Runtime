"""Acknowledgements a field gained in a later SDK, for version-aware compatibility with older mods.

A mod built with an older SDK was valid when it was written: its operations carry every acknowledgement that SDK
asked for. When a later SDK adds an acknowledgement to a field that was writable without one (0.28.0 added
allow_unverified_effect to 144 player weapon projectile, damage and explosion fields whose fired row it could no
longer establish, and to the SH-51 Directional Shield body's health and armor; 0.30.0 to the PLAS-45 Epoch's 30
partial-charge projectile, damage and explosion fields, a row only its partial charge fires), Runtime accepts that
field without the acknowledgement from a mod that declares an older SDK, and logs it as a legacy operation
(docs/legacy-sdk-compatibility.md). Mods that declare the newer SDK keep the rule.

A later SDK can also bound a field an earlier one let mods write without a maximum (0.31.2: a magazine's capacity and
magazine counts, by the network fields of the live counts; scripts/ammo_limits.py). A mod that declares an older SDK
keeps working: its larger value is clamped to the maximum and logged as a legacy operation.

  py scripts/generate_legacy_acknowledgements.py --research v0.28.1 0.30.0
      Compare the SDK catalogs published at tag v0.28.1 with the current ones and record, in
      schemas/legacy_acknowledgements.json, every field that 0.28.1 accepted without allow_unverified_effect and
      that now needs it, as introduced in 0.30.0. Entries of other releases are kept (0.28.0 was recorded with
      --research v0.27.0 0.28.0).
  py scripts/generate_legacy_acknowledgements.py --limits v0.31.1 0.31.2
      Compare the same way and record, in its "limits" list, every field the SDK at the tag let mods write with no
      maximum (or a larger one) that now carries a network ceiling (a field's networkLimit), as introduced in 0.31.2.
  py scripts/generate_legacy_acknowledgements.py [--check]
      Write (or check) domains/legacy_acknowledgements.lua, the runtime lookup, from that reviewed file. Every entry
      must still name an existing field.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / 'schemas/legacy_acknowledgements.json'
LUA_OUTPUT = ROOT / 'domains/legacy_acknowledgements.lua'
ACKNOWLEDGEMENT = 'allow_unverified_effect'
PLAYER = 'sdk/PlayerWeaponAuthoringCapabilities.json'
SUPPORT = 'sdk/SupportWeaponAuthoringCapabilities.json'
VEHICLE = 'sdk/VehicleWeaponCapabilities.json'
ATTACHMENT = 'sdk/MagazineAttachmentCapabilities.json'
# Catalogs whose field instances carry an instanceKey and a semantic target; only the resources the runtime lookup
# supports (domains/entity_writes.lua) may carry legacy entries.
INSTANCE_RESOURCES = {'backpack', 'vehicle'}


def lua(value) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, dict):
        return '{' + ','.join('[' + lua(key) + ']=' + lua(item) for key, item in sorted(value.items())) + '}'
    return '{' + ','.join(lua(item) for item in value) + '}'


def entity_field_key(target, field_id):
    """The lookup key of an entity field: its target path, linked entity, damage zone and mount, then its id (the
    identity domains/entity_writes.lua find_field matches)."""
    return '|'.join((target.get('path') or '', target.get('linked') or '', target.get('zone') or '',
        target.get('mount') or '', field_id))


def fields(catalogs):
    """Every field instance of the catalogs: key -> (identity, the field entry)."""
    found = {}
    player = catalogs.get(PLAYER)
    for weapon in (player or {}).get('weapons', []):
        for field in weapon['fields']:
            found[('player_weapon', weapon['name'], field['semanticFieldId'])] = field
    # Support weapons: the attack-qualified id (domains/player_weapon_writes.lua passes field.semanticFieldId, e.g.
    # explosion.primary_impact.inner_radius, with the resource support_weapon and the weapon name).
    for field in (catalogs.get(SUPPORT) or {}).get('fieldInstances', []):
        qualified = field.get('qualifiedSemanticFieldId')
        if qualified:
            operation = field.get('operation') or {}
            found[('support_weapon', field['supportWeapon'], qualified)] = {'editable': bool(field.get('writable')),
                'acknowledgement': operation.get('acknowledgement'), 'apiFieldConstant': field.get('apiFieldConstant'),
                'acknowledgementReason': operation.get('acknowledgementReason')}
    for path, catalog in sorted(catalogs.items()):
        if path == SUPPORT:
            continue
        for field in catalog.get('fieldInstances', []) if isinstance(catalog, dict) else []:
            target = field.get('target') or {}
            resource = target.get('resource')
            name = target.get(resource) if resource else None
            if not isinstance(name, str) or 'semanticFieldId' not in field:
                continue
            found[(resource, name, entity_field_key(target, field['semanticFieldId']))] = field
    return found


def git_catalogs(tag):
    names = subprocess.run(['git', 'ls-tree', '--name-only', tag, 'sdk/'], cwd=ROOT, capture_output=True, text=True,
        check=True).stdout.split()
    result = {}
    for name in names:
        if name.endswith('.json'):
            body = subprocess.run(['git', 'show', f'{tag}:{name}'], cwd=ROOT, capture_output=True, check=True).stdout
            result[name] = json.loads(body.decode('utf-8'))
    return result


def current_catalogs():
    return {path.relative_to(ROOT).as_posix(): json.loads(path.read_text(encoding='utf-8'))
        for path in sorted((ROOT / 'sdk').glob('*.json'))}


def published_max(field):
    """The maximum a published field instance states: its own max, or that of its support-weapon block."""
    if field.get('max') is not None:
        return field['max']
    for block in ('networkLimit', 'teamReload'):
        if isinstance(field.get(block), dict) and field[block].get('max') is not None:
            return field[block]['max']
    return None


def limit_fields(catalogs):
    """Every published field instance a network ceiling can apply to (scripts/ammo_limits.py): key ->
    {'editable', 'max', 'networkLimit', 'reason', 'apiFieldConstant'}. Keys are what the write domains pass:
    (resource, target, field id); a support weapon's id is attack-qualified, an attachment's target its semantic id."""
    found = {}

    def add(key, field, editable):
        limit = field.get('networkLimit')
        found[key] = {'editable': bool(editable), 'max': published_max(field), 'networkLimit': limit,
            'reason': field.get('rangeReason') or (limit or {}).get('rangeReason'),
            'apiFieldConstant': field.get('apiFieldConstant')}
    for weapon in (catalogs.get(PLAYER) or {}).get('weapons', []):
        for field in weapon['fields']:
            add(('player_weapon', weapon['name'], field['semanticFieldId']), field, field.get('editable'))
    for field in (catalogs.get(SUPPORT) or {}).get('fieldInstances', []):
        if field.get('qualifiedSemanticFieldId'):
            add(('support_weapon', field['supportWeapon'], field['qualifiedSemanticFieldId']), field,
                field.get('writable'))
    for field in (catalogs.get(VEHICLE) or {}).get('fieldInstances', []):
        add(('vehicle_weapon', field['weapon'], field['semanticFieldId']), field, field.get('writable'))
    for field in (catalogs.get(ATTACHMENT) or {}).get('fieldInstances', []):
        target = field.get('target') or {}
        if target.get('attachment'):
            add(('weapon_attachment', target['attachment'], field['semanticFieldId']), field, field.get('editable'))
    return found


def research_limits(tag, since):
    """Record the fields `since` bounded by a network ceiling that the SDK at `tag` let mods write above it."""
    previous = limit_fields(git_catalogs(tag))
    entries = []
    for key, field in sorted(limit_fields(current_catalogs()).items()):
        old = previous.get(key)
        limit = field['networkLimit']
        if not limit or not field['editable'] or old is None or not old['editable']:
            continue
        if old['max'] is not None and old['max'] <= limit['max']:
            continue
        resource, target, field_key = key
        entries.append({'since': since, 'resource': resource, 'target': target, 'field': field_key,
            'max': limit['max'], 'previousMax': old['max'], 'networkField': limit['networkField'],
            'apiFieldConstant': field['apiFieldConstant'], 'reason': field['reason']})
    history = json.loads(HISTORY.read_text(encoding='utf-8'))
    commit = subprocess.run(['git', 'rev-list', '-n', '1', tag], cwd=ROOT, capture_output=True, text=True,
        check=True).stdout.strip()
    history['limitsDescription'] = ("Maxima a field gained in a later SDK (the network ceilings of a magazine's live "
        'counts, scripts/ammo_limits.py). A mod that declares an SDK older than `since` wrote the field with no '
        'maximum and was valid then; Runtime clamps its larger value to `max` and logs it as a legacy operation '
        '(docs/legacy-sdk-compatibility.md). Generated by scripts/generate_legacy_acknowledgements.py --limits; '
        'reviewed.')
    history['limitReleases'] = sorted([item for item in history.get('limitReleases', []) if item['since'] != since]
        + [{'since': since, 'comparedWith': tag, 'comparedWithCommit': commit,
            'rule': 'editable with no maximum or a larger one in the SDK published at ' + tag + ', bounded by a '
            'network ceiling in ' + since}], key=lambda item: [int(part) for part in item['since'].split('.')])
    history['limits'] = [item for item in history.get('limits', []) if item['since'] != since] + entries
    HISTORY.write_text(json.dumps(history, indent=1, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    return entries


def needs(field):
    return bool(field.get('editable')) and field.get('acknowledgement') == ACKNOWLEDGEMENT


def research(tag, since):
    """Record the fields `since` started to require the acknowledgement on, compared with the SDK at `tag`."""
    previous = fields(git_catalogs(tag))
    current = fields(current_catalogs())
    entries = []
    for key, field in sorted(current.items()):
        old = previous.get(key)
        if old is None or not needs(field) or not old.get('editable') or old.get('acknowledgement') == ACKNOWLEDGEMENT:
            continue
        resource, target, field_key = key
        if resource not in ('player_weapon', 'support_weapon') and resource not in INSTANCE_RESOURCES:
            raise RuntimeError(f'{resource} {target} {field_key}: no runtime lookup for this resource')
        entries.append({'since': since, 'acknowledgement': ACKNOWLEDGEMENT, 'resource': resource, 'target': target,
            'field': field_key, 'apiFieldConstant': field.get('apiFieldConstant'),
            'reason': field.get('acknowledgementReason')})
    history = json.loads(HISTORY.read_text(encoding='utf-8')) if HISTORY.exists() else {'schemaVersion': 1,
        'releases': [], 'entries': []}
    commit = subprocess.run(['git', 'rev-list', '-n', '1', tag], cwd=ROOT, capture_output=True, text=True,
        check=True).stdout.strip()
    history['description'] = ('Acknowledgements a field gained in a later SDK. A mod that declares an SDK older than '
        '`since` wrote the field without the acknowledgement and was valid then; Runtime accepts it as a legacy '
        'operation and logs it (docs/legacy-sdk-compatibility.md). Generated by '
        'scripts/generate_legacy_acknowledgements.py --research; reviewed.')
    history['releases'] = sorted([item for item in history['releases'] if item['since'] != since]
        + [{'since': since, 'comparedWith': tag, 'comparedWithCommit': commit,
            'rule': 'editable without ' + ACKNOWLEDGEMENT + ' in the SDK published at ' + tag + ', editable and '
            'requiring it in ' + since}], key=lambda item: [int(part) for part in item['since'].split('.')])
    history['entries'] = [item for item in history['entries'] if item['since'] != since] + entries
    HISTORY.write_text(json.dumps(history, indent=1, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    return entries


def build():
    history = json.loads(HISTORY.read_text(encoding='utf-8'))
    current = fields(current_catalogs())
    table, missing = {}, []
    for entry in history['entries']:
        key = (entry['resource'], entry['target'], entry['field'])
        if key not in current:
            missing.append(' '.join(key))
            continue
        by_target = table.setdefault(entry['acknowledgement'], {}).setdefault(entry['resource'], {})
        by_target.setdefault(entry['target'], {})[entry['field']] = entry['since']
    # Maxima (0.31.2): network_limit -> resource -> target -> field -> {since, max}. Each entry still names a field
    # with that network ceiling.
    bounded = limit_fields(current_catalogs())
    for entry in history.get('limits', []):
        key = (entry['resource'], entry['target'], entry['field'])
        field = bounded.get(key)
        if field is None or not field['networkLimit'] or field['networkLimit']['max'] != entry['max']:
            missing.append(' '.join(key) + ' (max ' + str(entry['max']) + ')')
            continue
        by_target = table.setdefault('network_limit', {}).setdefault(entry['resource'], {})
        by_target.setdefault(entry['target'], {})[entry['field']] = {'since': entry['since'], 'max': entry['max']}
    if missing:
        raise RuntimeError('schemas/legacy_acknowledgements.json names fields that no longer exist: '
            + ', '.join(missing))
    return ('-- Generated by scripts/generate_legacy_acknowledgements.py from schemas/legacy_acknowledgements.json;\n'
        '-- do not edit. acknowledgement -> resource -> target -> field -> the SDK version that introduced it;\n'
        '-- network_limit -> resource -> target -> field -> {since, max}: a maximum introduced by that SDK.\n'
        'return ' + lua(table) + '\n')


def generate(check=False):
    body = build()
    stale = not LUA_OUTPUT.exists() or LUA_OUTPUT.read_text(encoding='utf-8') != body
    if stale and check:
        raise RuntimeError('Stale legacy acknowledgement table: ' + str(LUA_OUTPUT))
    if stale:
        LUA_OUTPUT.write_text(body, encoding='utf-8', newline='\n')
    return [LUA_OUTPUT] if stale else []


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--research', nargs=2, metavar=('TAG', 'SINCE'),
        help='compare the SDK catalogs at TAG with the current ones and record them as introduced in SINCE')
    parser.add_argument('--limits', nargs=2, metavar=('TAG', 'SINCE'),
        help='compare the SDK catalogs at TAG with the current ones and record the maxima introduced in SINCE')
    args = parser.parse_args()
    if args.research:
        print(len(research(*args.research)), 'fields gained', ACKNOWLEDGEMENT, 'in', args.research[1])
    if args.limits:
        print(len(research_limits(*args.limits)), 'fields gained a maximum in', args.limits[1])
    print(', '.join(str(p) for p in generate(args.check)) or 'up to date')
