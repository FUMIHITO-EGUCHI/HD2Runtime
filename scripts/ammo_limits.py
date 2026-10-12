"""The game's network ceilings for a weapon's live ammunition, as field maxima for the weapon generators (0.31.2).

The live round count of a magazine weapon is the network field rounds (int, 11 bits, 0..2047) and its spare-magazine
count the network field magazines_remaining (int, 5 bits, 0..31): research/pelican-F5FEE03DCFDB.json ammoNetwork,
research/docs/pelican-cas-F5FEE03DCFDB.md section 20a. The engine's field validator saturates a larger value in place
at the next flush (every shot queues one), so a capacity above 2047 shows only until the first shot, and peers read
the clamped or an out-of-date count (a player report: a Bastion coax capacity of 2500 showed about 2100 for its owner
and 500 for a friend). The magazine counts are written into the spare count, so 31 bounds them too.

Every generator that exposes WeaponMagazineComponentData +136 (capacity) or +140 / +144 / +148 (starting, from supply
and maximum spare magazines) applies these maxima, keeping any smaller reviewed maximum. A mod that declares an SDK
older than SINCE wrote these fields without the maximum; its larger value is clamped to the maximum as a logged legacy
operation (core/sdk_compatibility.lua, schemas/legacy_acknowledgements.json "limits",
docs/legacy-sdk-compatibility.md).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / 'research/pelican-F5FEE03DCFDB.json'
SINCE = '0.31.2'
_CACHE = {}


def network() -> dict:
    """{'rounds': 2047, 'spareMagazines': 31} from the research, checked against its field definitions."""
    if 'network' not in _CACHE:
        fields = json.loads(RESEARCH.read_text(encoding='utf-8'))['ammoNetwork']['fields']
        result = {}
        for name in ('rounds', 'spareMagazines'):
            (field,) = fields[name]
            if field['kind'] != 1 or field['min'] != 0 or field['max'] != (1 << field['bits']) - 1:
                raise ValueError(f'ammo network field {name} changed: {field!r}')
            result[name] = field['max']
        _CACHE['network'] = result
    return _CACHE['network']


def reasons() -> dict:
    limits = network()
    rounds = ('the live round count is the network field rounds (11 bits): the game clamps it to '
        f"{limits['rounds']} at the next shot, so a larger capacity shows only until the first shot and teammates "
        'see a different count')
    magazines = ('the live spare-magazine count is the network field magazines_remaining (5 bits): the game clamps '
        f"it to {limits['spareMagazines']} on every write")
    return {'rounds': rounds, 'magazines': magazines}


def limits() -> dict:
    """Field id -> (maximum, range reason, network field) for every field these maxima apply to."""
    if 'limits' not in _CACHE:
        values, why = network(), reasons()
        rounds = (values['rounds'], why['rounds'], 'rounds')
        magazines = (values['spareMagazines'], why['magazines'], 'magazines_remaining')
        _CACHE['limits'] = {'weapon.capacity': rounds, 'magazine.capacity': rounds,
            'attachment.magazine_capacity': rounds,
            'magazine.starting_magazines': magazines, 'magazine.magazines_from_supply': magazines,
            'magazine.spare_magazines': magazines, 'attachment.starting_magazines': magazines,
            'attachment.magazines_from_supply': magazines, 'attachment.spare_magazines': magazines}
    return _CACHE['limits']


def apply(field: dict, field_id: str | None = None) -> dict:
    """Bound one generated field dict (its 'min' / 'max' / 'rangeReason' keys) by its network ceiling. A smaller
    reviewed maximum is kept. The field gains 'networkLimit' (the ceiling and its network field) whenever the ceiling
    applies. Returns the field."""
    field_id = field_id or field.get('semanticFieldId') or field.get('id')
    limit = limits().get(field_id)
    if limit is None:
        return field
    maximum, reason, network_field = limit
    if field.get('max') is None or field['max'] > maximum:
        field['max'] = maximum
        field['rangeReason'] = reason
    if field.get('currentDefault') is not None and isinstance(field['currentDefault'], (int, float)) \
            and field['currentDefault'] > maximum:
        raise ValueError(f'{field_id}: the reviewed value {field["currentDefault"]} is above the network ceiling')
    field['networkLimit'] = {'max': maximum, 'networkField': network_field}
    return field


# 0.31.3: a rounds-fed weapon (WeaponRounds) replicates its spare rounds as spare_rounds, an int of 9 bits (0..511),
# and the chamber flag; the rounds in the feed have no network field (research/ammo-network-fields-F5FEE03DCFDB.json
# fieldSets, the 25 WeaponRounds types). Starting and supply rounds are written into the spare count, so 511 bounds
# them too. Used by the mounted-weapon generator only (the EXO-55 Breakthrough cannon): the player and support rounds
# fields keep their published ranges (team reload: TEAM_ROUNDS_MAX, the same 511).
FEED_RESEARCH = ROOT / 'research/ammo-network-fields-F5FEE03DCFDB.json'
ROUNDS_FEED_FIELDS = ('rounds.spare_rounds', 'rounds.rounds_from_supply', 'rounds.starting_rounds')


def spare_rounds() -> int:
    """511, from the research's spare_rounds width, checked to be one 9-bit int field in the rounds-feed set."""
    if 'spareRounds' not in _CACHE:
        research = json.loads(FEED_RESEARCH.read_text(encoding='utf-8'))
        (field,) = research['fieldWidths']['spare_rounds']
        if field['kind'] != 1 or field['min'] != 0 or field['max'] != (1 << field['bits']) - 1 \
                or 'chamber_empty+spare_rounds' not in research['fieldSets'] or not research['checks']['spareRounds9Bits']:
            raise ValueError(f'ammo network field spare_rounds changed: {field!r}')
        _CACHE['spareRounds'] = field['max']
    return _CACHE['spareRounds']


def apply_rounds_feed(field: dict) -> dict:
    """Bound a rounds-feed spare/starting/supply field by the 9-bit spare_rounds ceiling (like apply)."""
    field_id = field.get('semanticFieldId') or field.get('id')
    if field_id not in ROUNDS_FEED_FIELDS:
        return field
    maximum = spare_rounds()
    if field.get('max') is None or field['max'] > maximum:
        field['max'] = maximum
        field['rangeReason'] = ('the live spare-round count is the network field spare_rounds (9 bits): the game clamps '
            f'it to {maximum} on every write')
    if isinstance(field.get('currentDefault'), (int, float)) and field['currentDefault'] > maximum:
        raise ValueError(f'{field_id}: the reviewed value {field["currentDefault"]} is above the network ceiling')
    field['networkLimit'] = {'max': maximum, 'networkField': 'spare_rounds'}
    return field
