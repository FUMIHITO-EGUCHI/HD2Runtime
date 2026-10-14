-- Freezes or resumes the mission countdown on request: the game's own timer pause (the countdown slot's pause byte;
-- Evacuate High-Value Assets missions spawn with it set until the evacuation starts). While it is set the game's
-- update skips the countdown, its 0..2500 s clamp, its publish and its zero transition; mission creation clears it, so
-- the next mission starts normally. EXPERIMENTAL. The host controls it; with other players in the lobby the freeze is
-- published to their Runtimes, which set their own countdown's pause to match (runtime/mission_timer_sync.lua,
-- M.follow here). No polling, callback or kept address: every request locates and guards again (research
-- mission-countdown-static-rc15, docs/missions.md).
local N=require('hd2runtime/domains/mission_timer_diagnostics')
local diagnostics=require('hd2runtime/runtime/mission_timer_diagnostics')
local transaction=require('hd2runtime/core/guarded_transaction')
local log=require('hd2runtime/runtime/log').emit
local M={}
-- Its own timer source's state machine clears the pause when the evacuation starts: a freeze would not hold.
M.RELEASED_BY_THE_MISSION={['delta/857c2cd17f827849']='Evacuate High-Value Assets timers are paused and released by '
    ..'the mission itself'}

local function owner_of(world,address,size,writable)
    local r=world.runtime.query and world.runtime.query(address)
    if not(r and r.state==0x1000 and address>=r.base and address+size<=r.base+r.size)then return nil end
    if writable and not(r.type==0x20000 and r.protect==4)then return nil end
    return {base=r.allocation_base,size=r.base+r.size-r.allocation_base,type=r.type,protect=r.protect}
end
local function clock(seconds)
    seconds=math.max(0,math.floor(seconds))
    return ('%d:%02d'):format(math.floor(seconds/60),seconds%60)
end
M.clock=clock

-- The guarded write of this machine's own pause byte. role: 'host' (the player's request) or 'client' (following the
-- host's published freeze). {status = 'APPLIED' | 'UNCHANGED', frozen, remainingSeconds, source, verified} or nil,
-- code, reason.
local function apply(frozen,role)
    local ok,report,h=pcall(diagnostics.locate,N.freezePins)
    if not ok then return nil,'TARGET_UNAVAILABLE',tostring(report)end
    if not h then return nil,'TARGET_UNAVAILABLE','no active mission countdown (state '..tostring(report.state)..')'end
    if role=='host'and report.host~=true then
        return nil,'HOST_ONLY','the host controls the mission timer'
    elseif role=='client'and report.host~=false then
        return nil,'NOT_APPLICABLE','this machine is the host: it does not follow a published freeze'
    end
    local world=h.world
    local released=M.RELEASED_BY_THE_MISSION[h.source]
    if released then return nil,'NOT_APPLICABLE',released end
    local a=report.active
    if frozen and a.expired then return nil,'NOT_APPLICABLE','the mission timer has already run out'end
    -- (the slot's flag bytes only: its countdown float changes every frame)
    local flags_at=h.slot+N.expired
    local flags=world.view.read(flags_at,4)
    local pause=flags and flags:byte(N.pause-N.expired+1)
    if pause~=0 and pause~=1 then return nil,'GUARD_REJECTED','the pause byte holds '..tostring(pause)..', not 0 or 1'end
    local want=frozen and 1 or 0
    local result={frozen=frozen,remainingSeconds=a.remainingSeconds,source=h.source}
    if pause==want then result.status='UNCHANGED';return result end
    local owner=owner_of(world,flags_at,4,true)
    if not owner then return nil,'NOT_PRIVATE','the countdown slot is not in private read-write memory'end
    -- the identity chain: the manager global, the active count, the instance and its entity id, the slot's flags
    local snapshots={{owner=owner,offset=flags_at-owner.base,bytes=flags}}
    local function context(address,size)
        local o=owner_of(world,address,size,false)
        local bytes=o and world.view.read(address,size)
        if not bytes then return false end
        snapshots[#snapshots+1]={owner=o,offset=address-o.base,bytes=bytes}
        return true
    end
    if not(context(world.game+N.manager,8)and context(h.manager+N.count,4)and context(h.manager+N.entities,8)
            and context(h.entity+8,4))then
        return nil,'UNAVAILABLE','the mission instance chain is not readable memory'
    end
    local plan={snapshots=snapshots,changes={{label='mission.timer_paused',owner=owner,
        offset=h.slot+N.pause-owner.base,expected=string.char(pause),desired=string.char(want),
        before=string.char(pause),already_desired=false,
        identity={component='HiveMindMissionTimer',component_type='native',record_type='mission countdown slot',
            unique_owner=true,owner_count=1},chain={}}}}
    local applied=transaction.apply(world.runtime,plan)
    if applied.status~='APPLIED'then return nil,'GUARD_REJECTED',tostring(applied.reason)end
    local after=world.view.read(flags_at,4)
    result.status='APPLIED'
    result.verified=after~=nil and after:byte(N.pause-N.expired+1)==want
    log(('mission timer %s at %s remaining (%s, %s): the game\'s own timer pause, 1 write; read back %s; the next '
        ..'mission starts unpaused'):format(frozen and'FROZEN'or'RESUMED',clock(a.remainingSeconds),h.source,
        role=='host'and'the host'or'following the host',tostring(result.verified)))
    return result
end

-- set({frozen = true|false, allow_unverified_effect = true}): the host only; the other Runtimes in the lobby follow.
function M.set(request)
    assert(type(request)=='table','mission timer freeze request required')
    for k in pairs(request)do
        assert(k=='frozen'or k=='allow_unverified_effect','unsupported mission timer freeze option: '..tostring(k))
    end
    assert(type(request.frozen)=='boolean','frozen must be true or false')
    if request.allow_unverified_effect~=true then
        return nil,'ACKNOWLEDGEMENT_REQUIRED','freezing the mission timer is not gameplay-tested: it requires '
            ..'allow_unverified_effect=true'
    end
    local result,code,why=apply(request.frozen,'host')
    -- (published to the lobby, also when unchanged here, so every Runtime agrees)
    if result then pcall(function()require('hd2runtime/runtime/mission_timer_sync').host_set(result.frozen)end)end
    return result,code,why
end
-- A client following the host's published freeze (runtime/mission_timer_sync.lua).
function M.follow(frozen)
    assert(type(frozen)=='boolean','frozen must be true or false')
    return apply(frozen,'client')
end
return M
