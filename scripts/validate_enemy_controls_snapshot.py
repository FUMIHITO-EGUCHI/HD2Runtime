"""Exercise 0.32 enemy controls on retained memory with a reversible in-memory overlay.

Never opens a process or writes game files. Native source data and dynamic template
records use the production resolver, guard and transaction implementations.
"""
import argparse
import json
from pathlib import Path
import sys
from validate_entity_authoring_snapshot import ROOT, SNAPSHOT, lua, sources
from validate_attachment_authoring_snapshot import PROGRAM as BASE

OVERLAY=BASE[:BASE.index('local region')].replace("local domain=require('hd2runtime/domains/attachment_writes')",'').replace(
    "local database=require('hd2runtime/domains/attachment_authoring')",'').replace(
    "assert((protection[at-at%PAGE] or original_protect(at-at%PAGE))==4,'overlay write without writable page')",
    "local p=protection[at-at%PAGE] or original_protect(at-at%PAGE);assert(p==4 or p==0x40,'overlay page not writable')")

PROGRAM=OVERLAY+r'''
local enemies=require('hd2runtime/domains/enemy_writes')
local director=require('hd2runtime/domains/enemy_director_writes')
local ED=require('hd2runtime/domains/enemy_director')
local EC=require('hd2runtime/domains/enemy_controls')
local api=require('hd2runtime/api/enemy_director')
local hd2=require('hd2runtime/api/hd2')
local result={status='VALIDATED',mode='snapshot-overlay',build=profile.exe_sha:sub(1,12),runtimeVersion=hd2.version,
 liveGameTested=false,roundTrips={},rejections={},coverage={}}
local function resolve(domain,spec)
 local reader=Reader.new(runtime)
 local resolved=domain.capture(runtime,reader,spec)
 local plan=domain.prepare(resolved,reader,spec);reader.verify()
 return plan,resolved,reader
end
local function req(target,field,from,to)
 return {id='enemy-controls-check',target=target,field=field,expect=from,value=to,
  allow_shared=true,allow_unverified_effect=true}
end
local function reject(fn,needle)
 local ok,why=pcall(fn);assert(not ok,'accepted invalid control')
 assert(tostring(why):find(needle,1,true),tostring(why))
 result.rejections[#result.rejections+1]=needle
end
local function roundtrip(domain,request)
 reset()
 local spec=domain.validate_patch(request)
 local plan,resolved=resolve(domain,spec);local c=plan.changes[1]
 local at=c.owner.base+c.offset;local first=at-16;local before=runtime.read(first,36)
 assert(#c.desired==1 or at%4==0 or c.packed,request.field..' alignment '..tostring(at%4))
 local report=guarded.apply(runtime,plan)
 assert(report.status=='APPLIED'and report.writes==1,request.field..': '..tostring(report.reason))
 assert(runtime.read(at,#c.desired)==c.desired,'desired bytes missing')
 assert(runtime.read(first,36)==before:sub(1,16)..c.desired..before:sub(17+#c.desired),'neighboring bytes changed')
 assert(next(protection)==nil,'protection not restored')
 local inverse=guarded.apply(runtime,guarded.inverse(plan))
 assert(inverse.status=='APPLIED',inverse.reason)
 assert(runtime.read(first,36)==before,'inverse did not restore bytes')
 result.roundTrips[#result.roundTrips+1]={field=request.field,target=request.target.enemy or request.target.key,
  width=#c.desired,writes=report.writes,restored=true,nonTargetBytesUnchanged=true}
 reset();poke(at,string.rep('\127',#c.expected))
 reject(function()resolve(domain,spec)end,'CONFLICT');reset()
 return plan,resolved
end
local worker=coroutine.create(function()
 -- Every faction mode's four patrol factors: exact backing, neighbors and inverse.
 for _,mode in ipairs(ED.spawnModes)do
  for _,f in ipairs(mode.fields)do
   roundtrip(enemies,req(hd2.enemy(mode.enemy),f.id,f.currentDefault,f.currentDefault+0.25))
  end
 end
 -- Full component framing and index ownership on retained entity data.
 roundtrip(enemies,req(hd2.enemy('Charger'),'unit.scale_min',1,1.5))
 local health_fields={'entity.health_change_rate','entity.health_change_rate_disabled','entity.regeneration_cooldown',
  'entity.regeneration_segments','entity.regeneration_change_rate','entity.zone_bleedout_change_rate'}
 local charger=enemies.entry('Charger')
 for _,id in ipairs(health_fields)do
  local found=false
  for _,f in ipairs(charger.fields)do if f.id==id and f.editable then
   local value=f.backing.storage=='u8'and(1-f.currentDefault)or(f.currentDefault+1)
   roundtrip(enemies,req(hd2.enemy('Charger'),id,f.currentDefault,value));found=true;break
  end end
  assert(found,'new health field missing: '..id)
 end
 roundtrip(enemies,req(hd2.structure('il_spawner_ship'),'entity.health',5000,6000))
 roundtrip(enemies,req(hd2.structure('il_spawner_ship'),'spawner.release_delay',4,6))
 roundtrip(enemies,req(hd2.structure('cy_stratagem_blocker'),'jammer.radius',150,75))
 roundtrip(enemies,req(hd2.enemy('illuminate_dropship'),'transport.grid_dimension_0',5,4))
 local fabricator=hd2.structure('spawner_factory_conscript_base')
 roundtrip(enemies,req(fabricator:zone('insides'),'zone.fatal',1,0))
 local selected={}
 for name,entry in pairs(EC.enemies)do
  for _,component in ipairs(entry.components)do
   if not selected[component]and(component=='ShieldComponentData'or component=='HiveMindComponentData'or component=='BugholeComponentData')then
    local e=enemies.entry(name)
    local wanted=component=='ShieldComponentData'and'shield.recharge_per_second'
     or component=='HiveMindComponentData'and'hive.refill_clock_rate_players_1'or'breach.emission_radius'
    for _,f in ipairs(e.fields)do if f.id==wanted and f.editable then
     roundtrip(enemies,req(hd2.enemy(name),wanted,f.currentDefault,f.currentDefault+0.25));selected[component]=true;break
    end end
   end
  end
 end
 assert(selected.ShieldComponentData and selected.HiveMindComponentData and selected.BugholeComponentData)
 -- Arc/beam/direct component damage, with a typed settings chain rather than the old projectile-only mount chain.
 local arc
 for name,entry in pairs(EC.enemies)do
  for _,a in ipairs(entry.attacks or{})do
   if a.source.component=='ArcWeaponComponentData'and a.role=='damage'then
    local e=enemies.entry(name)
    for _,f in ipairs(e.fields)do if f.attack==a.id and f.id=='damage.standard_damage'and f.editable then
     roundtrip(enemies,req(hd2.enemy(name):attack(a.id),f.id,f.currentDefault,f.currentDefault+1));arc=true;break
    end end
   end
   if arc then break end
  end
  if arc then break end
 end
 assert(arc,'no arc damage target tested')
 roundtrip(director,req(api.difficulty(10),'difficulty.encounter_points',600,450))
 roundtrip(director,req(api.composition('terminids/family_1/row_0'),'composition.group_0_count',7,6))
 roundtrip(director,req(api.roster('terminids/row_0'),'spawn.weight_1',1,0.5))
 roundtrip(director,req(api.demolition_template('OrbitalBombardment'),'demolition.force',50,45))
 -- Every source row and template resolves at its actual address; mutations remain limited to the round trips above.
 local specs={};local categories={}
 for _,row in pairs(ED.rows)do if #row.fields>0 then
  local f=row.fields[1]
  if f.currentDefault>=f.min and f.currentDefault<=f.max then
   specs[#specs+1]=director.validate_patch(req({resource='enemy_director',path=row.kind,key=row.key},f.id,f.currentDefault,f.currentDefault))
   categories[row.kind]=(categories[row.kind]or 0)+1
  end
 end end
 local reader=Reader.new(runtime);local captures=director.capture_many(runtime,reader,specs)
 for i,spec in ipairs(specs)do assert(director.prepare(captures[i],reader,spec).changes[1].already_desired)end
 result.coverage.directorRows=categories
 -- Every writable entity/zone/attack field, not just the examples, must resolve
 -- its reviewed baseline through production ownership checks. No writes here.
 local names={};for name in pairs(EC.enemies)do names[#names+1]=name end;table.sort(names)
 local pending={};local field_count,target_count=0,0
 local function flush()
  if #pending==0 then return end
  local reader=Reader.new(runtime);local captures=enemies.capture_many(runtime,reader,pending)
  for i,spec in ipairs(pending)do
   local plan=enemies.prepare(captures[i],reader,spec)
   for _,change in ipairs(plan.changes)do assert(change.before==change.expected,'catalogue baseline differs: '..spec.enemy..' '..change.label)end
  end
  reader.verify();pending={}
 end
 for _,name in ipairs(names)do
  local entry=enemies.entry(name);local groups={}
  for _,field in ipairs(entry.fields)do if field.editable then
   local key=field.path..'/'..tostring(field.zone or field.attack)
   local group=groups[key]
   if not group then group={target={resource='enemy',enemy=name,path=field.path,zone=field.zone,attack=field.attack},fields={}};groups[key]=group end
   group.fields[#group.fields+1]=field
  end end
  for _,group in pairs(groups)do
   for start=1,#group.fields,32 do
    local changes={}
    for i=start,math.min(start+31,#group.fields)do
     local f=group.fields[i];local d=enemies.descriptor(entry,f)
     -- A native nonpositive jammer radius is inspectable, but newly requested
     -- values must be positive. Prepare its minimum without applying the plan.
     changes[#changes+1]={field=f.id,expect=f.currentDefault,value=math.max(d.min,math.min(d.max,f.currentDefault))}
    end
    pending[#pending+1]=enemies.validate_transaction({id='catalogue-baseline',target=group.target,changes=changes,
     allow_shared=true,allow_unverified_effect=true})
    field_count=field_count+#changes;target_count=target_count+1
    if #pending>=32 then flush()end
   end
  end
 end
 flush();result.coverage.entityFields=field_count;result.coverage.entityTargetBatches=target_count
 -- Corrupt identity, code, expected bytes and lifecycle state: each must fail closed.
 local rq=req(api.difficulty(10),'difficulty.encounter_points',600,450)
 local spec=director.validate_patch(rq);local image=runtime.address(runtime.module('game.dll'))
 poke(image+ED.pins[1].rva,'\0')
 reject(function()resolve(director,spec)end,'native code changed');reset()
 local row=ED.rows['difficulty/10'];local g=row.guards[1]
 poke(image+row.rva+g.offset,'\0')
 reject(function()resolve(director,spec)end,'row identity changed');reset()
 local state=require('hd2runtime/domains/event_natives').state
 local game=b.pointer(runtime.read(image+state.game,8),0)
 poke(game+state.state,b.encode(4,'u32'))
 reject(function()resolve(director,spec)end,'Ship state');reset()
 rq.allow_shared=nil;reject(function()director.validate_patch(rq)end,'allow_shared');rq.allow_shared=true
 rq.allow_unverified_effect=nil;reject(function()director.validate_patch(rq)end,'allow_unverified_effect')
 reject(function()enemies.validate_patch(req(hd2.structure('cy_stratagem_blocker'),'jammer.radius',150,0))end,'reviewed range')
 reject(function()enemies.validate_patch(req(hd2.enemy('illuminate_dropship'),'transport.grid_dimension_0',5,6))end,'reviewed range')
 reject(function()enemies.validate_patch(req(hd2.enemy('Charger'),'unit.scale_max',1,2))end,'read-only')
 reject(function()hd2.enemy('il_mothership'):zone('body_default')end,'ambiguous')
 -- Exercise public patch/transaction/ensure routing, scheduler completion, and cheap steady-state verification.
 local session=require('hd2runtime/api/session').new(runtime,function()end)
 local function finish(w)
  w.tick(3.1)
  for _=1,20000 do w.tick(0.001);if w.status=='complete'or w.status=='rejected'then break end end
  assert(w.status=='complete'and w.result.status=='APPLIED',tostring(w.error));return w
 end
 reset()
 finish(session.patch(req(hd2.enemy('Charger'),'unit.scale_min',1,1.5)))
 local r=req(api.difficulty(10),'difficulty.encounter_points',600,450)
 finish(session.transaction({id='director-public-transaction',target=r.target,
  allow_shared=true,allow_unverified_effect=true,changes={{field=r.field,expect=r.expect,value=r.value}}}))
 reset()
 r.id='director-plan-operation'
 finish(session.plan({id='director-public-plan',operations={r}}))
 reset()
 local ensure=session.ensure({patch=req(api.demolition_template('OrbitalBombardment'),'demolition.force',50,45),startup_delay=0})
 for _=1,20000 do ensure.tick(0.001);if ensure.runs==1 or ensure.status=='rejected'then break end end
 assert(ensure.runs==1 and ensure.status=='waiting',tostring(ensure.error))
 local writes=counts.writes
 for _=1,1200 do ensure.tick(1)end
 assert(ensure.runs==1 and counts.writes==writes,'steady ensure repeated its writes')
 ensure.cancel();reset()
 result.coverage.publicApi={patch=true,transaction=true,plan=true,ensure=true,steadyState=true}
 source.close();result.writes=counts.writes;result.protectionChanges=counts.protection_changes
 return result
end)
local ok,out
repeat ok,out=coroutine.resume(worker)until not ok or coroutine.status(worker)=='dead'
assert(ok,out);return json.encode(out)
'''


def validate(snapshot=SNAPSHOT):
    sys.path.insert(0,str(ROOT/'sdk'))
    from tools.lua_runner import execute
    preload='\n'.join('package.preload['+lua(name)+']=function(...) return assert(loadstring('+lua(body)+','+lua(name)+'))(...) end' for name,body in sources().items())
    return json.loads(execute((preload+'\nlocal SNAPSHOT_PATH='+lua(Path(snapshot).resolve())+'\n'+PROGRAM).encode()))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,default=SNAPSHOT)
    p.add_argument('--output',type=Path,default=ROOT/'validation/enemy-controls-snapshot.json');a=p.parse_args()
    result=validate(a.snapshot);a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,indent=2))
