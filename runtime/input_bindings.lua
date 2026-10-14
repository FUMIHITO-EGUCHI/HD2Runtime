-- How many inputs the game's live binding table holds for one native action (group, action): read only, for the
-- keybind page bridge (runtime/mod_bindings_bridge.lua). The table is the one the game's own Controls page edits in
-- place (bind appends a mapping and raises the record's count, unbind removes it and lowers it; a count of 0 is
-- unbound) and the one its per-frame input update reads (research input-bindings-F5FEE03DCFDB.json, proven on game.dll
-- and nine snapshots). Every read re-checks the pins (once per proven world), the map header and the record; anything
-- unexpected is unknown (nil), never 0. Nothing is written.
local L=require('hd2runtime/domains/input_bindings')
local W=require('hd2runtime/runtime/event_world')
local b=require('hd2runtime/core/bytes')
local M={}
local proven                 -- {key, ok, why}: the pins, per proven world
local KBM,PAD={},{}
for _,d in ipairs(L.devices.keyboardMouse)do KBM[d]=true end
for _,d in ipairs(L.devices.pad)do PAD[d]=true end

local function prove(world)
    if proven and proven.key==world.key then return proven.ok,proven.why end
    local ok,why=true,nil
    for _,p in ipairs(L.pins)do
        if not world.view.proves(world.game+p.rva,p.bytes)then ok,why=false,'input binding code changed: '..p.role;break end
    end
    proven={key=world.key,ok=ok,why=why}
    return ok,why
end

-- {total, keyboard_mouse, pad} for the action, or nil and why.
function M.count(group,action)
    if type(group)~='number'or type(action)~='number'or group%1~=0 or action%1~=0 or group<0 or group>L.maxGroup
        or action<0 or action>=L.actionsPerGroup then
        return nil,'not a native action handle'
    end
    local world,why=W.open()
    if not world then return nil,why end
    local ok,reason=prove(world)
    if not ok then return nil,reason end
    local v=world.view
    local owner=v.pointer(world.game+L.ownerGlobal)
    if not owner then return nil,'no input owner'end
    local head=v.read(owner+L.liveMap,0x14)
    if not head then return nil,'the binding table is unreadable'end
    local records=b.pointer(head,0)
    if records~=owner+L.liveStore or b.u32(head,8)~=L.capacity or b.u32(head,12)~=L.empty
        or b.u32(head,16)~=L.multiplier then
        return nil,'the binding table is not the reviewed one'
    end
    local code=group*65536+action
    -- the game's own probe (find_mapping): slot (code * multiplier + i) mod capacity, every slot, exact code match
    for i=0,L.capacity-1 do
        local slot=(code*L.multiplier+i)%L.capacity
        local at=records+slot*L.record
        local rec=v.read(at,8)
        if not rec then return nil,'a binding record is unreadable'end
        if b.u32(rec,0)==code then
            local n=b.u32(rec,4)
            if n>L.maxMappings then return nil,'a binding record holds '..n..' mappings'end
            local out={total=n,keyboard_mouse=0,pad=0}
            if n==0 then return out end
            local maps=v.read(at+8,n*L.mapping)
            if not maps then return nil,'the bindings are unreadable'end
            for j=0,n-1 do
                local device=b.u32(maps,j*L.mapping)%16
                if KBM[device]then out.keyboard_mouse=out.keyboard_mouse+1
                elseif PAD[device]then out.pad=out.pad+1 end
            end
            return out
        end
    end
    return nil,'the action has no binding record'
end
function M.reset_for_tests()proven=nil end
return M
