"""Catalog explosion branches below a submunition, linked to the explosion catalogue (0.31.2).

The wiki lists some explosions that a resolved explosion's submunitions cause: the RL-77's "RL-77 P1 IE" is the
explosion of "RL-77 P3", a submunition of "RL-77 P IE" (its rocket's burst). The read-only mapper compares a branch
with the weapon's own attacks only, so such a branch stays unresolved ("no structurally linked ExplosionSettings branch
matched this catalog branch"). The game links it structurally, and the research records hold every link:

  the parent explosion branch is RESOLVED to one of the weapon's explosions (its ExplosionSettings type), whose
  shrapnel projectile (+84, research/explosion-identities stats.shrapnelProjectile) impacts as one ExplosionSettings
  row (research/projectile-identities properties.impactExplosion), which the explosion catalogue names.

Such a branch is linked to that catalogued explosion: it is authored through hd2.explosion(name), not through the
support weapon (one row every burst of that kind uses). The branch's own published values are not compared (the wiki
record keeps only the fields that differ from the weapon's own explosion), so the link is structural.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPLOSIONS = ROOT / 'research/explosion-identities-F5FEE03DCFDB.json'
PROJECTILES = ROOT / 'research/projectile-identities-F5FEE03DCFDB.json'
_CACHE = {}


def _research():
    if 'research' not in _CACHE:
        explosions = {item['type']: item for item in json.loads(EXPLOSIONS.read_text(encoding='utf-8'))['explosions']}
        projectiles = {item['type']: item for item in json.loads(PROJECTILES.read_text(encoding='utf-8'))['types']}
        import generate_explosion_catalogue
        aliases = {kind: alias for kind, (alias, _why) in generate_explosion_catalogue.ALIASES.items()}
        _CACHE['research'] = (explosions, projectiles, aliases)
    return _CACHE['research']


def links(weapon: dict, candidate: dict | None) -> dict:
    """{branch name: link} for one support weapon's catalog branches (schemas/support_weapon_authoring_catalog.json)
    that the chain above links to a catalogued explosion."""
    if not candidate:
        return {}
    explosions, projectiles, aliases = _research()
    graph = {branch['name']: branch for branch in weapon['attackGraph']}
    own = {attack['role']: attack['explosionSettings']['recordType'] for attack in candidate['attacks']
        if attack.get('explosionSettings')}
    found = {}
    for branch in weapon['attackGraph']:
        if branch['kind'] != 'Explosion' or not branch.get('unresolvedReason'):
            continue
        parent = graph.get(branch.get('parentAttack'))
        source = parent and graph.get(parent.get('parentAttack'))
        if not parent or parent['kind'] != 'Projectile' or not source or source['kind'] != 'Explosion' \
                or source['state'] != 'RESOLVED':
            continue
        source_type = own.get((source.get('runtimeMatch') or {}).get('runtimeAttackRole'))
        origin = explosions.get(source_type)
        shrapnel = origin and origin['stats']['shrapnelProjectile']
        impact = ((projectiles.get(shrapnel) or {}).get('properties') or {}).get('impactExplosion') or {}
        target = explosions.get(impact.get('type'))
        if not shrapnel or not target or not target['name']:
            continue
        name = aliases.get(target['type'], target['name'])
        found[branch['name']] = {'explosion': name, 'researchId': target['name'],
            'handle': "hd2.explosion('" + name + "')",
            'chain': [source['name'] + ' (' + origin['name'] + ')', parent['name'] + ': its shrapnel projectile, '
                + str(origin['stats']['shrapnelCount']) + ' per burst', branch['name'] + ': that projectile\'s impact'],
            'evidence': 'structural: the explosion +84 shrapnel projectile and that projectile\'s impact explosion '
                '(research/explosion-identities, research/projectile-identities); the branch\'s published values are '
                'not compared',
            'reason': branch['name'] + ': authored through ' + "hd2.explosion('" + name + "')" + ' (the explosion '
                'catalogue): the impact of the shrapnel projectile ' + source['name'] + ' releases; one row every '
                'such burst uses'}
    return found
