import json
import unittest
from support import ROOT, run

class HeatsinkAttachmentTests(unittest.TestCase):
    def test_catalog_and_api(self):
        data=json.loads((ROOT/'sdk/HeatsinkAttachmentCapabilities.json').read_text())
        self.assertEqual(data['summary']['attachments'],9)
        self.assertEqual(data['summary']['fieldInstances'],50)
        self.assertTrue(all(f['allowSharedRequired'] and f['editable'] for f in data['fieldInstances']))
        run(r"""
local hd2=require('hd2runtime/api/hd2')
local p=require('hd2runtime/domains/patches')
local s=hd2.weapon('LAS-5 Scythe')
assert(#s:magazine_attachments()==3)
assert(#hd2.weapon('LAS-22 Shear'):magazine_attachments()==1)
assert(#hd2.weapon('LAS-12 Sai'):magazine_attachments()==3)
local t=s:magazine_attachment()
assert(t:describe().kind=='heatsink')
local r={id='heatsink',target=t,field=hd2.fields.heatsink.spare,expect=4,value=5}
assert(not pcall(p.validate,r));r.allow_shared=true;assert(not pcall(p.validate,r))
r.allow_unverified_effect=true;p.validate(r)
r.value=-1;assert(not pcall(p.validate,r))
assert(hd2.weapon_attachment('Laser Heatsink (Charge). Extended Heatsink'))
assert(hd2.weapon_attachment('Laser Heatsink (Charge). Rapid Heatsink'))
assert(hd2.weapon('AR-23 Liberator'):magazine_attachment():describe().kind=='magazine')
return 'ok'
""")
