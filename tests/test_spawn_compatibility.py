import unittest
from support import run


class SpawnCompatibilityTests(unittest.TestCase):
    def test_overlap_and_commit_guard_detect_late_load_without_reading_or_writing(self):
        run(r'''
local c=require('hd2runtime/runtime/spawn_compatibility')
assert(not c.status().blocked)
local targets={{resource='enemy_director',path='roster'},{resource='enemy_director',path='composition'},
 {resource='enemy_director',path='difficulty'},{resource='enemy'}}
PickYourBots={status='ready'}
for i,t in ipairs(targets)do assert(c.reason(t,i==4 and'hive.patrol_clock_rate_players_1'or''))end
assert(c.reason({resource='enemy'},'spawner.release_delay'))
for _,field in ipairs({'unit.scale','entity.health','attack.damage','zone.health','transport.grid_dimension_0'})do
 assert(not c.reason({resource='enemy'},field),field)
end
assert(not c.reason({resource='enemy_director',path='demolition_template'},'demolition.force'))
assert(not c.reason({resource='mission'},'mission.timer'))
local tx=require('hd2runtime/core/guarded_transaction')
local owner={base=65536}
local plan={snapshots={{owner=owner,offset=0,bytes='aaaa'}},changes={
 {owner=owner,offset=0,expected='aaaa',before='aaaa',desired='bbbb',compatibility_scope='enemy_spawns'}}}
local inverse=tx.inverse(plan)
local runtime=setmetatable({},{__index=function()error('ownership refusal must precede adapter access')end})
for _,p in ipairs({plan,inverse})do
 local result=tx.apply(runtime,p)
 assert(result.status=='REJECTED'and result.code==c.CODE and result.writes==0)
end
local D=require('hd2runtime/domains/enemy_director_writes')
local rows=require('hd2runtime/domains/enemy_director').rows
for key,row in pairs(rows)do if row.kind=='roster'then
 local ok,why=pcall(D.capture_many,runtime,runtime,{{row=key}})
 assert(not ok and tostring(why):find(c.CODE,1,true));break
end end
PickYourBots=nil;AllAutomatonReplace={status='disabled'}
assert(c.status().blocked,'loaded mod can enable its settings later')
AllAutomatonReplace=nil;assert(not c.plan_reason(plan.changes))
return 'ok'
''')

    def test_legacy_weight_api_and_enemy_prepare_cannot_bypass_owner(self):
        run(r'''
local c=require('hd2runtime/runtime/spawn_compatibility')
local weights=require('hd2runtime/runtime/enemy_spawn_weights')
PickYourBots={status='ready'}
local config,code=weights.configure({})
assert(not config and code==c.CODE)
local active={entity='test',owner='mods/test',label='test',status='applied',held={}}
weights.configs().test=active
weights.step();assert(active.status=='unavailable'and active.compatibility_status=='applied')
assert(weights.stop(active));assert(active.compatibility_status=='stopping','stop intent lost')
local ok,why=pcall(require('hd2runtime/domains/enemy_writes').prepare,nil,nil,
 {changes={{field='hive.patrol_clock_rate_players_1'}}})
assert(not ok and tostring(why):find(c.CODE,1,true))
return 'ok'
''')

    def test_gui_bridge_uses_normal_pump_restores_binding_and_handles_failure(self):
        run(r'''
local c=require('hd2runtime/runtime/spawn_compatibility')
PickYourBots={status='ready'}
local binding={poll=function()end,pressed=function()return false end,registered=false}
local settings_panel={open=false,sync=function()end}
local fail=false
local function pump()
 binding.poll()
 if fail then error('focus lost')end
 if binding.registered and binding.pressed()then settings_panel.open=true end
end
settings_panel.pump=function()return pump()end
local previous=function()settings_panel.pump()end
-- Actual installed packs include previous_update/game_update wrappers and private callback tables.
local function wrap(previous_update)return function(...)return previous_update(...)end end
local function opaque(game_update)
 local callbacks={update=game_update}
 return function(...)return callbacks.update(...)end
end
local function unexpected_name(saved_handler)return function(...)return saved_handler(...)end end
update=unexpected_name(opaque(wrap(wrap(previous))))
-- A performance observer may also wrap the panel's pump itself.
local function observe(fn)return function(...)return fn(...)end end
settings_panel.pump=observe(settings_panel.pump)
local poll,pressed=binding.poll,binding.pressed
local closed=0
assert(c.open_gui(function()closed=closed+1 end))
assert(settings_panel.open and closed==1)
assert(binding.poll==poll and binding.pressed==pressed and not binding.registered)
settings_panel.open=false;fail=true
local ok,why=c.open_gui()
assert(not ok and why:find('focus lost',1,true))
assert(binding.poll==poll and binding.pressed==pressed and not binding.registered)
update=nil;assert(not c.open_gui())
PickYourBots.open_settings=function()return false,'unavailable'end
local ok,why=c.open_gui();assert(not ok and why=='unavailable')
PickYourBots.open_settings=function()settings_panel.open=true end
assert(c.open_gui())
return 'ok'
''')
