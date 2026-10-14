"""Exercise complete throwable status sets through public APIs on a retained-memory overlay."""
import json
import sys
from pathlib import Path
from validate_enemy_controls_snapshot import OVERLAY
from validate_entity_authoring_snapshot import ROOT, SNAPSHOT, lua, sources

PROGRAM=OVERLAY+r'''
local h=require('hd2runtime/api/hd2')
local D=require('hd2runtime/domains/throwable_authoring')
local W=require('hd2runtime/domains/throwable_writes')
local S=require('hd2runtime/domains/status_catalog').statuses
local session=require('hd2runtime/api/session').new(runtime,function()end)
local result={status='VALIDATED',liveGameTested=false,scenarios={},rejections={}}
local function reject(fn,needle)
 local ok,why=pcall(fn);assert(not ok and tostring(why):find(needle,1,true),tostring(why))
 result.rejections[#result.rejections+1]=needle
end
local function resolve(spec)
 local reader=Reader.new(runtime);local r=W.capture(runtime,reader,spec)
 local p=W.prepare(r,reader,spec);reader.verify();return p,r
end
local function finish(w)
 w.tick(3.1)
 for _=1,20000 do w.tick(0.001);if w.status=='complete'or w.status=='rejected'then break end end
 assert(w.status=='complete'and w.result.status=='APPLIED',tostring(w.error));return w
end
local worker=coroutine.create(function()
 for _,item in ipairs({{'G-12 High Explosive','explosion','explosion.damage.'},
  {'K-2 Throwing Knife','damage','damage.'},{'G-6 Frag','shrapnel','damage.'},
  {'G-7 Pineapple','bomblets','damage.'},{'G-7 Pineapple','bomblet_explosion','explosion.damage.'}})do
  reset()
  local name,path,prefix=unpack(item)
  local target={resource='throwable',throwable=name,path=path}
  local fields=D.throwables[name].targets[path].fields
  local changes={};local statuses={'fire','gas','stun_small','poison'}
  for slot=1,4 do
   for _,kind in ipairs({'type','strength'})do
    local id=prefix..'status_'..slot..'_'..kind
    changes[#changes+1]={field=id,expect=fields[id].currentDefault,value=kind=='type'and statuses[slot]or slot}
   end
  end
  local request={id='four-statuses',target=target,changes=changes,allow_shared=true,allow_unverified_effect=true}
  local spec=W.validate_transaction(request);local plan=resolve(spec)
  finish(session.transaction(request))
  for _,c in ipairs(plan.changes)do assert(runtime.read(c.owner.base+c.offset,4)==c.desired,c.label)end
  assert(guarded.apply(runtime,guarded.inverse(plan)).status=='APPLIED','status inverse')
  for _,c in ipairs(plan.changes)do assert(runtime.read(c.owner.base+c.offset,4)==c.before)end
  result.scenarios[#result.scenarios+1]=name..'/'..path..': four types, four strengths, exact inverse'
  if path=='explosion'then
   reset();local operations={}
   -- Reverse order proves phase-wide packing, rather than relying on registration order.
   for i=#changes,1,-1 do
    local c=changes[i]
    operations[#operations+1]={id='status-'..i,target=target,field=c.field,expect=c.expect,value=c.value,
      allow_shared=true,allow_unverified_effect=true}
   end
   finish(session.plan({id='status-phase',operations=operations}))
   result.scenarios[#result.scenarios+1]='reverse-order plan phase'
  end
 end
 reset()
 local target=h.throwable('G-4 Gas'):explosion()
 local fields=D.throwables['G-4 Gas'].targets.explosion.fields
 local function clear(slot)
  local id='explosion.damage.status_'..slot..'_type'
  return {field=id,expect=fields[id].currentDefault,value='none'}
 end
 local request={id='clear-gas',target=target,changes={clear(1)},allow_shared=true,allow_unverified_effect=true}
 reject(function()resolve(W.validate_transaction(request))end,'STATUS_SLOT_GAP')
 request.changes={clear(1),clear(2)};finish(session.transaction(request))
 result.scenarios[#result.scenarios+1]='clear existing Gas and Gas Confusion together'
 reset()
 local name='G-12 High Explosive';local f=D.throwables[name].targets.explosion.fields['explosion.damage.status_4_type']
 local r={id='gap',target=h.throwable(name):explosion(),field=f.semanticFieldId,expect='none',value='fire',
  allow_shared=true,allow_unverified_effect=true}
 reject(function()resolve(W.validate_patch(r))end,'STATUS_SLOT_GAP')
 r.field='explosion.damage.status_1_type'
 local _,captured=resolve(W.validate_patch(r));local root=captured.roots.status
 local raw=root.records[S.fire.nativeType].bytes;local ptr=b.pointer(raw,8)
 poke(ptr,'X');reject(function()resolve(W.validate_patch(r))end,'live status table no longer names');reset()
 source.close();return result
end)
local ok,out
repeat ok,out=coroutine.resume(worker);assert(ok,out)until coroutine.status(worker)=='dead'
return json.encode(out)
'''


def validate():
    sys.path.insert(0,str(ROOT/'sdk'))
    from tools.lua_runner import execute
    preload='\n'.join('package.preload['+lua(n)+']=function(...) return assert(loadstring('+lua(s)+','+lua(n)+'))(...) end' for n,s in sources().items())
    return json.loads(execute((preload+'\nlocal SNAPSHOT_PATH='+lua(Path(SNAPSHOT).resolve())+'\n'+PROGRAM).encode()))


if __name__=='__main__':
    report=validate()
    (ROOT/'validation/throwable-status-slots.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
