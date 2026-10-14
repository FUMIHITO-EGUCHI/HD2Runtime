"""Typed HUD atlas residency: exact ownership, asynchronous loading, deduplication, local scope."""
import unittest
from support import run

class HudAssetLoadingTests(unittest.TestCase):
    def test_icon_packages_load_once_and_remain_local(self):
        self.assertEqual(run(r'''
local h=require('hd2runtime/api/hd2')
local api=require('hd2runtime/api/assets')
local assets=require('hd2runtime/core/assets')
local sync=require('hd2runtime/runtime/asset_sync')
assets.reset();sync.reset_for_tests()
local rifle=h.resources.game_icon('weapon','AR-23 Liberator')
local grenade=h.resources.game_icon('throwable','G-31 Arc')
local faction=h.resources.game_icon('faction','automatons')
assert(h.asset_dependency(rifle).package=='atlas_mission')
assert(h.asset_dependency(grenade).package=='atlas_mission')
assert(h.asset_dependency(faction).package=='atlas_shared')
-- The private handle identity wins over caller-mutated display fields.
rifle.kind='faction';rifle.name='automatons'
assert(h.asset_dependency(rifle).package=='atlas_mission')
local calls,loaded={},{}
assets.prove=function()return {instance=1,request=2,capacity=1024}end
local runtime={mode='simulated',read=function(_,n)return string.rep('\0',n)end,
 package_request=function(_,_,id)calls[id]=(calls[id]or 0)+1 end,
 package_state=function(id)return loaded[id]and'resident'or'queued'end}
local watch=api.start(runtime,function()end,{id='hud',targets={rifle,grenade,faction}})
watch.tick(0.3);assert(watch.status=='waiting_for_assets')
assert(#assets.holdings()==2)
for _,n in pairs(calls)do assert(n==1,'shared atlas requested twice')end
assert(#sync.status().shared==0,'UI-only packages must not be broadcast to the lobby')
for _,d in ipairs(watch.asset_dependencies)do loaded[d.package]=true end
watch.tick(0.3);assert(watch.status=='complete'and watch.result.status=='RESIDENT')
local again=api.start(runtime,function()end,{id='hud-again',target=grenade})
again.tick(0.3);assert(again.status=='complete')
for _,n in pairs(calls)do assert(n==1)end
local timeout=api.start(runtime,function()end,{id='hud-timeout',target=grenade})
loaded={};timeout.tick(91);assert(timeout.status=='rejected'and timeout.result.code=='ASSET_UNAVAILABLE')
assert(not h.asset_dependency({kind='weapon',name='AR-23 Liberator'}).known,'forged handle')
return 'ok'
'''),b'ok')

    def test_every_new_icon_has_a_proven_atlas_dependency(self):
        self.assertEqual(run(r'''
local h=require('hd2runtime/api/hd2')
local packages={};local count=0
for _,kind in ipairs({'weapon','throwable','faction','objective'})do
 for _,name in ipairs(h.resources.game_icons(kind))do
  local d=h.asset_dependency(h.resources.game_icon(kind,name))
  assert(d.known and d.autoLoadSupported and d.derivation=='hud_atlas_package',name)
  packages[d.package]=true;count=count+1
 end
end
assert(count==283 and packages.atlas_mission and packages.atlas_shared)
return 'ok'
'''),b'ok')
