"""The custom stratagems' cost per update (0.31.2; a player's report: "a pulse, a quick stutter whenever it performs it";
the F10 Performance tab showed the custom stratagems at 53.8 ms in one update, about every 5 s):
  * aboard the ship every carrier revalidation (M.REVALIDATE_EVERY, 5 s: the ship allocation and the panel's group
    view) ran one carrier discovery per registered custom stratagem, each reading every catalogued stratagem again (about
    1,700 reads each live, one ReadProcessMemory per read). A discovery is now shared by the definitions that ask the
    same (runtime/carrier_allocator.lua), the stratagem facts it reads are read once per update
    (runtime/stratagem_slot_conversion.lua carrier_facts) and a type scan that found nothing once per update
    (runtime/stratagem_loadout.lua type_of);
  * measured in work units (reads of game memory), not wall time: the worst update over a simulated minute aboard the
    ship does not grow with the number of registered custom stratagems, and stays within a fixed budget (before: 93,275
    reads with the three examples, 465,467 with fifteen custom stratagems; after: 590 for both). A generous
    wall-time ceiling only catches a gross regression;
  * the results are the same: an allocation of twenty definitions sharing its discoveries equals the one that runs a
    discovery per definition with no facts kept, verdict for verdict; a Runtime write in the update drops the facts."""
import unittest

import test_custom_stratagem_flow as flow

COMMON = r"""
local ffi=require('ffi')
pcall(ffi.cdef,'int QueryPerformanceCounter(int64_t*);int QueryPerformanceFrequency(int64_t*);')
local qv=ffi.new('int64_t[1]');ffi.C.QueryPerformanceFrequency(qv);local QF=tonumber(qv[0])
local function now()ffi.C.QueryPerformanceCounter(qv);return tonumber(qv[0])/QF end
local slots=require('hd2runtime/runtime/stratagem_slot_conversion')
local allocator=require('hd2runtime/runtime/carrier_allocator')
local scheduler=require('hd2runtime/runtime/scheduler')
local transaction=require('hd2runtime/core/guarded_transaction')
local profile=require('hd2runtime/schemas/current')
rawset(_G,'ModOptionsMenu',MENU)
-- Every read of game memory (the work unit: live, each one is a ReadProcessMemory).
local reads=0
local read=W.runtime.read
W.runtime.read=function(...)reads=reads+1;return read(...)end
local discoveries=0
local discover=slots.discover_carriers
slots.discover_carriers=function(...)discoveries=discoveries+1;return discover(...)end
-- n more custom stratagems of three families (distinct codes), as more custom stratagem mods would register.
local DIRS={'up','down','left','right'}
local function register(first,n)
    for k=first,first+n-1 do
        local code={'up','down'}
        local x=k
        for _=1,4 do code[#code+1]=DIRS[x%4+1];x=math.floor(x/4)end
        code[#code+1]='left'
        local spec={id=('perf_%02d'):format(k),name='P'..k,description='d',icon='p',code=code}
        if k%3==0 then spec.carrier={beacon='offensive',prefer_families={'orbital'}};spec.pelican={hover=60}
        elseif k%3==1 then
            spec.carrier={beacon='offensive',prefer_families={'orbital'}}
            spec.orbital={pattern='Orbital 120mm HE Barrage',impact_explosion='Orbital Gas Strike',native=true}
        else spec.carrier={beacon='support'};spec.delivery={family='support',items={{donor='EAT-17 Expendable Anti-Tank'}}}end
        custom.register(spec,'mods/perf/m'..k)
    end
end
-- A simulated minute of updates (0.125 s each): the worst update's reads and seconds, and the discoveries made.
local function minute()
    local worst,worst_reads,d0=0,0,discoveries
    for _=1,480 do
        local r0,t0=reads,now()
        update(0.125)
        local dt,dr=now()-t0,reads-r0
        if dt>worst then worst=dt end
        if dr>worst_reads then worst_reads=dr end
    end
    return {reads=worst_reads,seconds=worst,discoveries=discoveries-d0}
end
"""


class CustomStratagemPerformanceTests(unittest.TestCase):
    def lua(self, body):
        flow.CustomStratagemFlowTests.lua(self, COMMON + body, carriers=flow.EAT_CARRIERS)

    def test_the_ship_update_cost_does_not_grow_with_the_registered_custom_stratagems(self):
        self.lua(r"""
examples()
tick(40)
ship({})
tick(8)
select_into(0)
tick(80)
local few=minute()
-- The revalidations ran during the minute (every 5 s), so the minute measured them.
assert(few.discoveries>=12,'no revalidation in the minute: '..few.discoveries)
register(1,12)
assert(#custom.status()==15)
tick(80)
local many=minute()
assert(many.discoveries>=12,'no revalidation in the minute: '..many.discoveries)
local text=('three custom stratagems: %d reads, %.2f ms; fifteen: %d reads, %.2f ms'):format(few.reads,few.seconds*1000,
    many.reads,many.seconds*1000)
-- Work units: the worst update does not grow with the registered custom stratagems, and stays within the budget
-- (before 0.31.2: 93,275 and 465,467 reads, every 5 s).
assert(many.reads<=few.reads*1.25+100,'the worst update grows with the custom stratagems: '..text)
assert(many.reads<=2000,'over the per-update read budget: '..text)
-- A generous ceiling on the wall time (before: about 120 and 570 ms here), robust to a slow or busy machine.
assert(many.seconds<0.05,'an update took too long: '..text)
return 'ok'
""")

    def test_shared_discoveries_and_kept_facts_give_the_same_allocation(self):
        self.lua(r"""
examples()
tick(40)
ship({})
tick(8)
local world=world_module.open()
local S=1000
local serial=scheduler.serial
-- Twenty definitions of every policy shape the registry uses.
local POLICIES={{beacon='any'},{beacon='offensive',prefer_families={'orbital'}},{beacon='support'},
    {beacon='support',prefer_families={'support','backpack'},allow_families={'support','backpack'}}}
local function definitions(unique)
    local out={}
    for k=1,20 do
        local p=POLICIES[k%4+1]
        local policy={beacon=p.beacon,prefer_families=p.prefer_families,allow_families=p.allow_families,
            -- an exclusion naming no catalogued stratagem: the same discovery, but its own (nothing is shared)
            exclude=unique and{'not catalogued '..k}or nil}
        out[k]={id=('d%02d'):format(k),label='D'..k,token='Orbital Precision Strike',policy=policy,selected=k%2==0}
    end
    return out
end
local function text(a)
    local parts={a.line,tostring(a.ready)}
    for _,id in ipairs(a.order)do
        local x=a.assignments[id]
        parts[#parts+1]=id..'='..(x and(x.carrier..'/'..tostring(x.stable_id)..'/'..tostring(x.tentative))or('refused '..
            tostring(a.refused[id])))
        local v={}
        for sid,verdict in pairs(a.verdicts[id]or{})do v[#v+1]=tostring(sid)..':'..verdict end
        table.sort(v)
        parts[#parts+1]=table.concat(v,';')
        local c={}
        for _,cand in ipairs(a.candidates[id]or{})do
            c[#c+1]=cand.name..':'..tostring(cand.eligible)..':'..table.concat(cand.codes,',')
        end
        parts[#parts+1]=table.concat(c,';')
    end
    return table.concat(parts,'\n')
end
-- As before 0.31.2: a discovery per definition, every fact read again (outside an update nothing is kept).
scheduler.serial=function()return nil end
local r0,d0=reads,discoveries
local before=allocator.allocate_lobby(world,definitions(true),{present={},players=1},{})
local before_reads,before_discoveries=reads-r0,discoveries-d0
-- Now, inside one update: shared discoveries, the facts read once.
scheduler.serial=function()return S end
r0,d0=reads,discoveries
local now_=allocator.allocate_lobby(world,definitions(false),{present={},players=1},{})
local now_reads,now_discoveries=reads-r0,discoveries-d0
assert(before.ready and now_.ready and next(now_.assignments)~=nil)
assert(text(before)==text(now_),'the allocation changed:\n'..text(before)..'\n---\n'..text(now_))
assert(before_discoveries==20 and now_discoveries==1,before_discoveries..' / '..now_discoveries)
assert(now_reads*5<before_reads,('reads %d before, %d now'):format(before_reads,now_reads))
-- A second allocation in the same update reads (almost) nothing again.
r0=reads
local again=allocator.allocate_lobby(world,definitions(false),{present={},players=1},{})
assert(text(again)==text(now_)and reads-r0<now_reads/10,'the facts were read again: '..(reads-r0))
-- The facts are kept only while nothing is written: a Runtime write in the update (any guarded transaction write)
-- drops them, and so does the next update.
local first
for _,c in ipairs(now_.candidates.d02)do if c.selectable then first=c;break end end
assert(first,'a selectable candidate')
local row=world.view.pointer(world.game+profile.stratagem.table_rva+first.type*8)
local original=W.read(row+0x80,4)
W.write(row+0x80,W.u32(0))
local function selectable(name)
    for _,c in ipairs(slots.discover_carriers(world,'Orbital Precision Strike',{present={}}).candidates)do
        if c.name==name then return c.selectable end
    end
end
assert(selectable(first.name)==true,'kept for the update')
transaction.issued=transaction.issued+1
assert(selectable(first.name)==false,'a Runtime write drops the kept facts')
W.write(row+0x80,original)
S=S+1
assert(selectable(first.name)==true,'the next update reads again')
scheduler.serial=serial
return 'ok'
""")


if __name__ == '__main__':
    unittest.main()
