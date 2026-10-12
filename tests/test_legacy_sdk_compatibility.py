"""Version-aware acknowledgements (docs/legacy-sdk-compatibility.md).

0.28.0 added allow_unverified_effect to 146 fields that 0.27.0 let mods write without it, and 0.30.0 to the 30
PLAS-45 Epoch partial-charge fields that 0.28.1 let mods write without it. An operation from a mod that declares an
SDK older than the field's release is accepted without it as a logged legacy operation; a mod that declares that
release or later, or whose declaration cannot be read, keeps the rule. The declaration is read from the three published addon wrapper
shapes: ModBuilder's ModExporter.Wrap (exactly as ModBuilder 1.3.1 exported the user-report fixtures), the
ModTemplate's build.ps1 and the SDK's hd2.py wrap_addon."""
import json
import re
import subprocess
import sys
import unittest

from support import ROOT, run

sys.path.insert(0, str(ROOT / 'sdk'))
sys.path.insert(0, str(ROOT / 'scripts'))
import hd2 as sdk  # noqa: E402
import generate_legacy_acknowledgements as legacy_table  # noqa: E402
# ModBuilder's wrapper, cut from a real ModBuilder 1.3.1 export (the packaged scenarios use the same one).
from validate_packaged_runtime import modbuilder_wrap  # noqa: E402

# How a generated addon body starts (ModBuilder's LuaGenerator, the ModTemplate's src/addon.lua).
REQUIRE = "local hd2=require('mods/skyeshade/hd2runtime')\n"


def lua_string(text):
    return '"' + ''.join(c if 32 <= ord(c) < 127 and c not in '"\\' else '\\%03d' % ord(c) for c in text) + '"'


def template_wrap(resource, minimum, body):
    """The ModTemplate's build.ps1 wrapper ($Prefix, source, $Suffix)."""
    script = (ROOT / 'starter/build.ps1').read_text(encoding='utf-8')
    prefix = re.search(r'\$Prefix = @"\r?\n(.*?)\r?\n"@', script, re.S).group(1) + '\n'
    suffix = re.search(r'\$Suffix = @"\r?\n(.*?)\r?\n"@', script, re.S).group(1)
    return (prefix.replace('$Resource', resource).replace('$Minimum', minimum) + REQUIRE + body
        + suffix).replace('\r\n', '\n')


PURIFIER = "hd2.weapon('PLAS-101 Purifier'):attack('primary'):projectile()"
# The user report's exact operation (ModBuilder 1.3.1 / SDK 0.27.0): no allow_unverified_effect.
PURIFIER_DRAG = ("hd2.ensure({patch={id='purifier-drag',target=" + PURIFIER + ",allow_shared=true,"
    "field=hd2.fields.projectile.drag,expect=1.5,value=0.8}})")
PURIFIER_DRAG_ACK = PURIFIER_DRAG.replace('allow_shared=true,', 'allow_shared=true,allow_unverified_effect=true,')

HARNESS = r'''
rawset(_G,'CowboyBingusModLoader',rawget(_G,'CowboyBingusModLoader')or{api=1,version=18})
local hd2=require('hd2runtime/api/hd2')
package.preload['mods/skyeshade/hd2runtime']=function()return hd2 end
local lines={}
require('hd2runtime/runtime/log').emit=function(line)lines[#lines+1]=line end
local json=require('hd2runtime/primary_mapper/json')
local out={}
for index,mod in ipairs(MODS)do
 local before=#hd2.diagnostics.operations()
 local first=#lines+1
 local ok,why=pcall(assert(loadstring(mod.source,'@'..mod.name)))
 local ops=hd2.diagnostics.operations()
 local mine={}
 for i=before+1,#ops do mine[#mine+1]=ops[i]end
 local logged={}
 for i=first,#lines do logged[#logged+1]=lines[i]end
 out[index]={name=mod.name,ok=ok,why=not ok and tostring(why)or nil,operations=mine,log=logged}
end
return json.encode(out)
'''


def run_mods(mods, extra=''):
    table = ','.join('{name=' + lua_string(name) + ',source=' + lua_string(source) + '}' for name, source in mods)
    out = run('local MODS={' + table + '}\n' + extra + HARNESS).decode()
    return {item['name']: item for item in json.loads(out[out.index('['):])}


def only(result):
    assert result['ok'], result['why']
    assert len(result['operations']) == 1, result['operations']
    return result['operations'][0]


def legacy_lines(result):
    return [line for line in result['log'] if ': legacy SDK ' in line]


class LegacyOperationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        coyote = ("hd2.ensure({patch={id='coyote-burst',target=hd2.weapon('AR-2 Coyote'),"
            "field=hd2.fields.fire_mode.burst_rounds,expect=3,value=4}})")
        slowdown = ("hd2.ensure({patch={id='purifier-slowdown',target=" + PURIFIER + ",allow_shared=true,"
            "field=hd2.fields.projectile.penetration_slowdown,expect=0.3499999940395355,value=0.2}})")
        ergonomics = ("hd2.ensure({patch={id='purifier-ergonomics',target=hd2.weapon('PLAS-101 Purifier'),"
            "field=hd2.fields.weapon.ergonomics,expect=65,value=70}})")
        shield = ("hd2.ensure({patch={id='sh51-health',target=hd2.backpack('SH-51 Directional Shield'),"
            "field=hd2.fields.entity.health,expect=400,value=600}})")
        transaction = ("hd2.ensure({transaction={id='purifier-damage',target=" + PURIFIER + ",allow_shared=true,"
            "changes={{field=hd2.fields.projectile.drag,expect=1.5,value=0.8},"
            "{field=hd2.fields.projectile.velocity,expect=VELOCITY,value=500}}}})")
        velocity = cls.purifier_default('projectile.velocity')
        transaction = transaction.replace('VELOCITY', repr(velocity))
        cls.results = run_mods([
            ('modbuilder-027', modbuilder_wrap('mods/test/legacy_027', '0.27.0', PURIFIER_DRAG)),
            ('modbuilder-028', modbuilder_wrap('mods/test/current_028', '0.28.0', PURIFIER_DRAG)),
            ('modbuilder-028-ack', modbuilder_wrap('mods/test/current_028_ack', '0.28.0', PURIFIER_DRAG_ACK)),
            ('modbuilder-026', modbuilder_wrap('mods/test/legacy_026', '0.26.1', PURIFIER_DRAG)),
            ('bare', REQUIRE + PURIFIER_DRAG.replace("'purifier-drag'", "'bare-drag'")),
            ('sdk-027', sdk.wrap_addon('mods/test/sdk_027', '0.27.0', PURIFIER_DRAG)),
            ('sdk-028-rc', sdk.wrap_addon('mods/test/sdk_028_rc', '0.28.0-rc.1', PURIFIER_DRAG)),
            ('template-025', template_wrap('mods/test/template_025', '0.25.0', PURIFIER_DRAG)),
            ('unrelated-027', modbuilder_wrap('mods/test/unrelated_027', '0.27.0', coyote)),
            ('new-in-028-027', modbuilder_wrap('mods/test/new_028_field', '0.27.0', slowdown)),
            ('unprotected-027', modbuilder_wrap('mods/test/unprotected_027', '0.27.0', ergonomics)),
            ('shield-027', modbuilder_wrap('mods/test/shield_027', '0.27.0', shield)),
            ('shield-028', modbuilder_wrap('mods/test/shield_028', '0.28.0', shield)),
            ('transaction-027', modbuilder_wrap('mods/test/transaction_027', '0.27.0', transaction)),
        ])

    @staticmethod
    def purifier_default(field):
        catalog = json.loads((ROOT / 'sdk/PlayerWeaponAuthoringCapabilities.json').read_text(encoding='utf-8'))
        weapon = next(w for w in catalog['weapons'] if w['name'] == 'PLAS-101 Purifier')
        return next(f for f in weapon['fields'] if f['semanticFieldId'] == field)['currentDefault']

    def assert_legacy(self, name, sdk_version, source='wrapper', fields=(('PLAS-101 Purifier', 'projectile.drag'),)):
        result = self.results[name]
        op = only(result)
        self.assertNotEqual(op['status'], 'rejected', op.get('error'))
        self.assertEqual((op['sdk'], op['sdk_source']), (sdk_version, source))
        self.assertEqual([(item['target'], item['field'], item['since']) for item in op['legacy']],
            [(target, field, '0.28.0') for target, field in fields])
        lines = legacy_lines(result)
        self.assertEqual(len(lines), len(fields), lines)
        return lines

    def assert_refused(self, name, *needles):
        op = only(self.results[name])
        self.assertEqual(op['status'], 'rejected')
        self.assertFalse(op['legacy'])
        self.assertIn('field requires allow_unverified_effect=true', op['error'])
        for needle in needles:
            self.assertIn(needle, op['error'])
        self.assertEqual(legacy_lines(self.results[name]), [])
        self.assertTrue(any(' rejected: field requires allow_unverified_effect=true' in line
            for line in self.results[name]['log']))

    def test_sdk_027_operation_on_a_newly_protected_field_is_accepted_as_legacy(self):
        line, = self.assert_legacy('modbuilder-027', '0.27.0')
        self.assertIn('ensure purifier-drag: legacy SDK 0.27.0 operation from mods/test/legacy_027: PLAS-101 Purifier '
            'projectile.drag needs allow_unverified_effect=true since SDK 0.28.0 and is applied without it', line)
        self.assertIn('Rebind the project to SDK 0.28.0 or later and re-export it', line)
        self.assertIn('Only the charge levels that name this projectile fire it', line)
        self.assertEqual(only(self.results['modbuilder-027'])['mod'], 'mods/test/legacy_027')

    def test_sdk_028_operation_without_the_acknowledgement_is_still_refused(self):
        self.assert_refused('modbuilder-028', 'required since SDK 0.28.0; mods/test/current_028 declares SDK 0.28.0')
        # An SDK prerelease of 0.28.0 already carried the acknowledgement: only MAJOR.MINOR.PATCH is compared.
        self.assert_refused('sdk-028-rc', 'declares SDK 0.28.0-rc.1')

    def test_sdk_028_operation_with_the_acknowledgement_applies_without_a_legacy_note(self):
        op = only(self.results['modbuilder-028-ack'])
        self.assertNotEqual(op['status'], 'rejected', op.get('error'))
        self.assertEqual((op['sdk'], op['legacy'] or []), ('0.28.0', []))
        self.assertEqual(legacy_lines(self.results['modbuilder-028-ack']), [])

    def test_an_unreadable_declaration_keeps_the_current_rule(self):
        self.assert_refused('bare', "Runtime could not read the SDK version of")
        self.assertEqual(only(self.results['bare'])['sdk_source'], 'unknown')

    def test_every_published_wrapper_shape_declares_its_version(self):
        self.assert_legacy('modbuilder-026', '0.26.1')
        self.assert_legacy('sdk-027', '0.27.0')
        self.assert_legacy('template-025', '0.25.0')

    def test_unrelated_protected_fields_behave_as_before(self):
        # Needed allow_unverified_effect already in 0.27.0.
        self.assert_refused('unrelated-027', 'fire_mode.burst_rounds')
        self.assertNotIn('required since', only(self.results['unrelated-027'])['error'])
        # New in 0.28 (and protected): an SDK 0.27 mod never had it, so there is no earlier rule to keep.
        self.assert_refused('new-in-028-027', 'penetration_slowdown')
        # Not protected at all: unchanged, no legacy note.
        op = only(self.results['unprotected-027'])
        self.assertNotEqual(op['status'], 'rejected', op.get('error'))
        self.assertEqual((op['sdk'], op['legacy'] or []), ('0.27.0', []))

    def test_sh51_body_fields_follow_the_same_rule(self):
        self.assert_legacy('shield-027', '0.27.0', fields=(('SH-51 Directional Shield', 'entity.health'),))
        self.assert_refused('shield-028', 'declares SDK 0.28.0')

    def test_one_line_per_legacy_field_of_a_transaction(self):
        velocity = only(self.results['transaction-027'])
        self.assertEqual({item['field'] for item in velocity['legacy']}, {'projectile.drag', 'projectile.velocity'})
        self.assertEqual(len(legacy_lines(self.results['transaction-027'])), 2)


BASTION_MG = "hd2.vehicle('TD-220 Bastion MK XVI'):weapon('attach_tank_gun_mg')"
BASTION_CANNON = "hd2.vehicle('TD-220 Bastion MK XVI'):weapon('attach_tank_gun')"
# The player report (0.31.2): a Bastion coax capacity of 2500 showed about 2100 for its owner and 500 for a friend.
MG_CAPACITY = ("hd2.ensure({patch={id='mg-capacity',target=" + BASTION_MG + ",allow_unverified_effect=true,"
    "field=hd2.fields.weapon.capacity,expect=2000,value=2500}})")
LIMITS_TRANSACTION = ("hd2.ensure({transaction={id='cannon-ammo',target=" + BASTION_CANNON + ",allow_unverified_effect=true,"
    "changes={{field=hd2.fields.magazine.spare_magazines,expect=30,value=45},"
    "{field=hd2.fields.magazine.magazines_from_supply,expect=30,value=31}}}})")


class LegacyLimitTests(unittest.TestCase):
    """0.31.2 bounds a magazine's capacity (2047) and magazine counts (31) by the network fields of the live counts
    (scripts/ammo_limits.py). A mod that declares an older SDK had no maximum: its larger value is clamped to the
    ceiling as a logged legacy operation. A mod that declares 0.31.2, or whose declaration cannot be read, is refused."""

    @classmethod
    def setUpClass(cls):
        cls.results = run_mods([
            ('mg-0311', modbuilder_wrap('mods/test/limits_0311', '0.31.1', MG_CAPACITY)),
            ('mg-sdk-0300', sdk.wrap_addon('mods/test/limits_sdk_0300', '0.30.0', MG_CAPACITY)),
            ('mg-bare', REQUIRE + MG_CAPACITY.replace("'mg-capacity'", "'bare-mg-capacity'")),
            ('cannon-0311', modbuilder_wrap('mods/test/limits_cannon_0311', '0.31.1', LIMITS_TRANSACTION)),
        ])

    def test_an_older_sdk_value_above_the_ceiling_applies_clamped_as_legacy(self):
        for name, sdk_version in (('mg-0311', '0.31.1'), ('mg-sdk-0300', '0.30.0')):
            op = only(self.results[name])
            self.assertNotEqual(op['status'], 'rejected', op.get('error'))
            self.assertEqual(op['sdk'], sdk_version)
            self.assertEqual([(item['target'], item['field'], item['since'], item['limit']) for item in op['legacy']],
                [('TD-220 Bastion MK XVI / attach_tank_gun_mg', 'weapon.capacity', '0.31.2', {'value': 2500, 'max': 2047})])
            line, = legacy_lines(self.results[name])
            self.assertIn(': legacy SDK ' + sdk_version + ' operation from ', line)
            self.assertIn('TD-220 Bastion MK XVI / attach_tank_gun_mg weapon.capacity = 2500 is above its maximum 2047 '
                'since SDK 0.31.2 and is applied as 2047', line)
            self.assertIn('the network field rounds (11 bits)', line)

    def test_an_unreadable_declaration_is_refused(self):
        # (A project bound to SDK 0.31.2 is refused the same way: test_the_clamped_value_is_what_is_written checks it
        # directly. It was written when the runtime was still versioned 0.31.1 and its wrappers refused 0.31.2 projects.)
        for name, needle in (('mg-bare', 'Runtime could not read the SDK version'),):
            op = only(self.results[name])
            self.assertEqual(op['status'], 'rejected')
            self.assertIn('value is above the reviewed maximum 2047 for weapon.capacity', op['error'])
            self.assertIn(needle, op['error'])
            self.assertFalse(op['legacy'])
            self.assertEqual(legacy_lines(self.results[name]), [])

    def test_only_the_value_above_the_ceiling_is_a_legacy_use(self):
        op = only(self.results['cannon-0311'])
        self.assertNotEqual(op['status'], 'rejected', op.get('error'))
        self.assertEqual([(item['field'], item['limit']) for item in op['legacy']],
            [('magazine.spare_magazines', {'value': 45, 'max': 31})])

    def test_the_clamped_value_is_what_is_written(self):
        # The write domain encodes the ceiling, not the declared value; a value within it is untouched.
        out = run(r'''
local hd2=require('hd2runtime/api/hd2')
local compat=require('hd2runtime/core/sdk_compatibility')
local weapons=require('hd2runtime/domains/player_weapon_writes')
local attachments=require('hd2runtime/domains/attachment_writes')
local b=require('hd2runtime/core/bytes')
local function origin(sdk)return {mod='mods/test/written',sdk=sdk,source='wrapper',pending={},logged={}}end
local old=origin('0.31.1')
local spec=compat.with_origin(old,weapons.validate_transaction,{id='x',allow_unverified_effect=true,
 target=hd2.vehicle('TD-220 Bastion MK XVI'):weapon('attach_tank_gun'),changes={
 {field=hd2.fields.magazine.spare_magazines,expect=30,value=45},
 {field=hd2.fields.magazine.magazines_from_supply,expect=30,value=31}}})
assert(spec.changes[1].desired==b.encode(31,'u32')and spec.changes[1].value==31,'clamped to 31')
assert(spec.changes[2].desired==b.encode(31,'u32'))
assert(#old.pending==1 and old.pending[1].limit.value==45 and old.pending[1].limit.max==31)
-- A magazine attachment definition (the same ceiling on its own delta row).
local catalog=require('hd2runtime/domains/attachment_authoring')
local id
for key,entry in pairs(catalog.attachments)do if entry.fields and entry.fields['attachment.magazine_capacity']then id=key;break end end
local field=catalog.attachments[id].fields['attachment.magazine_capacity']
assert(field.max==2047,'attachment capacity bounded')
local spec2=compat.with_origin(origin('0.31.1'),attachments.validate_patch,{id='y',allow_shared=true,
 allow_unverified_effect=true,target={resource='weapon_attachment',path='magazine',attachment=id},
 field='attachment.magazine_capacity',expect=field.currentDefault,value=5000})
assert(spec2.changes[1].desired==b.encode(2047,'u32'))
local ok,why=pcall(compat.with_origin,origin('0.31.2'),attachments.validate_patch,{id='y',allow_shared=true,
 allow_unverified_effect=true,target={resource='weapon_attachment',path='magazine',attachment=id},
 field='attachment.magazine_capacity',expect=field.currentDefault,value=5000})
assert(not ok and tostring(why):find('above the reviewed maximum 2047',1,true),tostring(why))
assert(tostring(why):find('maximum since SDK 0.31.2; mods/test/written declares SDK 0.31.2',1,true),tostring(why))
ok,why=pcall(compat.with_origin,origin('0.31.2'),weapons.validate_patch,{id='z',allow_unverified_effect=true,
 target=hd2.vehicle('TD-220 Bastion MK XVI'):weapon('attach_tank_gun_mg'),field=hd2.fields.weapon.capacity,
 expect=2000,value=2500})
assert(not ok and tostring(why):find('declares SDK 0.31.2',1,true),tostring(why))
return 'ok'
''')
        self.assertEqual(out, b'ok')


class DeclarationTests(unittest.TestCase):
    def test_callback_registrations_use_the_declaration_remembered_for_their_mod(self):
        # The SDK wrapper runs the startup as the mod (run_as). A later registration from that mod's callback (here a
        # run_as scope outside any wrapper) finds no wrapper on the stack and uses the remembered declaration; another
        # mod's does not.
        out = run(r'''
rawset(_G,'CowboyBingusModLoader',{api=1,version=18})
local hd2=require('hd2runtime/api/hd2')
package.preload['mods/skyeshade/hd2runtime']=function()return hd2 end
require('hd2runtime/runtime/log').emit=function()end
assert(loadstring(''' + lua_string(sdk.wrap_addon('mods/test/callbacks', '0.27.0', 'return true')) + r'''))()
local events=require('hd2runtime/runtime/events')
local handle,other
events.run_as('mods/test/callbacks',function()handle=''' + PURIFIER_DRAG + r''' end)
events.run_as('mods/test/other',function()other=''' + PURIFIER_DRAG.replace("'purifier-drag'", "'other-drag'") + r''' end)
local ops=hd2.diagnostics.operations()
assert(handle.status~='rejected',tostring(handle.error))
assert(ops[#ops-1].sdk=='0.27.0'and ops[#ops-1].sdk_source=='mod'and#ops[#ops-1].legacy==1)
assert(other.status=='rejected'and ops[#ops].sdk_source=='unknown')
return 'ok'
''')
        self.assertEqual(out, b'ok')

    def test_an_option_change_revalidates_as_the_registering_mod(self):
        body = r'''
local page=hd2.options({id='legacy_test',title='Legacy'})
local drag=page:slider({id='drag',label='Drag',min=0.5,max=1.5,step=0.1,default=0.8})
return hd2.ensure({patch={id='bound-drag',target=''' + PURIFIER + r''',allow_shared=true,
 field=hd2.fields.projectile.drag,expect=1.5,value=drag}})
'''
        out = run(r'''
rawset(_G,'CowboyBingusModLoader',{api=1,version=18})
local hd2=require('hd2runtime/api/hd2')
package.preload['mods/skyeshade/hd2runtime']=function()return hd2 end
local lines={}
require('hd2runtime/runtime/log').emit=function(line)lines[#lines+1]=line end
local function count(text)local n=0;for _,l in ipairs(lines)do if l:find(text,1,true)then n=n+1 end end;return n end
local callbacks={}
rawset(_G,'ModOptionsMenu',{api=1,register_option=function()return true end,get=function()return nil end,
 on_change=function(id,fn)callbacks[id]=fn;return true end,ready=function()return true end})
local metrics=require('hd2runtime/runtime/metrics')
local function checks()return metrics.snapshot().counters['compatibility.legacy_checks']or 0 end
local handle=assert(loadstring(''' + lua_string(modbuilder_wrap('mods/test/options_027', '0.27.0', body)) + r'''))()
assert(handle.status~='rejected',tostring(handle.error))
assert(count(': legacy SDK 0.27.0 operation')==1,'one legacy line for every bind-time sample')
local ops=hd2.diagnostics.operations()
assert(ops[#ops].sdk=='0.27.0'and#ops[#ops].legacy==1)
local function tick(seconds)for _=1,math.floor(seconds/0.1+0.5)do if update then update(0.1)end end end
tick(1)
assert(callbacks['legacy_test.drag'],'the option registered with the menu')
local before=checks()
callbacks['legacy_test.drag'](1.2)
tick(2)
-- The change re-validated outside the wrapper, as the registering 0.27.0 mod: accepted, not blocked, logged once.
assert(checks()>before,'the option change re-validated')
assert(count('ensure bound-drag blocked')==0,table.concat(lines,' | '))
assert(count(': legacy SDK 0.27.0 operation')==1)
assert(require('hd2runtime/core/sdk_compatibility').current()==nil)
return 'ok'
''')
        self.assertEqual(out, b'ok')

    def test_version_helpers(self):
        out = run(r'''
local c=require('hd2runtime/core/sdk_compatibility')
assert(c.older('0.27.0','0.28.0')and c.older('0.27.9','0.28.0')and c.older('0.9.0','0.28.0'))
assert(not c.older('0.28.0','0.28.0')and not c.older('0.28.0-rc.1','0.28.0')and not c.older('0.29.0','0.28.0'))
assert(not c.older('bad','0.28.0')and not c.older('0.28','0.28.0')and c.core('1.2.3+build.4')[3]==3)
assert(c.core('0.28.0-')==nil and c.core('0.28.0x')==nil)
-- Outside any registration nothing is legacy.
assert(c.legacy('allow_unverified_effect','player_weapon','PLAS-101 Purifier','projectile.drag')==false)
return 'ok'
''')
        self.assertEqual(out, b'ok')


class LegacyTableTests(unittest.TestCase):
    def test_table_is_current_and_names_the_published_scope(self):
        legacy_table.generate(check=True)
        history = json.loads(legacy_table.HISTORY.read_text(encoding='utf-8'))
        counts = {}
        # 0.31.3: allow_shared entries (the LAS-5 Scythe's rows, shared with the newly catalogued LAS-22 Shear).
        shared = [entry for entry in history['entries'] if entry['acknowledgement'] == 'allow_shared']
        self.assertEqual({(e['since'], e['resource'], e['target']) for e in shared},
            {('0.31.3', 'player_weapon', 'LAS-5 Scythe')})
        self.assertEqual(len(shared), 19)
        self.assertEqual({e['field'].split('.')[0] for e in shared}, {'damage', 'beam'})
        self.assertEqual([item['since'] for item in history['sharedReleases']], ['0.31.3'])
        for entry in history['entries']:
            if entry['acknowledgement'] == 'allow_shared':
                continue
            self.assertEqual(entry['acknowledgement'], 'allow_unverified_effect')
            self.assertIn(entry['since'], ('0.28.0', '0.30.0', '0.31.0'))
            counts.setdefault(entry['since'], {})
            counts[entry['since']][entry['target']] = counts[entry['since']].get(entry['target'], 0) + 1
        self.assertEqual(counts['0.28.0'], {'PLAS-101 Purifier': 28, 'P-34 Breacher': 28, 'P-33 Missile Pistol': 28,
            'PLAS-15 Loyalist': 28, 'P-92 Warrant': 16, 'LAS-17 Double-Edge Sickle': 16,
            'SH-51 Directional Shield': 2})
        self.assertEqual(sum(v for k, v in counts['0.28.0'].items() if k != 'SH-51 Directional Shield'), 144)
        # 0.30.0: the PLAS-45 Epoch partial-charge projectile, damage and explosion fields (research/charge-explosions).
        self.assertEqual(counts['0.30.0'], {'PLAS-45 Epoch': 30})
        self.assertEqual({entry['resource'] for entry in history['entries'] if entry['since'] == '0.30.0'},
            {'support_weapon'})
        # 0.31.0: the team-reload weapons' own magazine rows and the AC-8's own rounds rows
        # (research/team-reload-ammo-F5FEE03DCFDB.json; 0.30.3 accepted them as "no effect" rows).
        self.assertEqual(counts['0.31.0'], {'GR-8 Recoilless Rifle': 3, 'RL-77 Airburst Rocket Launcher': 3,
            'FAF-14 Spear': 3, 'StA-X3 W.A.S.P. Launcher': 3, 'AC-8 Autocannon': 3})
        self.assertEqual({entry['field'] for entry in history['entries'] if entry['since'] == '0.31.0'},
            {'magazine.spare_magazines', 'magazine.starting_magazines', 'magazine.magazines_from_supply',
             'rounds.spare_rounds', 'rounds.starting_rounds', 'rounds.rounds_from_supply'})
        self.assertEqual([item['since'] for item in history['releases']], ['0.28.0', '0.30.0', '0.31.0'])
        # 0.31.2: the network ceilings of a magazine's live counts (scripts/ammo_limits.py), on every field the SDK at
        # v0.31.1 let mods write above them: player, support and mounted weapons and magazine attachments.
        self.assertEqual([item['since'] for item in history['limitReleases']], ['0.31.2'])
        limits = {}
        for entry in history['limits']:
            self.assertEqual(entry['since'], '0.31.2')
            self.assertEqual(entry['max'], 2047 if entry['field'].endswith('capacity') else 31)
            self.assertIsNone(entry['previousMax'])
            limits.setdefault(entry['resource'], set()).add(entry['field'])
        self.assertEqual(limits, {'player_weapon': {'magazine.capacity', 'magazine.starting_magazines',
                'magazine.magazines_from_supply', 'magazine.spare_magazines'},
            'support_weapon': {'weapon.capacity', 'magazine.starting_magazines', 'magazine.magazines_from_supply',
                'magazine.spare_magazines'},
            'vehicle_weapon': {'weapon.capacity', 'magazine.starting_magazines', 'magazine.magazines_from_supply',
                'magazine.spare_magazines'},
            'weapon_attachment': {'attachment.magazine_capacity', 'attachment.starting_magazines',
                'attachment.magazines_from_supply', 'attachment.spare_magazines'}})
        # The team-reload weapons' own magazine rows were bounded to 31 in 0.31.0: no 0.31.2 entry.
        self.assertFalse([e for e in history['limits'] if e['target'] == 'GR-8 Recoilless Rifle'
            and e['field'].startswith('magazine.')])
        self.assertIn(('vehicle_weapon', 'TD-220 Bastion MK XVI / attach_tank_gun_mg', 'weapon.capacity'),
            {(e['resource'], e['target'], e['field']) for e in history['limits']})
        # Every entry still names a field that needs the acknowledgement now.
        current = legacy_table.fields(legacy_table.current_catalogs())
        for entry in history['entries']:
            field = current[(entry['resource'], entry['target'], entry['field'])]
            if entry['acknowledgement'] == 'allow_shared':
                self.assertTrue(field['editable'] and field['affectsMultipleWeapons'], entry)
            else:
                self.assertTrue(legacy_table.needs(field), entry)

    @unittest.skipUnless(all(subprocess.run(['git', 'rev-parse', '-q', '--verify', tag + '^{commit}'], cwd=ROOT,
        capture_output=True).returncode == 0 for tag in ('v0.27.0', 'v0.28.1')), 'the v0.27.0 / v0.28.1 tags are not '
        'available')
    def test_entries_are_exactly_the_published_fields_that_gained_it(self):
        # Each release's entries are exactly the fields the SDK it was compared with let mods write without the
        # acknowledgement and that the next published SDK (or the current one, for the latest release) requires it on.
        history = json.loads(legacy_table.HISTORY.read_text(encoding='utf-8'))
        releases = history['releases']
        current = legacy_table.fields(legacy_table.current_catalogs())
        for index, release in enumerate(releases):
            previous = legacy_table.fields(legacy_table.git_catalogs(release['comparedWith']))
            following = (legacy_table.fields(legacy_table.git_catalogs(releases[index + 1]['comparedWith']))
                if index + 1 < len(releases) else current)
            expected = {key for key, field in following.items() if legacy_table.needs(field) and key in previous
                and previous[key].get('editable') and previous[key].get('acknowledgement') != 'allow_unverified_effect'
                and key in current and legacy_table.needs(current[key])}
            self.assertEqual({(e['resource'], e['target'], e['field']) for e in history['entries']
                if e['since'] == release['since'] and e['acknowledgement'] == 'allow_unverified_effect'}, expected,
                release['since'])

    @unittest.skipUnless(subprocess.run(['git', 'rev-parse', '-q', '--verify', 'v0.31.2^{commit}'], cwd=ROOT,
        capture_output=True).returncode == 0, 'the v0.31.2 tag is not available')
    def test_shared_entries_are_exactly_the_fields_that_became_shared(self):
        # 0.31.3: every player weapon field the SDK at v0.31.2 let mods write without allow_shared that is shared now.
        history = json.loads(legacy_table.HISTORY.read_text(encoding='utf-8'))
        (release,) = history['sharedReleases']
        previous = legacy_table.fields(legacy_table.git_catalogs(release['comparedWith']))
        current = legacy_table.fields(legacy_table.current_catalogs())
        expected = {key for key, field in current.items() if key[0] == 'player_weapon' and key in previous
            and field.get('editable') and field.get('affectsMultipleWeapons') and previous[key].get('editable')
            and not previous[key].get('affectsMultipleWeapons')}
        self.assertEqual({(e['resource'], e['target'], e['field']) for e in history['entries']
            if e['acknowledgement'] == 'allow_shared'}, expected)


SCYTHE_DAMAGE = ("hd2.ensure({patch={id='scythe-damage',target=hd2.weapon('LAS-5 Scythe'),"
    "field=hd2.fields.damage.player_standard_damage,expect=350,value=500}})")


class SharedLegacyTests(unittest.TestCase):
    """0.31.3: the LAS-5 Scythe's beam and damage rows are shared with the newly catalogued LAS-22 Shear. A mod that
    declares an older SDK wrote them without allow_shared and keeps working (logged); newer mods need it."""
    @classmethod
    def setUpClass(cls):
        cls.results = run_mods([
            ('scythe-0312', modbuilder_wrap('mods/test/scythe_0312', '0.31.2', SCYTHE_DAMAGE)),
            ('scythe-0312-shared', modbuilder_wrap('mods/test/scythe_0312_shared', '0.31.2',
                SCYTHE_DAMAGE.replace("id='scythe-damage',", "id='scythe-damage',allow_shared=true,"))),
            ('scythe-bare', REQUIRE + SCYTHE_DAMAGE.replace("'scythe-damage'", "'scythe-bare'")),
        ])

    def test_an_older_sdk_writes_the_newly_shared_row_as_legacy(self):
        result = self.results['scythe-0312']
        op = only(result)
        self.assertNotEqual(op['status'], 'rejected', op.get('error'))
        self.assertEqual([(i['acknowledgement'], i['target'], i['field'], i['since']) for i in op['legacy']],
            [('allow_shared', 'LAS-5 Scythe', 'damage.standard_damage', '0.31.3')])
        line, = legacy_lines(result)
        self.assertIn('LAS-5 Scythe damage.standard_damage needs allow_shared=true since SDK 0.31.3', line)
        self.assertIn('shared with LAS-22 Shear', line)

    def test_the_current_sdk_and_an_unreadable_declaration_need_allow_shared(self):
        op = only(self.results['scythe-bare'])
        self.assertEqual(op['status'], 'rejected')
        self.assertIn('shared field requires allow_shared=true: damage.standard_damage', op['error'])
        self.assertIn('Runtime could not read the SDK version of', op['error'])
        self.assertEqual(legacy_lines(self.results['scythe-bare']), [])
        # With allow_shared the write applies with no legacy note.
        op = only(self.results['scythe-0312-shared'])
        self.assertNotEqual(op['status'], 'rejected', op.get('error'))
        self.assertEqual(op['legacy'] or [], [])
        # A mod declaring 0.31.3 (not loadable before the bump: the dependency check) keeps the rule.
        self.assertEqual(run(r'''
local c=require('hd2runtime/core/sdk_compatibility')
local function check(sdk)
 return c.with_origin({mod='mods/test/x',sdk=sdk,source='wrapper',pending={},logged={}},function()
  return c.legacy('allow_shared','player_weapon','LAS-5 Scythe','damage.standard_damage','shared with LAS-22 Shear')end)
end
local ok,why=check('0.31.3')
assert(ok==false and why=='required since SDK 0.31.3; mods/test/x declares SDK 0.31.3',tostring(why))
assert(check('0.31.2')==true)
-- The Shear's own fields were never published without allow_shared: no legacy entry.
assert(c.with_origin({mod='m',sdk='0.27.0',source='wrapper',pending={},logged={}},function()
 return c.legacy('allow_shared','player_weapon','LAS-22 Shear','damage.standard_damage')end)==false)
return 'ok'
'''), b'ok')


if __name__ == '__main__':
    unittest.main()
