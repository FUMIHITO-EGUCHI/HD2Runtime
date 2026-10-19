-- Pre-fire homing support, extracted from the user-tested AR-23 Homing Lab 0.4.1.
-- The generic Runtime integration is not yet live-tested.
-- Private engine query used by Guided Rounds, independently traced in the
-- current unpacked EXE image; see validation/homing-lock-port.json and the
-- retained complete code pins. Requires Runtime's proven world.
-- Query result starts at output+0; stride44, distance+24, unit+28.
-- Descriptor0 selects world2 and all-hit mode. Reference argument5 is preserved
-- as UINT_MAX; its full filter semantics are not assumed here.
local M={MAX_HITS=8,OUT_SIZE=16384,WORLDS=0x27BA870,DESCRIPTORS=0x27B9440}
local pins=require('hd2runtime/runtime/homing_los_pins')
local b=require('hd2runtime/core/bytes')
local cache,failed
local function finite(n)return type(n)=='number'and n==n and math.abs(n)<math.huge end
local function descriptor(world)
    return world.view.proves(world.exe+M.DESCRIPTORS,'0200000002000000050000000c8fc36a01000080')
end
local function physics(world)
    -- Only the one live physics world that descriptor0 explicitly selects.
    local selected
    for i=0,3 do
        local data=world.view.read(world.exe+M.WORLDS+i*0xB0+0x20,8)
        if not data then return nil,'physics_world_unreadable'end
        local lo,hi=b.u32(data,0),b.u32(data,4)
        local p=lo+hi*4294967296
        if i==2 then
            if p<65536 or p>=140737488355328 then return nil,'physics_world_missing'end
            selected=p
        elseif p~=0 then return nil,'physics_world_ambiguous'end
    end
    local vt=world.view.pointer(selected+0x20)
    local method=vt and world.view.pointer(vt+0x148)
    if not method then return nil,'physics_query_method_unavailable'end
    return selected
end
local function bind(world)
    for _,pin in ipairs(pins)do
        if not world.view.proves(world.exe+pin.rva,pin.hex)then return nil,'raycast_code_changed'end
    end
    if not descriptor(world)then return nil,'raycast_descriptor_changed'end
    local ffi=require('ffi')
    return{key=world.key,ffi=ffi,fn=ffi.cast(
        'uint32_t (*)(uint32_t, const float *, const float *, float, uint32_t, void *, uint32_t)',world.exe+0x77DEC0),
        origin=ffi.new('float[3]'),direction=ffi.new('float[3]'),out=ffi.new('uint8_t[?]',M.OUT_SIZE+64)}
end
-- Kept pure and exposed for binary-layout regression checks, without invoking
-- the engine. A saturated count is conservatively unknown, never no-hit/clear.
function M.decode(bytes,count,distance)
    if not finite(count)or count<0 or count%1~=0 or count>=M.MAX_HITS then return nil,'raycast_saturated'end
    if type(bytes)~='string'or#bytes<count*44 then return nil,'raycast_output_incomplete'end
    local hits={}
    for i=0,count-1 do
        local at=i*44;local ok,d=pcall(b.value,bytes,at+24,'f32');local unit=b.u32(bytes,at+28)
        if not ok or not finite(d)or d<0 or d>distance+.01 then return nil,'raycast_output_invalid'end
        hits[#hits+1]={distance=math.min(d,distance),unit=unit,
            flags=b.u32(bytes,at+32),material=b.u32(bytes,at+36)}
    end
    return hits
end
function M.read(world,q)
    if failed then return nil,failed end
    if type(q)~='table'or not finite(q.distance)or q.distance<1 or q.distance>400 then return nil,'invalid_native_query'end
    local length=0
    for _,k in ipairs({'x','y','z'})do
        if type(q.origin)~='table'or type(q.direction)~='table'or not finite(q.origin[k])
            or math.abs(q.origin[k])>100000 or not finite(q.direction[k])or math.abs(q.direction[k])>1.01 then
            return nil,'invalid_native_query'
        end
        length=length+q.direction[k]^2
    end
    if length<.99 or length>1.01 then return nil,'invalid_native_query'end
    if type(world)~='table'or not world.exe or not world.view or world.key~=q.world_key then return nil,'world_unavailable'end
    local W=require('hd2runtime/runtime/event_world')
    local game=W.game_state(world);local players=W.players(world,true)
    if not game or game.mission~=true or game.host~=true or not players or#players~=1 then return nil,'solo_mission_required'end
    if not cache or cache.key~=world.key then
        local value,why=bind(world);if not value then return nil,why end;cache=value
    end
    if not descriptor(world)then return nil,'raycast_descriptor_changed'end
    local pw,why=physics(world);if not pw then return nil,why end
    local c=cache;local F=c.ffi
    for i,k in ipairs({'x','y','z'})do c.origin[i-1]=q.origin[k];c.direction[i-1]=q.direction[k]end
    F.fill(c.out,M.OUT_SIZE+64,0)
    F.fill(c.out+M.OUT_SIZE,64,0xA5)
    local n=tonumber(c.fn(0,c.origin,c.direction,q.distance,4294967295,c.out,M.MAX_HITS))
    for i=M.OUT_SIZE,M.OUT_SIZE+63 do if c.out[i]~=0xA5 then cache=nil;failed='raycast_buffer_guard';return nil,failed end end
    local hits,why=M.decode(F.string(c.out,M.MAX_HITS*44),n,q.distance)
    if not hits then return nil,why end
    return{abi_verified=true,world_verified=true,world_key=world.key,complete=true,overflow=false,hits=hits,
        query='reference_descriptor_0',physics_world=2,hit_observed=n>0}
end
return M
