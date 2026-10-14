"""Knife launch and melee contracts, native ownership, and reversible writes."""
import unittest
from support import run


class KnifeMeleeTests(unittest.TestCase):
    def test_catalogues_and_public_targets(self):
        import generate_melee_authoring
        import generate_throwable_authoring
        self.assertEqual(generate_melee_authoring.generate(check=True),[])
        self.assertEqual(generate_throwable_authoring.generate(check=True),[])
        self.assertEqual(run(r'''
local h=require('hd2runtime/api/hd2')
local W=require('hd2runtime/domains/melee_writes')
local D=require('hd2runtime/domains/melee_authoring')
assert(#h.melee.names()==112)
assert(h.fields.melee.volume_z=='melee.volume_z')
assert(h.fields.throwable.launch_speed_override=='throwable.launch_speed_override')
assert(#h.throwable('K-2 Throwing Knife'):flight():describe().fields==11)
assert(#h.melee('CQC-20 Breaching Hammer'):zones()==2)
assert(#h.melee('CQC-42 Machete'):zones()==1)
local key=require('hd2runtime/core/shared_records').key
local a=D.entries['AR-23 Liberator'].targets.zone_1.fields['melee.volume_z']
local c=D.entries['AR-23A Liberator Carbine'].targets.zone_1.fields['melee.volume_z']
assert(key(a.backing)==key(c.backing),'shared gun-bash volume identity')
local function request(v)
 return {id='melee',target=h.melee('CQC-2 Saber'):zone(1),field='melee.volume_z',expect=0.85,value=v,
  allow_shared=true,allow_unverified_effect=true}
end
assert(W.validate_patch(request(1.5)).kind=='melee')
for _,v in ipairs({0,-1,21,0/0,math.huge})do assert(not pcall(W.validate_patch,request(v)))end
local q=request(1.5);q.target.extra=true;assert(not pcall(W.validate_patch,q))
assert(not pcall(function()h.melee('CQC-2 Saber'):zone('missing')end))
return 'ok'
'''),b'ok')

    def test_snapshot_overlay_roundtrips_and_corruptions(self):
        import validate_knife_melee_snapshot
        result=validate_knife_melee_snapshot.validate()
        self.assertEqual(result['status'],'VALIDATED')
        self.assertEqual(result['fields'],3497)
        self.assertEqual(result['flightFields'],253)
        self.assertEqual(len(result['roundTrips']),39)
        self.assertIn('weapon ability link',result['rejections'])
        self.assertFalse(result['liveGameTested'])
