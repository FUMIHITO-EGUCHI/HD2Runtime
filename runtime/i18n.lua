-- HD2Runtime's own on-screen text in the game's languages (0.31.1). Every text the Runtime shows a player (the F10 panel,
-- the startup and safety notices, the alert cards, the custom stratagem panel, the startup progress) is written in
-- English in the code and looked up here by that English text: M.t('Startup notice'). The translations live in
-- domains/runtime_locale.lua (generated from schemas/runtime_locale.json by scripts/generate_runtime_locale.py), one per
-- game language; a missing one shows the English text.
--
-- The language: the F10 panel's Language setting. 'auto' (the default) follows the language the game is set to, read
-- from the game's own current-language member (runtime/text_resources.lua language: only on a proven build; English
-- otherwise); a language code picks that one whatever the game uses. The game's language is polled at most once a
-- second (the game has no change event): a panel that keeps its text on screen redraws when M.language() changes.
--
-- Templates keep the English text's format specifiers, in the same order (string.format). A translation whose
-- specifiers differ is refused by the generator; at run time a template that fails to format shows the English one.
-- Mod-provided text (custom stratagem names, mod names) is never translated here.
local M={}
M.AUTO='auto'
M.DEFAULT='us'

local locale
local function data()
    if locale==nil then
        local ok,value=pcall(require,'hd2runtime/domains/runtime_locale')
        locale=ok and type(value)=='table'and value or{languages={},strings={},fallback={}}
    end
    return locale
end
-- The game languages in the order the panel lists them: {code, name} (each name in its own language).
function M.languages()return data().languages end
local function known(code)
    for _,item in ipairs(data().languages)do if item.code==code then return true end end
    return false
end

M.hooks={}
-- The game's current language code, or nil (an unproven build, or outside the game).
function M.hooks.game_language()
    if type(rawget(_G,'stingray'))~='table'then return nil end
    local ok,code=pcall(function()
        local world=require('hd2runtime/runtime/event_world').open()
        return world and world.runtime and require('hd2runtime/runtime/text_resources').language(world.runtime)
    end)
    return ok and type(code)=='string'and code or nil
end
function M.hooks.clock()local ok,v=pcall(os.clock);return ok and v or 0 end
-- The Language setting: 'auto' or a code (runtime/runtime_settings.lua).
function M.hooks.setting()
    local ok,settings=pcall(require,'hd2runtime/runtime/runtime_settings')
    if ok and type(settings.value)=='function'then
        local okv,value=pcall(settings.value,'language')
        if okv and type(value)=='string'then return value end
    end
    return M.AUTO
end

local game={code=nil,at=-math.huge}
-- The game's language, polled at most once a second.
function M.game_language()
    local now=M.hooks.clock()
    if now-game.at>=1 or now<game.at then
        game.at=now
        local ok,code=pcall(M.hooks.game_language)
        game.code=ok and known(code)and code or nil
    end
    return game.code
end
-- The language the Runtime shows its text in now: the setting's, or the game's ('auto'), else English.
function M.language()
    local setting=M.hooks.setting()
    if setting~=M.AUTO and known(setting)then return setting end
    return M.game_language()or M.DEFAULT
end
-- The name of a language code in its own language ('auto': nil).
function M.name(code)
    for _,item in ipairs(data().languages)do if item.code==code then return item.name end end
    return nil
end

-- The text in the current language (or `language`): the translation of the English `source`, formatted with the
-- arguments like string.format; the English text when there is no translation (or it fails to format).
local function lookup(source,language)
    local D=data()
    local entry=D.strings[source]
    if type(entry)~='table'then return source end
    local code=language
    for _=1,4 do
        if not code then break end
        local text=entry[code]
        if type(text)=='string'and text~=''then return text end
        code=D.fallback[code]
    end
    return source
end
function M.translate(language,source,...)
    local text=lookup(source,language)
    if select('#',...)==0 then return text end
    local ok,result=pcall(string.format,text,...)
    if ok then return result end
    return string.format(source,...)
end
function M.t(source,...)return M.translate(M.language(),source,...)end

------------------------------------------------------------------------------------------------- upper case --
-- Upper case for the scripts the game's European and Russian fonts draw (string.upper changes ASCII only): Latin-1,
-- Latin Extended-A (Polish), Cyrillic. Other characters (CJK, digits) are kept.
local function upper_code(c)
    if c>=0x61 and c<=0x7A then return c-32 end
    if c>=0xE0 and c<=0xFE and c~=0xF7 then return c-32 end
    if c>=0x0100 and c<=0x017F then
        local even_lower=(c>=0x0139 and c<=0x0148)or(c>=0x0179 and c<=0x017E)
        if c==0x0138 or c==0x0149 or c==0x017F then return c end
        if even_lower then
            if c%2==0 then return c-1 end
        elseif c%2==1 then return c-1 end
        return c
    end
    if c>=0x0430 and c<=0x044F then return c-0x20 end
    if c>=0x0450 and c<=0x045F then return c-0x50 end
    return c
end
local function encode(c)
    if c<0x80 then return string.char(c)end
    if c<0x800 then return string.char(0xC0+math.floor(c/0x40),0x80+c%0x40)end
    if c<0x10000 then
        return string.char(0xE0+math.floor(c/0x1000),0x80+math.floor(c/0x40)%0x40,0x80+c%0x40)
    end
    return string.char(0xF0+math.floor(c/0x40000),0x80+math.floor(c/0x1000)%0x40,0x80+math.floor(c/0x40)%0x40,
        0x80+c%0x40)
end
function M.upper(s)
    s=tostring(s)
    if not s:find('[\128-\255]')then return s:upper()end
    local out={}
    local i,n=1,#s
    while i<=n do
        local b=s:byte(i)
        local len=b<0x80 and 1 or b>=0xF0 and 4 or b>=0xE0 and 3 or b>=0xC0 and 2 or 1
        local c=b
        if len==2 then c=(b-0xC0)*0x40+(s:byte(i+1)or 0x80)-0x80
        elseif len==3 then c=(b-0xE0)*0x1000+((s:byte(i+1)or 0x80)-0x80)*0x40+(s:byte(i+2)or 0x80)-0x80
        elseif len==4 then
            c=(b-0xF0)*0x40000+((s:byte(i+1)or 0x80)-0x80)*0x1000+((s:byte(i+2)or 0x80)-0x80)*0x40
                +(s:byte(i+3)or 0x80)-0x80
        end
        out[#out+1]=encode(upper_code(c))
        i=i+len
    end
    return table.concat(out)
end

function M.reset_for_tests()game={code=nil,at=-math.huge};locale=nil end
return M
