-- The game's own keybind page for hd2.input bindings, through Mod Bindings Menu (CowboyBingus; the global
-- ModBindingsMenu, api 1). A binding declared with native = {label, category} is also registered there: it appears
-- on the game's Controls page under the MODS tab, where the player can bind any key, mouse button or controller
-- input to it. That input presses the binding exactly as its own key does (runtime/input.lua); the key keeps working.
-- Optional: without the addon, or when it refuses a registration (logged once), nothing changes. Mod Bindings Menu
-- assigns no default input: the player chooses one on that page. Only its published API is used
-- (register_binding, is_down): no offsets of its own.
-- One input, not two (the user's request of 2026-10-14): the first time the input bound there presses a binding, it
-- takes over: from then on, while Mod Bindings Menu answers, the binding's own key is ignored. Kept between sessions in
-- the Runtime's own store; without Mod Bindings Menu the key works again.
local log=require('hd2runtime/runtime/log')
local i18n=require('hd2runtime/runtime/i18n')
local M={}
local declared,order={}, {}   -- id -> {binding, label, category, registered, said, tried}
M.STORE_KEY='input.native_keys'
M.hooks={}
function M.hooks.store()
    if type(rawget(_G,'stingray'))~='table'then return nil end
    return require('hd2runtime/runtime/mod_store').open('hd2runtime')
end
local owned_cache
local function owned_map()
    if owned_cache then return owned_cache end
    local ok,s=pcall(M.hooks.store)
    local ok2,map=false,nil
    if ok and s then ok2,map=pcall(s.get,s,M.STORE_KEY)end
    owned_cache=ok2 and type(map)=='table'and map or{}
    return owned_cache
end
-- Whether the input bound on the game's keybind page has taken this binding over.
function M.owned(id)return owned_map()[id]==true end
-- How many keyboard / mouse inputs the game's keybind page holds for the binding's native action now: a count, or nil
-- when unknown. Known, it decides alone: one or more and the binding's own key is ignored, none (emptied there, or only
-- a controller input) and the key works again. Unknown, the first use takes over (M.owned).
-- The action: Mod Bindings Menu's own assignments file (id, group, action per line; re-read when its revision
-- changes). The count: the game's live binding table, read only (runtime/input_bindings.lua).
M.ASSIGNMENTS_FILE='\\CowboyBingus\\Helldivers2\\Logs\\ModBindingsMenu.assignments'
local assignments              -- {revision, actions = {[id] = {group, action}}}
function M.hooks.assignments_text()
    local base=os.getenv('LOCALAPPDATA')
    local handle=base and io.open(base..M.ASSIGNMENTS_FILE,'rb')
    if not handle then return nil end
    local text=handle:read('*a');handle:close()
    return text
end
local function action_of(id,revision)
    if not assignments or assignments.revision~=revision then
        local actions={}
        local ok,text=pcall(M.hooks.assignments_text)
        for line in tostring(ok and text or''):gmatch('[^\r\n]+')do
            local name,group,action=line:match('^([^\t]+)\t(%d+)\t(%d+)')
            if name then actions[name]={group=tonumber(group),action=tonumber(action)}end
        end
        assignments={revision=revision,actions=actions}
    end
    return assignments.actions[id]
end
M.action_of=action_of
function M.hooks.bound_count(id,revision)
    local a=action_of(id,revision)
    if not a then return nil end
    local count=require('hd2runtime/runtime/input_bindings').count(a.group,a.action)
    return count and count.keyboard_mouse or nil
end
M.COUNT_EVERY=20               -- update ticks between two reads of a binding's count

local function api()
    local a=rawget(_G,'ModBindingsMenu')
    if type(a)=='table'and a.api==1 and type(a.register_binding)=='function'and type(a.is_down)=='function'then
        return a
    end
end
local function say(entry,text)
    if entry.said~=text then entry.said=text;pcall(log.emit,'[HD2Runtime] '..text)end
end
-- The label in the current language: a mod's function, else the Runtime's own translation of the text (a text it
-- has none of is shown as given). Mod Bindings Menu 3 asks again whenever a binding page opens; older versions take
-- the text once.
local function text_of(label)
    if type(label)=='function'then
        local ok,text=pcall(label)
        return ok and type(text)=='string'and text~=''and text:sub(1,127)or nil
    end
    return i18n.t(label)
end
local function label_for(a,entry)
    if(tonumber(a.version)or 1)>=3 then
        local label=entry.label
        local first=text_of(label)or entry.id
        return function()return text_of(label)or first end
    end
    return text_of(entry.label)or entry.id
end

-- native: {label = text (1-127 bytes) or a function returning it, category = text (1-64 bytes)}; validated by
-- runtime/input.lua.
function M.declare(binding,native)
    local entry=declared[binding.id]
    if not entry then
        entry={id=binding.id};declared[binding.id]=entry;order[#order+1]=binding.id
    end
    entry.binding,entry.label,entry.category=binding,native.label,native.category
    entry.registered,entry.tried=false,nil
end
function M.forget(id)
    if not declared[id]then return end
    declared[id]=nil
    for i,x in ipairs(order)do if x==id then table.remove(order,i)break end end
end

-- Once per update tick (runtime/input.lua's poll): registers what is not registered yet (again only after the
-- addon's revision changed: a refusal is not retried every tick), then reads each registered binding's native state
-- into binding.native_down (true / false; nil when unknown).
function M.step()
    local a=api()
    if not a then
        for _,id in ipairs(order)do
            local b=declared[id].binding
            b.native_down,b.native_owned,b.native_bound=nil,nil,nil
        end
        return
    end
    local revision=a.revision
    for _,id in ipairs(order)do
        local entry=declared[id]
        if not entry.registered and entry.tried~=(revision or true)then
            entry.tried=revision or true
            local ok,result,why=pcall(a.register_binding,id,label_for(a,entry),nil,{category=entry.category})
            if ok and result==true then
                entry.registered=true
                say(entry,('input binding %s: also on the game\'s keybind page (Mod Bindings Menu, MODS tab: "%s" under '
                    ..'%s); bind any input to it there, its own key keeps working'):format(id,tostring(text_of(entry.label)),
                    entry.category))
            else
                say(entry,('input binding %s: not on the game\'s keybind page: Mod Bindings Menu refused it (%s); its own '
                    ..'key works as before'):format(id,tostring(ok and(why or result)or result)))
            end
        end
        if entry.registered then
            local ok,down=pcall(a.is_down,id)
            entry.binding.native_down=ok and down==true or false
            if entry.binding.native_down and not M.owned(id)then
                local map=owned_map()
                map[id]=true
                local oks,s=pcall(M.hooks.store)
                if oks and s then pcall(s.set,s,M.STORE_KEY,map)end
                say(entry,('input binding %s: its input on the game\'s keybind page took over: its own key %s is ignored '
                    ..'from now on (it works again without Mod Bindings Menu; change the input on that page)'):format(id,
                    tostring(entry.binding.key)))
            end
            entry.binding.native_owned=M.owned(id)
            local bound=entry.bound
            entry.count_in=(entry.count_in or 0)-1
            if entry.count_in<=0 then
                entry.count_in=M.COUNT_EVERY
                local okc,count=pcall(M.hooks.bound_count,id,revision)
                count=okc and type(count)=='number'and count or nil
                bound=nil
                if count then bound=count>0 end
            end
            if bound~=entry.bound then
                entry.bound=bound
                if bound==true then
                    say(entry,('input binding %s: its input on the game\'s keybind page controls it; its own key %s is '
                        ..'ignored while that input is set'):format(id,tostring(entry.binding.key)))
                elseif bound==false then
                    say(entry,('input binding %s: no input on the game\'s keybind page: its own key %s works'):format(id,
                        tostring(entry.binding.key)))
                end
            end
            entry.binding.native_bound=bound
        else
            entry.binding.native_down,entry.binding.native_owned,entry.binding.native_bound=nil,nil,nil
        end
    end
end
function M.describe(id)
    local entry=declared[id]
    return entry and{label=text_of(entry.label),category=entry.category,registered=entry.registered==true,
        owned=M.owned(id),bound=entry.bound}or nil
end
function M.reset_for_tests()declared,order,owned_cache,assignments={}, {},nil,nil end
return M
