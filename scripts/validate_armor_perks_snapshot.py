"""Run production perk captures, writes and inverses on retained snapshots (no live process writes)."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_profile
from validate_entity_authoring_snapshot import lua,sources
from validate_attachment_authoring_snapshot import PROGRAM as BASE
PROGRAM=BASE[:BASE.index('local region')]+r'''
local W=require('hd2runtime/domains/armor_perk_writes')
local D=require('hd2runtime/domains/armor_perks')
local result={perks=#D.entries,fields=0,roundTrips=0,conflicts=0,guards=0,mode='snapshot-overlay'}
local function request(e,f,value)
 return {id='perk-check',target={resource='armor_perk',armor_perk=e.id},allow_shared=true,
  allow_unverified_effect=true,field=f.semanticFieldId,expect=f.currentDefault,value=value or f.currentDefault}
end
local function resolve(spec)
 local reader=Reader.new(runtime);local r=W.capture(runtime,reader,spec)
 local plan=W.prepare(r,reader,spec);reader.verify();return plan,r
end
local function rejects(fn,needle)
 local ok,why=pcall(fn);assert(not ok and tostring(why):find(needle,1,true),tostring(why));result.guards=result.guards+1
end
local worker=coroutine.create(function()
 reset()
 for _,e in ipairs(D.entries)do
  for _,f in ipairs(e.fields)do
   local spec=W.validate_patch(request(e,f))
   local p=resolve(spec);local c=p.changes[1]
   assert(c.before==c.expected,e.name..' '..f.semanticFieldId..' not vanilla')
   assert(guarded.apply(runtime,p).status=='ALREADY_DESIRED')
   result.fields=result.fields+1
   local v=f.currentDefault+((f.unit=='count'or f.type=='integer')and 1 or 0.25)
   if v>f.max then v=f.min end
   local changed=W.validate_patch(request(e,f,v))
   local plan,r=resolve(changed)
   local before={};for part,data in pairs(r.parts)do before[part]=runtime.read(data.owner.base+data.offset,#data.bytes)end
   local applied=guarded.apply(runtime,plan);assert(applied.status=='APPLIED',json.encode(applied))
   assert(applied.writes==1 and applied.protection_changes==0)
   for part,data in pairs(r.parts)do
    local want=before[part]
    if part==f.backing.part then local at=f.backing.offset;want=want:sub(1,at)..b.encode(v,'f32')..want:sub(at+5)end
    assert(runtime.read(data.owner.base+data.offset,#want)==want,'write affected neighboring fields')
   end
   local undone=guarded.apply(runtime,guarded.inverse(plan));assert(undone.status=='APPLIED',json.encode(undone))
   assert(runtime.read(c.owner.base+c.offset,4)==c.before);result.roundTrips=result.roundTrips+1
   -- Foreign edits must be refused, not adopted as a baseline.
   poke(c.owner.base+c.offset,b.encode(v+0.25,'f32'))
   local ok,why=pcall(resolve,changed)
   assert(not ok and tostring(why):find('CONFLICT',1,true),tostring(why));result.conflicts=result.conflicts+1
   poke(c.owner.base+c.offset,c.before)
  end
 end
 local e=D.entries[3];local f=e.fields[1];local spec=W.validate_patch(request(e,f))
 local req=request(e,f);req.allow_shared=nil;rejects(function()W.validate_patch(req)end,'allow_shared')
 req=request(e,f);req.allow_unverified_effect=nil;rejects(function()W.validate_patch(req)end,'allow_unverified_effect')
 req=request(e,f,f.max+1);rejects(function()W.validate_patch(req)end,'range')
 req=request(e,f);req.expect=999;rejects(function()W.validate_patch(req)end,'expect')
 local p,r=resolve(spec);local part=r.parts.modifier;local at=part.owner.base+part.offset
 poke(at,b.encode(0,'u32'));rejects(function()resolve(spec)end,'modifier identity');reset()
 local base=runtime.address(runtime.module('game.dll'))
 local manager=b.pointer(runtime.read(base+D.manager.globalRva,8),0)
 local table=b.pointer(runtime.read(manager+D.manager.passives,8),0)
 local slot=b.u32(runtime.read(manager+D.manager.passiveIndex+e.id*4,4),0)
 local record=b.pointer(runtime.read(table+slot*8,8),0)
 poke(record,b.encode(999,'u32'));rejects(function()resolve(spec)end,'identity changed');reset()
 poke(record+0x18,b.encode(99,'u32'));rejects(function()resolve(spec)end,'array count');reset()
 poke(manager+D.manager.passives,string.rep('\0',8));rejects(function()resolve(spec)end,'pointer absent');reset()
 local statentry;for _,entry in ipairs(D.entries)do if entry.id==16 then statentry=entry end end
 local statspec=W.validate_patch(request(statentry,statentry.fields[1]));local _,statrow=resolve(statspec)
 local statpart=statrow.parts.stat
 poke(statpart.owner.base+statpart.offset,b.encode(19,'u32'))
 rejects(function()resolve(statspec)end,'stat identity');reset()
 protection[at-at%PAGE]=0x20;rejects(function()resolve(spec)end,'private read-write');reset()
 local pin=D.pins[1]
 poke(base+pin.rva,string.rep('\0',#pin.hex/2));rejects(function()resolve(spec)end,'code changed');reset()
 -- Capture all fields together, as the editor's batched apply does.
 local specs={};for _,entry in ipairs(D.entries)do if#entry.fields>0 then
  local changes={};for _,field in ipairs(entry.fields)do
   local v=field.currentDefault+((field.type=='integer'or field.unit=='count')and 1 or 0.25)
   if v>field.max then v=field.min end
   changes[#changes+1]={field=field.semanticFieldId,expect=field.currentDefault,value=v}end
  specs[#specs+1]=W.validate_transaction({id='batch-'..entry.id,target={resource='armor_perk',armor_perk=entry.id},
   allow_shared=true,allow_unverified_effect=true,changes=changes})
 end end
 local reader=Reader.new(runtime);local captures=W.capture_many(runtime,reader,specs)
 local plan={snapshots=reader.snapshots,changes={}}
 for i,s in ipairs(specs)do for _,c in ipairs(W.prepare(captures[i],reader,s).changes)do
  plan.changes[#plan.changes+1]=c end end;reader.verify()
 local applied=guarded.apply(runtime,plan);assert(applied.status=='APPLIED',json.encode(applied))
 assert(applied.writes==75 and applied.protection_changes==0)
 local restored=guarded.apply(runtime,guarded.inverse(plan));assert(restored.status=='APPLIED',json.encode(restored))
 result.batchContexts=#reader.snapshots;result.batchWrites=applied.writes;result.batchResetWrites=restored.writes
 result.batch=#specs;result.status='VALIDATED';source.close();return result
end)
local ok,out
repeat ok,out=coroutine.resume(worker)until not ok or coroutine.status(worker)=='dead'
assert(ok,out);return json.encode(out)
'''

def validate(snapshot):
    sys.path.insert(0,str(ROOT/'sdk'))
    from tools.lua_runner import execute
    preload='\n'.join('package.preload['+lua(n)+']=function(...) return assert(loadstring('+lua(s)+','+lua(n)+'))(...) end' for n,s in sources().items())
    return json.loads(execute((preload+'\nlocal SNAPSHOT_PATH='+lua(snapshot)+'\n'+PROGRAM).encode()))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',action='append');a=p.parse_args()
    names=a.snapshot or [s['snapshot'] for s in json.loads((ROOT/'research/player-attributes-F5FEE03DCFDB.json').read_text(encoding='utf8'))['snapshots']]
    out={}
    for name in names:
        out[name]=validate(build_profile.snapshot_directory()/name);print(name,out[name],flush=True)
    (ROOT/'research/validation/armor-perks-snapshot.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8')
