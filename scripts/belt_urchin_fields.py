"""Reviewed exceptions for a backpack-fed host and code-selected pulse payloads."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NAME='GL-28 Belt-Fed Grenade Launcher'
RESEARCH=ROOT/'research/belt-urchin-F5FEE03DCFDB.json'
def load():return json.loads(RESEARCH.read_text(encoding='utf-8'))
def hosts(items):
    proof=load()['belt']
    for item in items:
        if item['weapon']==NAME:
            assert item['status']=='ACTIVE_DIRECT' and item['mechanism']=='component'
            item.update(componentHost=True,reason='Reviewed backpack-linked ammunition supplies rounds without selecting projectiles; the fired source is ProjectileWeapon +0.')
    return items
def host_proof(candidate):
    p=load()['belt'];assert candidate['resourceHash']==p['resource']
    own=candidate['ownership']['ProjectileWeaponComponentData']
    assert all(own[k]==p['projectile'][k] for k in ('recordIndex','indexRow','ownerCount'))
    return p['linkedAmmo']
