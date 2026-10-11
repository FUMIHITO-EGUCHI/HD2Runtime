-- DamageInfo status slot packing, shared by every write domain that edits status slots (domains/player_weapon_writes,
-- domains/throwable_writes). A row has four slots at +44+8n ({StatusEffectType u32, strength f32}); used slots are
-- packed from slot 1 (no live row has a gap), and a write must never leave one.
--
-- A slot write is judged on the row as the whole write set leaves it: the live bytes, overlaid with every status
-- type this write set sets (one transaction, or every operation of one plan phase: domains/composition_plans.lua).
-- So one plan can fill slot 1 and slot 2 of an empty row together, and slot k of a row whose earlier slots an earlier
-- operation filled is accepted. Setting a status or changing a strength in slot k needs slots 1 to k-1 to hold a
-- status; a slot is cleared ('none') only when every later slot is empty afterwards (clearing never needs the earlier
-- slots: an empty slot k cannot open a gap). A strength write that leaves its bytes as they are (a no-op at the
-- reviewed value) changes nothing and is not judged. Each slot's own bytes are still checked against its exact
-- reviewed value by core/ownership.lua; this only decides whether the result stays packed.
local b=require('hd2runtime/core/bytes')
local M={}
M.SLOTS=4

function M.new()return {rows={},checks={}}end

-- One slot change. row_key names the DamageInfo row (owner base and record offset), bytes are its live bytes,
-- status_type the desired StatusEffectType of a type write (nil for a strength write), label the field, unchanged
-- true when the write leaves the slot's bytes as they are.
function M.note(packing,row_key,bytes,slot,status_type,label,unchanged)
    assert(type(slot)=='number'and slot>=1 and slot<=M.SLOTS and slot%1==0,'status slot outside the row')
    local row=packing.rows[row_key]
    if not row then row={bytes=bytes,planned={}};packing.rows[row_key]=row end
    if status_type==nil and unchanged then return end
    if status_type~=nil then row.planned[slot]=status_type end
    packing.checks[#packing.checks+1]={row=row,slot=slot,clear=status_type==0,label=tostring(label)}
end

local function used(row,slot)
    local planned=row.planned[slot]
    if planned~=nil then return planned~=0 end
    return b.u32(row.bytes,44+(slot-1)*8)~=0
end

-- Refuses the whole write set when any noted change would leave a gap in its row.
function M.verify(packing)
    for _,check in ipairs(packing.checks)do
        for index=1,check.clear and 0 or check.slot-1 do
            assert(used(check.row,index),'STATUS_SLOT_GAP: status slot '..index..' is empty: '..check.label
                ..' (slot '..check.slot..') can be set only when slots 1 to '..(check.slot-1)..' hold a status, '
                ..'live or set by this write (the slots are packed from slot 1)')
        end
        if check.clear then
            for index=check.slot+1,M.SLOTS do
                assert(not used(check.row,index),'STATUS_SLOT_GAP: '..check.label..' clears slot '..check.slot
                    ..' while slot '..index..' still holds a status (clear the later slots too, or only the last '
                    ..'used slot, so the slots stay packed)')
            end
        end
    end
end
return M
