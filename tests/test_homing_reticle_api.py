import unittest
from homing_test_support import run

class ReticleApiTests(unittest.TestCase):
    def test_style_hide_replacement_and_stop_are_visual_only(self):
        self.assertEqual(run('''
local cancelled=0;local callback
package.preload['hd2runtime/runtime/events']=function()return{
 emit_log=function()end,frame=function(fn)callback=fn;return{cancel=function()cancelled=cancelled+1 end}end}end
package.preload['hd2runtime/runtime/homing_view']=function()return{project=function()end,radius=function()end}end
package.preload['hd2runtime/runtime/homing_visibility']=function()return{blocked=function()return true end}end
local handle={status='active',owner='mod/a',weapon='AR-23 Liberator',_lock={
 visual_snapshot=function()return{visible=false}end}}
local api=require('hd2runtime/api/homing_reticle')
local r=api.open(handle,{locked_color='#FFFFFF'});assert(r:status().visible)
local observer=handle._lock.on_visual
r:hide();assert(not r:status().visible and handle.status=='active')
r:style({marker_shape='cross',ring=false});r:show()
assert(handle._lock.on_visual==observer and handle.status=='active')
assert(not pcall(r.style,r,{ring_segments=1}));assert(r:status().visible)
callback();r:stop();r:stop();assert(cancelled==1 and handle._lock.on_visual==nil)
assert(handle.status=='active','HUD stop must not stop homing')
handle.status='refused';assert(not pcall(api.open,handle,{}))
''',('runtime/homing_reticle_style','runtime/homing_reticle','api/homing_reticle')),b'ok')
