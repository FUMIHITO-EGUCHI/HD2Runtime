"""0.31.3: the LAS-22 Shear, a catalogued player weapon (research/weapon-roots additions, docs/player-weapon-authoring.md).

The catalogue's identities came from a published-stat dataset that has no Shear, so its root (laser_rifle_charge) was
only the LAS-5 Scythe's dropped second candidate. The game's own armory names it: the loadout weapon table entry of
armory item 7DE53646 (primary category) holds that root, and its EncyclopediaEntry composes "LAS-22 Shear". It is a
charge beam rifle with its own WeaponData, WeaponHeat and BeamWeapon records and fires the Scythe's BeamSettings and
DamageInfo rows (shared). Its default Laser Heatsink (Charge) overwrites most heat members at weapon build."""
import json
import unittest

from support import ROOT, run
from test_multi_mod_composition import build_profile, snapshot_run

NAME = 'LAS-22 Shear'
ROOT_RESOURCE = '0x7E3145A5BAA4B948'


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


PLAYER = load('sdk/PlayerWeaponAuthoringCapabilities.json')
SHEAR = next(w for w in PLAYER['weapons'] if w['name'] == NAME)
FIELDS = {f['semanticFieldId']: f for f in SHEAR['fields']}
SCYTHE = {f['semanticFieldId']: f for w in PLAYER['weapons'] if w['name'] == 'LAS-5 Scythe' for f in w['fields']}

# Base values of the Shear's own records on the reference snapshot (research/field-ownership baseValue, the catalogue
# candidate resolved by the snapshot mapper), and the shared rows it fires (the Scythe's).
VANILLA = {
    'weapon.ergonomics': 65, 'weapon.sway': 1, 'weapon.horizontal_spread': 10, 'weapon.vertical_spread': 10,
    'weapon.recoil_drift_horizontal': 0, 'weapon.recoil_drift_vertical': 0, 'weapon.recoil_climb_horizontal': 0,
    'weapon.recoil_climb_vertical': 0, 'weapon.suppressed': False, 'weapon.crosshair_type': 10,
    'weapon.primary_fire_mode': 1, 'weapon.slot': 'primary',
    'heat.capacity': 100, 'heat.heat_per_shot': 2, 'heat.heat_per_second': 30, 'heat.cool_per_second': 15,
    'heatsink.starting': 4, 'heatsink.from_supply': 6, 'heatsink.spare': 6,
    'heat.firing_charge': 100, 'heat.charge_gain_per_second': 300, 'heat.charge_loss_per_second': 500,
    'heat.reset_charge_after_shot': True,
    'beam.fire_mode': 4, 'beam.fire_rate': 60, 'beam.pulse_beams': 1, 'beam.pulse_seconds': 0,
    'damage.type': 501, 'damage.standard_damage': 350, 'damage.durable_damage': 70, 'damage.ap_direct': 2,
    'damage.ap_slight': 2, 'damage.ap_large': 2, 'damage.ap_extreme': 0, 'damage.demolition': 10,
    'damage.stagger': 0, 'damage.push_force': 0, 'damage.status_1_type': 'fire', 'damage.status_1_strength': 1,
    'beam.radius': 0, 'beam.length': 1000,
    'presentation.traits': ['light_armor_penetrating', 'beam', 'heat'], 'presentation.armor_penetration': 'light',
}
# Members the default Laser Heatsink (Charge). Standard Heatsink patches at every build, with the value it builds the
# weapon with (research/field-ownership effectiveValue, decoded from its entity delta).
OVERRIDDEN = {'heat.heat_per_second': 25, 'heat.cool_per_second': 15, 'heatsink.starting': 4,
    'heatsink.from_supply': 6, 'heatsink.spare': 6, 'heat.firing_charge': 100, 'heat.charge_gain_per_second': 300,
    'heat.charge_loss_per_second': 100, 'heat.reset_charge_after_shot': 1}


class IdentityTests(unittest.TestCase):
    def test_the_armory_names_the_dropped_scythe_root(self):
        roots = load('research/weapon-roots-F5FEE03DCFDB.json')
        (addition,) = roots['additions']
        self.assertEqual((addition['weapon'], addition['root'], addition['slot'], addition['category'],
            addition['candidateOf']), (NAME, ROOT_RESOURCE, 'primary', 'Energy-Based', ['LAS-5 Scythe']))
        evidence = addition['evidence']
        self.assertEqual((evidence['kind'], evidence['armoryCategory'], evidence['itemId'],
            evidence['encyclopediaRecord'], evidence['loadoutSlot'], evidence['composedName']),
            ('armory_entry', 1, '7DE53646', 579, 'primary', NAME))
        self.assertTrue(evidence['entityPath'].endswith('/laser_rifle_charge/laser_rifle_charge'))
        names = load('research/weapon-name-text-ids-F5FEE03DCFDB.json')
        armory = [a for a in names['armory'] if a['resource'] == ROOT_RESOURCE]
        self.assertEqual([(a['category'], a['composedName'], a['inDomains']) for a in armory], [(1, NAME, True)])
        # The method holds for every other catalogued weapon: its armory entry holds its catalogue root.
        catalog = load('schemas/player_weapon_authoring_catalog.json')
        by_resource = {}
        for item in names['armory']:
            by_resource.setdefault(item['resource'], []).append(item['category'])
        for weapon in catalog['weapons']:
            self.assertEqual(by_resource[weapon['resources'][0]], [{'primary': 1, 'secondary': 3}[weapon['slot']]],
                weapon['name'])
        # The Scythe keeps its proven root; the dropped one is named.
        scythe = next(c for c in roots['corrections'] if c['weapon'] == 'LAS-5 Scythe')
        self.assertEqual(scythe['droppedRoots'], [ROOT_RESOURCE])
        self.assertIn('LAS-22 Shear', scythe['droppedIs'])

    def test_catalogue_entry(self):
        catalog = load('schemas/player_weapon_authoring_catalog.json')
        entry = next(w for w in catalog['weapons'] if w['name'] == NAME)
        self.assertEqual((entry['slot'], entry['category'], entry['resolution'], entry['resources']),
            ('primary', 'Energy-Based', 'UNIQUE', [ROOT_RESOURCE]))
        self.assertEqual(entry['rootAddition']['evidence'], 'armory_entry')
        ownership = catalog['candidates'][ROOT_RESOURCE]['ownership']
        self.assertEqual({name: item['recordIndex'] for name, item in ownership.items()},
            {'BeamWeaponComponentData': 17, 'LoadoutPackageComponentData': 465, 'WeaponCustomizationComponentData': 119,
             'WeaponDataComponentData': 293, 'WeaponHeatComponentData': 19})
        self.assertTrue(all(item['uniqueOwner'] and item['ownerCount'] == 1 for item in ownership.values()))
        self.assertEqual(SHEAR['implementationFamilies'], ['beam'])
        self.assertFalse(SHEAR['ordinaryWritesBlocked'])
        ammo = next(w for w in load('sdk/PlayerWeaponAmmoCapabilities.json')['weapons'] if w['name'] == NAME)
        self.assertEqual(ammo['effectiveCapacity'], {'status': 'NOT_APPLICABLE'})

    def test_runtime_names_and_game_text(self):
        events = (ROOT / 'domains/event_entities.lua').read_text(encoding='utf-8')
        self.assertIn('["7E3145A5BAA4B948"]={["name"]="LAS-22 Shear",["kind"]="weapon"}', events)
        equipment = load('research/player-equipment-F5FEE03DCFDB.json')
        self.assertEqual(equipment['catalog']['7E3145A5BAA4B948']['name'], NAME)


class FieldTests(unittest.TestCase):
    def test_vanilla_values_are_the_game_data(self):
        for field_id, value in VANILLA.items():
            self.assertEqual(FIELDS[field_id]['currentDefault'], value, field_id)
        ownership = {row['field']: row for row in load('research/field-ownership-F5FEE03DCFDB.json')['fields']
            if row['weapon'] == NAME}
        for field_id, row in ownership.items():
            if field_id in VANILLA and field_id != 'weapon.slot':
                self.assertEqual(row['baseValue'], VANILLA[field_id], field_id)
        self.assertEqual({k: r['owner']['effectiveValue'] for k, r in ownership.items() if r['status'] == 'OVERRIDDEN'
            and k != 'attack.beam'}, OVERRIDDEN)
        # The same component members as the family's other weapons (the Scythe's), on the Shear's own records.
        for field_id, field in FIELDS.items():
            backing = field.get('backing') or {}
            other = (SCYTHE.get(field_id) or {}).get('backing') or {}
            if backing.get('kind') == 'component' and other:
                self.assertEqual((backing['component'], backing['offset'], backing['storage']),
                    (other['component'], other['offset'], other['storage']), field_id)

    def test_writability_and_acknowledgements(self):
        writable = sorted(f for f, item in FIELDS.items() if item['editable'])
        # The Scythe's field set, including the new reload-duration control.
        self.assertEqual(set(FIELDS), set(SCYTHE))
        self.assertEqual(len(FIELDS), 65)
        self.assertEqual(len(writable), 39)
        for field_id in ('weapon.ergonomics', 'weapon.sway', 'weapon.horizontal_spread', 'weapon.suppressed',
                'weapon.recoil_climb_vertical'):
            self.assertTrue(FIELDS[field_id]['editable'] and FIELDS[field_id]['writeScope'] == 'weapon_local')
            self.assertIsNone(FIELDS[field_id].get('acknowledgement'), field_id)
            self.assertEqual(FIELDS[field_id]['effect']['activeSource'], 'ACTIVE_AT_INSTANTIATION', field_id)
        # No published heat data cross-checks the Shear: its own heat members need allow_unverified_effect.
        for field_id in ('heat.capacity', 'heat.heat_per_shot'):
            field = FIELDS[field_id]
            self.assertTrue(field['editable'] and field['acknowledgement'] == 'allow_unverified_effect', field_id)
            self.assertIn('No published heat data', field['acknowledgementReason'])
        # The default heatsink overwrites the rest at every build: read-only, with the value the game builds it with.
        for field_id in OVERRIDDEN:
            self.assertFalse(FIELDS[field_id]['editable'], field_id)
            self.assertIn('Laser Heatsink (Charge). Standard Heatsink', FIELDS[field_id]['reason'], field_id)
        self.assertIn('(to 25; the base value here is 30)', FIELDS['heat.heat_per_second']['reason'])
        self.assertIn('(to 100; the base value here is 500)', FIELDS['heat.charge_loss_per_second']['reason'])
        # Its own beam record: fire mode, rate and pulse, as on every beam weapon (allow_unverified_effect).
        for field_id in ('beam.fire_mode', 'beam.fire_rate', 'beam.pulse_beams', 'beam.pulse_seconds'):
            self.assertTrue(FIELDS[field_id]['editable'] and FIELDS[field_id]['writeScope'] == 'weapon_local')
            self.assertEqual(FIELDS[field_id]['backing']['recordIndex'], 17)
        # Its BeamWeapon +0 is dormant: the default muzzle Laser. Charge Standard patches it (weapon:beam_source()).
        self.assertFalse(FIELDS['attack.beam']['editable'])
        self.assertIn('Laser. Charge Standard', FIELDS['attack.beam']['reason'])
        # The beam and damage rows are the Scythe's: shared both ways (allow_shared).
        for field_id in ('damage.standard_damage', 'damage.ap_direct', 'beam.length', 'beam.radius'):
            self.assertTrue(FIELDS[field_id]['affectsMultipleWeapons'], field_id)
            self.assertEqual(FIELDS[field_id]['sharedWithWeapons'], ['LAS-5 Scythe'], field_id)
            self.assertTrue(SCYTHE[field_id]['affectsMultipleWeapons'], field_id)
            self.assertEqual(SCYTHE[field_id]['sharedWithWeapons'], [NAME], field_id)
            self.assertEqual(FIELDS[field_id]['backing']['row'], SCYTHE[field_id]['backing']['row'], field_id)
        # Nothing about the Shear is live-proven.
        self.assertFalse([f for f, item in FIELDS.items() if item.get('liveEvidence')])

    def test_runtime_api(self):
        self.assertEqual(run(r'''
local hd2=require('hd2runtime/api/hd2')
local patches=require('hd2runtime/domains/patches')
local function rejects(fn,needle)local ok,why=pcall(fn);assert(not ok and tostring(why):find(needle,1,true),tostring(why))end
local F=hd2.fields
local shear=hd2.weapon('LAS-22 Shear')
patches.validate{id='e',target=shear,field=F.weapon.ergonomics,expect=65,value=80}
patches.validate{id='c',target=shear,field=F.heat.capacity,expect=100,value=150,allow_unverified_effect=true}
rejects(function()patches.validate{id='c',target=shear,field=F.heat.capacity,expect=100,value=150}end,
 'field requires allow_unverified_effect=true')
rejects(function()patches.validate{id='h',target=shear,field=F.heat.heat_per_second,expect=30,value=10,
 allow_unverified_effect=true}end,'field is read-only')
rejects(function()patches.validate{id='d',target=shear,field=F.damage.player_standard_damage,expect=350,value=500}end,
 'shared field requires allow_shared=true')
patches.validate{id='d',target=shear,field=F.damage.player_standard_damage,expect=350,value=500,allow_shared=true}
local source=shear:beam_source()
assert(source.writable and source.mechanism=='attachment'and source.item=='Laser. Charge Standard',source.reason)
assert(hd2.attack_output('LAS-22 Shear'):describe().beamType==8)
return 'ok'
'''), b'ok')


@unittest.skipUnless(build_profile.SNAPSHOT.is_file(), 'retained current-build snapshot not available')
class SnapshotTests(unittest.TestCase):
    def test_fields_resolve_on_the_shears_own_records(self):
        result = snapshot_run(r'''
local shear=hd2.weapon('LAS-22 Shear')
local cases={
 {F.weapon.ergonomics,65,'f32',80},{F.weapon.sway,1,'f32',2},{F.heat.capacity,100,'f32',150},
 {F.heat.heat_per_shot,2,'f32',1},{F.beam.fire_rate,60,'u32',90},
}
local seen={}
for _,case in ipairs(cases)do
 local found=resolve('patch',{id='s',target=shear,field=case[1],expect=case[2],value=case[4],
  allow_unverified_effect=true})
 check(#found==1,case[1]..': one member')
 check(found[1].before==b.encode(case[2],case[3]),case[1]..': the snapshot holds the catalogued value')
 seen[#seen+1]=found[1].at
end
-- Its own records, not the Scythe's: the same fields resolve elsewhere on the Scythe.
local scythe=resolve('patch',{id='s',target=hd2.weapon('LAS-5 Scythe'),field=F.weapon.ergonomics,expect=65,value=80})
check(scythe[1].at~=seen[1],'the Shear and the Scythe share no WeaponData record')
-- The shared damage row resolves to the same bytes from both weapons.
local a=resolve('patch',{id='d',target=shear,field=F.damage.player_standard_damage,expect=350,value=500,allow_shared=true})
local c=resolve('patch',{id='d',target=hd2.weapon('LAS-5 Scythe'),field=F.damage.player_standard_damage,expect=350,
 value=500,allow_shared=true})
check(a[1].at==c[1].at,'one DamageInfo row')
-- The beam source writes the Shear's own default muzzle delta row (not the Scythe's Standard Prism).
local source=shear:beam_source()
local own=resolve('patch',{id='b',target=source.target,field=F.attack.beam,expect=source.expect,value=source.expect,
 allow_shared=true})
local prism=hd2.weapon('LAS-5 Scythe'):beam_source()
local other=resolve('patch',{id='b',target=prism.target,field=F.attack.beam,expect=prism.expect,value=prism.expect,
 allow_shared=true})
check(#own==1 and own[1].before==b.encode(8,'u32')and own[1].at~=other[1].at,'the Shear muzzle row')
check(counts.writes==0 and next(overlay)==nil,'resolution wrote')
return json.encode({ok=true})
''')
        self.assertTrue(result['ok'])


if __name__ == '__main__':
    unittest.main()
