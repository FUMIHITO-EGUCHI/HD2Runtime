-- Cooperative ownership of spawn systems. No foreign settings or game data are changed.
local M={}
M.NAME='Pick your bots/bugs/squids'
M.CODE='SPAWN_SYSTEM_OWNED'
M.REASON='Pick your bots/bugs/squids is loaded. Its spawn controls own this area; HD2Runtime leaves these changes pending.'
local function foreign()
    local state=rawget(_G,'PickYourBots')or rawget(_G,'AllAutomatonReplace')
    return type(state)=='table'and state or nil
end
function M.status()
    local state=foreign()
    return {blocked=state~=nil,owner=state and M.NAME or nil,code=state and M.CODE or nil,
        reason=state and M.REASON or nil,foreign_status=state and rawget(state,'status')or nil}
end
-- Logical ownership includes source definitions from which the foreign mod
-- makes private mission copies. Health, size, damage, timers and demolition stay independent.
function M.overlaps(target,field)
    target=target or{};field=field or''
    if target.resource=='enemy_director'then
        return target.path=='roster'or target.path=='composition'or target.path=='difficulty'
    end
    if target.resource=='enemy'then
        return field:match('^hive%.')~=nil or field:match('^spawner%.')~=nil
    end
    return false
end
function M.reason(target,field)
    if foreign()and M.overlaps(target,field)then return M.REASON,M.CODE end
end
function M.require(target,field)
    local reason,code=M.reason(target,field)
    assert(not reason,(code or'')..': '..(reason or''))
end
function M.scope(target,field)return M.overlaps(target,field)and'enemy_spawns'or nil end
function M.plan_reason(changes)
    if not foreign()then return nil end
    for _,change in ipairs(changes or{})do
        if change.compatibility_scope=='enemy_spawns'then return M.REASON,M.CODE end
    end
end

-- Test7 keeps its panel as an upvalue of the chained update callback. Discover
-- only that callback chain, on a user click. Never scan globals or patch native input.
local function upvalue(fn,wanted)
    if not(debug and debug.getupvalue)or type(fn)~='function'then return end
    for i=1,64 do
        local name,value=debug.getupvalue(fn,i)
        if not name then break end
        if name==wanted then return value end
    end
end
local CALLBACK_KEYS={'previous','previous_update','prev_update','old_update','original_update',
    'game_update','saved_update','update','original','prev','old','fn','callback'}
local function panel()
    if not(debug and debug.getupvalue)then return end
    local stack={rawget(_G,'update')};local seen={};local visited=0
    local function enqueue(fn)
        if type(fn)=='function'and not seen[fn]and#stack<2048 then stack[#stack+1]=fn end
    end
    while #stack>0 and visited<1024 do
        local fn=table.remove(stack)
        if type(fn)=='function'and not seen[fn]then
            seen[fn]=true;visited=visited+1
            local preferred={}
            for i=1,128 do
                local name,value=debug.getupvalue(fn,i)
                if not name then break end
                if name=='settings_panel'and type(value)=='table'
                    and type(rawget(value,'pump'))=='function'and type(rawget(value,'sync'))=='function'
                    and type(rawget(value,'open'))=='boolean'then return value end
                if type(value)=='function'then
                    if name:find('update')or name:find('prev')or name:find('original')or name=='fn'then
                        preferred[#preferred+1]=value
                    else enqueue(value)end
                elseif type(value)=='table'and value~=_G and value~=package.loaded then
                    -- Some observers retain callbacks in a private table. Inspect only
                    -- named callback slots, never iterate mod caches or the shared heap.
                    for _,key in ipairs(CALLBACK_KEYS)do
                        local next_fn=rawget(value,key)
                        if type(next_fn)=='function'then preferred[#preferred+1]=next_fn end
                    end
                end
            end
            for _,next_fn in ipairs(preferred)do enqueue(next_fn)end
        end
    end
end
local function open_gui(before_open)
    local state=foreign()
    if not state then return false,'Pick your bots/bugs/squids is not loaded.'end
    -- Prefer an explicit bridge if a future version exposes one.
    local open=rawget(state,'open_settings')
    if type(open)=='function'then
        if before_open then before_open()end
        local ok,result,why=pcall(open)
        return ok and result~=false,not ok and tostring(result)or why
    end
    local p=panel()
    if not p then return false,'The spawn picker GUI is unavailable. Use its mod binding or F9 fallback.'end
    if p.open then if before_open then before_open()end;return true end
    local binding
    local queue={p.pump};local seen={};local at=1
    while at<=#queue and at<=32 and not binding do
        local fn=queue[at];at=at+1
        if not seen[fn]then
            seen[fn]=true;binding=upvalue(fn,'binding')
            for _,key in ipairs({'pump','fn','original','callback'})do
                local next_fn=upvalue(fn,key)
                if type(next_fn)=='function'then queue[#queue+1]=next_fn end
            end
        end
    end
    if type(binding)~='table'or type(binding.poll)~='function'or type(binding.pressed)~='function'then
        return false,'The spawn picker GUI bridge does not recognize this version.'
    end
    -- One normal opening pass through the mod's own focus, resource and input
    -- handling. Restore the panel-local binding methods immediately, even on error.
    if before_open then before_open()end
    local poll,pressed,registered=binding.poll,binding.pressed,binding.registered
    binding.poll=function()end;binding.pressed=function()return true end;binding.registered=true
    local ok,why=pcall(p.pump)
    binding.poll,binding.pressed,binding.registered=poll,pressed,registered
    if not ok or not p.open then return false,tostring(why or p.fault or'The spawn picker could not open. Focus the game and retry.')end
    return true
end
function M.open_gui(before_open)
    local ok,opened,reason=pcall(open_gui,before_open)
    if not ok then reason=tostring(opened);opened=false end
    local message=opened and'opened'or('failed: '..tostring(reason))
    require('hd2runtime/runtime/log').emit('[HD2Runtime] spawn picker GUI request '..message)
    return opened,reason
end
return M
