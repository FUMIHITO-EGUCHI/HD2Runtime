"""Exercise shotgun references and Urchin payload copies without a game process."""
import json
from pathlib import Path
from validate_enemy_controls_snapshot import OVERLAY
from validate_entity_authoring_snapshot import ROOT, SNAPSHOT, lua, sources
PROGRAM=OVERLAY+r'''
local h=require('hd2runtime/api/hd2')
local W=require('hd2runtime/domains/player_weapon_writes')
local T=require('hd2runtime/domains/throwable_writes')
local result={status='VALIDATED',changedWrites=0,rejections=0,rollbackFailures=0,liveGameTested=false}
local function resolve(domain,spec)
 local reader=Reader.new(runtime);local r=domain.capture(runtime,reader,spec)
 local p=domain.prepare(r,reader,spec);reader.verify();return p,r
end
local function request(target,field,expect,value)
 return {id='belt-urchin',target=target,field=field,expect=expect,value=value,
  allow_shared=true,allow_unverified_effect=true,allow_unverified_reference=true}
end
local function read_plan(p)
 local out={};for _,c in ipairs(p.changes)do out[#out+1]=runtime.read(c.owner.base+c.offset,#c.desired)end;return table.concat(out)
end
local function exercise(domain,req)
 reset();local spec=domain.validate_patch(req);local p,r=resolve(domain,spec)
 local c=p.changes[1];local expected,desired={},{}
 for _,part in ipairs(p.changes)do expected[#expected+1]=part.expected;desired[#desired+1]=part.desired end
 expected=table.concat(expected);desired=table.concat(desired)
 local original=read_plan(p)
 assert(guarded.apply(runtime,p).status=='APPLIED')
 assert(read_plan(p)==desired)
 local again=resolve(domain,spec);assert(again.changes[1].already_desired)
 assert(guarded.apply(runtime,guarded.inverse(p)).status=='APPLIED')
 assert(read_plan(p)==original)
 result.changedWrites=result.changedWrites+1;return spec,p,r
end
local worker=coroutine.create(function()
 local weapon=h.support_weapon('GL-28 Belt-Fed Grenade Launcher')
 local src=weapon:projectile_source();assert(src.writable and src.target)
 local req=request(src.target,src.field,src.expect,h.attack_output('SG-225 Breaker'))
 local spec,_,r=exercise(W,req)
 local linked=r.catalog.record(r.candidate,'WeaponLinkedAmmoComponentData')
 poke(linked.owner.base+linked.offset,b.encode(99,'u32'))
 local ok,why=pcall(function()resolve(W,spec)end)
 assert(not ok and tostring(why):find('BACKPACK_HOST_CHANGED',1,true),tostring(why));result.rejections=result.rejections+1
 local own='throwable/g109_urchin/detonation'
 for _,id in ipairs({'support_weapon/plas45_epoch/impact','support_weapon/plas45_epoch/charge_2_expiry'})do
  local q=request(h.throwable('G-109 Urchin'):pulse(),'throwable.pulse_explosion',h.explosion(own),h.explosion(id))
  local ts,plan,res=exercise(T,q)
  assert(#ts.asset_dependencies==(id:find('charge_2',1,true)and 1 or 0),'donor asset dependency missing')
  local root=res.roots.explosion;local row=root.records[369];local before=runtime.read(root.owner.base+row.offset,4)
  local final_before=runtime.read(root.owner.base+root.records[412].offset,4)
  assert(guarded.apply(runtime,plan).status=='APPLIED')
  assert(runtime.read(root.owner.base+row.offset,4)==before,'recipient type overwritten')
  assert(runtime.read(root.owner.base+root.records[412].offset,4)==final_before,'final type overwritten')
  assert(guarded.apply(runtime,guarded.inverse(plan)).status=='APPLIED')
  -- Fail once as the final-discharge row starts writing: both rows must return to their original bytes.
  local before_all=read_plan(plan);local native_write=runtime.write;local failed=false
  local final=root.records[412];local fail_at=root.owner.base+final.offset+4
  runtime.write=function(at,data)
   if not failed and at==fail_at then failed=true;return false,'injected final pulse failure',0 end
   return native_write(at,data)
  end
  local bad=guarded.apply(runtime,plan);runtime.write=native_write
  assert(failed and bad.status=='REJECTED'and read_plan(plan)==before_all,'partial pulse override survived failure '..json.encode({failed=failed,status=bad.status,reason=bad.reason,rollback=bad.rollback,equal=read_plan(plan)==before_all}))
  assert(next(protection)==nil,'rollback left writable pages');result.rollbackFailures=result.rollbackFailures+1
  local option=ts.changes[1].descriptor.payloadOptions[id]
  poke(root.owner.base+option.arrayOffset,string.rep('\0',#b.unhex(option.arrayHex)))
  local ok,why=pcall(function()resolve(T,ts)end)
  assert(not ok and tostring(why):find('array changed',1,true),tostring(why));result.rejections=result.rejections+1
  reset();q.allow_unverified_reference=nil
  assert(not pcall(T.validate_patch,q));result.rejections=result.rejections+1
 end
 reset()
 local function pulse(id)
  return T.validate_patch(request(h.throwable('G-109 Urchin'):pulse(),'throwable.pulse_explosion',h.explosion(own),h.explosion(id)))
 end
 local first=pulse('support_weapon/plas45_epoch/impact');local p=resolve(T,first);local original=read_plan(p)
 assert(guarded.apply(runtime,p).status=='APPLIED')
 local second=pulse('support_weapon/plas45_epoch/charge_2_expiry')
 second.changes[1].owned=first.changes[1].desired
 p=resolve(T,second);assert(guarded.apply(runtime,p).status=='APPLIED')
 assert(read_plan(p)==second.changes[1].desired)
 local restore=pulse(own);restore.changes[1].owned=second.changes[1].desired
 p=resolve(T,restore);assert(guarded.apply(runtime,p).status=='APPLIED')
 assert(read_plan(p)==original,'owned transition did not restore both original definitions')
 result.ownedTransitions=2
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
    preload='\n'.join('package.preload['+lua(n)+']=function(...) return assert(loadstring('+lua(s)+','+lua(n)+'))(...) end' for n,s in sources().items())
    return json.loads(execute((preload+'\nlocal SNAPSHOT_PATH='+lua(Path(snapshot).resolve())+'\n'+PROGRAM).encode()))
if __name__=='__main__':
    r=validate();(ROOT/'validation/belt-urchin-snapshot.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
