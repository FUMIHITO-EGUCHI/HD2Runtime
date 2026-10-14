-- Explicit diagnostic only: no subscription, polling, writes or cached addresses.
local D=require('hd2runtime/domains/missions')
local N=require('hd2runtime/domains/mission_timer_diagnostics')
local S=require('hd2runtime/domains/event_natives').state
local b=require('hd2runtime/core/bytes')
local W=require('hd2runtime/runtime/event_world')
local M={}
-- One proven read of the mission timers. Returns the report and, for runtime/mission_timer_freeze.lua, the active
-- instance's addresses ({world, manager, slot, entity, id, source}; nil without an active countdown). extra_pins are
-- proven with the rest.
function M.locate(extra_pins)
    local world,why=W.open();assert(world,why)
    local v,base=world.view,world.game
    for _,list in ipairs({D.pins,N.pins,extra_pins or{}})do for _,p in ipairs(list)do
        assert(v.proves(base+p.rva,p.bytes),'mission diagnostic code changed: '..p.role)
    end end
    local function read(a,n)return assert(v.read(a,n),'mission diagnostic memory unavailable')end
    local function ptr(a)return assert(v.pointer(a),'mission diagnostic pointer unavailable')end
    local function u32(a)return assert(v.u32(a),'mission diagnostic integer unavailable')end
    local function f32(a)
        local x=b.value(read(a,4),0,'f32')
        assert(x==x and x>=0 and x<1e9,'invalid mission duration');return x
    end
    local state=assert(W.game_state(world),'game state unavailable')
    local game=ptr(base+S.game)
    local selection=ptr(game+N.selection)
    local mission_index=b.u16(read(selection+N.missionIndex,2),0)
    local selected
    if mission_index<#D.missions then
        local m=D.missions[mission_index+1]
        for _,g in ipairs(m.guards)do assert(v.proves(base+m.rva+g.offset,g.hex),'mission identity changed')end
        selected={id=m.id,name=m.name,faction=m.faction,timerGroup=m.source}
    end
    local table=ptr(ptr(base+N.definitions)+N.definitionIndex)
    assert(read(table-28,28)==b.unhex(D.layout.header),'mission definition table changed')
    local values,by_resource={},{}
    for source,s in pairs(D.sources)do if s.kind=='component'then
        local at=table+s.identity.indexRow*16
        assert(b.resource(read(at,8),0)==s.resource and u32(at+8)==s.identity.recordIndex,
            'mission definition ownership changed')
        local seconds=f32(table+D.layout.record_offset+s.identity.recordIndex*D.layout.stride+s.offset)
        values[source]={seconds=seconds,defaultSeconds=s.currentDefault}
        by_resource[s.resource]={source=source,seconds=seconds}
    end end
    local result={state=state.name,host=state.host,selected=selected,definitions=values,active=false}
    local manager=ptr(base+N.manager)
    local count=u32(manager+N.count)
    assert(count<=N.maxActive,'unexpected mission instance count')
    local handle
    if state.mission and count==1 then
        local entity=ptr(manager+N.entities)
        local id=u32(entity+8);local resource=b.resource(read(entity,8),0)
        assert(state.mode_entity==id,'mission descriptor and timer instance disagree')
        local def=assert(by_resource[resource],'unknown active mission definition')
        local effective,private=def.seconds,false
        local capacity=u32(manager+N.privateCount)
        assert(capacity<=N.maxPrivateIndex,'unexpected mission private index size')
        local index=capacity>0 and ptr(manager+N.privateIndex)
        for i=0,capacity-1 do
            local at=index+i*8
            if u32(at)==id then
                local row=u32(at+4)
                if row~=0xffffffff then
                    assert(row<N.maxActive,'unexpected private mission record')
                    effective=f32(manager+N.privateRecords+row*D.layout.stride+116);private=true
                end
                break
            end
        end
        -- (the instance's countdown slot: maxActive is 1, so it is slot 0)
        local slot=manager+N.remaining
        local flags=read(slot+N.expired,4)
        result.active={source=def.source,baseSeconds=def.seconds,effectiveSeconds=effective,
            remainingSeconds=f32(slot),privateDefinition=private,
            paused=flags:byte(N.pause-N.expired+1)~=0,expired=flags:byte(1)~=0}
        handle={world=world,manager=manager,slot=slot,entity=entity,id=id,source=def.source}
        assert(ptr(manager+N.entities)==entity and u32(entity+8)==id,'mission instance changed during diagnostic')
    end
    assert(u32(game+S.state)==state.state and u32(manager+N.count)==count
        and ptr(base+N.manager)==manager and ptr(game+N.selection)==selection
        and b.u16(read(selection+N.missionIndex,2),0)==mission_index,'mission changed during diagnostic')
    return result,handle
end
function M.read()
    local ok,value=pcall(M.locate)
    if ok then return value end
    return nil,tostring(value)
end
return M
