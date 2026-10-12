"""0.31.1: the fired attack of a weapon whose only projectile is its default ammunition (scripts/ammunition_attacks.py,
research/ammunition-projectiles-F5FEE03DCFDB.json). The P-2 Peacemaker and P-19 Redeemer have a base ProjectileWeapon
member of 0, so the reviewed catalogue gave them no attack and no projectile or damage field; they now get the
ammunition row the write path already resolves through the re-proven ammunition delta."""
import json
import unittest

from support import ROOT, run
from test_multi_mod_composition import build_profile, snapshot_run

RESEARCH = json.loads((ROOT / 'research/ammunition-projectiles-F5FEE03DCFDB.json').read_text(encoding='utf-8'))
PLAYER = json.loads((ROOT / 'sdk/PlayerWeaponAuthoringCapabilities.json').read_text(encoding='utf-8'))
CATALOG = json.loads((ROOT / 'schemas/player_weapon_authoring_catalog.json').read_text(encoding='utf-8'))


def fields(name):
    weapon = next(item for item in PLAYER['weapons'] if item['name'] == name)
    return {field['semanticFieldId']: field for field in weapon['fields']}


class ResearchTests(unittest.TestCase):
    def test_the_method_reproduces_the_reviewed_catalogue(self):
        # Where the base member already is the ammunition row, the research must equal the reviewed attack exactly.
        weapons = {item['name']: item for item in CATALOG['weapons']}
        checked = 0
        for item in RESEARCH['weapons']:
            if not item['baseIsAmmunitionRow']:
                continue
            attack = CATALOG['candidates'][weapons[item['weapon']]['resources'][0]]['attacks'][0]
            self.assertEqual(attack['projectileSettings'], item['projectileSettings'], item['weapon'])
            self.assertEqual(attack['damageInfo'], item['damageInfo'], item['weapon'])
            for key, value in item['resolvedFields'].items():
                self.assertEqual(attack['resolvedFields'][key], value, (item['weapon'], key))
            checked += 1
        self.assertEqual(checked, 4)
        self.assertEqual(sorted(RESEARCH['summary']['baseDiffersFromAmmunition']), ['P-19 Redeemer', 'P-2 Peacemaker'])

    def test_the_ammunition_rows(self):
        rows = {item['weapon']: item for item in RESEARCH['weapons']}
        peacemaker, redeemer = rows['P-2 Peacemaker'], rows['P-19 Redeemer']
        self.assertEqual((peacemaker['projectileType'], peacemaker['projectileSettings']['row']), (337, 166))
        self.assertEqual((redeemer['projectileType'], redeemer['projectileSettings']['row']), (291, 164))
        self.assertEqual(peacemaker['resolvedFields']['standard_damage'], 100)
        self.assertEqual(redeemer['resolvedFields']['standard_damage'], 70)
        # Their own damage rows, used by no other projectile row.
        self.assertEqual(peacemaker['damageInfo']['projectileConsumerCount'], 1)
        self.assertEqual(redeemer['damageInfo']['projectileConsumerCount'], 1)
        self.assertEqual(peacemaker['baseConsumers'], [])
        self.assertEqual(peacemaker['explosions'], {})


class CatalogueTests(unittest.TestCase):
    def test_projectile_and_damage_fields_with_acknowledgements(self):
        for name, damage, velocity, shared in (('P-2 Peacemaker', 100, 320, ['MP-98 Knight', 'P-19 Redeemer']),
                ('P-19 Redeemer', 70, 375, ['MP-98 Knight'])):
            found = fields(name)
            for field_id in ('damage.standard_damage', 'damage.durable_damage', 'damage.ap_direct',
                    'projectile.velocity', 'projectile.mass', 'damage.status_1_type'):
                field = found[field_id]
                self.assertTrue(field['editable'], (name, field_id))
                self.assertEqual(field['acknowledgement'], 'allow_unverified_effect', (name, field_id))
                self.assertTrue(field['affectsMultipleWeapons'], (name, field_id))
                self.assertEqual(field['sharedWithWeapons'], shared, (name, field_id))
                self.assertTrue(field['ammunitionSource'].startswith('PISTOL-SMG 9x20mm.'))
            self.assertEqual(found['damage.standard_damage']['currentDefault'], damage)
            self.assertEqual(found['projectile.velocity']['currentDefault'], velocity)
            reference = found['attack.primary.projectile']
            self.assertFalse(reference['editable'])
            self.assertTrue(reference['reason'].startswith('DORMANT_PROJECTILE_REFERENCE: '), reference['reason'])

    def test_no_other_weapon_changed_shape(self):
        # Every other weapon keeps the projectile and damage fields it had; only these two gained them.
        with_damage = [item['name'] for item in PLAYER['weapons'] if any(f['editable'] and
            f['semanticFieldId'].startswith(('projectile.', 'damage.')) for f in item['fields'])]
        self.assertEqual(len(with_damage), 81)   # 0.31.3: + the LAS-22 Shear (its beam's damage row)
        self.assertEqual(PLAYER['summary']['weaponsWithProjectileDamageWrites'], 81)


class ApiTests(unittest.TestCase):
    def test_targets_and_acknowledgements(self):
        run('''
local hd2=require('hd2runtime/api/hd2')
local patches=require('hd2runtime/domains/patches')
local function rejects(fn,needle)local ok,why=pcall(fn);assert(not ok and tostring(why):find(needle,1,true),tostring(why))end
for name,damage in pairs({['P-2 Peacemaker']=100,['P-19 Redeemer']=70})do
 local weapon=hd2.weapon(name)
 local attack=weapon:attack('primary')
 assert(attack:describe().active_source=='ammunition',name)
 local projectile=attack:projectile()
 local request={id='d',target=projectile,field=hd2.fields.damage.player_standard_damage,expect=damage,value=damage*2,
  allow_shared=true,allow_unverified_effect=true}
 patches.validate(request)
 request.allow_unverified_effect=nil
 rejects(function()patches.validate(request)end,'allow_unverified_effect')
 request.allow_unverified_effect=true;request.allow_shared=nil
 rejects(function()patches.validate(request)end,'allow_shared')
 -- The swap stays on the ammunition (the base member is dormant).
 rejects(function()patches.validate{id='s',target=attack,field=hd2.fields.attack.projectile,
  expect=attack:projectile(),value=hd2.weapon('LAS-58 Talon'):attack('primary'):projectile()}end,
  'DORMANT_PROJECTILE_REFERENCE')
 assert(weapon:projectile_source().target.path=='ammunition')
end
''')


@unittest.skipUnless(build_profile.SNAPSHOT.is_file(), 'retained current-build snapshot not available')
class SnapshotTests(unittest.TestCase):
    def test_the_ammunition_row_is_written_through_the_proven_delta(self):
        result = snapshot_run(r'''
update=update or function()end
local projectile=hd2.weapon('P-2 Peacemaker'):attack('primary'):projectile()
local changes={{field=F.damage.player_standard_damage,expect=100,value=150},
    {field=F.damage.player_durable_damage,expect=32,value=40},{field=F.projectile.velocity,expect=320,value=400}}
local where=resolve('transaction',{id='p',target=projectile,allow_shared=true,allow_unverified_effect=true,
    changes=changes})
check(#where==3,'three members: '..#where)
local h={}
events.run_as('mods/test/peacemaker_damage',function()
    h.op=hd2.ensure({transaction={id='peacemaker-hp',target=projectile,allow_shared=true,
        allow_unverified_effect=true,changes=changes}})
end)
settle({h.op})
check(h.op.result and h.op.result.status=='APPLIED','peacemaker transaction '..tostring(h.op.error))
check(runtime.read(where[1].at,4)==b.encode(150,'i32'),'standard damage 150 written')
check(runtime.read(where[3].at,4)==b.encode(400,'f32'),'velocity 400 written')
local n=0
for _ in pairs(overlay)do n=n+1 end
check(n==3,'exactly three members written: '..n)
return json.encode({ok=true})
''')
        self.assertTrue(result['ok'])

    def test_a_changed_ammunition_default_is_refused(self):
        result = snapshot_run(r'''
update=update or function()end
local projectile=hd2.weapon('P-19 Redeemer'):attack('primary'):projectile()
local where=resolve('patch',{id='r',target=projectile,field=F.damage.player_standard_damage,expect=70,value=70,
    allow_shared=true,allow_unverified_effect=true})
-- Another mod makes the ammunition delta name another projectile: the row is no longer what the weapon fires.
local ammo=hd2.weapon('P-19 Redeemer'):ammunition()
local delta=resolve('patch',{id='a',target=ammo,field=F.ammunition.projectile,expect=ammo:projectile(),
    value=ammo:projectile(),allow_shared=true,allow_unverified_effect=true})[1]
overlay[delta.at]=b.encode(337,'u32')
local h={}
events.run_as('mods/test/redeemer_tamper',function()
    h.op=hd2.ensure({patch={id='redeemer-fmj',target=projectile,allow_shared=true,allow_unverified_effect=true,
        field=F.damage.player_standard_damage,expect=70,value=90}})
end)
settle({h.op})
check(not(h.op.result and h.op.result.status=='APPLIED'),'a write to the old row must not apply')
check(runtime.read(where[1].at,4)==b.encode(70,'i32'),'the FMJ row is untouched')
local n=0
for _ in pairs(overlay)do n=n+1 end
check(n==1,'nothing written besides the tamper: '..n)
return json.encode({ok=true,error=tostring(h.op.error or(h.op.result and(h.op.result.reason or h.op.result.status)))})
''')
        self.assertTrue(result['ok'], result)


if __name__ == '__main__':
    unittest.main()
