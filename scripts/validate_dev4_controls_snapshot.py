"""Exercise shield and Accelerator changes on retained memory, never a live process."""
import json
from pathlib import Path
from validate_enemy_controls_snapshot import OVERLAY
from validate_entity_authoring_snapshot import ROOT,SNAPSHOT,lua,sources
PROGRAM=OVERLAY+r'''
local h=require('hd2runtime/api/hd2')
local W=require('hd2runtime/domains/player_weapon_writes')
local T=require('hd2runtime/domains/throwable_writes')
local D=require('hd2runtime/domains/player_weapon_authoring')
local result={status='VALIDATED',liveGameTested=false,roundTrips=0,rejections=0}
local function resolve(domain,spec)
 local reader=Reader.new(runtime);local r=domain.capture(runtime,reader,spec)
 local p=domain.prepare(r,reader,spec);reader.verify();return p
end
local function roundtrip(domain,target,id,from,to)
 reset()
 local req={id='dev4-test',target=target,field=id,expect=from,value=to,allow_unverified_effect=true}
 local spec=domain.validate_patch(req);local plan=resolve(domain,spec)
 local before={}
 for _,c in ipairs(plan.changes)do
  local at=c.owner.base+c.offset;before[#before+1]={at=at-8,bytes=runtime.read(at-8,#c.desired+16)}
 end
 local applied=guarded.apply(runtime,plan);assert(applied.status=='APPLIED',applied.error)
 for _,c in ipairs(plan.changes)do assert(runtime.read(c.owner.base+c.offset,#c.desired)==c.desired)end
 assert(guarded.apply(runtime,guarded.inverse(plan)).status=='APPLIED')
 for _,v in ipairs(before)do assert(runtime.read(v.at,#v.bytes)==v.bytes,'inverse or neighboring bytes differ')end
 result.roundTrips=result.roundTrips+1
 req.allow_unverified_effect=nil
 assert(not pcall(domain.validate_patch,req),'acknowledgement bypass');result.rejections=result.rejections+1
end
local worker=coroutine.create(function()
 for _,f in ipairs(D.weapons['PLAS-39 Accelerator Rifle'].fields)do if f.reviewedAcceleratorCharge then
  local value=f.currentDefault
  local changed=type(value)=='boolean'and not value or(type(value)=='number'and value+0.1)
  if f.type=='integer'then changed=value+1 end
  roundtrip(W,h.weapon('PLAS-39 Accelerator Rifle'),f.semanticFieldId,value,changed)
 end end
 roundtrip(W,h.weapon('PLAS-39 Accelerator Rifle'),'fire_mode.modes',{'single'},{'single','unsafe'})
 for _,f in ipairs({'shield.recharge_delay','shield.broken_recharge_delay','shield.recharge_rate'})do
  roundtrip(T,h.throwable('G/SH-39 Shield'):shield(),f,f=='shield.recharge_rate'and 0 or 20,f=='shield.recharge_rate'and 50 or 2)
 end
 assert(not pcall(W.validate_patch,{id='invalid-mode',target=h.weapon('PLAS-39 Accelerator Rifle'),
  field='fire_mode.modes',expect={'single'},value={'automatic'},allow_unverified_effect=true}))
 result.rejections=result.rejections+1
 assert(result.roundTrips==18)
 reset();source.close();return result
end)
local ok,out
repeat ok,out=coroutine.resume(worker);assert(ok,out)until coroutine.status(worker)=='dead'
return json.encode(out)
'''
def validate(snapshot=SNAPSHOT):
 import sys
 sys.path.insert(0,str(ROOT/'sdk'))
 from tools.lua_runner import execute
 preload='\n'.join('package.preload['+lua(n)+']=function(...) return assert(loadstring('+lua(s)+','+lua(n)+'))(...) end'for n,s in sources().items())
 return json.loads(execute((preload+'\nlocal SNAPSHOT_PATH='+lua(Path(snapshot).resolve())+'\n'+PROGRAM).encode()))
if __name__=='__main__':
 result=validate();(ROOT/'validation/dev4-controls-snapshot.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
