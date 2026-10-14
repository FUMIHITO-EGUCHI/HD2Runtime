"""Changed explosion-arc writes and ownership rejection on a retained-memory overlay."""
import json
from pathlib import Path
from validate_enemy_controls_snapshot import OVERLAY
from validate_entity_authoring_snapshot import ROOT, SNAPSHOT, lua, sources

PROGRAM=OVERLAY+r'''
local h=require('hd2runtime/api/hd2')
local D=require('hd2runtime/domains/support_weapon_authoring')
local W=require('hd2runtime/domains/player_weapon_writes')
local result={status='VALIDATED',liveGameTested=false,changedWrites=0,rejections={}}
local function resolve(spec)
 local reader=Reader.new(runtime);local r=W.capture(runtime,reader,spec)
 local p=W.prepare(r,reader,spec);reader.verify();return p,r
end
local function request(f)
 return {id='explosion-arc-test',target=f.target,field=f.semanticFieldId:gsub('%.'..f.target.attack..'%.','.'),expect=f.currentDefault,
  value=f.currentDefault==0 and 1 or f.currentDefault*0.5,allow_shared=true,allow_unverified_effect=true}
end
local function prefill(f)
 if not f.backing.statusSlot then return end
 local changes={}
 for _,other in ipairs(D.weapons['GL-52 De-Escalator'].fields)do
  if other.type=='status_reference'and other.target.attack==f.target.attack
   and other.backing.statusSlot<f.backing.statusSlot and other.currentDefault=='none'then
   changes[#changes+1]={field=other.semanticFieldId:gsub('%.'..other.target.attack..'%.','.'),expect='none',value='fire'}
  end
 end
 if #changes==0 then return end
 local spec=W.validate_transaction({id='arc-prefill',target=f.target,changes=changes,
  allow_shared=true,allow_unverified_effect=true})
 assert(guarded.apply(runtime,resolve(spec)).status=='APPLIED')
end
local worker=coroutine.create(function()
 local arc_field
 for _,f in ipairs(D.weapons['GL-52 De-Escalator'].fields)do
  if (f.backing.linkage or''):find('explosion_arc',1,true)
   or(f.backing.parentLinkage or''):find('explosion_arc',1,true)then
   if f.type=='number'or f.type=='integer'then
    reset();prefill(f);local req=request(f);if f.type=='integer'then req.value=math.floor(req.value)end
    local spec=W.validate_patch(req);local plan=resolve(spec)
    assert(#plan.changes==1);local c=plan.changes[1]
    assert(guarded.apply(runtime,plan).status=='APPLIED')
    assert(runtime.read(c.owner.base+c.offset,#c.desired)==c.desired)
    assert(guarded.apply(runtime,guarded.inverse(plan)).status=='APPLIED')
    assert(runtime.read(c.owner.base+c.offset,#c.expected)==c.expected)
    result.changedWrites=result.changedWrites+1
   end
   if f.semanticFieldId=='damage.primary_impact_arc.standard_damage'then arc_field=f end
  end
 end
 assert(arc_field,'arc damage field missing')
 for _,link in ipairs({'projectile','explosion','arc'})do
  reset();local spec=W.validate_patch(request(arc_field));local _,r=resolve(spec)
  local kind,typ,offset
  if link=='projectile'then kind,typ,offset='projectile',222,144
  elseif link=='explosion'then kind,typ,offset='explosion',41,120
  else kind,typ,offset='arc',15,36 end
  local root=r.roots[kind];local row=root.records[typ]
  poke(root.owner.base+row.offset+offset,b.encode(0,'u32'))
  local before=counts.writes;local ok,why=pcall(function()resolve(spec)end)
  assert(not ok,'changed '..link..' link accepted');assert(counts.writes==before)
  result.rejections[#result.rejections+1]={link=link,error=tostring(why)}
 end
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
    result=validate()
    (ROOT/'validation/explosion-arcs-snapshot.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
