"""0.31.1: the direct-hit damage of the missile a support weapon spawns per shot (scripts/missile_hit_fields.py;
research/wasp-rocket-F5FEE03DCFDB.json). The FAF-14 Spear, MLS-4X Commando and StA-X3 W.A.S.P. missiles carry their
weapon's ProjectileWeapon +0 row as their hit row; only its damage is published (the missile flies by its own
SeekingMissile record), on the same row the write path already resolves for the impact explosion."""
import json
import unittest

from support import ROOT, run
from test_multi_mod_composition import build_profile, snapshot_run

SUPPORT = json.loads((ROOT / 'sdk/SupportWeaponAuthoringCapabilities.json').read_text(encoding='utf-8'))
INSTANCES = list(SUPPORT['fieldInstances'].values()) if isinstance(SUPPORT['fieldInstances'], dict) \
    else SUPPORT['fieldInstances']
WEAPONS = {'FAF-14 Spear': 4000, 'MLS-4X Commando': 1100, 'StA-X3 W.A.S.P. Launcher': 200}


def fields(name):
    return {f['qualifiedSemanticFieldId']: f for f in INSTANCES if f['supportWeapon'] == name}


class CatalogueTests(unittest.TestCase):
    def test_direct_hit_damage_only(self):
        for name, damage in WEAPONS.items():
            found = fields(name)
            hit = {key: field for key, field in found.items() if key.startswith('damage.primary.')}
            self.assertEqual(len(hit), 17, name)    # nine damage members and the four free status slots (0.31.2)
            self.assertEqual(hit['damage.primary.standard_damage']['value']['baseline'], damage, name)
            for key, field in hit.items():
                self.assertTrue(field['writable'], (name, key))
                self.assertEqual(field['operation']['acknowledgement'], 'allow_unverified_effect', (name, key))
                self.assertTrue(field['operation']['allowSharedRequired'], (name, key))
                self.assertEqual(field['target']['path'], 'projectile_reference')
                self.assertNotIn('liveEvidence', field)
            # Not the row's flight: the missile flies by missile.* (its own SeekingMissile record).
            self.assertFalse([key for key in found if key.startswith('projectile.primary.')], name)
            self.assertTrue([key for key in found if key.startswith('missile.')], name)

    def test_no_other_weapon_gains_a_partial_branch(self):
        # Writable fields on a target whose catalogue branches are all unresolved: only the missile direct hits.
        gained = sorted({f['supportWeapon'] for f in INSTANCES if f['writable'] and f['target'].get('catalogBranches')
            and not any(branch['state'] == 'RESOLVED' for branch in f['target']['catalogBranches'])})
        self.assertEqual(gained, sorted(WEAPONS))


class ApiTests(unittest.TestCase):
    def test_targets_and_acknowledgements(self):
        run('''
local hd2=require('hd2runtime/api/hd2')
local patches=require('hd2runtime/domains/patches')
local function rejects(fn,needle)local ok,why=pcall(fn);assert(not ok and tostring(why):find(needle,1,true),tostring(why))end
for name,damage in pairs({['FAF-14 Spear']=4000,['MLS-4X Commando']=1100,['StA-X3 W.A.S.P. Launcher']=200})do
 local hit=hd2.support_weapon(name):attack('primary'):projectile()
 local request={id='d',target=hit,field=hd2.fields.damage.player_standard_damage,expect=damage,value=damage+500,
  allow_shared=true,allow_unverified_effect=true}
 patches.validate(request)
 request.allow_unverified_effect=nil
 rejects(function()patches.validate(request)end,'allow_unverified_effect')
 request.allow_unverified_effect=true;request.allow_shared=nil
 rejects(function()patches.validate(request)end,'allow_shared')
 -- Its flight members are not offered.
 rejects(function()patches.validate{id='v',target=hit,field=hd2.fields.projectile.velocity,expect=1,value=2,
  allow_shared=true,allow_unverified_effect=true}end,'')
end
''')


@unittest.skipUnless(build_profile.SNAPSHOT.is_file(), 'retained current-build snapshot not available')
class SnapshotTests(unittest.TestCase):
    def test_the_spear_direct_hit_is_written(self):
        result = snapshot_run(r'''
update=update or function()end
local hit=hd2.support_weapon('FAF-14 Spear'):attack('primary'):projectile()
local blast=hd2.support_weapon('FAF-14 Spear'):attack('primary_impact'):explosion()
local changes={{field=F.damage.player_standard_damage,expect=4000,value=6000},
    {field=F.damage.player_durable_damage,expect=4000,value=6000}}
local where=resolve('transaction',{id='s',target=hit,allow_shared=true,allow_unverified_effect=true,changes=changes})
check(#where==2,'two members: '..#where)
local blast_at=resolve('patch',{id='e',target=blast,field=F.explosion.standard_damage,expect=200,value=200,
    allow_shared=true})[1].at
check(where[1].at~=blast_at,'the direct hit is not the impact explosion row')
local h={}
events.run_as('mods/test/spear_hit',function()
    h.op=hd2.ensure({transaction={id='spear-hit',target=hit,allow_shared=true,allow_unverified_effect=true,
        changes=changes}})
end)
settle({h.op})
check(h.op.result and h.op.result.status=='APPLIED','spear transaction '..tostring(h.op.error))
check(runtime.read(where[1].at,4)==b.encode(6000,'i32'),'standard 6000 written')
check(runtime.read(blast_at,4)==b.encode(200,'i32'),'the impact explosion is untouched')
local n=0
for _ in pairs(overlay)do n=n+1 end
check(n==2,'exactly two members written: '..n)
return json.encode({ok=true})
''')
        self.assertTrue(result['ok'])

    def test_another_carried_row_is_refused(self):
        result = snapshot_run(r'''
update=update or function()end
local hit=hd2.support_weapon('MLS-4X Commando'):attack('primary'):projectile()
local where=resolve('patch',{id='c',target=hit,field=F.damage.player_standard_damage,expect=1100,value=1100,
    allow_shared=true,allow_unverified_effect=true})
-- Another mod points the Commando's ProjectileWeapon +0 (the carried row) at the Spear's projectile.
-- (fire_rate is ProjectileWeapon +8 of the same record.)
local rate=resolve('patch',{id='r',target=hd2.support_weapon('MLS-4X Commando'),field=F.weapon.fire_rate,
    expect=240,value=240})[1]
check(runtime.read(rate.at-8,4)==b.encode(245,'u32'),'ProjectileWeapon +0 is the Commando missile row 245')
local h={}
overlay[rate.at-8]=b.encode(225,'u32')
events.run_as('mods/test/commando_tamper',function()
    h.op=hd2.ensure({patch={id='commando-hit',target=hit,allow_shared=true,allow_unverified_effect=true,
        field=F.damage.player_standard_damage,expect=1100,value=1500}})
end)
settle({h.op})
check(not(h.op.result and h.op.result.status=='APPLIED'),'a write to the old row must not apply')
check(runtime.read(where[1].at,4)==b.encode(1100,'i32'),'the Commando row is untouched')
local n=0
for _ in pairs(overlay)do n=n+1 end
check(n==1,'nothing written besides the tamper: '..n)
return json.encode({ok=true,error=tostring(h.op.error or(h.op.result and(h.op.result.reason or h.op.result.status)))})
''')
        self.assertTrue(result['ok'], result)


if __name__ == '__main__':
    unittest.main()
