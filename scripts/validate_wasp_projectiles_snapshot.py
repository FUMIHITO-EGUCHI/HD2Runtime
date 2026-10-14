"""Offline apply/reset and foreign-host refusal checks for both W.A.S.P. hit selectors."""
import json
from pathlib import Path
from validate_belt_urchin_snapshot import PROGRAM as BASE
from validate_entity_authoring_snapshot import ROOT, SNAPSHOT, lua, sources
START=BASE.index(' local weapon=h.support_weapon(')
END=BASE.index('end)\nlocal ok,out', START)
PROGRAM=BASE[:START]+r"""
 local weapon=h.support_weapon('StA-X3 W.A.S.P. Launcher')
 for _,src in ipairs({weapon:projectile_source(),weapon:feed('programmable'):source()})do
  assert(src.writable and src.target,json.encode(src))
  for _,donor in ipairs({'SG-225 Breaker','AR-23 Liberator'})do
   local req=request(src.target,src.field,src.expect,h.attack_output(donor))
   local spec,p,r=exercise(W,req)
   assert(#p.changes==1 and #p.changes[1].desired==4,'swap touched missile entity or other mode')
   local desc=spec.changes[1].descriptor
   assert(#desc.missileProjectileHost==2)
   -- Every mode validates both entities, including the carried-type fallback.
   for _,proof in ipairs(desc.missileProjectileHost)do
    for _,offset in ipairs({173,176})do
     reset();r=select(2,resolve(W,spec))
     local candidate
     for _,c in ipairs(r.catalog.candidates)do if c.resourceHash==proof.link.entity then candidate=c end end
     assert(candidate,'reviewed missile missing')
     local missile=r.catalog.record(candidate,proof.component)
     poke(missile.owner.base+missile.offset+offset,offset==173 and string.char(0)or b.encode(99,'u32'))
     local ok,why=pcall(function()resolve(W,spec)end)
     assert(not ok and tostring(why):find('MISSILE_HOST_CHANGED',1,true),tostring(why))
     result.rejections=result.rejections+1
    end
   end
   reset();r=select(2,resolve(W,spec))
   local pw=r.catalog.record(r.candidate,'ProjectileWeaponComponentData')
   poke(pw.owner.base+pw.offset+40,string.rep('\0',8))
   local ok,why=pcall(function()resolve(W,spec)end)
   assert(not ok and tostring(why):find('SPAWNED_ENTITY_CHANGED',1,true),tostring(why))
   result.rejections=result.rejections+1
   reset();req.allow_unverified_effect=false;assert(not pcall(W.validate_patch,req))
   result.rejections=result.rejections+1
  end
 end
 reset();source.close();return result
"""+BASE[END:]

def validate(snapshot=SNAPSHOT):
    import sys
    sys.path.insert(0,str(ROOT/'sdk'))
    from tools.lua_runner import execute
    preload='\n'.join('package.preload['+lua(n)+']=function(...) return assert(loadstring('+lua(s)+','+lua(n)+'))(...) end' for n,s in sources().items())
    return json.loads(execute((preload+'\nlocal SNAPSHOT_PATH='+lua(Path(snapshot).resolve())+'\n'+PROGRAM).encode()))
if __name__=='__main__':
    result=validate()
    (ROOT/'research/validation/wasp-projectiles-snapshot.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
