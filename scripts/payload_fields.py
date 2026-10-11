"""Impact and expiry payloads of the projectile rows a support weapon fires (0.31.2; docs/explosions.md "Payloads on
support weapons").

A primary or secondary weapon publishes `terminal.<role>.<phase>.explosion`: the ExplosionType members of the
ProjectileSettings row its attack fires (+144 impact, +156 expiry), written through
`weapon:attack(role):projectile():terminal_action(phase)` with `hd2.fields.terminal.explosion`. A support weapon now
publishes the same field on every projectile row one of its attacks fires, for every feed the authoring catalogue
models: its normal attack, its ProgrammableAmmo projectile (role `programmable`: the AC-8's flak, the GR-8's HE, the
RL-77's cluster round), its charge levels (PLAS-45 Epoch) and its rounds feed (SG-88).

The backing is the row the role's existing projectile fields already write, resolved the same way on every write
(domains/player_weapon_writes.lua support_linked: ProjectileWeapon +0, WeaponRounds +64, the WeaponCharge level
selectors or ProjectileWeapon +576), with only the member offset changed. What is proven, per member:

* owner, layout and semantic: ProjectileInfo +144 / +156 are typed ExplosionType members (the same members the
  primaries' field writes; research/projectile-stats checks every row against the explosion catalogue);
* active source: the row of the role is the row the role's projectile fields edit, so the same proof applies; each
  weapon's caveat (a magazine pattern's tracer rows, a charge level) is carried into the field;
* sharing: a support projectile row is always treated as shared (allow_shared), and its consumers are listed from
  research/projectile-identities (every typed member naming the row, and every explosion that releases it as shrapnel);
* lifecycle: the spawn copies the row's +144 / +156 into each shot (research/docs/projectile-swap-and-payloads), so a
  write applies to shots fired after it.

Excluded, with the reason in the weapon's blockedFields:
* the expiry of a missile's carried row (FAF-14, MLS-4X, StA-X3): the missile is a unit-driven projectile that ends by
  its own SeekingMissile lifetime; whether the carried row's expiry explosion ever fires is not traced. Its impact is
  the carried row's +144 (research/wasp-rocket section 3) and is published;
* the StA-X3's ProgrammableAmmo missile (its +576 row): no reviewed attack of the weapon resolves it.

No support payload write is live-tested: every write needs allow_unverified_effect, a catalogued donor (hd2.explosion
(name)) also allow_unverified_reference, and every write allow_shared.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / 'research/projectile-stats-F5FEE03DCFDB.json'
IDENTITIES = ROOT / 'research/projectile-identities-F5FEE03DCFDB.json'
EXPLOSIONS = ROOT / 'research/explosion-identities-F5FEE03DCFDB.json'
SWAPS = ROOT / 'research/projectile-swap-and-payloads-F5FEE03DCFDB.json'

PHASES = (('impact', 144), ('expiry', 156))
FIELD = 'terminal.explosion'
REASON = ('Re-points the impact or expiry explosion of the projectile row this support attack fires (ProjectileInfo '
    '+144 / +156, re-resolved through the weapon on every write). Every weapon and explosion that fires or releases '
    'this row changes with it (allow_shared). No support payload write is live-tested yet.')
MISSILE_EXPIRY = ('The missile is a unit-driven projectile that ends by its own SeekingMissile lifetime '
    '(missile.max_lifetime); whether the carried row\'s expiry explosion ever fires is not traced, so no expiry payload '
    'is offered. Its impact payload is (terminal.primary.impact.explosion).')
MISSILE_FUNCTION = ('The StA-X3 W.A.S.P. Launcher\'s ProgrammableAmmo missile carries its own row, but no reviewed attack '
    'of the weapon resolves it: no payload field is offered for that missile.')
PATTERN = ('This weapon\'s magazine pattern also fires another row (its tracer rounds): those rounds keep their own '
    'impact and expiry explosions. The payload changes the rounds of this row only.')
NO_LIFETIME = ('The row has no lifetime (0): its expiry explosion only fires when the projectile expires some other way '
    '(a fuse), so an expiry payload on it may never go off. Prefer the impact payload.')
UNIT_DRIVEN = ('The weapon spawns a missile that carries this row as its hit row: the missile\'s impact explosion is the '
    'row\'s +144 (research/wasp-rocket-F5FEE03DCFDB.json). The missile flies by its own record.')

_CACHE = {}


def _load():
    if not _CACHE:
        stats = json.loads(STATS.read_text(encoding='utf-8'))['rows']
        identities = {item['type']: item for item in
            json.loads(IDENTITIES.read_text(encoding='utf-8'))['types']}
        explosions = json.loads(EXPLOSIONS.read_text(encoding='utf-8'))
        swaps = {item['weapon']: item for item in json.loads(SWAPS.read_text(encoding='utf-8'))['weapons']}
        _CACHE.update(stats=stats, identities=identities, swaps=swaps,
            explosions={item['type']: item for item in explosions['explosions']},
            settings=explosions['layout']['settingsGroup'])
    return _CACHE


def current(projectile_type, phase):
    """The explosion type the row holds at the phase's member (0 = none), from the pinned datalibrary."""
    row = _load()['stats'][str(projectile_type)]
    item = row.get(phase)
    return item['type'] if item else 0


def lifetime(projectile_type):
    return _load()['stats'][str(projectile_type)]['flight']['lifetime']


def explosion_settings(explosion_type):
    data = _load()
    entry = data['explosions'][explosion_type]
    assert entry['settingsVerified'], 'explosion row not verified: ' + str(explosion_type)
    return {'group': data['settings']['group'], 'row': entry['row'], 'recordType': explosion_type,
        'settingsType': data['settings']['settingsType']}


def explosion_name(explosion_type):
    if not explosion_type:
        return None
    entry = _load()['explosions'][explosion_type]
    return entry['name']


def consumers(projectile_type, weapon_name):
    """Who fires or releases the row: semantic names (deduplicated, the weapon itself excluded) and the count of typed
    references whose owner carries no name."""
    data = _load()
    item = data['identities'][projectile_type]
    named, unnamed = set(), 0
    for owner in item['identity']['owners']:
        names = [entry['name'] for entry in owner.get('names') or [] if entry.get('name')]
        if not names and owner.get('path'):
            # An entity named only by its resource path (as the attack output catalogue names it).
            names = [owner['path'].rsplit('/', 1)[-1]]
        if names:
            named.update(names)
        else:
            unnamed += 1
    released = []
    for source in item['identity']['submunitionOf']:
        name = explosion_name(source['explosion'])
        released.append({'explosion': name, 'count': source['count']})
    named.discard(weapon_name)
    return sorted(named), unnamed, sorted(released, key=lambda entry: str(entry['explosion']))


def swap_class(weapon_name):
    item = _load()['swaps'].get(weapon_name)
    return item['swapClass'] if item else None


def add(weapon_name, fields, attacks, make_field, settings, hit=None):
    """Append the payload fields of every projectile role of one support weapon; return (fields added, blocked
    declarations)."""
    added, blocked = [], []
    missile_role = hit[0]['role'] if hit else None
    for role in sorted(attacks):
        attack = attacks[role]
        if attack['kind'] != 'Projectile':
            continue
        sibling = next((field for field in fields if field['target'].get('attack') == role
            and field['target']['path'] == 'projectile_reference'
            and field['backing'].get('settings') == 'projectile'), None)
        if sibling:
            template = sibling['backing']
        elif role == missile_role:
            template = settings('projectile', hit[0]['projectileSettings'], 0, 'u32', role, 'projectile')
        else:
            raise AssertionError(weapon_name + ': projectile role without a projectile row: ' + role)
        projectile_type = template['recordType']
        projectile_settings = {key: template[key] for key in ('group', 'row', 'recordType', 'settingsType')}
        named, unnamed, released = consumers(projectile_type, weapon_name)
        for phase, offset in PHASES:
            if role == missile_role and phase == 'expiry':
                blocked.append({'attack': role, 'field': 'terminal.' + role + '.expiry.explosion',
                    'reason': MISSILE_EXPIRY})
                continue
            explosion_type = current(projectile_type, phase)
            backing = dict(template, offset=offset, storage='u32', width=4)
            target = {'resource': 'support_weapon', 'path': 'terminal_action', 'weapon': weapon_name, 'attack': role,
                'phase': phase}
            field = make_field('terminal.' + role + '.' + phase + '.explosion',
                {'weapon': weapon_name, 'attack': role, 'phase': phase, 'explosionType': explosion_type},
                backing, target, acknowledgement='allow_unverified_effect')
            field['acknowledgementReason'] = REASON
            field['affectsMultipleWeapons'] = True
            field['sharedWithWeapons'] = sorted(set(field['sharedWithWeapons']) | set(named))
            field.update(referenceKind='explosion', referenceRole=role, referencePhase=phase, nullSentinel=0,
                projectileSettings=projectile_settings,
                referenceSettings=explosion_settings(explosion_type) if explosion_type else None)
            notes = []
            if role == missile_role:
                notes.append(UNIT_DRIVEN)
            if swap_class(weapon_name) == 'MAGAZINE_PATTERN':
                notes.append(PATTERN)
            if phase == 'expiry' and not explosion_type and not lifetime(projectile_type):
                notes.append(NO_LIFETIME)
            for key in ('chargeLevel', 'programmableFeed', 'effect'):
                if sibling and sibling.get(key):
                    field[key] = sibling[key]
            if sibling and sibling.get('chargeLevel'):
                notes.append(sibling['acknowledgementReason'])
            field['payload'] = {'role': role, 'phase': phase, 'current': explosion_name(explosion_type),
                'consumers': named, 'unnamedConsumers': unnamed, 'releasedBy': released,
                'unitDriven': role == missile_role, 'notes': notes,
                'options': 'hd2.explosions.payload_options(terminal) / terminal:payload_options()',
                'acknowledgements': {'own': ['allow_shared', 'allow_unverified_effect'],
                    'none': ['allow_shared', 'allow_unverified_effect'],
                    'catalogue': ['allow_shared', 'allow_unverified_effect', 'allow_unverified_reference']}}
            added.append(field)
    if weapon_name == 'StA-X3 W.A.S.P. Launcher':
        blocked.append({'attack': 'programmable', 'field': 'terminal.programmable.impact.explosion',
            'reason': MISSILE_FUNCTION})
    return added, blocked
