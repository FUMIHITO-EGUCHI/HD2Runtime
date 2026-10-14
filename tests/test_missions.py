import unittest
from support import run
import generate_missions

class MissionTests(unittest.TestCase):
    def test_shared_timer_ownership_uses_source_identity(self):
        self.assertEqual(run(r'''
local W=require('hd2runtime/domains/mission_writes')
local S=require('hd2runtime/core/shared_records')
local D=require('hd2runtime/domains/missions')
local first=D.missions[1];local source=D.sources[first.source]
local spec=W.validate_patch({id='mission-owner',target={resource='mission',mission=first.id},
 field='mission.duration_seconds',expect=source.currentDefault,value=2500,allow_shared=true,allow_unverified_effect=true})
S.claim(spec,'patch','mods/test/mission')
local alias=W.fields(source.missions[#source.missions])[1]
local holders=S.holders(alias,spec.changes[1].desired)
assert(holders[1].holds and holders[1].mod=='mods/test/mission')
assert(S.describe(alias):find('mission ',1,true))
assert(S.holders(alias,spec.changes[1].expected)[1].holds~=true)
return 'ok'
'''),b'ok')

    def test_diagnostic_failure_is_read_only_and_non_throwing(self):
        self.assertEqual(run(r'''
local h=require('hd2runtime/api/hd2')
assert(type(h.diagnostics.mission_timer)=='function')
local world=require('hd2runtime/runtime/event_world')
world.set_runtime({module=function()error('test: unavailable game')end})
local result,why=h.diagnostics.mission_timer()
assert(result==nil and why:find('test: unavailable game',1,true))
return 'ok'
'''),b'ok')

    def test_timer_freeze_refusals_write_nothing(self):
        # The host controls it (a client gets HOST_ONLY; a client follows through follow(), never the host); HVA timers
        # are released by the mission; the acknowledgement is the caller's own. Freeze and resume themselves: research
        # validate_mission_timer_freeze.
        self.assertEqual(run(r'''
local h=require('hd2runtime/api/hd2')
local F=require('hd2runtime/runtime/mission_timer_freeze')
local D=require('hd2runtime/runtime/mission_timer_diagnostics')
local tx=require('hd2runtime/core/guarded_transaction')
local applied=0;local apply=tx.apply;tx.apply=function(...)applied=applied+1;return apply(...)end
assert(type(h.freeze_mission_timer)=='function')
local r,code=h.freeze_mission_timer({frozen=true});assert(not r and code=='ACKNOWLEDGEMENT_REQUIRED')
assert(not pcall(h.freeze_mission_timer,{frozen='yes',allow_unverified_effect=true}))
assert(not pcall(h.freeze_mission_timer,{frozen=true,allow_unverified_effect=true,all=true}))
assert(not pcall(F.follow,'yes'))
local report={state='Mission',host=false,active={remainingSeconds=1800,paused=false,expired=false}}
local handle={world={},manager=0,slot=0,entity=0,id=1,source='terminids/mode_1'}
local locate=D.locate
D.locate=function(pins)assert(pins and#pins>0,'the freeze pins are proven too');return report,handle end
r,code=h.freeze_mission_timer({frozen=true,allow_unverified_effect=true});assert(not r and code=='HOST_ONLY',code)
report.host=true
r,code=F.follow(true);assert(not r and code=='NOT_APPLICABLE','the host never follows: '..tostring(code))
handle.source='delta/857c2cd17f827849'
r,code=h.freeze_mission_timer({frozen=true,allow_unverified_effect=true});assert(not r and code=='NOT_APPLICABLE',code)
report.host=false;r,code=F.follow(true);assert(not r and code=='NOT_APPLICABLE',code)
D.locate=function()return {state='Ship',active=false},nil end
r,code=h.freeze_mission_timer({frozen=true,allow_unverified_effect=true});assert(not r and code=='TARGET_UNAVAILABLE',code)
D.locate=function()error('mission diagnostic code changed: pause check')end
r,code=h.freeze_mission_timer({frozen=true,allow_unverified_effect=true});assert(not r and code=='TARGET_UNAVAILABLE',code)
D.locate,tx.apply=locate,apply
assert(applied==0,'a refusal reached the write')
return 'ok'
'''),b'ok')

    def test_timer_freeze_lobby_sync(self):
        # The host publishes hd2mt/1;<0|1>;<seq> (and 0 once out of the mission); a client in a mission follows the host's
        # value, never another member's; a new mission starts unpaused; a refusal is retried and logged once.
        self.assertEqual(run(r'''
local sync=require('hd2runtime/runtime/mission_timer_sync');sync.reset_for_tests()
local logmod=require('hd2runtime/runtime/log');local emit=logmod.emit;local logged={}
logmod.emit=function(t)logged[#logged+1]=t end
local function count(text)local n=0;for _,l in ipairs(logged)do if l:find(text,1,true)then n=n+1 end end;return n end
local F=require('hd2runtime/runtime/mission_timer_freeze')
local channel=require('hd2runtime/runtime/peer_channel')
local W=require('hd2runtime/runtime/event_world')
assert(channel.KEYS.hd2mt)
assert(sync.parse('hd2mt/1;1;7')==true and select(2,sync.parse('hd2mt/1;1;7'))==7)
assert(sync.parse('hd2mt/1;0;3')==false and sync.parse('hd2mt/2;1;1')==nil and sync.parse('x')==nil and sync.parse(nil)==nil)
local posts,values,game={},{},{mission=true,host=true,mode_entity=5}
local open,state,publish,lobby,poll,follow=W.open,W.game_state,channel.publish,channel.lobby,channel.poll,F.follow
W.open=function()return {}end
W.game_state=function()return game end
channel.publish=function(value,by,key)assert(key=='hd2mt');posts[#posts+1]=value;return {status='posted'}end
channel.lobby=function()return {members={'A','B','C'},host_peer='A'}end
channel.poll=function(_,opts)assert(opts.key=='hd2mt')
  return {values={{peer='A',value=values.A},{peer='C',value=values.C}}}end
-- The host: nothing published before the first freeze; then on every change; 0 once it left the mission.
sync.step_for_tests();assert(#posts==0)
sync.host_set(true);assert(posts[1]=='hd2mt/1;1;1')
sync.step_for_tests();assert(#posts==1,'unchanged: not posted again')
sync.host_set(false);assert(posts[2]=='hd2mt/1;0;2')
sync.host_set(true);game={mission=false,host=true}
sync.step_for_tests();assert(posts[#posts]=='hd2mt/1;0;4',posts[#posts])
-- A client: follows the host only.
local calls={}
F.follow=function(frozen)calls[#calls+1]=frozen;return {status='APPLIED',frozen=frozen,remainingSeconds=1500}end
game={mission=true,host=false,mode_entity=9}
values.C='hd2mt/1;1;1'
sync.step_for_tests();assert(#calls==0,'another member\'s value is ignored; the new mission stays unpaused')
values.A='hd2mt/1;1;3';sync.step_for_tests();assert(calls[1]==true)
sync.step_for_tests();assert(#calls==1,'applied once')
values.A='hd2mt/1;0;4';sync.step_for_tests();assert(calls[2]==false)
-- A refusal: retried every step, logged once.
values.A='hd2mt/1;1;5'
F.follow=function(frozen)calls[#calls+1]=frozen;return nil,'TARGET_UNAVAILABLE','not yet'end
sync.step_for_tests();sync.step_for_tests();assert(#calls==4)
assert(count('this machine cannot follow (TARGET_UNAVAILABLE: not yet); retried')==1)
-- A new mission: the previous one's state is not carried.
F.follow=function(frozen)calls[#calls+1]=frozen;return {status='APPLIED',frozen=frozen,remainingSeconds=2400}end
sync.step_for_tests();assert(calls[#calls]==true)
game={mission=true,host=false,mode_entity=10};values.A='hd2mt/1;0;6'
local n=#calls;sync.step_for_tests();assert(#calls==n,'unpaused new mission: nothing to do')
W.open,W.game_state,channel.publish,channel.lobby,channel.poll,F.follow=open,state,publish,lobby,poll,follow
logmod.emit=emit
return 'ok'
'''),b'ok')

    def test_generated(self):
        self.assertEqual(generate_missions.generate(check=True),[])

    def test_catalogue_and_validation(self):
        self.assertEqual(run(r'''
local h=require('hd2runtime/api/hd2')
local W=require('hd2runtime/domains/mission_writes')
local domains=require('hd2runtime/domains/write_domains')
assert(#h.missions()==162)
assert(#h.missions({faction='terminids'})==59)
assert(#h.missions({faction='automatons'})==58)
assert(#h.missions({faction='illuminate'})==45)
assert(domains.for_kind('mission')==W and domains.for_resource('mission')==W)
assert(h.fields.mission.duration_seconds=='mission.duration_seconds')
local groups={}
for _,m in ipairs(h.missions())do
 local t=h.mission(m.id);local d=t:describe();local f=d.fields[1]
 groups[d.timerGroup]=true
 assert(f.currentDefault>=60 and #d.sharedWith>0)
 local r={id='test',target=t,field=f.semanticFieldId,expect=f.currentDefault,value=1800,
   allow_shared=true,allow_unverified_effect=true}
 assert(W.validate_patch(r).kind=='mission')
 for _,value in ipairs({-1,0,59,2501,7200,math.huge})do r.value=value;assert(not pcall(W.validate_patch,r))end
 r.value=2500;assert(W.validate_patch(r).kind=='mission','the 2500-second ceiling itself is accepted')
 r.value=0/0;assert(not pcall(W.validate_patch,r));r.value=1800
 r.allow_shared=false;assert(not pcall(W.validate_patch,r));r.allow_shared=true
 r.allow_unverified_effect=false;assert(not pcall(W.validate_patch,r));r.allow_unverified_effect=true
 r.expect=1;assert(not pcall(W.validate_patch,r))
 if m.name:find('Blitz:',1,true)then assert(f.currentDefault==720)end
 if m.name=='Evacuate High-Value Assets'then assert(f.currentDefault==1200)end
 d.sharedWith[1]='mutated';assert(t:describe().sharedWith[1]~='mutated')
 d.fields[1].sharedWith[1]='mutated';assert(t:describe().fields[1].sharedWith[1]~='mutated')
end
local n=0;for _ in pairs(groups)do n=n+1 end;assert(n==19)
assert(not pcall(h.missions,{faction='bad'}));assert(not pcall(h.mission,'bad'))
return 'ok'
'''),b'ok')

    def test_game_text_identity(self):
        self.assertEqual(run(r'''
local text=require('hd2runtime/api/text')
local h=require('hd2runtime/api/hd2')
local kinds=text.KINDS.mission()
local count=0
for _,m in ipairs(h.missions())do
 assert(type(kinds[m.id].nameText.name)=='number'and kinds[m.id].nameText.name>0)
 count=count+1
end
assert(count==162)
return 'ok'
'''),b'ok')

if __name__=='__main__':unittest.main()
