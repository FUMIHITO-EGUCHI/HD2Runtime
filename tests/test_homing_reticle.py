import unittest
from homing_test_support import run

PRELUDE=r'''
local Hud=require('hd2runtime/runtime/homing_reticle')

calls={create=0,destroy=0,triangles=0,rects=0,rect_updates=0,texts=0,text_updates=0,temps=0}
guis={};next_id=0;live_worlds={'main','ui'};font_ready=true;fail_rect=false
local function finite(n)return type(n)=='number' and n==n and math.abs(n)<100000 end
local function vector(...)local t={...};for _,v in ipairs(t)do assert(finite(v))end;return t end
S={Application={worlds=function()return live_worlds end,main_world=function()return'main'end,
can_get=function()return font_ready end},World={},Gui={},Vector2=vector,Vector3=vector,Color=vector,
Script={temp_count=function()return 99 end,set_temp_count=function(n)assert(n==99);calls.temps=calls.temps+1 end}}
S.World.create_screen_gui=function(world,mode,x,y)
 assert(world=='ui' and mode=='scale' and x==1 and y==1)
 calls.create=calls.create+1;local gui={world=world,rects={},texts={}};guis[#guis+1]=gui;return gui
end
S.World.destroy_gui=function(world,gui)
 local found=false;for _,w in pairs(live_worlds)do if w==world then found=true end end
 assert(found,'destroy on dead world');assert(not gui.dead);gui.dead=true;calls.destroy=calls.destroy+1
end
S.Gui.resolution=function()return 1920,1080 end
S.Gui.triangle=function(gui,a,b,c,layer,color)
 assert(not gui.dead and a[2]==0 and b[2]==0 and c[2]==0)
 assert(layer>=0 and layer<=1023);calls.triangles=calls.triangles+1
end
S.Gui.rect=function(gui,pos,size,color)
 if fail_rect then error('injected GUI failure')end
 assert(not gui.dead and size[1]>0 and size[2]>0)
 next_id=next_id+1;gui.rects[next_id]={pos=pos,size=size,color=color};calls.rects=calls.rects+1;return next_id
end
S.Gui.update_rect=function(gui,id,pos,size,color)
 assert(not gui.dead and gui.rects[id]);assert(size[1]>0 and size[2]>0)
 gui.rects[id]={pos=pos,size=size,color=color};calls.rect_updates=calls.rect_updates+1
end
S.Gui.destroy_rect=function(gui,id)assert(not gui.dead and gui.rects[id]);gui.rects[id]=nil end
S.Gui.text=function(gui,text,font,size,material,pos,color)
 assert(font_ready and not gui.dead);assert(font=='core/performance_hud/monaco' and material==font)
 next_id=next_id+1;gui.texts[next_id]={text=text,pos=pos,color=color};calls.texts=calls.texts+1;return next_id
end
S.Gui.update_text=function(gui,id,text,font,size,material,pos,color)
 assert(font_ready and not gui.dead and gui.texts[id]);gui.texts[id]={text=text,pos=pos,color=color}
 calls.text_updates=calls.text_updates+1
end
S.Gui.destroy_text=function(gui,id)assert(not gui.dead and gui.texts[id]);gui.texts[id]=nil end
View={project=function(frame,target)
 if target.behind then return nil end
 return {x=target.x,y=target.y,depth=target.z}
end,radius=function(frame,angle)return frame.radius or 120 end}
frame={width=1920,height=1080,world='main',ui_world='ui',sr=S}
function snapshot()return {visible=true,frame=frame,session='one',half_angle=12,max_targets=3,mode='multi',
locked={{key='b',x=1200,y=600,z=10}},acquiring={{key='a',x=500,y=300,z=10,progress=.25}}}end
logs={};function make()return Hud.new({view=View,log=function(text)logs[#logs+1]=text end})end
function text_present(wanted)
 for _,gui in ipairs(guis)do if not gui.dead then for _,item in pairs(gui.texts)do
  if item.text:find(wanted,1,true)then return true end end end end
 return false
end
function live_gui_count()local n=0;for _,gui in ipairs(guis)do if not gui.dead then n=n+1 end end;return n end

'''

class ReticleTests(unittest.TestCase):
    def test_style_bounds_colours_shapes_and_two_owners_do_not_interfere(self):
        self.check('''
local a=Hud.new({view=View,style={marker_shape='cross',marker_size=20,ring_color='#FF000080',
 ring_width=4,ring_segments=24,show_labels=false,show_numbers=false,show_los=false}})
local s=snapshot();a:update(s)
assert(calls.triangles==48 and calls.texts==0)
local b=Hud.new({view=View,style={marker_shape='box',locked_color={0,255,0}}})
b:update(s);assert(live_gui_count()==4 and a:status().state=='drawing')
a:shutdown();assert(live_gui_count()==2 and b:status().state=='drawing')
for _,bad in ipairs({{marker_shape='triangle'},{ring_width=0},{ring_segments=129},
 {marker_size=0/0},{locked_color='#xyz'},{show_labels=1},{unknown_key=1}})do
 assert(not pcall(Hud.new,{view=View,style=bad}),'invalid style accepted')
end
assert(b:status().state=='drawing')
''')

    def check(self,body):self.assertEqual(run(PRELUDE+body,('runtime/homing_reticle_style','runtime/homing_reticle')),b'ok')

    def test_idle_invisible_snapshot_does_not_emit_two_log_lines_every_frame(self):
        self.check('''
local h=Hud.new({view=View,log=function(text)logs[#logs+1]=text end,
 blocked=function()return true,'not_aiming'end})
local s=snapshot();s.visible=false
for i=1,30 do h:tick();h:update(s)end
assert(#logs<=2,'hidden/suppressed status oscillated while nothing was drawn')
assert(live_gui_count()==0)
''')

    def test_los_label_is_independent_of_locked_state(self):
        self.check('''
local h=make();local s=snapshot();s.locked[1].los='blocked';h:update(s)
assert(text_present('LOCK') and text_present('LOS BLOCKED'))
s.locked[1].los='clear';h:update(s);assert(text_present('LOS CLEAR') and not text_present('LOS BLOCKED'))
s.locked[1].los='unknown';h:update(s);assert(text_present('LOS ?') and not text_present('LOS CLEAR'))
''')

    def test_menu_open_hides_existing_gui_without_waiting_for_engine_observation(self):
        self.check('''
local blocked=false
local h=Hud.new({view=View,blocked=function()return blocked,'escape_menu'end})
local s=snapshot();h:update(s);assert(live_gui_count()==2)
blocked=true;h:tick();assert(live_gui_count()==0 and h:status().reason=='escape_menu')
h:update(s);assert(live_gui_count()==0)
blocked=false;h:tick();assert(live_gui_count()==0,'do not redraw an old camera frame')
h:update(s);assert(live_gui_count()==2)
''')

    def test_ring_and_target_markers_are_retained_and_snapshot_is_not_modified(self):
        self.check('''
local h=make();local s=snapshot();h:update(s,.016)
assert(h:status().state=='drawing' and h:status().markers==2)
assert(calls.create==2 and calls.triangles==192 and calls.rects>16)
assert(text_present('LOCK') and text_present('25%'))
local rc,tc=calls.rects,calls.texts;local count=calls.temps
h:update(s,.016)
assert(calls.create==2 and calls.triangles==192 and calls.rects==rc and calls.texts==tc)
assert(calls.rect_updates==0 and calls.text_updates==0 and calls.temps>count)
assert(s.acquiring[1].progress==.25 and s.acquiring[1].key=='a' and s.locked[1].key=='b')
''')

    def test_promotion_and_motion_keep_numbers_and_gui_handles(self):
        self.check('''
local h=make();local s=snapshot();h:update(s,.016)
local numbers=h:status().numbers;local a,b=numbers.a,numbers.b
assert(a~=b and a>=1 and b<=6)
s.locked={{key='a',x=510,y=320,z=10},{key='b',x=1190,y=600,z=10}};s.acquiring={}
h:update(s,.016)
assert(calls.create==2 and calls.destroy==0 and calls.triangles==192)
assert(h:status().numbers.a==a and h:status().numbers.b==b and h:status().locked==2)
assert(calls.rect_updates>0 and text_present('LOCK') and not text_present('25%'))
''')

    def test_radius_change_rebuilds_only_ring_and_resolution_rebuilds_both(self):
        self.check('''
local h=make();local s=snapshot();h:update(s,.016)
frame.radius=140;h:update(s,.016)
assert(calls.create==3 and calls.destroy==1 and calls.triangles==384)
frame.radius=140.1;h:update(s,.016);assert(calls.create==3)
frame.width=2560;frame.height=1440;h:update(s,.016)
assert(calls.create==5 and calls.destroy==3 and h:status().markers==2)
''')

    def test_hidden_shutdown_and_session_changes_clear_owned_primitives(self):
        self.check('''
local h=make();local s=snapshot();h:update(s,.016)
s.session='two';h:update(s,.016);assert(calls.destroy==2 and calls.create==4)
s.visible=false;h:update(s,.016)
assert(calls.destroy==4 and live_gui_count()==0 and h:status().state=='hidden')
s.visible=true;h:update(s,.016);assert(live_gui_count()==2)
h:shutdown();assert(live_gui_count()==0 and h:status().state=='stopped')
local count=calls.create;h:update(s,.016);assert(calls.create==count)
''')

    def test_dead_world_is_never_passed_to_native_destroy(self):
        self.check('''
local h=make();local s=snapshot();h:update(s,.016)
live_worlds={'main'};h:update(s,.016)
assert(calls.destroy==0 and h:status().state=='unavailable')
h:shutdown();assert(calls.destroy==0)
''')

    def test_ui_world_must_be_distinct_and_camera_projection_uses_bottom_origin(self):
        self.check('''
local h=make();local s=snapshot();s.locked={};h:update(s,.016)
for _,gui in ipairs(guis)do if not gui.dead then for _,item in pairs(gui.rects)do
 assert(item.pos[2]>270 and item.pos[2]<340,'unexpected top-origin conversion')
end end end
frame.ui_world='main';h:update(s,.016)
assert(h:status().state=='unavailable' and calls.create==2 and live_gui_count()==0)
''')

    def test_bad_geometry_and_offscreen_targets_are_never_submitted(self):
        self.check('''
local h=make();local s=snapshot()
s.locked={{key='nan',x=0/0,y=100,z=10},{key='left',x=-100,y=100,z=10},
 {key='behind',x=100,y=100,z=-1},{key='far',x=2000,y=400,z=10}}
s.acquiring={};h:update(s,.016)
assert(h:status().markers==0 and calls.rects==0 and calls.texts==0)
frame.width=0/0;h:update(s,.016)
assert(h:status().state=='unavailable')
''')

    def test_font_unavailable_keeps_numbered_geometry_and_progress_without_font_calls(self):
        self.check('''
font_ready=false;local h=make();local s=snapshot();h:update(s,.016)
assert(h:status().markers==2 and not h:status().text_supported)
assert(h:status().reason=='font_unavailable' and calls.texts==0 and calls.rects>16)
local n=h:status().numbers;assert(n.a and n.b and n.a~=n.b)
font_ready=true;h:update(s,.016);assert(calls.create==2 and calls.texts==4)
font_ready=false;h:update(s,.016);assert(not text_present('LOCK'))
''')

    def test_six_target_limit_duplicates_and_retired_number_reuse_are_bounded(self):
        self.check('''
local h=make();local s=snapshot();s.locked={};s.acquiring={};s.max_targets=6
for i=1,10 do s.locked[i]={key='t'..i,x=100+i*50,y=100,z=10}end
h:update(s,.016);assert(h:status().markers==6)
local old=h:status().numbers
s.locked={{key='t2',x=200,y=100,z=10},{key='t2',x=200,y=100,z=10},
 {key='new',x=300,y=100,z=10}};h:update(s,.016)
assert(h:status().markers==2 and h:status().numbers.t2==old.t2)
assert(h:status().numbers.new and h:status().numbers.t1==nil)
''')
