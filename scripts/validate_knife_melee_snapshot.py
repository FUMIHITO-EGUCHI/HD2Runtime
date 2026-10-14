"""Prove launch and melee edits against retained memory, with reversible overlay writes only."""
import argparse
import json
from pathlib import Path
import sys
from validate_enemy_controls_snapshot import OVERLAY
from validate_entity_authoring_snapshot import ROOT,SNAPSHOT,lua,sources

PROGRAM=OVERLAY+r'''
local h=require('hd2runtime/api/hd2')
local W=require('hd2runtime/domains/melee_writes')
local T=require('hd2runtime/domains/throwable_writes')
local D=require('hd2runtime/domains/melee_authoring')
local TD=require('hd2runtime/domains/throwable_authoring')
local result={status='VALIDATED',mode='snapshot-overlay',liveGameTested=false,roundTrips={},fields=0,flightFields=0,rejections={}}
local function req(target,f,value)
 return {id='knife-melee-check',target=target,field=f.semanticFieldId,expect=f.currentDefault,value=value,
  allow_shared=true,allow_unverified_effect=true}
end
local function resolve(domain,spec)
 local reader=Reader.new(runtime);local r=domain.capture(runtime,reader,spec)
 local p=domain.prepare(r,reader,spec);reader.verify();return p,r
end
local function reject(fn,label)
 local ok,why=pcall(fn);assert(not ok,'accepted '..label);result.rejections[#result.rejections+1]=label
 return tostring(why)
end
local function roundtrip(domain,request)
 reset();local spec=domain.validate_patch(request);local plan=resolve(domain,spec)
 local c=plan.changes[1];local at=c.owner.base+c.offset;local before=runtime.read(at-16,36)
 local applied=guarded.apply(runtime,plan);assert(applied.status=='APPLIED',applied.reason)
 assert(runtime.read(at-16,36)==before:sub(1,16)..c.desired..before:sub(21),'neighbor bytes changed')
 assert(next(protection)==nil,'page protection not restored')
 local restored=guarded.apply(runtime,guarded.inverse(plan));assert(restored.status=='APPLIED',restored.reason)
 assert(runtime.read(at-16,36)==before,'inverse mismatch')
 result.roundTrips[#result.roundTrips+1]=request.field
 reset();poke(at,string.rep('\127',4));assert(reject(function()resolve(domain,spec)end,'third-party field conflict'):find('CONFLICT',1,true))
 reset();return spec
end
local worker=coroutine.create(function()
 local knife=TD.throwables['K-2 Throwing Knife'].targets.flight
 for _,f in pairs(knife.fields)do
  roundtrip(T,req(h.throwable('K-2 Throwing Knife'):flight(),f,f.currentDefault+0.25))
 end
 for _,name in ipairs({'CQC-2 Saber','CQC-19 Stun Lance','CQC-20 Breaching Hammer','CQC-42 Machete',
     'CQC-73 Entrenchment Tool','CQC-9 Defoliation Tool','AR-23 Liberator'})do
  local e=D.entries[name];assert(e,name)
  for key,t in pairs(e.targets)do
   local target=key=='tuning'and h.melee(name)or h.melee(name):zone(key)
   local id=key=='tuning'and'melee.stamina_cost'or'melee.volume_z';local f=t.fields[id]
   roundtrip(W,req(target,f,f.currentDefault+0.01))
   if key~='tuning'then
    f=t.fields['damage.standard_damage'];roundtrip(W,req(target,f,f.currentDefault+1))
   end
  end
 end
 -- Resolve every exposed field against the production reader; no writes for this catalogue pass.
 local specs={}
 for name,e in pairs(D.entries)do for key,t in pairs(e.targets)do
  local changes={};for id,f in pairs(t.fields)do changes[#changes+1]={field=id,expect=f.currentDefault,value=f.currentDefault}end
  specs[#specs+1]=W.validate_transaction({id='melee-all',target={resource='melee',melee=name,path=key},
   changes=changes,allow_shared=true,allow_unverified_effect=true});result.fields=result.fields+#changes
 end end
 local reader=Reader.new(runtime);local resolved=W.capture_many(runtime,reader,specs)
 for i,s in ipairs(specs)do W.prepare(resolved[i],reader,s)end;reader.verify()
 for name,e in pairs(TD.throwables)do
  local changes={}
  for id,f in pairs(e.targets.flight.fields)do
   changes[#changes+1]={field=id,expect=f.currentDefault,value=f.currentDefault}
  end
  local s=T.validate_transaction({id='flight-all',target=h.throwable(name):flight(),changes=changes,
   allow_shared=true,allow_unverified_effect=true})
  resolve(T,s);result.flightFields=result.flightFields+#changes
 end
 local name='CQC-2 Saber';local e=D.entries[name];local z=e.targets.zone_1;local f=z.fields['melee.volume_z']
 local request=req(h.melee(name):zone(1),f,1.5);local spec=W.validate_patch(request)
 local plan,r=resolve(W,spec);local image=runtime.address(runtime.module('game.dll'))
 poke(image+z.rva,'\0\0\0\0');reject(function()resolve(W,spec)end,'zone identity');reset()
 poke(image+z.pins[1].rva,'\0');reject(function()resolve(W,spec)end,'ability handler pin');reset()
 local link=z.links[1];local record=r.catalog.record(r.candidate,link.component)
 poke(record.owner.base+record.offset+link.offset,b.encode(0,'u32'));reject(function()resolve(W,spec)end,'weapon ability link');reset()
 request.allow_shared=nil;reject(function()W.validate_patch(request)end,'shared acknowledgement');request.allow_shared=true
 request.allow_unverified_effect=nil;reject(function()W.validate_patch(request)end,'unverified acknowledgement')
 local session=require('hd2runtime/api/session').new(runtime,function()end)
 local function finish(w)
  w.tick(3.1)
  for _=1,20000 do w.tick(0.001);if w.status=='complete'or w.status=='rejected'then break end end
  assert(w.status=='complete'and w.result.status=='APPLIED',tostring(w.error))
 end
 reset();request.allow_unverified_effect=true
 finish(session.patch(request));reset()
 finish(session.transaction({id='melee-transaction',target=request.target,
  changes={{field=request.field,expect=request.expect,value=request.value}},
  allow_shared=true,allow_unverified_effect=true}));reset()
 finish(session.plan({id='melee-plan',operations={request}}));reset()
 local watch=session.ensure({patch=request,startup_delay=0})
 for _=1,20000 do watch.tick(0.001);if watch.runs==1 or watch.status=='rejected'then break end end
 assert(watch.runs==1 and watch.status=='waiting',tostring(watch.error))
 local writes=counts.writes
 for _=1,1200 do watch.tick(1)end
 assert(watch.runs==1 and counts.writes==writes,'steady melee ensure rewrites')
 watch.cancel();reset()
 result.publicApi={patch=true,transaction=true,plan=true,ensure=true,steadyState=true}
 source.close();return result
end)
local ok,out
repeat ok,out=coroutine.resume(worker);assert(ok,out)until coroutine.status(worker)=='dead'
return json.encode(out)
'''


def validate(snapshot=SNAPSHOT):
    sys.path.insert(0,str(ROOT/'sdk'))
    from tools.lua_runner import execute
    preload='\n'.join('package.preload['+lua(n)+']=function(...) return assert(loadstring('+lua(s)+','+lua(n)+'))(...) end' for n,s in sources().items())
    return json.loads(execute((preload+'\nlocal SNAPSHOT_PATH='+lua(Path(snapshot).resolve())+'\n'+PROGRAM).encode()))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,default=SNAPSHOT);a=p.parse_args()
    report=validate(a.snapshot)
    (ROOT/'validation/knife-melee-snapshot.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
