import unittest
from support import run


class SpawnMultiplierTests(unittest.TestCase):
    def test_channels_and_difficulties_do_not_cross_scopes(self):
        self.assertEqual(run(r'''
local api=require('hd2runtime/api/enemy_director')
local D=require('hd2runtime/domains/enemy_director')
local W=require('hd2runtime/domains/enemy_writes')
local DW=require('hd2runtime/domains/enemy_director_writes')
local families={patrol=1,map=3,reinforcement=4}
for _,faction in ipairs({'terminids','automatons','illuminate'})do
 local touched={}
 for channel,family in pairs(families)do
  local r=api.spawn_multiplier(faction,5,channel)
  assert(r.fields>0)
  for _,tx in ipairs(r.transactions)do
   assert(tx.target:describe().metadata.family==family)
   assert(not touched[tx.target.key],'channels overlap');touched[tx.target.key]=true
   DW.validate_transaction(tx)
   for _,c in ipairs(tx.changes)do
    if channel=='map'then
     assert(c.field=='composition.cost_multiplier'and c.value==c.expect/5,'map fill limit was changed')
    else assert(c.field:match('_count$'))end
   end
  end
 end
 for _,factor in ipairs({0.1,0.5,1,2,5})do
  local r=api.patrol_frequency(faction,factor);assert(r.fields>0)
  for _,tx in ipairs(r.transactions)do
   W.validate_transaction(tx);assert(#tx.changes==4)
   for _,c in ipairs(tx.changes)do
    assert(c.field:match('^hive%.patrol_clock_rate_players_[1-4]$'))
    assert(c.value==c.expect*factor,'clock multiplier compounded')
   end
  end
 end
end
for level=1,10 do
 for _,channel in ipairs({'encounter_budget','map_budget','spawner_frequency'})do
  for _,factor in ipairs({0.1,0.5,1,2,5})do
   local r=api.difficulty_multiplier(level,channel,factor)
   local tx=r.transactions[1];DW.validate_transaction(tx)
   assert(tx.target.key==tostring(level)and#tx.changes==1)
   local c=tx.changes[1]
   assert(c.value==(channel=='spawner_frequency'and c.expect/factor or c.expect*factor))
  end
 end
end
assert(not pcall(api.spawn_multiplier,'terminids',2,'invalid'))
assert(not pcall(api.difficulty_multiplier,11,'map_budget',2))
assert(not pcall(api.difficulty_multiplier,1,'counts',2))
assert(not pcall(api.patrol_frequency,'all',2))
assert(not pcall(api.patrol_frequency,'terminids',math.huge))
return 'ok'
'''),b'ok')

    def test_faction_recipes_are_guarded_counts_from_defaults(self):
        self.assertEqual(run(r'''
local api=require('hd2runtime/api/enemy_director')
local W=require('hd2runtime/domains/enemy_director_writes')
for _,faction in ipairs({'terminids','automatons','illuminate'})do
 for _,mult in ipairs({0.1,0.5,1,2,3,5})do
  local r=api.spawn_multiplier(faction,mult)
  assert(#r.transactions>0 and r.fields>100 and r.scope=='composition_counts')
  local count=0
  for _,tx in ipairs(r.transactions)do
   assert(tx.target:describe().metadata.faction==faction)
   local spec=W.validate_transaction(tx)
   assert(#spec.changes==#tx.changes)
   for _,c in ipairs(tx.changes)do
    assert(c.field:match('^composition%.group_%d+_count$'))
    assert(c.value<=math.min(32,math.floor(c.expect*mult+0.5)))
    if mult==1 then assert(c.value==c.expect)end
   count=count+1
   end
   local total=0;for _,c in ipairs(tx.changes)do total=total+c.value end
   assert(total<=32,'native squad queue overflow')
   assert(tx.target:describe().metadata.role~='map','999 map fill templates are not count-scaled')
  end
  assert(count==r.fields)
 end
end
assert(not pcall(api.spawn_multiplier,'all',2))
for _,bad in ipairs({0,-1,5.1,math.huge,0/0})do assert(not pcall(api.spawn_multiplier,'terminids',bad))end
local h=require('hd2runtime/api/hd2')
assert(h.fields.hive.patrol_clock_rate_players_1=='hive.patrol_clock_rate_players_1')
assert(h.fields.orbital.walking_speed=='orbital.walking_speed')
for i=1,10 do
 local icon=assert(h.resources.game_icon('difficulty',tostring(i)))
 assert(icon:describe().mode=='image')
 assert(h.asset_dependency(icon).known and h.asset_dependency(icon).autoLoadSupported)
end
return 'ok'
'''),b'ok')

    def test_squad_queue_limit_rejects_old_presets_and_combined_live_counts(self):
        self.assertEqual(run(r'''
local api=require('hd2runtime/api/enemy_director')
local W=require('hd2runtime/domains/enemy_director_writes')
local D=require('hd2runtime/domains/enemy_director')
local b=require('hd2runtime/core/bytes')
local row,fields
for _,r in pairs(D.rows)do if r.kind=='composition'and r.metadata.role=='patrol'then
 local counts={}
 for _,f in ipairs(r.fields)do if f.id:match('_count$')and f.currentDefault>0 then counts[#counts+1]=f end end
 if#counts==2 then row,fields=r,counts;break end
end end
assert(row)
local function request(a,c)
 return {id='capacity-test',target=api.composition(row.key),allow_shared=true,allow_unverified_effect=true,changes={
  {field=fields[1].id,expect=fields[1].currentDefault,value=a},
  {field=fields[2].id,expect=fields[2].currentDefault,value=c}}}
end
local ok,why=pcall(W.validate_transaction,request(17,16))
assert(not ok and tostring(why):find('SPAWN_CAPACITY',1,true),tostring(why))
assert(not pcall(W.validate_transaction,request(35,0)),'old 5x group accepted')
W.validate_transaction(request(16,16))
local spec=W.validate_patch({id='live-capacity',target=api.composition(row.key),allow_shared=true,
 allow_unverified_effect=true,field=fields[1].id,expect=fields[1].currentDefault,value=1})
local raw=b.unhex(row.hex);local off=fields[2].offset
raw=raw:sub(1,off)..b.encode(32,'u32')..raw:sub(off+5)
ok,why=pcall(W.prepare,{row=row,bytes=raw},{snapshots={}},spec)
assert(not ok and tostring(why):find('SPAWN_CAPACITY',1,true),'other operations bypassed total limit: '..tostring(why))
for _,faction in ipairs({'terminids','automatons','illuminate'})do
 local r=api.spawn_multiplier(faction,5,'patrol')
 assert(r.cappedCompositions>0 and r.maxCompositionCount==32)
 for _,tx in ipairs(r.transactions)do
  local sum=0;for _,c in ipairs(tx.changes)do sum=sum+c.value end
  assert(sum<=32);W.validate_transaction(tx)
 end
end
return 'ok'
'''),b'ok')
