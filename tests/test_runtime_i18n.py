"""0.31.1: HD2Runtime's own on-screen text in the game's languages (runtime/i18n.lua, domains/runtime_locale.lua from
schemas/runtime_locale.json by scripts/generate_runtime_locale.py), the F10 Language setting (Automatic follows the
game's language; or one of the 15 game languages), and hd2.ui.open_settings for a mod's own settings button."""
import json
import re
import unittest

from support import ROOT, run

import sys
sys.path.insert(0, str(ROOT / 'scripts'))
import generate_runtime_locale  # noqa: E402

LOCALE = json.loads((ROOT / 'schemas/runtime_locale.json').read_text(encoding='utf-8'))

SETUP = r'''
local i18n=require('hd2runtime/runtime/i18n')
local settings=require('hd2runtime/runtime/runtime_settings')
settings.reset_for_tests()
local saved={}
settings.hooks.store=function()return {get=function(_,k)return saved[k]end,set=function(_,k,v)saved[k]=v end}end
local game=nil
i18n.hooks.game_language=function()return game end
local now=0
i18n.hooks.clock=function()return now end
'''


def lua(body):
    return run(SETUP + body + "\nreturn 'ok'")


class LocaleTests(unittest.TestCase):
    def test_the_generated_table_is_current_and_complete(self):
        generate_runtime_locale.generate(check=True)
        sources = generate_runtime_locale.sources()
        self.assertEqual(sorted(sources), sorted(LOCALE['strings']))
        codes = [item['code'] for item in LOCALE['languages']]
        self.assertEqual(len(codes), 15)
        # every language but English has every text
        for code in codes:
            if code in ('us', 'gb'):
                continue
            missing = [s for s in sources if code not in LOCALE['strings'][s]]
            self.assertFalse(missing, (code, missing[:5]))

    def test_every_translation_keeps_the_format_specifiers_in_order_and_capitals(self):
        for source, entry in LOCALE['strings'].items():
            want = generate_runtime_locale.specifiers(source)
            for code, text in entry.items():
                self.assertEqual(generate_runtime_locale.specifiers(text), want, (code, source, text))
                if source.isupper() and code not in ('jp', 'ko', 'cn', 'tc'):
                    self.assertEqual(text, text.upper(), (code, source, text))

    def test_every_character_is_in_a_font_that_draws_it(self):
        # The Runtime's FS Sinclair, or the game's own font for that language (domains/ui_fonts_<key>.lua): nothing
        # shows as '?' once the font is loaded. Language names in the list are checked in their own language's font.
        def codepoints(rel):
            return {int(m) for m in re.findall(r'\[(\d+)\]=', (ROOT / rel).read_text(encoding='utf-8'))}
        ui = (ROOT / 'domains/ui_fonts.lua').read_text(encoding='utf-8')
        role = {int(x) for x in re.findall(r'\[(\d+)\]=', re.search(r'\["advances"\]=\{([^}]*)\}', ui).group(1))}
        font_of = {'ru': 'ru', 'jp': 'ja', 'ko': 'ko', 'cn': 'zh_hans', 'tc': 'zh_hant'}
        fonts = {}

        def font(code):
            key = font_of.get(code, 'default')
            if key not in fonts:
                fonts[key] = codepoints('domains/ui_fonts_' + key + '.lua')
            return fonts[key]
        missing = []
        for source, entry in LOCALE['strings'].items():
            for code, text in entry.items():
                missing += [(code, source, ch) for ch in text if ord(ch) not in role and ord(ch) not in font(code)]
        for item in LOCALE['languages']:
            missing += [(item['code'], 'name', ch) for ch in item['name']
                        if ord(ch) not in role and ord(ch) not in font(item['code'])]
        self.assertFalse(missing, missing[:10])

    def test_a_wrong_specifier_is_refused(self):
        data = json.loads(json.dumps(LOCALE))
        data['strings']['%d PER MISSION']['de'] = '%s PRO EINSATZ'
        old = generate_runtime_locale.SOURCE.read_text(encoding='utf-8')
        try:
            generate_runtime_locale.SOURCE.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            with self.assertRaises(AssertionError):
                generate_runtime_locale.build()
        finally:
            generate_runtime_locale.SOURCE.write_text(old, encoding='utf-8', newline='\n')


class LanguageTests(unittest.TestCase):
    def test_automatic_follows_the_game_and_a_choice_overrides_it(self):
        self.assertEqual(lua(r'''
assert(settings.value('language')=='auto','Automatic by default')
assert(i18n.language()=='us','English when the game language is unknown')
game='de';now=now+2
assert(i18n.language()=='de','the game language (polled)')
assert(i18n.t('Startup notice')~='Startup notice','translated')
-- polled at most once a second
game='fr'
assert(i18n.language()=='de','not read again within a second')
now=now+1.5
assert(i18n.language()=='fr')
settings.set_value('language','jp')
assert(saved['setting.language']=='jp'and i18n.language()=='jp','a picked language, saved')
settings.set_value('language','auto')
assert(i18n.language()=='fr')
local ok=pcall(settings.set_value,'language','xx')
assert(not ok,'an unknown code is refused')
-- an unknown game language is English
game='zz';now=now+2
assert(i18n.language()=='us')
'''), b'ok')

    def test_translation_fallback_and_templates(self):
        self.assertEqual(lua(r'''
-- English UK falls back to English; Latin American Spanish has its own; unknown sources stay English
assert(i18n.translate('gb','Startup notice')=='Startup notice')
assert(i18n.translate('us','Startup notice')=='Startup notice')
assert(i18n.translate('de','not a Runtime text')=='not a Runtime text')
assert(i18n.translate('de','%d PER MISSION',3):find('3',1,true))
assert(i18n.translate('jp','Game %s','F5FEE03DCFDB'):find('F5FEE03DCFDB',1,true))
-- a template that fails to format shows the English one
local D=require('hd2runtime/domains/runtime_locale')
D.strings['%d SEC'].de='%d %d'
assert(i18n.translate('de','%d SEC',5)=='5 SEC')
'''), b'ok')

    def test_upper_case_beyond_ascii(self):
        self.assertEqual(lua(r'''
assert(i18n.upper('abc')=='ABC')
assert(i18n.upper('éèàçöüß')=='ÉÈÀÇÖÜß','Latin-1 (ß has no single capital)')
assert(i18n.upper('ąćęłńóśźż')=='ĄĆĘŁŃÓŚŹŻ','Polish')
assert(i18n.upper('привет ёж')=='ПРИВЕТ ЁЖ','Cyrillic')
assert(i18n.upper('日本語 abc')=='日本語 ABC','CJK kept')
'''), b'ok')


class PanelTests(unittest.TestCase):
    def test_the_language_list_opens_picks_and_closes_with_esc_first(self):
        self.assertEqual(lua(r'''
local function builder(w,h)
    local d={width=w,height=h,scale=1,texts={}}
    function d:rect()end
    function d:text(s)self.texts[#self.texts+1]=s end
    function d:text_width(s,size)return#s*size*0.55 end
    function d:wrap(s)return {s}end
    return d
end
local function has(d,s)for _,t in ipairs(d.texts)do if t==s then return true end end;return false end
local keys={}
local input={pressed=function(name)return keys[name]==true end}
game='fr';now=now+2
local d=builder(1920,1080)
local L=settings.draw(d,nil,input)
assert(has(d,'LANGUE')or has(d,'LANGUAGE'),'the section, in French')
assert(has(d,settings.language_text('auto')),'Automatic, with the game language')
-- open the list
local box=L.language
local m={x=box.x+box.w-10,y=box.y+box.h/2,left=false}
settings.draw(builder(1920,1080),m,input)
m.left=true
settings.draw(builder(1920,1080),m,input)
-- the list shows every language in its own name
d=builder(1920,1080)
m.left=false
L=settings.draw(d,m,input)
for _,item in ipairs(i18n.languages())do assert(has(d,item.name),item.name)end
-- Esc closes the list, not the panel
local closed=0
local close=settings.close
settings.close=function()closed=closed+1 end
keys.ESCAPE=true
settings.draw(builder(1920,1080),m,input)
keys.ESCAPE=nil
assert(closed==0,'Esc closed the list first')
-- open again, pick Deutsch
m.left=false;settings.draw(builder(1920,1080),m,input)
m.left=true;L=settings.draw(builder(1920,1080),m,input)
m.left=false;L=settings.draw(builder(1920,1080),m,input)
local de
for _,o in ipairs(L.options)do if o.option.code=='de'then de=o end end
m.x,m.y=de.box.x+10,de.box.y+de.box.h/2
settings.draw(builder(1920,1080),m,input)
m.left=true;settings.draw(builder(1920,1080),m,input)
assert(settings.value('language')=='de'and i18n.language()=='de','Deutsch picked')
d=builder(1920,1080)
m.left=false
settings.draw(d,m,input)
assert(has(d,'SPRACHE'),'the panel is German now')
settings.close=close
'''), b'ok')

    def test_a_mod_can_open_the_panel(self):
        self.assertEqual(lua(r'''
local hd2=require('hd2runtime/api/hd2')
assert(type(hd2.ui.open_settings)=='function'and type(hd2.ui.close_settings)=='function')
local opened=0
settings.open=function()opened=opened+1 end
assert(hd2.ui.open_settings()==true and opened==1)
local code,setting=hd2.ui.language()
assert(type(code)=='string'and setting=='auto')
'''), b'ok')


if __name__ == '__main__':
    unittest.main()
