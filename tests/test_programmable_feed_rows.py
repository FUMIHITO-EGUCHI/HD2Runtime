"""0.31.1: the projectile a support weapon fires through its native ProgrammableAmmo function, its own row and damage
(scripts/programmable_feed_fields.py, research/programmable-projectiles-F5FEE03DCFDB.json): the AC-8 Autocannon's flak,
the GR-8 Recoilless Rifle's and the RL-77 Airburst Rocket Launcher's +576 projectiles, through the role 'programmable'.
Every write re-reads ProjectileWeapon +576; a swapped or emptied function projectile is refused."""
import json
import unittest

from support import ROOT, run
from test_multi_mod_composition import build_profile, snapshot_run

SUPPORT = json.loads((ROOT / 'sdk/SupportWeaponAuthoringCapabilities.json').read_text(encoding='utf-8'))
INSTANCES = list(SUPPORT['fieldInstances'].values()) if isinstance(SUPPORT['fieldInstances'], dict) \
    else SUPPORT['fieldInstances']
RESEARCH = json.loads((ROOT / 'research/programmable-projectiles-F5FEE03DCFDB.json').read_text(encoding='utf-8'))


def fields(name):
    return {f['qualifiedSemanticFieldId']: f for f in INSTANCES if f['supportWeapon'] == name
        and '.programmable.' in f['qualifiedSemanticFieldId']}


class ResearchTests(unittest.TestCase):
    def test_hosts_rows_and_sharing(self):
        rows = {item['weapon']: item for item in RESEARCH['weapons']}
        self.assertEqual(sorted(rows), ['AC-8 Autocannon', 'GR-8 Recoilless Rifle', 'RL-77 Airburst Rocket Launcher'])
        self.assertEqual((rows['AC-8 Autocannon']['projectileType'], rows['AC-8 Autocannon']['explosions']),
            (284, {'impact': 380}))
        self.assertEqual(rows['AC-8 Autocannon']['sharedWithWeapons'], [])
        self.assertEqual(rows['GR-8 Recoilless Rifle']['sharedWithWeapons'],
            ['TD-110 Maelstrom slot 2', 'TD-220 Bastion MK XVI attach_tank_gun'])
        # The RL-77's function rocket links the DamageInfo row of its normal rocket.
        self.assertEqual([item['owners'] for item in rows['RL-77 Airburst Rocket Launcher']['damageSharedWith']],
            [['RL-77 Airburst Rocket Launcher']])


class CatalogueTests(unittest.TestCase):
    def test_fields(self):
        flak = fields('AC-8 Autocannon')
        self.assertEqual(flak['damage.programmable.standard_damage']['value']['baseline'], 150)
        self.assertEqual(flak['projectile.programmable.velocity']['value']['baseline'], 820)
        self.assertIn('projectile.programmable.lifetime', flak)
        self.assertNotIn('projectile.programmable.lifetime', fields('GR-8 Recoilless Rifle'))   # native 0: no limit
        for name in ('AC-8 Autocannon', 'GR-8 Recoilless Rifle', 'RL-77 Airburst Rocket Launcher'):
            found = fields(name)
            # nine damage members and the four free status slots (0.31.2: every empty slot is offered)
            self.assertEqual(len([key for key in found if key.startswith('damage.')]), 17, name)
            for key, field in found.items():
                self.assertTrue(field['writable'], (name, key))
                self.assertEqual(field['operation']['acknowledgement'], 'allow_unverified_effect', (name, key))
                self.assertTrue(field['operation']['allowSharedRequired'], (name, key))
                self.assertEqual(field['programmableFeed']['feed'], 'programmable')
                self.assertNotIn('liveEvidence', field)
        # No other weapon gets a programmable row (the S-11 and the rest have no native function projectile).
        self.assertEqual(sorted({f['supportWeapon'] for f in INSTANCES if '.programmable.' in f['qualifiedSemanticFieldId']}),
            ['AC-8 Autocannon', 'GR-8 Recoilless Rifle', 'RL-77 Airburst Rocket Launcher'])


class ApiTests(unittest.TestCase):
    def test_targets_and_acknowledgements(self):
        run('''
local hd2=require('hd2runtime/api/hd2')
local patches=require('hd2runtime/domains/patches')
local function rejects(fn,needle)local ok,why=pcall(fn);assert(not ok and tostring(why):find(needle,1,true),tostring(why))end
local ac8=hd2.support_weapon('AC-8 Autocannon')
local flak=ac8:attack('programmable'):projectile()
assert(flak.path=='projectile_reference'and flak.attack=='programmable')
local request={id='f',target=flak,field=hd2.fields.damage.player_standard_damage,expect=150,value=300,
 allow_shared=true,allow_unverified_effect=true}
patches.validate(request)
request.allow_unverified_effect=nil
rejects(function()patches.validate(request)end,'allow_unverified_effect')
request.allow_unverified_effect=true;request.allow_shared=nil
rejects(function()patches.validate(request)end,'allow_shared')
patches.validate{id='v',target=flak,field=hd2.fields.projectile.velocity,expect=820,value=600,allow_shared=true,
 allow_unverified_effect=true}
-- The APHET round keeps its own target and values.
patches.validate{id='a',target=ac8:attack('primary'):projectile(),field=hd2.fields.damage.player_standard_damage,
 expect=325,value=325,allow_shared=true}
-- A weapon without a native function projectile has no such attack.
rejects(function()hd2.support_weapon('S-11 Speargun'):attack('programmable')end,'unknown reviewed support attack')
''')


@unittest.skipUnless(build_profile.SNAPSHOT.is_file(), 'retained current-build snapshot not available')
class SnapshotTests(unittest.TestCase):
    PRELUDE = r'''
update=update or function()end
local ac8=hd2.support_weapon('AC-8 Autocannon')
local flak=ac8:attack('programmable'):projectile()
local function member()
    local feed=ac8:feed('programmable')
    return resolve('patch',{id='m',target=ac8,field=F.function_ammo.projectile,expect=feed:projectile(),
        value=feed:projectile(),allow_unverified_effect=true,allow_unverified_reference=true})[1].at
end
'''

    def test_the_flak_row_is_written(self):
        result = snapshot_run(self.PRELUDE + r'''
local changes={{field=F.damage.player_standard_damage,expect=150,value=300},
    {field=F.projectile.velocity,expect=820,value=600}}
local where=resolve('transaction',{id='f',target=flak,allow_shared=true,allow_unverified_effect=true,changes=changes})
local aphet=resolve('patch',{id='a',target=ac8:attack('primary'):projectile(),field=F.damage.player_standard_damage,
    expect=325,value=325,allow_shared=true})[1].at
check(where[1].at~=aphet,'the flak damage row is not the APHET row')
check(runtime.read(member(),4)==b.encode(284,'u32'),'ProjectileWeapon +576 is the flak projectile 284')
local h={}
events.run_as('mods/test/ac8_flak',function()
    h.op=hd2.ensure({transaction={id='flak',target=flak,allow_shared=true,allow_unverified_effect=true,changes=changes}})
end)
settle({h.op})
check(h.op.result and h.op.result.status=='APPLIED','flak transaction '..tostring(h.op.error))
check(runtime.read(where[1].at,4)==b.encode(300,'i32'),'flak damage 300 written')
check(runtime.read(where[2].at,4)==b.encode(600,'f32'),'flak velocity 600 written')
check(runtime.read(aphet,4)==b.encode(325,'i32'),'the APHET row is untouched')
local n=0
for _ in pairs(overlay)do n=n+1 end
check(n==2,'exactly two members written: '..n)
return json.encode({ok=true})
''')
        self.assertTrue(result['ok'])

    def test_an_emptied_or_swapped_function_projectile_is_refused(self):
        for value, needle in ((0, 'FUNCTION_PROJECTILE_CHANGED'), (115, 'identity changed')):
            with self.subTest(value=value):
                result = snapshot_run(self.PRELUDE + r'''
local where=resolve('patch',{id='w',target=flak,field=F.damage.player_standard_damage,expect=150,value=150,
    allow_shared=true,allow_unverified_effect=true})
overlay[member()]=b.encode(''' + str(value) + r''','u32')
local h={}
events.run_as('mods/test/ac8_tamper',function()
    h.op=hd2.ensure({patch={id='flak-tamper',target=flak,allow_shared=true,allow_unverified_effect=true,
        field=F.damage.player_standard_damage,expect=150,value=200}})
end)
settle({h.op})
local text=tostring(h.op.error or(h.op.result and(h.op.result.reason or h.op.result.status)))
check(not(h.op.result and h.op.result.status=='APPLIED'),'must not apply')
check(runtime.read(where[1].at,4)==b.encode(150,'i32'),'the flak row is untouched')
local n=0
for _ in pairs(overlay)do n=n+1 end
check(n==1,'nothing written besides the tamper: '..n)
return json.encode({ok=true,error=text})
''')
                self.assertTrue(result['ok'], result)
                self.assertIn(needle, result['error'])


if __name__ == '__main__':
    unittest.main()
