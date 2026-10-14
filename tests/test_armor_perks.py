import unittest
from support import run
import generate_armor_perks

class ArmorPerkTests(unittest.TestCase):
    def test_generated(self):
        self.assertEqual(generate_armor_perks.generate(check=True),[])

    def test_catalogue_and_validation(self):
        self.assertEqual(run(r'''
local h=require('hd2runtime/api/hd2')
local W=require('hd2runtime/domains/armor_perk_writes')
local domains=require('hd2runtime/domains/write_domains')
assert(domains.typed_kind('armor_perk')and domains.for_resource('armor_perk')==W)
assert(domains.for_kind('armor_perk')==W)
local fields=0
for _,p in ipairs(h.passives.list())do
 local t=h.passives.perk(p.name:lower());assert(t.armor_perk==p.id)
 local d=t:describe();assert(d.icon==p.icon and#d.icon==16)
 for _,f in ipairs(d.fields)do
  fields=fields+1
  local r={id='check',target=t,field=f.semanticFieldId,expect=f.currentDefault,value=f.currentDefault,
   allow_shared=true,allow_unverified_effect=true}
  assert(W.validate_patch(r).kind=='armor_perk')
  for _,v in ipairs({f.min-1,f.max+1,math.huge})do r.value=v;assert(not pcall(W.validate_patch,r))end
  r.value=0/0;assert(not pcall(W.validate_patch,r));r.value=f.currentDefault
  r.allow_shared=nil;assert(not pcall(W.validate_patch,r));r.allow_shared=true
  r.allow_unverified_effect=nil;assert(not pcall(W.validate_patch,r));r.allow_unverified_effect=true
  r.expect=999;assert(not pcall(W.validate_patch,r));r.expect=f.currentDefault
  r.target={resource='armor_perk',armor_perk=p.id,extra=true};assert(not pcall(W.validate_patch,r))
  d.fields[1].min=999;assert(t:fields()[1].min~=999,'public descriptor mutated validator')
 end
end
assert(fields==75 and#h.passives.perk(0):fields()==0)
assert(not pcall(h.passives.perk,4)and not pcall(h.passives.perk,'unknown'))
assert(h.fields.perk.radar_scan_interval=='perk.radar_scan_interval')
local gunslinger=h.passives.perk(18):fields();assert(gunslinger[2].currentDefault==1.6)
local feet=h.passives.perk(31):fields();assert(feet[3].semanticFieldId=='perk.leg_injury_immunity')
for _,f in ipairs(h.passives.perk(17):fields())do assert(f.semanticFieldId~='perk.death_explosion')end
return 'ok'
'''),b'ok')

    def test_atlas_residency_and_game_text(self):
        self.assertEqual(run(r'''
local h=require('hd2runtime/api/hd2')
local text=require('hd2runtime/api/text')
local names=h.resources.game_icons('passive');assert(#names==32)
local kinds=text.KINDS.passive()
for _,p in ipairs(h.passives.list())do
 local icon=assert(h.resources.game_icon('passive',p.name))
 local info=icon:describe();assert(info.mode=='image'and info.width>0)
 local asset=h.asset_dependency(icon);assert(asset.known and asset.autoLoadSupported and asset.package=='atlas_ship')
 assert(kinds[p.name].nameText.name>0)
end
return 'ok'
'''),b'ok')

    def test_claims_share_exact_field_identity(self):
        self.assertEqual(run(r'''
local h=require('hd2runtime/api/hd2');local W=require('hd2runtime/domains/armor_perk_writes')
local records=require('hd2runtime/core/shared_records');local own=require('hd2runtime/core/ownership')
local t=h.passives.perk(2);local f=t:fields()[1]
local spec=W.validate_patch({id='scout',target=t,allow_shared=true,allow_unverified_effect=true,
 field=f.semanticFieldId,expect=f.currentDefault,value=4})
records.claim(spec,'patch','mods/test/perk')
local state,owner=own.state(spec.changes[1],spec.changes[1].desired)
assert(state=='runtime'and owner=='mods/test/perk')
assert(records.describe(f):find('SCOUT',1,true))
return 'ok'
'''),b'ok')
