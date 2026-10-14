-- hd2.text (0.31.2; docs/game-text.md): the game's own texts and object names in the language the game is set to.
-- Read-only, no acknowledgement; works in the ship and in missions. Nothing raises on game state: a lookup that cannot
-- answer returns nil (or false), a code and a reason, and the caller shows its own text (a domain key) instead.
--
-- Only the game's current language is in memory (runtime/text_resources.lua game_text). Text ids are internal: the
-- generated domains carry each object's ids (nameText, scripts/game_names.py); a mod asks by object, hd2.text.name(kind,
-- key) or target:display_name(). Codes: UNAVAILABLE (the game has not registered its text yet, or is switching language:
-- ask again later, e.g. when drawing), UNSUPPORTED_BUILD, LANGUAGE_NOT_LOADED, UNSUPPORTED_LANGUAGE, NO_TEXT,
-- INVALID_TEXT, UNKNOWN_OBJECT, NO_NAME (the object has no game name: an underbarrel).
local texts=require('hd2runtime/runtime/text_resources')
local M={}

M.hooks={}
-- The game process the texts are read from (the proven event world's adapter), or nil and why.
function M.hooks.runtime()
    local ok,world,why=pcall(function()return require('hd2runtime/runtime/event_world').open()end)
    if ok and type(world)=='table'and world.runtime then return world.runtime end
    return nil,tostring(ok and(why or'the game is not loaded')or world)
end
local function runtime()
    local value,why=M.hooks.runtime()
    if value then return value end
    return nil,'UNAVAILABLE',tostring(why)
end

-- The kinds hd2.text.name takes (the builder each is a target of) and their generated entries, by key.
M.KINDS={
    passive=function()
        local out={}
        for _,p in ipairs(require('hd2runtime/domains/player_passives').passives)do
            out[p.name]={nameText={name=tonumber(p.nameId,16)}}
        end
        return out
    end,
    mission=function()
        local out={};for _,m in ipairs(require('hd2runtime/domains/missions').missions)do out[m.id]=m end
        return out
    end,
    weapon=function()return require('hd2runtime/domains/player_weapon_authoring').weapons end,
    support_weapon=function()return require('hd2runtime/domains/support_weapon_authoring').weapons end,
    throwable=function()return require('hd2runtime/domains/throwable_authoring').throwables end,
    backpack=function()return require('hd2runtime/domains/entity_authoring').backpacks end,
    vehicle=function()return require('hd2runtime/domains/entity_authoring').vehicles end,
    booster=function()return require('hd2runtime/domains/booster_authoring').boosters end,
    stratagem=function()return require('hd2runtime/domains/stratagem_authoring').stratagems end}

local function text_id(id)
    if type(id)=='number'and id>=1 and id<=0xFFFFFFFF and id==math.floor(id)then return id end
    if type(id)=='string'then
        local hex=id:match('^0[xX](%x%x%x%x%x%x%x%x)$')or id:match('^(%x%x%x%x%x%x%x%x)$')
        local value=hex and tonumber(hex,16)
        if value and value~=0 then return value end
    end
    return nil
end

-- The game's text language: its code ('us', 'de', 'cn' ...), or nil, code and reason. Not hd2.ui.language (the language
-- HD2Runtime's own panels use, which the F10 setting can force).
function M.language()
    local rt,code,reason=runtime()
    if not rt then return nil,code,reason end
    local ok,language,why=texts.available(rt)
    if not ok then return nil,language,why end
    if not texts.is_language(language)then return nil,'UNSUPPORTED_LANGUAGE','not one of the game\'s languages: '..language end
    return language
end
-- Whether the game's texts can be read now: true and the language code, or false, code and reason.
function M.available()
    local rt,code,reason=runtime()
    if not rt then return false,code,reason end
    return texts.available(rt)
end
-- The game's text of a text id (a u32, or 8 hex digits with or without 0x), in the current language: text and the
-- language code, or nil, code and reason. opts: a language code (LANGUAGE_NOT_LOADED unless it is the current one), or
-- {language = code, plain = true (strip the <c=...>...</c> colour markup)}.
function M.game(id,opts)
    local value=text_id(id)
    if not value then error('hd2.text.game takes a text id: a u32 or 8 hex digits',2)end
    if type(opts)=='string'then opts={language=opts}end
    if opts~=nil and type(opts)~='table'then error('hd2.text.game options must be a language code or a table',2)end
    local rt,code,reason=runtime()
    if not rt then return nil,code,reason end
    return texts.game_text(rt,value,opts and{language=opts.language,plain=opts.plain==true})
end

local function trim(s)return(s:gsub('^%s+',''):gsub('%s+$',''))end
-- The display name of a generated nameText record: '<prefix> <name>' in the game's language. The prefix is the
-- designation text ('AR-23'); when a language's prefix text is empty, or the record has none (StratagemInfo has no
-- designation), the en-US designation (a model number) stands in. The name is the cased text, else the upper-case
-- one. Returns the name and {prefix, name, name_upper, description (markup stripped), language}, or nil, code, reason.
function M.display(record)
    if type(record)~='table'or type(record.name)~='number'then return nil,'NO_NAME','the object has no game name'end
    local rt,rcode,rreason=runtime()
    if not rt then return nil,rcode,rreason end
    local name,language,reason=texts.game_text(rt,record.name)
    if not name and language=='NO_TEXT'and record.nameUpper and record.nameUpper~=record.name then
        name,language,reason=texts.game_text(rt,record.nameUpper)
    end
    if not name then return nil,language,reason end
    name=trim(name)
    if name==''then return nil,'NO_TEXT','the name text is blank'end
    local prefix
    if record.prefix then
        local text,code,why=texts.game_text(rt,record.prefix)
        if text then prefix=trim(text)elseif code~='NO_TEXT'then return nil,code,why end
    end
    if(prefix==nil or prefix=='')and type(record.designation)=='string'then prefix=record.designation end
    local display=name
    if prefix and prefix~=''and name:sub(1,#prefix+1)~=prefix..' 'then display=prefix..' '..name end
    local upper=record.nameUpper and texts.game_text(rt,record.nameUpper)
    local description=record.description and texts.game_text(rt,record.description,{plain=true})
    return display,{prefix=prefix~=''and prefix or nil,name=name,name_upper=upper and trim(upper)or nil,
        description=description,language=language}
end
-- The game's display name of a reviewed object by kind ('weapon', 'support_weapon', 'throwable', 'backpack',
-- 'vehicle', 'booster', 'stratagem') and its key (the name hd2.<kind>(key) takes): as M.display. The key stays the
-- object's identity; show it when this returns nil.
function M.name(kind,key)
    local entries=M.KINDS[kind]
    if not entries then
        error("hd2.text.name kind must be 'weapon', 'support_weapon', 'throwable', 'backpack', 'vehicle', 'booster' or "
            .."'stratagem'",2)
    end
    if type(key)~='string'then error('hd2.text.name takes the object\'s key (a string)',2)end
    local ok,list=pcall(entries)
    local entry=ok and type(list)=='table'and list[key]
    if not entry then return nil,'UNKNOWN_OBJECT','no reviewed '..kind..' '..key end
    if not entry.nameText then return nil,'NO_NAME',key..' has no game name (no name record)'end
    return M.display(entry.nameText)
end
return M
