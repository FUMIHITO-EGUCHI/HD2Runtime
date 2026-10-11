"""0.31.2 (research/overheat-cooling-F5FEE03DCFDB.json, research/docs/projectile-swap-and-payloads-F5FEE03DCFDB.md
section 3): the LAS-99 Quasar's separate 15 s lockout is WeaponHeat +140, the cooling rate while overheated, read by
the heat step only when +144 is 0. Exposed as heat.cool_per_second_overheated on the Quasar alone, behind
allow_unverified_effect. heat.overheat_cooldown names it instead of heat.cool_per_second; every other heat weapon
needs a heatsink change after an overheat (+144 set)."""
import json
import sys
import unittest
from pathlib import Path

from support import run
from test_multi_mod_composition import build_profile, snapshot_run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import equipment_fields  # noqa: E402


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


class ResearchTests(unittest.TestCase):
    def test_only_the_quasar_record_reads_plus_140(self):
        research = load('research/overheat-cooling-F5FEE03DCFDB.json')
        self.assertEqual(research['writes'], 0)
        roles = {pin['rva']: pin['asm'] for group in research['proofs'].values() for pin in group}
        self.assertEqual(roles[0x763018], 'mulss xmm2, dword ptr [rdi + 0x8c]')
        self.assertEqual(roles[0x763005], 'mulss xmm2, dword ptr [rdi + 0x80]')
        self.assertEqual(roles[0x7630B6], 'cmp byte ptr [rdi + 0x90], 0')
        quasar = [r for r in research['records'] if r['owner'] == 'LAS-99 Quasar Cannon']
        self.assertEqual(len(quasar), 1)
        self.assertAlmostEqual(quasar[0]['coolPerSecondOverheated'], 6.66, places=5)
        self.assertEqual((quasar[0]['releaseThreshold'], quasar[0]['noPassiveCoolingWhileOverheated']), (0.0, 0))
        self.assertAlmostEqual(quasar[0]['lockoutSeconds'], 15.015, places=3)
        cooling = sorted(r['owner'] for r in research['records'] if not r['noPassiveCoolingWhileOverheated'])
        self.assertEqual(cooling, ['LAS-99 Quasar Cannon', 'shoulder_mounted_camera'])

    def test_overheat_cooldown_reasons(self):
        quasar = equipment_fields.overheat_record(28)
        self.assertIn('heat.cool_per_second_overheated = (100 - 0) / 6.66 = 15.0 s',
            equipment_fields.overheat_cooldown_reason(quasar))
        self.assertIn('heatsink', equipment_fields.overheat_cooldown_reason(equipment_fields.overheat_record(27)))
        self.assertIn('Never overheats', equipment_fields.overheat_cooldown_reason(equipment_fields.overheat_record(21)))
        for record in load('research/overheat-cooling-F5FEE03DCFDB.json')['records']:
            self.assertNotIn('edit heat.capacity or heat.cool_per_second', equipment_fields.overheat_cooldown_reason(
                record))

    def test_published_catalogues(self):
        support = {w['name']: w for w in load('sdk/SupportWeaponAuthoringCapabilities.json')['weapons']}
        owners = [name for name, w in support.items()
            if 'heat.cool_per_second_overheated' in w['writableFieldsByDomain'].get('heat', [])]
        self.assertEqual(owners, ['LAS-99 Quasar Cannon'])
        blocked = {b['field']: b['reason'] for b in support['LAS-98 Laser Cannon']['blockedFields']}
        self.assertIn('heatsink is changed', blocked['heat.overheat_cooldown'])
        self.assertNotIn('20.0 s', blocked['heat.overheat_cooldown'])
        player = load('sdk/PlayerWeaponAuthoringCapabilities.json')
        self.assertNotIn('heat.cool_per_second_overheated', json.dumps(player['weapons']))
        heat = load('sdk/PlayerWeaponHeatCapabilities.json')
        for weapon in heat['weapons']:
            for field in weapon.get('fields', []):
                if field['id'] == 'heat.overheat_cooldown':
                    self.assertNotIn('edit heat.capacity or heat.cool_per_second', field['reason'])


class CatalogueTests(unittest.TestCase):
    def test_field_and_acknowledgement(self):
        self.assertEqual(run(r'''
local S=require('hd2runtime/domains/support_weapon_authoring').weapons
local function field(e,id)for _,f in ipairs(e.fields)do if f.semanticFieldId==id then return f end end end
local q=S['LAS-99 Quasar Cannon']
local f=assert(field(q,'heat.cool_per_second_overheated'))
assert(math.abs(f.currentDefault-6.66)<1e-5 and f.editable and f.acknowledgement=='allow_unverified_effect')
assert(f.backing.component=='WeaponHeatComponentData'and f.backing.offset==140 and f.backing.storage=='f32')
assert(f.writeScope=='weapon_local'and f.backing.uniqueOwner==true)
assert(f.min==0.1 and f.max==1000 and f.effect.appliesWhen=='next_frame')
-- Same record as heat.cool_per_second.
local c=assert(field(q,'heat.cool_per_second'))
assert(c.backing.recordIndex==f.backing.recordIndex and c.backing.offset==128)
local constants=require('hd2runtime/domains/constants')
assert(constants.fields.heat.cool_per_second_overheated=='heat.cool_per_second_overheated')
-- Not offered where +144 is set (the LAS-98: no passive cooling while overheated).
assert(not field(S['LAS-98 Laser Cannon'],'heat.cool_per_second_overheated'))
local patches=require('hd2runtime/domains/patches')
local hd2=require('hd2runtime/api/hd2')
local quasar=hd2.support_weapon('LAS-99 Quasar Cannon')
local ok,why=pcall(patches.validate,{id='a',target=quasar,field='heat.cool_per_second_overheated',
    expect=6.659999847412109,value=20})
assert(not ok and tostring(why):find('allow_unverified_effect',1,true),tostring(why))
ok,why=pcall(patches.validate,{id='a',target=quasar,allow_unverified_effect=true,
    field='heat.cool_per_second_overheated',expect=6.659999847412109,value=0})
assert(not ok and tostring(why):find('minimum',1,true),tostring(why))
ok,why=pcall(patches.validate,{id='a',target=quasar,allow_unverified_effect=true,
    field='heat.cool_per_second_overheated',expect=6.659999847412109,value=20})
assert(ok,tostring(why))
return 'ok'
'''), b'ok')


@unittest.skipUnless(build_profile.SNAPSHOT.is_file(), 'retained current-build snapshot not available')
class SnapshotTests(unittest.TestCase):
    def test_quasar_lockout_write(self):
        result = snapshot_run(r'''
update=update or function()end
local quasar=hd2.support_weapon('LAS-99 Quasar Cannon')
local change={field='heat.cool_per_second_overheated',expect=6.659999847412109,value=20}
local where=resolve('transaction',{id='w',target=quasar,allow_unverified_effect=true,changes={change}})
check(#where==1,'one member of the Quasar WeaponHeat record: '..#where)
local h={}
events.run_as('mods/test/quasar_lockout',function()
    h.q=hd2.ensure({patch={id='quasar-lockout',target=quasar,allow_unverified_effect=true,
        field=change.field,expect=change.expect,value=change.value}})
end)
settle({h.q})
check(h.q.runs>=1 and h.q.result.status=='APPLIED','quasar '..tostring(h.q.error))
check(runtime.read(where[1].at,4)==b.encode(20,'f32'),'20 written')
local n=0
for _ in pairs(overlay)do n=n+1 end
check(n==1,'exactly one member written: '..n)
return json.encode({ok=true})
''')
        self.assertTrue(result['ok'])


if __name__ == '__main__':
    unittest.main()
