"""The game's own names of the Runtime's objects (0.31.2; research/docs/game-text-api-F5FEE03DCFDB.md, docs/game-text.md).

The domain generators stamp an internal `nameText` record into their runtime entries: the u32 text ids of the object's
name, upper-case name, designation prefix and description, as the game's own records hold them, plus the en-US
designation (a model number, the fallback when a language's prefix text is empty). runtime/text_resources.lua looks the
ids up in the game's text registry (only the current game language is in memory) and api/text.lua composes the display
name. The ids are internal: they go into the runtime domains only, never into a public SDK JSON.

Input: research/weapon-name-text-ids-F5FEE03DCFDB.json (research/scripts/research_weapon_name_text.py, private), the
EncyclopediaEntry record of each object's entity resource, the booster table row of each booster and the StratagemInfo
row of each stratagem. Stamped by identity (entity resource, booster enum value, stratagem id), never by name:

- equipment (player, support weapons, throwables, backpacks, vehicles): the first of the entry's attack resource and
  entity resources (identityResource, resource, resources) whose record the research resolved for an equipment object.
  Underbarrels (sub-weapons) have no record and get none: their name falls back to the key.
- `name` is the cased name id, or the upper-case one when the object has no cased text (the CQC melee weapons, LAS-58
  Talon, TED-63 Dynamite, ...: the same in every language).
- `designation`: the en-US prefix text; for a record without a prefix whose key is a designation plus the game's name
  (StratagemInfo has no designation member; the support-weapon backpacks), the key's designation.
- `keyMismatch`: the game's en-US name is not the key (reviewed: CQC-73 / the game's CQC-72, the RL-77 backpack, the
  Super Earth FRV variant and the GATER rig). The game's name is still shown; the key stays the identity.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / 'research/weapon-name-text-ids-F5FEE03DCFDB.json'
EQUIPMENT = ('primary', 'secondary', 'support', 'throwable', 'backpack', 'vehicle')
_CACHE = {}


def norm(text):
    return re.sub(r'[^A-Z0-9]', '', (text or '').upper())


def load() -> dict:
    if 'research' not in _CACHE:
        research = json.loads(RESEARCH.read_text(encoding='utf-8'))
        by_resource = {}
        for item in research['objects']:
            if item['family'] not in EQUIPMENT or not item.get('textIds'):
                continue
            resource = int(item['resource'], 16)
            record = (item['textIds'], item['en'], item['nameSource'])
            if by_resource.setdefault(resource, record) != record:
                raise ValueError(f'game names: resource {item["resource"]} has two records')
        _CACHE['research'] = {'build': research['build'], 'byResource': by_resource,
            'boosters': {item['enumValue']: item for item in research['boosters']},
            'stratagems': {item['id']: item for item in research['stratagems'] if item.get('textIds')}}
    return _CACHE['research']


def _id(value):
    return int(value, 16) if value else None


def _designation(key, prefix, name):
    """The en-US designation: the prefix text, else the key's leading designation when the key ends with the name."""
    if prefix:
        return prefix
    name = (name or '').strip()
    if name and key.lower().endswith(name.lower()) and len(key) > len(name):
        head = key[:len(key) - len(name)].strip()
        return head or None
    return None


def _record(key, ids, name_id, prefix_text, name_text):
    designation = _designation(key, prefix_text, name_text)
    composed = ' '.join(part for part in (designation, (name_text or '').strip()) if part)
    out = {'name': name_id, 'nameUpper': _id(ids.get('nameUpper'))}
    if ids.get('prefix'):
        out['prefix'] = _id(ids['prefix'])
    if ids.get('description'):
        out['description'] = _id(ids['description'])
    if designation:
        out['designation'] = designation
    if norm(composed) != norm(key):
        out['keyMismatch'] = True
    return out


def resources_of(entry: dict) -> list[int]:
    """The entry's entity resources in the research's order: identityResource, resource, then resources."""
    out = []
    for value in [entry.get('identityResource'), entry.get('resource')] + list(entry.get('resources') or []):
        if isinstance(value, str) and value.startswith('0x'):
            value = int(value, 16)
        if isinstance(value, int) and value not in out:
            out.append(value)
    return out


def equipment(key: str, entry: dict) -> dict | None:
    """nameText of an equipment entry (weapon, throwable, backpack, vehicle), or None (no record: underbarrels)."""
    index = load()['byResource']
    preferred = [int(entry['attackResource'], 16)] if entry.get('attackResource') else []
    for resource in preferred + resources_of(entry):
        if resource in index:
            ids, en, source = index[resource]
            name_id = _id(ids['name'] if source == 'cased' else ids['nameUpper'])
            return _record(key, ids, name_id, en.get('prefix'), en.get('name') or en.get('nameUpper'))
    return None


def booster(key: str, enum_value: int) -> dict | None:
    item = load()['boosters'].get(enum_value)
    if item is None:
        return None
    ids, en = item['textIds'], item['en']
    name_id = _id(ids['nameUpper'] if item.get('nameFallbackToUpper') else ids['name'])
    return _record(key, ids, name_id, None, en.get('name') or en.get('nameUpper'))


def stratagem(key: str, stratagem_id: int) -> dict | None:
    item = load()['stratagems'].get(stratagem_id)
    if item is None:
        return None
    ids = item['textIds']
    return _record(key, ids, _id(ids.get('name') or ids.get('nameUpper')), None, item['en'].get('name'))


def stamped(entries: dict, name_text) -> dict:
    """A copy of {key: entry} with nameText added where name_text(key, entry) gives one (the entries are not
    changed: a generator's public document may share them)."""
    out = {}
    for key, entry in entries.items():
        record = name_text(key, entry)
        out[key] = dict(entry, nameText=record) if record else entry
    return out
