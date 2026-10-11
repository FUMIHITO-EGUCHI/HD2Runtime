"""The game's own names (0.31.2; docs/game-text.md, research/docs/game-text-api-F5FEE03DCFDB.md): the internal nameText
records the generators stamp into the domains (scripts/game_names.py) against the research, and the read-only lookup
(runtime/text_resources.lua game_text, api/text.lua) on the offline event world's text registry. Nothing here touches
a game process; none of it is live-tested."""
import json
import re
import unittest

from support import ROOT, run
from test_event_scripting import PRELUDE

RESEARCH = json.loads((ROOT / 'research/weapon-name-text-ids-F5FEE03DCFDB.json').read_text(encoding='utf-8'))
# The game's en-US name is not the key (game facts, research summary.mismatches): the game's name is shown.
MISMATCHES = {('weapon', 'CQC-73 Entrenchment Tool'), ('backpack', 'RL-77 Airburst Rocket Launcher Backpack'),
    ('vehicle', 'FRV (Super Earth variant)'), ('vehicle', 'GATER Oil Rig')}
UNDERBARRELS = {'AR-11 Arbitrator / underbarrel', 'AR/GL-21 One-Two / underbarrel', 'SMG/FLAM-34 Stoker / underbarrel'}
KINDS = {('player_weapon_authoring', 'weapons'): 'weapon', ('support_weapon_authoring', 'weapons'): 'support_weapon',
    ('throwable_authoring', 'throwables'): 'throwable', ('entity_authoring', 'backpacks'): 'backpack',
    ('entity_authoring', 'vehicles'): 'vehicle'}

DUMP = r'''
local rows={}
local function hex(v)return v and string.format('%08X',v)or''end
local function dump(domain,coll,kind)
  local D=require('hd2runtime/domains/'..domain)
  for key,entry in pairs(D[coll])do
    local n=entry.nameText
    rows[#rows+1]=table.concat({kind,key,n and'1'or'0',n and hex(n.name)or'',n and hex(n.nameUpper)or'',
      n and hex(n.prefix)or'',n and hex(n.description)or'',n and n.designation or'',n and n.keyMismatch and'1'or''},'\t')
  end
end
dump('player_weapon_authoring','weapons','weapon')
dump('support_weapon_authoring','weapons','support_weapon')
dump('throwable_authoring','throwables','throwable')
dump('entity_authoring','backpacks','backpack')
dump('entity_authoring','vehicles','vehicle')
dump('booster_authoring','boosters','booster')
dump('stratagem_authoring','stratagems','stratagem')
return table.concat(rows,'\n')
'''


def norm(text):
    return re.sub(r'[^A-Z0-9]', '', (text or '').upper())


class NameRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = {}
        for line in run(DUMP).decode('utf-8').splitlines():
            kind, key, has, name, upper, prefix, description, designation, mismatch = line.split('\t')
            cls.records[(kind, key)] = None if has == '0' else {'name': name, 'nameUpper': upper,
                'prefix': prefix or None, 'description': description or None, 'designation': designation or None,
                'keyMismatch': mismatch == '1'}

    def test_equipment_records_are_the_researched_ids(self):
        checked = 0
        for item in RESEARCH['objects']:
            kind = KINDS.get((item['domain'], item['collection']))
            if kind is None:
                continue
            record = self.records[(kind, item['key'])]
            if item['status'] == 'no_record':
                self.assertIsNone(record, item['key'])
                continue
            ids = item['textIds']
            # The name id: the cased one, the upper-case one when the object has no cased text.
            self.assertEqual(record['name'], ids['name'] if item['nameSource'] == 'cased' else ids['nameUpper'],
                item['key'])
            self.assertEqual((record['nameUpper'], record['prefix'], record['description']),
                (ids['nameUpper'], ids.get('prefix'), ids.get('description')), item['key'])
            # The en-US composition reproduces the key, except the reviewed game-vs-key mismatches.
            name = (item['en']['name'] or item['en']['nameUpper']).strip()
            composed = ' '.join(p for p in (record['designation'], name) if p)
            self.assertEqual(norm(composed) != norm(item['key']), (kind, item['key']) in MISMATCHES, item['key'])
            self.assertEqual(record['keyMismatch'], (kind, item['key']) in MISMATCHES, item['key'])
            checked += 1
        self.assertEqual(checked, 170)
        self.assertEqual({k for k, r in self.records.items() if r and r['keyMismatch']}, MISMATCHES)
        # Underbarrels have no record: their name falls back to the key (NO_NAME).
        self.assertEqual({k for (kind, k), r in self.records.items() if r is None}, UNDERBARRELS)
        # The CQC-73 key stays; its game name is the CQC-72 (one record with the support weapon).
        self.assertEqual(self.records[('weapon', 'CQC-73 Entrenchment Tool')]['designation'], 'CQC-72')
        self.assertEqual(self.records[('weapon', 'CQC-73 Entrenchment Tool')]['name'],
            self.records[('support_weapon', 'CQC-72 Entrenchment Tool')]['name'])
        # A support weapon is named by its delivered weapon (LAS-98: not the Laser Sentry turret it also lists).
        self.assertEqual(self.records[('support_weapon', 'LAS-98 Laser Cannon')]['designation'], 'LAS-98')

    def test_booster_and_stratagem_records(self):
        for item in RESEARCH['boosters']:
            record = self.records[('booster', item['key'])]
            ids = item['textIds']
            self.assertEqual(record['name'], ids['nameUpper'] if item['nameFallbackToUpper'] else ids['name'])
            self.assertEqual((record['nameUpper'], record['description'], record['prefix']),
                (ids['nameUpper'], ids['description'], None))
            self.assertFalse(record['keyMismatch'], item['key'])
        self.assertEqual(self.records[('booster', 'Dead Sprint')]['name'],
            next(b['textIds']['nameUpper'] for b in RESEARCH['boosters'] if b['key'] == 'Dead Sprint'))
        stratagems = 0
        for item in RESEARCH['stratagems']:
            record = self.records[('stratagem', item['key'])]
            self.assertEqual((record['name'], record['nameUpper'], record['description'], record['prefix']),
                (item['textIds']['name'], item['textIds']['nameUpper'], item['textIds']['description'], None))
            self.assertFalse(record['keyMismatch'], item['key'])
            # StratagemInfo has no designation member: the key's designation stands in.
            if item['status'] == 'no_designation':
                self.assertEqual(norm(record['designation'] + ' ' + item['en']['name']), norm(item['key']))
            else:
                self.assertIsNone(record['designation'], item['key'])
            stratagems += 1
        self.assertEqual(stratagems, 94)
        self.assertEqual(self.records[('stratagem', 'A/MG-43 Machine Gun Sentry')]['designation'], 'A/MG-43')

    def test_ids_stay_internal(self):
        for path in (ROOT / 'sdk').glob('*.json'):
            self.assertNotIn('nameText', path.read_text(encoding='utf-8'), path.name)
        self.assertNotIn('nameText', (ROOT / 'schemas/stratagem_authoring_catalog.json').read_text(encoding='utf-8'))


LOOKUP = PRELUDE + r'''
local texts=require('hd2runtime/runtime/text_resources')
texts.reset_for_tests()
local PW=require('hd2runtime/domains/player_weapon_authoring').weapons
local SW=require('hd2runtime/domains/support_weapon_authoring').weapons
local TH=require('hd2runtime/domains/throwable_authoring').throwables
local EA=require('hd2runtime/domains/entity_authoring')
local BO=require('hd2runtime/domains/booster_authoring').boosters
local ST=require('hd2runtime/domains/stratagem_authoring').stratagems
local LIB=PW['AR-23 Liberator'].nameText
local SENTRY=ST['A/MG-43 Machine Gun Sentry'].nameText
local GAS=ST['Eagle Gas Airstrike'].nameText
local function hex(v)return string.format('%08X',v)end
local function us_table(extra)
    local t={[LIB.name]='Liberator',[LIB.nameUpper]='LIBERATOR',[LIB.prefix]='AR-23',
        [LIB.description]='The <c=#FFD700>standard</c> rifle.',[SENTRY.name]='Machine Gun Sentry',
        [GAS.name]='Eagle Gas Airstrike '}
    for k,v in pairs(extra or{})do t[k]=v end
    return {us=t}
end
'''


def lookup(body):
    return run(LOOKUP + body)


class LookupTests(unittest.TestCase):
    def check(self, body):
        self.assertEqual(lookup(body + "\nreturn 'ok'"), b'ok')

    def test_unavailable_before_the_game_registers_its_text(self):
        self.check(r'''
local ok,code=hd2.text.available()
assert(ok==false and code=='UNAVAILABLE',tostring(code))
local name,why=hd2.text.name('weapon','AR-23 Liberator')
assert(name==nil and why=='UNAVAILABLE',tostring(why))
assert(hd2.weapon('AR-23 Liberator'):display_name()==nil)
local text,tcode=hd2.text.game(LIB.name)
assert(text==nil and tcode=='UNAVAILABLE')
assert(hd2.text.language()==nil)
-- The language member is set but the registry is not there yet: still UNAVAILABLE.
local reg=W.text_registry({tables={us_table()}})
reg.rebuild({})                                     -- the game clears the registry (count 0) on a language change
ok,code=hd2.text.available()
assert(ok==false and code=='UNAVAILABLE')
assert(select(2,hd2.text.game(LIB.name))=='UNAVAILABLE')
''')

    def test_names_and_texts_in_the_current_language(self):
        self.check(r'''
local reg=W.text_registry({tables={us_table(),{us={[LIB.name]='SHADOWED'}}}})
local ok,language=hd2.text.available()
assert(ok==true and language=='us',tostring(language))
assert(hd2.text.language()=='us')
-- The first table holding the id wins, as in the game's reader.
assert(hd2.text.game(LIB.name)=='Liberator')
assert(hd2.text.game(hex(LIB.name))=='Liberator'and hd2.text.game('0x'..hex(LIB.name))=='Liberator')
assert(hd2.text.game(LIB.description)=='The <c=#FFD700>standard</c> rifle.')
assert(hd2.text.game(LIB.description,{plain=true})=='The standard rifle.')
local name,info=hd2.text.name('weapon','AR-23 Liberator')
assert(name=='AR-23 Liberator',tostring(name))
assert(info.prefix=='AR-23'and info.name=='Liberator'and info.name_upper=='LIBERATOR'and info.language=='us')
assert(info.description=='The standard rifle.')
assert(hd2.weapon('AR-23 Liberator'):display_name()=='AR-23 Liberator')
-- A stratagem has no designation member: the key's designation stands in; a trailing space is trimmed.
assert(hd2.text.name('stratagem','A/MG-43 Machine Gun Sentry')=='A/MG-43 Machine Gun Sentry')
assert(hd2.stratagem('A/MG-43 Machine Gun Sentry'):display_name()=='A/MG-43 Machine Gun Sentry')
assert(hd2.text.name('stratagem','Eagle Gas Airstrike')=='Eagle Gas Airstrike')
-- Codes.
local text,code=hd2.text.game(LIB.name,'de')
assert(text==nil and code=='LANGUAGE_NOT_LOADED',tostring(code))
assert(hd2.text.game(LIB.name,{language='us'})=='Liberator')
assert(select(2,hd2.text.game(LIB.name,'xx'))=='UNSUPPORTED_LANGUAGE')
assert(select(2,hd2.text.game(0x12345678))=='NO_TEXT')
assert(select(2,hd2.text.name('weapon','AR-11 Arbitrator / underbarrel'))=='NO_NAME')
assert(select(2,hd2.weapon('AR-11 Arbitrator'):underbarrel():display_name())=='NO_NAME')
assert(select(2,hd2.text.name('weapon','No Such Gun'))=='UNKNOWN_OBJECT')
assert(select(2,hd2.text.name('support_weapon','AR-23 Liberator'))=='UNKNOWN_OBJECT')
-- The name is known but its text is not registered: NO_TEXT (show the key).
assert(select(2,hd2.text.name('booster','Dead Sprint'))=='NO_TEXT')
for _,bad in ipairs({0,-1,2^32,1.5,'xyz','0x123','12345678 '})do
    assert(not pcall(hd2.text.game,bad),tostring(bad))
end
assert(not pcall(hd2.text.game,LIB.name,5))
assert(not pcall(hd2.text.name,'enemy','x'))
assert(not pcall(hd2.text.name,'weapon',5))
''')

    def test_every_target_kind_has_a_display_name(self):
        self.check(r'''
local function ids(record,t,name)t[record.name]=name;if record.prefix then t[record.prefix]=''end end
local t={}
ids(SW['M-105 Stalwart'].nameText,t,'Stalwart')
ids(TH['G-4 Gas'].nameText,t,'Gas')
ids(EA.backpacks['AC-8 Autocannon Backpack'].nameText,t,'Autocannon Backpack')
ids(EA.vehicles['EXO-45 Patriot Exosuit'].nameText,t,'Patriot Exosuit')
ids(BO['Dead Sprint'].nameText,t,'DEAD SPRINT')
local reg=W.text_registry({tables={us_table(t)}})
-- An empty localized prefix: the en-US designation stands in (SG-88 in every language but English).
assert(hd2.support_weapon('M-105 Stalwart'):display_name()=='M-105 Stalwart')
assert(hd2.throwable('G-4 Gas'):display_name()=='G-4 Gas')
-- A support backpack's record has no prefix; the key's designation stands in.
assert(hd2.backpack('AC-8 Autocannon Backpack'):display_name()=='AC-8 Autocannon Backpack')
assert(hd2.vehicle('EXO-45 Patriot Exosuit'):display_name()=='EXO-45 Patriot Exosuit')
-- Dead Sprint has no cased name: its upper-case one is the name.
assert(hd2.booster('Dead Sprint'):display_name()=='DEAD SPRINT')
-- The cased text missing in a language: the upper-case one.
local full={us={}};for k,v in pairs(us_table().us)do if k~=LIB.name then full.us[k]=v end end
reg.rebuild({full})
assert(hd2.text.name('weapon','AR-23 Liberator')=='AR-23 LIBERATOR')
''')

    def test_a_language_change_refreshes_the_cache(self):
        self.check(r'''
local reg=W.text_registry({tables={us_table()}})
assert(hd2.text.name('weapon','AR-23 Liberator')=='AR-23 Liberator')
-- The game clears the registry and registers the new language's tables (new pointers), then its language.
reg.rebuild({{cn={[LIB.name]='解放者',[LIB.nameUpper]='解放者',[LIB.prefix]='AR-23'}}})
reg.set_language('cn')
local name,info=hd2.text.name('weapon','AR-23 Liberator')
assert(name=='AR-23 解放者'and info.language=='cn',tostring(name))
assert(hd2.text.language()=='cn')
assert(select(2,hd2.text.game(LIB.name,'us'))=='LANGUAGE_NOT_LOADED')
-- An empty localized prefix falls back to the en-US designation.
reg.rebuild({{cn={[LIB.name]='解放者',[LIB.prefix]=''}}})
assert(hd2.text.name('weapon','AR-23 Liberator')=='AR-23 解放者')
-- The same language registered again with other text (new tables): the cache follows the registry.
reg.rebuild({{cn={[LIB.name]='解放者二'}}})
assert(hd2.text.game(LIB.name)=='解放者二')
reg.set_language('us');reg.rebuild({us_table()})
assert(hd2.text.name('weapon','AR-23 Liberator')=='AR-23 Liberator')
''')

    def test_long_chunked_and_invalid_strings(self):
        self.check(r'''
local LONG=string.rep('abcdefghij',300)..'é'            -- 3002 bytes: across many 256-byte chunks
local TOO=string.rep('x',4096)                           -- no NUL within the 4096-byte limit
local reg=W.text_registry({tables={{us={[1]=LONG,[2]=TOO,[3]='\255bad',[4]='line\r\n\ttab',[5]='a\1b',
    [6]='\237\160\128'}}}})
assert(hd2.text.game(1)==LONG)
local text,code=hd2.text.game(2)
assert(text==nil and code=='INVALID_TEXT',tostring(code))
assert(select(2,hd2.text.game(3))=='INVALID_TEXT')
assert(hd2.text.game(4)=='line\r\n\ttab')
assert(select(2,hd2.text.game(5))=='INVALID_TEXT')
assert(select(2,hd2.text.game(6))=='INVALID_TEXT')
-- The reader never reads across a page it was not sent to: chunks stop at each page end.
local memory={}
local BASE=4096*20-37
local s=string.rep('z',600)
local fake={read=function(at,n)
    assert(math.floor(at/4096)==math.floor((at+n-1)/4096),'a read crossed a page boundary')
    local out={}
    for i=0,n-1 do
        local k=at+i-BASE+1
        out[#out+1]=k>=1 and k<=#s and s:sub(k,k)or(k==#s+1 and'\0'or'?')
    end
    return table.concat(out)
end}
assert(texts.read_cstring_for_tests(fake,BASE)==s)
''')

    def test_unproven_build(self):
        self.check(r'''
local reg=W.text_registry({tables={us_table()}})
local D=require('hd2runtime/domains/text_resources')
local saved=D.source.exeSha256
D.source.exeSha256='0000'
texts.reset_for_tests()
local ok,code=hd2.text.available()
assert(ok==false and code=='UNSUPPORTED_BUILD',tostring(code))
assert(select(2,hd2.text.name('weapon','AR-23 Liberator'))=='UNSUPPORTED_BUILD')
D.source.exeSha256=saved
texts.reset_for_tests()
assert(hd2.text.name('weapon','AR-23 Liberator')=='AR-23 Liberator')
''')


if __name__ == '__main__':
    unittest.main()
