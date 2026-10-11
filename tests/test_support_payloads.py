"""Impact and expiry payloads on support weapons and the payload options (0.31.2; docs/explosions.md "Payloads on
support weapons", "Payload options"): terminal.<role>.<phase>.explosion on every projectile row a support attack fires
(scripts/payload_fields.py -> domains/support_weapon_authoring.lua), its guarded write (domains/player_weapon_writes.lua
support_explosion_change), the package a catalogued explosion needs, and every value a payload field takes
(scripts/generate_payload_options.py -> domains/payload_options.lua, sdk/PayloadOptions.json, api/payload_options.lua).
Offline; the retained-snapshot write proofs are scripts/validate_explosion_catalogue_snapshot.py (support payloads)
and scripts/validate_support_weapon_authoring_snapshot.py (every payload field's identity)."""
import json
import re
import unittest

from support import ROOT, run

import generate_payload_options
import generate_support_weapon_authoring

SUPPORT = json.loads((ROOT / 'sdk/SupportWeaponAuthoringCapabilities.json').read_text(encoding='utf-8'))
OPTIONS = json.loads((ROOT / 'sdk/PayloadOptions.json').read_text(encoding='utf-8'))
CATALOGUE = json.loads((ROOT / 'sdk/ExplosionCatalogue.json').read_text(encoding='utf-8'))
SNAPSHOT_REPORT = ROOT / 'validation/explosion-catalogue-snapshot.json'
SUPPORT_REPORT = ROOT / 'research/support-weapon-authoring-validation-F5FEE03DCFDB.json'

BOTH = ('impact', 'expiry')
# (weapon, role) -> phases offered. Missiles (FAF-14, MLS-4X, StA-X3) offer their impact only.
EXPECTED = {
    ('AC-8 Autocannon', 'primary'): BOTH, ('AC-8 Autocannon', 'programmable'): BOTH,
    ('APW-1 Anti-Materiel Rifle', 'primary'): BOTH,
    ('EAT-17 Expendable Anti-Tank', 'primary'): BOTH, ('EAT-411 Leveller', 'primary'): BOTH,
    ('EAT-700 Expendable Napalm', 'primary'): BOTH,
    ('FAF-14 Spear', 'primary'): ('impact',),
    ('GL-21 Grenade Launcher', 'primary'): BOTH, ('GL-28 Belt-Fed Grenade Launcher', 'primary'): BOTH,
    ('GL-52 De-Escalator', 'primary'): BOTH,
    ('GR-8 Recoilless Rifle', 'primary'): BOTH, ('GR-8 Recoilless Rifle', 'programmable'): BOTH,
    ('LAS-99 Quasar Cannon', 'primary'): BOTH, ('M-1000 Maxigun', 'primary'): BOTH,
    ('M-105 Stalwart', 'primary'): BOTH, ('MG-206 Heavy Machine Gun', 'primary'): BOTH,
    ('MG-43 Machine Gun', 'primary'): BOTH, ('MGX-42 Bullet Storm', 'primary'): BOTH,
    ('MLS-4X Commando', 'primary'): ('impact',),
    ('PLAS-45 Epoch', 'primary'): BOTH, ('PLAS-45 Epoch', 'full_charge'): BOTH,
    ('RL-77 Airburst Rocket Launcher', 'primary'): BOTH, ('RL-77 Airburst Rocket Launcher', 'programmable'): BOTH,
    ('RS-422 Railgun', 'primary'): BOTH, ('S-11 Speargun', 'primary'): BOTH,
    ('SG-88 Break-Action Shotgun', 'feed_primary'): BOTH,
    ('StA-X3 W.A.S.P. Launcher', 'primary'): ('impact',),
}
CURRENT = {
    ('AC-8 Autocannon', 'terminal.primary.impact.explosion'): 'support_weapon/ac8_autocannon/impact',
    ('AC-8 Autocannon', 'terminal.programmable.impact.explosion'): 'support_weapon/ac8_autocannon/function_impact',
    ('AC-8 Autocannon', 'terminal.programmable.expiry.explosion'): None,
    ('APW-1 Anti-Materiel Rifle', 'terminal.primary.impact.explosion'): None,
    ('APW-1 Anti-Materiel Rifle', 'terminal.primary.expiry.explosion'): None,
    ('GR-8 Recoilless Rifle', 'terminal.programmable.impact.explosion'):
        'support_weapon/gr8_recoilless_rifle/function_impact',
    ('RL-77 Airburst Rocket Launcher', 'terminal.programmable.expiry.explosion'):
        'support_weapon/rl77_airburst_rocket_launcher/function_expiry',
    ('S-11 Speargun', 'terminal.primary.expiry.explosion'): 'support_weapon/s11_speargun/expiry',
    ('FAF-14 Spear', 'terminal.primary.impact.explosion'): 'support_weapon/faf14_spear/impact',
}


def payloads():
    return [item for item in SUPPORT['fieldInstances'] if item['semanticFieldId'] == 'terminal.explosion']


class FieldTests(unittest.TestCase):
    def test_generated_outputs_are_current(self):
        self.assertFalse(generate_support_weapon_authoring.generate(check=True))
        self.assertEqual(generate_payload_options.generate(check=True), [])

    def test_every_support_projectile_row_and_feed_has_its_payloads(self):
        found = {}
        for item in payloads():
            found.setdefault((item['supportWeapon'], item['target']['attackRole']), []).append(
                item['payload']['phase'])
        self.assertEqual({key: tuple(sorted(value, key=BOTH.index)) for key, value in found.items()}, EXPECTED)
        self.assertEqual(len(payloads()), 51)
        for item in payloads():
            role, phase = item['target']['attackRole'], item['payload']['phase']
            self.assertEqual(item['qualifiedSemanticFieldId'], 'terminal.' + role + '.' + phase + '.explosion')
            self.assertEqual(item['apiFieldConstant'], 'hd2.fields.terminal.explosion')
            self.assertEqual(item['target']['path'], 'terminal_action')
            self.assertEqual(item['target']['accessor'][-2:], ['projectile', 'terminal_action'])
            self.assertTrue(item['writable'])
            self.assertEqual(item['operation']['acknowledgement'], 'allow_unverified_effect')
            self.assertTrue(item['operation']['allowSharedRequired'])
            self.assertNotIn('liveEvidence', item)
            self.assertEqual(item['value']['baseline'], {'explosion': item['payload']['current'] or 'none'})
            self.assertEqual(item['payload']['acknowledgements']['catalogue'],
                ['allow_shared', 'allow_unverified_effect', 'allow_unverified_reference'])
        for (weapon, field), current in CURRENT.items():
            item = next(i for i in payloads() if i['supportWeapon'] == weapon and i['qualifiedSemanticFieldId'] == field)
            self.assertEqual(item['payload']['current'], current, (weapon, field))

    def test_caveats_travel_with_the_field(self):
        by = {(i['supportWeapon'], i['qualifiedSemanticFieldId']): i for i in payloads()}
        for weapon in ('MG-43 Machine Gun', 'MGX-42 Bullet Storm'):
            self.assertTrue(any('magazine pattern' in note for note in
                by[(weapon, 'terminal.primary.impact.explosion')]['payload']['notes']))
        for weapon in ('FAF-14 Spear', 'MLS-4X Commando', 'StA-X3 W.A.S.P. Launcher'):
            self.assertTrue(by[(weapon, 'terminal.primary.impact.explosion')]['payload']['unitDriven'])
        epoch = by[('PLAS-45 Epoch', 'terminal.full_charge.impact.explosion')]
        self.assertEqual(epoch['chargeLevel']['level'], 'full')
        self.assertEqual(by[('AC-8 Autocannon', 'terminal.programmable.impact.explosion')]['programmableFeed']['feed'],
            'programmable')
        wasp = by[('StA-X3 W.A.S.P. Launcher', 'terminal.primary.impact.explosion')]['payload']
        self.assertEqual(wasp['releasedBy'], [{'explosion': 'support_weapon/stax3_wasp_launcher/function_impact',
            'count': 7}])
        self.assertIn('E/GL-21 Grenadier Battlement',
            by[('GL-21 Grenade Launcher', 'terminal.primary.impact.explosion')]['payload']['consumers'])
        # The flak row has no lifetime of 0: an expiry payload on it can go off; the APW-1 bullet's would not.
        self.assertFalse(by[('AC-8 Autocannon', 'terminal.programmable.expiry.explosion')]['payload']['notes'])
        self.assertTrue(any('no lifetime' in note for note in
            by[('APW-1 Anti-Materiel Rifle', 'terminal.primary.expiry.explosion')]['payload']['notes']))
        blocked = {(w['name'], b['field']): b['reason'] for w in SUPPORT['weapons'] for b in w['blockedFields']
            if b['field'].startswith('terminal.')}
        self.assertEqual(set(blocked), {('FAF-14 Spear', 'terminal.primary.expiry.explosion'),
            ('MLS-4X Commando', 'terminal.primary.expiry.explosion'),
            ('StA-X3 W.A.S.P. Launcher', 'terminal.primary.expiry.explosion'),
            ('StA-X3 W.A.S.P. Launcher', 'terminal.programmable.impact.explosion')})
        self.assertIn('unit-driven', blocked[('FAF-14 Spear', 'terminal.primary.expiry.explosion')])


class WriteTests(unittest.TestCase):
    def test_own_none_and_catalogued_values_with_their_acknowledgements(self):
        self.assertEqual(run(r'''
local hd2=require('hd2runtime/api/hd2')
local W=require('hd2runtime/domains/player_weapon_writes')
local function rejects(request,needle)
    local ok,why=pcall(W.validate_patch,request)
    assert(not ok and tostring(why):find(needle,1,true),needle..' / '..tostring(why))
end
local apw=hd2.support_weapon('APW-1 Anti-Materiel Rifle'):attack('primary'):projectile():terminal_action('impact')
assert(apw:describe().current==nil and apw:current().path=='no_explosion')
local frag=hd2.explosion('throwable/g6_frag/detonation')
local base={id='p',target=apw,field=hd2.fields.terminal.explosion,expect=apw:no_explosion(),value=frag}
local function with(extra)local r={}for k,v in pairs(base)do r[k]=v end for k,v in pairs(extra)do r[k]=v end return r end
rejects(with({allow_unverified_effect=true,allow_unverified_reference=true}),'allow_shared')
rejects(with({allow_shared=true,allow_unverified_reference=true}),'allow_unverified_effect')
rejects(with({allow_shared=true,allow_unverified_effect=true}),'allow_unverified_reference')
local spec=W.validate_patch(with({allow_shared=true,allow_unverified_effect=true,allow_unverified_reference=true}))
assert(spec.changes[1].catalogue_explosion and#spec.asset_dependencies==1)
-- none on a row without an explosion, and the row's own explosion (restore) on one with one
W.validate_patch(with({value=apw:no_explosion(),allow_shared=true,allow_unverified_effect=true}))
rejects(with({value=apw:no_explosion(),allow_shared=true}),'allow_unverified_effect')
local ok=pcall(function()return apw:explosion()end)
assert(not ok,'the APW-1 bullet has no impact explosion of its own')
local flak=hd2.support_weapon('AC-8 Autocannon'):attack('programmable'):projectile():terminal_action('impact')
assert(flak:describe().current=='support_weapon/ac8_autocannon/function_impact')
W.validate_patch({id='f',target=flak,field='terminal.explosion',expect=flak:explosion(),value=flak:explosion(),
    allow_shared=true,allow_unverified_effect=true})
W.validate_patch({id='f',target=flak,field='terminal.explosion',expect=flak:explosion(),value=flak:no_explosion(),
    allow_shared=true,allow_unverified_effect=true})
-- expect must be the field's own current handle
rejects({id='f',target=flak,field='terminal.explosion',expect=flak:no_explosion(),value=flak:explosion(),
    allow_shared=true,allow_unverified_effect=true},'expect does not represent')
rejects({id='f',target=flak,field='terminal.explosion',expect=apw:no_explosion(),value=flak:explosion(),
    allow_shared=true,allow_unverified_effect=true},'expect must be the target terminal action')
rejects({id='f',target=flak,field='terminal.explosion',expect=frag,value=flak:explosion(),
    allow_shared=true,allow_unverified_effect=true},'expect must be the target terminal action')
-- "none" is the field's own no_explosion()
rejects({id='f',target=flak,field='terminal.explosion',expect=flak:explosion(),value=apw:no_explosion(),
    allow_shared=true,allow_unverified_effect=true},'own terminal:no_explosion()')
-- another weapon's terminal explosion: the catalogued explosion it names, with the catalogue's acknowledgements
local eruptor=hd2.weapon('R-36 Eruptor'):attack('primary'):projectile():terminal_action('impact'):explosion()
rejects({id='f',target=flak,field='terminal.explosion',expect=flak:explosion(),value=eruptor,
    allow_shared=true,allow_unverified_effect=true},'allow_unverified_reference')
spec=W.validate_patch({id='f',target=flak,field='terminal.explosion',expect=flak:explosion(),value=eruptor,
    allow_shared=true,allow_unverified_effect=true,allow_unverified_reference=true})
assert(spec.changes[1].desired_selector.catalogue=='weapon/r36_eruptor/impact')
local gr8=hd2.support_weapon('GR-8 Recoilless Rifle'):attack('primary'):projectile():terminal_action('impact')
spec=W.validate_patch({id='f',target=flak,field='terminal.explosion',expect=flak:explosion(),value=gr8:explosion(),
    allow_shared=true,allow_unverified_effect=true,allow_unverified_reference=true})
assert(spec.changes[1].desired_selector.catalogue=='support_weapon/gr8_recoilless_rifle/impact')
-- a support payload handle as a primary's donor goes through the catalogue too
local own=hd2.weapon('R-36 Eruptor'):attack('primary'):projectile():terminal_action('impact')
spec=W.validate_patch({id='e',target=own,field='terminal.explosion',expect=own:explosion(),value=flak:explosion(),
    allow_unverified_effect=true,allow_unverified_reference=true})
assert(spec.changes[1].desired_selector.catalogue=='support_weapon/ac8_autocannon/function_impact')
-- the generic and the qualified field id are one field
W.validate_patch({id='q',target=flak,field='terminal.programmable.impact.explosion',expect=flak:explosion(),
    value=flak:explosion(),allow_shared=true,allow_unverified_effect=true})
-- not offered: a missile's expiry (the reason is named), the W.A.S.P.'s ProgrammableAmmo missile
local spear=hd2.support_weapon('FAF-14 Spear'):attack('primary'):projectile()
local _,why=pcall(spear.terminal_action,spear,'expiry')
assert(tostring(why):find('unit-driven',1,true),tostring(why))
rejects({id='s',target={resource='support_weapon',path='terminal_action',weapon='FAF-14 Spear',attack='primary',
    phase='expiry'},field='terminal.explosion',expect='none',value='none',allow_shared=true,
    allow_unverified_effect=true},'unit-driven')
W.validate_patch({id='s',target=spear:terminal_action('impact'),field='terminal.explosion',
    expect=spear:terminal_action('impact'):explosion(),value=frag,allow_shared=true,allow_unverified_effect=true,
    allow_unverified_reference=true})
-- an explosion without a known package is refused (ASSET_UNAVAILABLE)
local enemy
for _,e in ipairs(hd2.explosions.list({payload=false}))do enemy=enemy or e.name end
rejects(with({value=hd2.explosion(enemy),allow_shared=true,allow_unverified_effect=true,
    allow_unverified_reference=true}),'ASSET_UNAVAILABLE')
return 'ok'
'''), b'ok')

    def test_every_payload_field_takes_its_own_value_and_none(self):
        self.assertEqual(run(r'''
local hd2=require('hd2runtime/api/hd2')
local W=require('hd2runtime/domains/player_weapon_writes')
local S=require('hd2runtime/domains/support_weapon_authoring')
local count=0
for name,weapon in pairs(S.weapons)do
    for _,f in ipairs(weapon.fields)do
        if f.type=='explosion_reference'then
            local t=hd2.support_weapon(name):attack(f.referenceRole):projectile():terminal_action(f.referencePhase)
            local spec=W.validate_patch({id='own',target=t,field='terminal.explosion',expect=t:current(),
                value=t:current(),allow_shared=true,allow_unverified_effect=true})
            assert(#(spec.asset_dependencies or{})==0,name..' own value loads nothing')
            W.validate_patch({id='none',target=t,field='terminal.explosion',expect=t:current(),value=t:no_explosion(),
                allow_shared=true,allow_unverified_effect=true})
            count=count+1
        end
    end
end
assert(count==51,count)
return 'ok'
'''), b'ok')

    def test_a_grenade_or_orbital_explosion_loads_its_package_before_the_write(self):
        self.assertEqual(run(r'''
local hd2=require('hd2runtime/api/hd2')
local patches=require('hd2runtime/domains/patches')
local assets=require('hd2runtime/core/assets')
local apw=hd2.support_weapon('APW-1 Anti-Materiel Rifle'):attack('primary'):projectile():terminal_action('impact')
local flak=hd2.support_weapon('AC-8 Autocannon'):attack('programmable'):projectile():terminal_action('impact')
local function deps(target,value)
    local spec=patches.validate{id='load',target=target,field=hd2.fields.terminal.explosion,expect=target:current(),
        value=value,allow_shared=true,allow_unverified_effect=true,allow_unverified_reference=true}
    return spec,assets.collect(spec)
end
local spec,found=deps(apw,hd2.explosion('throwable/g6_frag/detonation'))
assert(#found==1 and found[1].name=='packages/generated/loadout/frag_grenade',found[1]and found[1].name)
local _,flak_found=deps(flak,hd2.explosion('stratagem/orbital_120mm_he_barrage/shell_impact'))
assert(#flak_found==1 and flak_found[1].name=='packages/generated/loadout/orbital_strike',flak_found[1].name)
local _,hellbomb=deps(flak,hd2.explosion('stratagem/nux223_hellbomb/behavior'))
assert(#hellbomb==1 and hellbomb[1].name=='packages/generated/loadout/hellbomb',hellbomb[1].name)
-- a mission-effects explosion needs no load (resident in every mission)
local _,none=deps(apw,hd2.explosion('weapon/plas15_loyalist/impact'))
assert(#none==0)
-- The patch's asset gate: waiting_for_assets until the package is resident, then ready; one native request.
assets.reset()
local calls,loaded=0,false
local runtime={mode='simulated',package_state=function()return loaded and'resident'or'queued'end}
local original=assets.prove
assets.prove=function()return {instance=1,request=2,capacity=1024}end
runtime.package_request=function()calls=calls+1 end
runtime.read=function(at,n)return string.rep('\0',n)end
local gate=assets.gate(runtime,{id='apw-frag',asset_dependencies=found,shared=true})
assert(gate.tick(0.3)=='waiting'and calls==1)
loaded=true
assert(gate.tick(0.3)=='ready')
-- A package that never becomes resident fails the operation (ASSET_UNAVAILABLE): the row keeps its value.
assets.reset();loaded=false
local late=assets.gate(runtime,{id='flak-shell',asset_dependencies=flak_found,shared=true})
local state,why
for _=1,400 do state,why=late.tick(0.3);if state=='failed'then break end end
assert(state=='failed'and tostring(why):find('ASSET_UNAVAILABLE',1,true)
    and tostring(why):find('orbital_strike',1,true),tostring(why))
-- The patch itself reports waiting_for_assets while its gate waits.
assets.reset()
local watch=require('hd2runtime/api/patch').start_spec(runtime,function()end,spec,0)
watch.tick(0.3)
assert(watch.status=='waiting_for_assets'and#watch.asset_dependencies==1,watch.status)
watch.cancel()
assets.prove=original;assets.reset()
return 'ok'
'''), b'ok')


class OptionTests(unittest.TestCase):
    def test_the_public_options_carry_no_raw_ids(self):
        text = json.dumps(OPTIONS)
        self.assertIsNone(re.search(r'0x[0-9A-Fa-f]{6,}', text))
        for token in ('"type"', 'recordType', 'explosionType', 'projectileType', '"row"'):
            self.assertNotIn(token, text)
        self.assertEqual(OPTIONS['contract'], 'hd2runtime.payload_options.v1')

    def test_every_payload_explosion_is_offered_once_in_its_group(self):
        payload = {item['name'] for item in CATALOGUE['explosions'] if item['payload']}
        names = [item['name'] for item in OPTIONS['options']]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), payload)
        self.assertEqual(OPTIONS['summary']['options'], 138)
        self.assertEqual(OPTIONS['summary']['byGroup'], {'weapon': 18, 'support_weapon': 31, 'throwable': 23,
            'orbital': 13, 'eagle': 12, 'hellbomb': 2, 'sentry': 7, 'mine': 4, 'vehicle': 11, 'backpack': 1,
            'enemy': 7, 'other': 9})
        by = {item['name']: item for item in OPTIONS['options']}
        for name in ('stratagem/nux223_hellbomb/behavior', 'backpack/b100_portable_hellbomb/behavior'):
            self.assertEqual(by[name]['group'], 'hellbomb')
            self.assertIn('very_large', by[name]['warnings'])
        gas = by['stratagem/orbital_gas_strike/shell_impact']
        self.assertTrue(gas['lingeringField'] and 'lingering_field' in gas['warnings'])
        self.assertEqual(set(gas['statuses']), {'gas', 'gas_confusion'})
        self.assertEqual(by['throwable/g6_frag/detonation']['group'], 'throwable')
        self.assertEqual(by['stratagem/eagle_airstrike/payload_impact']['group'], 'eagle')
        self.assertEqual(by['stratagem/aac8_autocannon_sentry/impact']['group'], 'sentry')
        self.assertEqual(by['stratagem/md17_antitank_mines/mine']['group'], 'mine')
        self.assertTrue(by['weapon/plas15_loyalist/impact']['package']['mission'])
        for item in OPTIONS['options']:
            self.assertEqual(item['acknowledgements'], ['allow_unverified_reference', 'allow_unverified_effect'])
        # Display order: group order, then label.
        groups = [g['id'] for g in OPTIONS['groups']]
        order = [groups.index(item['group']) for item in OPTIONS['options']]
        self.assertEqual(order, sorted(order))

    def test_fields_list_their_refusals(self):
        self.assertEqual(OPTIONS['summary']['payloadFields'], 185)
        self.assertEqual(OPTIONS['summary']['payloadFieldsByResource'], {'player_weapon': 134, 'support_weapon': 51})
        excluded = {(f['weapon'], f['field']): [e['name'] for e in f['excluded']] for f in OPTIONS['fields']
            if f['excluded']}
        self.assertEqual(excluded, {('StA-X3 W.A.S.P. Launcher', 'terminal.primary.impact.explosion'):
            ['support_weapon/stax3_wasp_launcher/function_impact']})
        apw = next(f for f in OPTIONS['fields'] if f['weapon'] == 'APW-1 Anti-Materiel Rifle'
            and f['phase'] == 'impact')
        self.assertEqual(apw['acknowledgements'], {'own': ['allow_shared', 'allow_unverified_effect'],
            'catalogue': ['allow_shared', 'allow_unverified_effect', 'allow_unverified_reference']})

    def test_every_option_of_a_field_validates_with_its_acknowledgements(self):
        self.assertEqual(run(r'''
local hd2=require('hd2runtime/api/hd2')
local W=require('hd2runtime/domains/player_weapon_writes')
assert(#hd2.explosions.payload_options()==138)
assert(#hd2.explosions.payload_options({group='hellbomb'})==2)
assert(#hd2.explosions.payload_groups()==12 and hd2.explosions.payload_warnings().very_large)
local function check(target,expected_options)
    local o=target:payload_options()
    assert(#o.options==expected_options,#o.options)
    local function flags(list)local r={}for _,a in ipairs(list)do r[a]=true end return r end
    for _,item in ipairs(o.options)do
        local acks=flags(item.acknowledgements)
        local spec=W.validate_patch({id='o',target=target,field='terminal.explosion',expect=target:current(),
            value=item.value,allow_shared=acks.allow_shared,allow_unverified_effect=acks.allow_unverified_effect,
            allow_unverified_reference=acks.allow_unverified_reference})
        -- (a weapon handle loads its weapon's own package instead: the primaries' rule)
        assert(item.via or item.package.mission==(#(spec.asset_dependencies or{})==0),item.name)
    end
    if o.own then
        local acks=flags(o.own.acknowledgements)
        W.validate_patch({id='o',target=target,field='terminal.explosion',expect=target:current(),value=o.own.value,
            allow_shared=acks.allow_shared,allow_unverified_effect=acks.allow_unverified_effect})
    end
    return o
end
-- the APW-1's bullet (no explosion: every option) and the AC-8 flak (its own explosion is not repeated as an option)
local apw=check(hd2.support_weapon('APW-1 Anti-Materiel Rifle'):attack('primary'):projectile():terminal_action('impact'),138)
assert(apw.own==nil and apw.none and apw.shared and#apw.excluded==0)
local flak=check(hd2.support_weapon('AC-8 Autocannon'):attack('programmable'):projectile():terminal_action('impact'),137)
assert(flak.own.name=='support_weapon/ac8_autocannon/function_impact')
-- the W.A.S.P.'s carried row refuses the explosion that releases it as shrapnel
local wasp=hd2.explosions.payload_options(
    hd2.support_weapon('StA-X3 W.A.S.P. Launcher'):attack('primary'):projectile():terminal_action('impact'))
assert(#wasp.excluded==1 and wasp.excluded[1].reason:find('RECURSIVE_COMPOSITION',1,true))
-- a primary: another primary's own explosion keeps that weapon's handle (no catalogue acknowledgement)
local eruptor=check(hd2.weapon('R-36 Eruptor'):attack('primary'):projectile():terminal_action('impact'),137)
local via=0
for _,item in ipairs(eruptor.options)do if item.via=='weapon_handle'then via=via+1;assert(#item.acknowledgements==0)end end
assert(via>0)
-- filters
local filtered=flak.options
local orbital=hd2.support_weapon('AC-8 Autocannon'):attack('programmable'):projectile():terminal_action('impact')
    :payload_options({group='orbital'})
assert(#orbital.options==13)
for _,g in ipairs(orbital.groups)do assert(g.id=='orbital'and g.count==13 or g.count==0)end
assert(#hd2.explosions.payload_options({search='hellbomb'})==2)
assert(#hd2.explosions.payload_options({without_warning='very_large'})==138-17)
local ok=pcall(hd2.explosions.payload_options,{colour='red'})
assert(not ok)
return 'ok'
'''), b'ok')


class SnapshotReportTests(unittest.TestCase):
    @unittest.skipUnless(SNAPSHOT_REPORT.is_file(), 'snapshot validation report absent')
    def test_support_payload_writes_on_the_snapshot(self):
        report = json.loads(SNAPSHOT_REPORT.read_text(encoding='utf-8'))
        self.assertEqual(report['supportPayloadWrites'], 3)
        self.assertEqual(report['supportPayloadNoops'], 1)
        self.assertEqual(report['proofRejections']['supportRecursion'], 1)

    @unittest.skipUnless(SUPPORT_REPORT.is_file(), 'support snapshot validation report absent')
    def test_every_payload_field_resolves_on_the_snapshot(self):
        report = json.loads(SUPPORT_REPORT.read_text(encoding='utf-8'))
        self.assertEqual(report['payloadTerminals'], 51)
        self.assertFalse(report['failures'])
        self.assertEqual((report['writes'], report['protectionChanges']), (0, 0))


if __name__ == '__main__':
    unittest.main()
