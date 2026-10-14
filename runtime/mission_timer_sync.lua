-- The host's mission timer freeze, shared with the lobby's other Runtimes (EXPERIMENTAL; the user's request of
-- 2026-10-14: "let the host control it, sync the freeze over our network"). The host publishes its freeze under the
-- Runtime's own lobby member-data key hd2mt (runtime/peer_channel.lua): "hd2mt/1;<0|1>;<seq>". Every other Runtime in
-- a mission reads the host's value and sets its own countdown's pause the same way (runtime/mission_timer_freeze.lua,
-- follow). The host publishes 0 whenever it is not in a frozen mission, so a freeze never carries into the next one; a
-- missing or unreadable value is no freeze. A member without a Runtime follows whatever the game itself replicates.
local channel=require('hd2runtime/runtime/peer_channel')
local world_module=require('hd2runtime/runtime/event_world')
local scheduler=require('hd2runtime/runtime/scheduler')
local log_module=require('hd2runtime/runtime/log')
local M={}
M.KEY='hd2mt'
M.BY='mission timer sync'
M.POLL_EVERY=2
local S
local function st()
    S=S or{frozen=false,seq=0,published=nil,acc=0,mission=nil,applied=nil,said={},watch=nil}
    return S
end
local function log(text)pcall(log_module.emit,'[HD2Runtime] mission timer sync: '..text)end
local function say(key,text)
    local s=st()
    if s.said[key]~=text then s.said[key]=text;log(text)end
end

function M.value(frozen,seq)return ('hd2mt/1;%d;%d'):format(frozen and 1 or 0,seq)end
-- "hd2mt/1;1;7" -> true, 7; anything else -> nil.
function M.parse(value)
    if type(value)~='string'then return nil end
    local f,seq=value:match('^hd2mt/1;([01]);(%d+)$')
    if not f or#seq>9 then return nil end
    return f=='1',tonumber(seq)
end

local function publish()
    local s=st()
    local value=M.value(s.frozen,s.seq)
    if s.published==value then return end
    s.published=value
    local result=channel.publish(value,M.BY,M.KEY)
    if result and(result.status=='refused'or result.status=='failed')then
        say('post',('post %s %s (%s: %s)'):format(value,result.status,tostring(result.code),tostring(result.reason)))
    end
end
-- The host froze or resumed its timer (runtime/mission_timer_freeze.lua set).
function M.host_set(frozen)
    local s=st()
    if s.frozen==frozen and s.published then return end
    s.frozen=frozen;s.seq=s.seq+1
    publish()
end

local function step()
    local s=st()
    local world=world_module.open()
    if not world then return end
    local game=world_module.game_state(world)
    local in_mission=game and game.mission
    -- The host: 0 once it is not in a mission any more (or no longer the host).
    if s.frozen and not(in_mission and game.host==true)then s.frozen=false;s.seq=s.seq+1 end
    if s.published then publish()end
    -- A client in a mission: the host's value.
    if not(in_mission and game.host==false)then s.mission,s.applied=nil,nil;return end
    if s.mission~=game.mode_entity then s.mission,s.applied=game.mode_entity,nil end
    local lobby=channel.lobby(world)
    if not lobby or#lobby.members<2 or not lobby.host_peer then return end
    local p=channel.poll(world,{key=M.KEY})
    if not p then return end
    local value
    for _,entry in ipairs(p.values)do if entry.peer==lobby.host_peer then value=entry.value end end
    local frozen=M.parse(value)or false
    if s.applied==frozen then return end
    if s.applied==nil and not frozen then s.applied=false;return end   -- (a new mission starts unpaused)
    local freeze=require('hd2runtime/runtime/mission_timer_freeze')
    local result,code,why=freeze.follow(frozen)
    if result then
        s.applied=frozen
        say('follow',('the host %s the mission timer: this machine %s at %s'):format(frozen and'froze'or'resumed',
            result.status=='APPLIED'and(frozen and'froze too'or'resumed too')or'already matched',
            freeze.clock(result.remainingSeconds)))
    else
        say('follow',('the host %s the mission timer; this machine cannot follow (%s: %s); retried'):format(
            frozen and'froze'or'resumed',tostring(code),tostring(why)))
    end
end
M.step_for_tests=step

-- Attaches the watch (once). Started at load in the game (api/hd2.lua); every POLL_EVERY s it publishes the host's
-- state when it changed and, in a mission as a client, reads the host's.
function M.start()
    local s=st()
    if s.watch and s.watch.status=='waiting'then return s.watch end
    local watch={status='waiting',perf_label='mission timer sync'}
    function watch.cancel()watch.status='cancelled'end
    function watch.tick(dt)
        dt=type(dt)=='number'and dt>=0 and dt<10 and dt or 0
        s.acc=s.acc+dt
        if s.acc>=M.POLL_EVERY then
            s.acc=0
            local ok,why=pcall(step)
            if not ok then say('step','step failed: '..tostring(why))end
        end
    end
    s.watch=watch
    scheduler.attach(watch)
    return watch
end
function M.status()
    local s=st()
    return {frozen=s.frozen,seq=s.seq,published=s.published,following=s.applied}
end
function M.reset_for_tests()S=nil end
return M
