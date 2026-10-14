"""Changed writes, inverse writes and broken heat-chain rejection on retained memory."""
import json
from pathlib import Path
from validate_enemy_controls_snapshot import OVERLAY
from validate_entity_authoring_snapshot import ROOT, SNAPSHOT, lua, sources

PROGRAM=OVERLAY+r'''
local h=require('hd2runtime/api/hd2')
local D=require('hd2runtime/domains/player_weapon_authoring')
local W=require('hd2runtime/domains/player_weapon_writes')
local A=require('hd2runtime/domains/attachment_authoring')
local AW=require('hd2runtime/domains/attachment_writes')
local result={status='VALIDATED',liveGameTested=false,firearms=0,baseReloads=0,magazineReloads=0,noReloadAbility=0,heatFields=0,changedWrites=0,rejections={}}
local function resolve(domain,spec)
 local reader=Reader.new(runtime);local r=domain.capture(runtime,reader,spec)
 local p=domain.prepare(r,reader,spec);reader.verify();return p,r
end
local function changed(v,f)
 if type(v)=='boolean'then return not v end
 local next=v==0 and 0.5 or v*0.8
 if f.type=='integer'then next=v+1 end
 if f.max and next>f.max then next=v-1 end
 return next
end
local function exercise(domain,req)
 reset();local spec=domain.validate_transaction(req);local plan=resolve(domain,spec)
 local values={}
 for _,c in ipairs(plan.changes)do values[#values+1]={at=c.owner.base+c.offset,bytes=runtime.read(c.owner.base+c.offset,c.width or#c.expected)}end
 local applied=guarded.apply(runtime,plan);assert(applied.status=='APPLIED',applied.error)
 for _,c in ipairs(plan.changes)do assert(runtime.read(c.owner.base+c.offset,#c.desired)==c.desired)end
 local inv=guarded.inverse(plan);assert(guarded.apply(runtime,inv).status=='APPLIED')
 for _,v in ipairs(values)do assert(runtime.read(v.at,#v.bytes)==v.bytes,'inverse differs')end
 result.changedWrites=result.changedWrites+#plan.changes
end
local worker=coroutine.create(function()
 for name,e in pairs(D.weapons)do
  local heat={}
  for _,f in ipairs(e.fields)do
   if f.reloadTiming and f.reloadTiming.noReloadAbility then
    result.noReloadAbility=result.noReloadAbility+1
    assert(not f.acceptedForWrites)
    local ok=pcall(W.validate_patch,{id='no-reload',target=h.weapon(name),field=f.semanticFieldId,
      expect=f.currentDefault,value=1,allow_unverified_effect=true})
    assert(not ok,'non-reloading weapon accepted reload write')
   elseif f.semanticFieldId=='reload.duration'and f.reloadTiming then
    result.firearms=result.firearms+1
    local target=h.weapon(name);local field=f.semanticFieldId;local expect=f.currentDefault;local domain=W
    if f.reloadTiming.defaultAttachment then
     local id=f.reloadTiming.defaultAttachment;target=h.weapon_attachment(id);field='attachment.reload_duration'
     expect=A.attachments[id].fields[field].currentDefault;domain=AW;result.magazineReloads=result.magazineReloads+1
    else result.baseReloads=result.baseReloads+1 end
    exercise(domain,{id='reload-test',target=target,changes={{field=field,expect=expect,value=1.25}},
     allow_shared=true,allow_unverified_effect=true})
   elseif f.reviewedReloadHeat and f.editable then
    heat[#heat+1]={field=f.semanticFieldId,expect=f.currentDefault,value=changed(f.currentDefault,f)}
    result.heatFields=result.heatFields+1
   end
  end
  for start=1,#heat,32 do
   local changes={};for i=start,math.min(start+31,#heat)do changes[#changes+1]=heat[i]end
   exercise(W,{id='heat-test',target=h.weapon(name),changes=changes,allow_shared=true,allow_unverified_effect=true})
  end
 end
 -- 0.31.3 adds the Shear. Four Sickle windup fields already have release descriptors.
 assert(result.firearms==77 and result.noReloadAbility==1 and result.heatFields==85)
 local name='LAS-17 Double-Edge Sickle'
 for _,field in ipairs({'heat.level_1.damage.standard_damage','heat.level_3.self_damage.standard_damage'})do
  reset();local f
  for _,x in ipairs(D.weapons[name].fields)do if x.semanticFieldId==field then f=x end end
  local spec=W.validate_patch({id='broken-heat-link',target=h.weapon(name),field=field,expect=f.currentDefault,
   value=f.currentDefault+1,allow_shared=true,allow_unverified_effect=true})
  local _,r=resolve(W,spec);local c=r.catalog.record(r.candidate,'WeaponHeatComponentData')
  local o=(f.backing.heatLevel-1)*24+(field:find('self_damage',1,true)and 20 or 4)
  poke(c.owner.base+c.offset+o,b.encode(0,'u32'))
  local ok,why=pcall(function()resolve(W,spec)end);assert(not ok and tostring(why):find('selector changed',1,true),tostring(why))
  result.rejections[#result.rejections+1]=field
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
    (ROOT/'validation/reload-heat-snapshot.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
