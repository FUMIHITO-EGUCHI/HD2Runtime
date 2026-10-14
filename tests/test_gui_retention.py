"""Retained monitor geometry, text cache correctness and profiler attribution."""
import unittest
from support import run
from test_ui_overlay import HARNESS
from test_perf_watch import PRELUDE
from test_game_font_text import OVERLAY


class GuiRetentionTests(unittest.TestCase):
    def test_retained_text_follows_fallback_font_residency_and_resolution(self):
        run(HARNESS+OVERLAY+r'''
local builds=0
local ov=hd2.ui.overlay({owner='mods/t/retained-cjk'})
ov:draw(function(d)
 d:_retain('label',1,function(d)
  builds=builds+1
  d:text('Score 中文',10,100,{size=20})
 end)
end)
frames(1);local n=#calls;frames(5)
assert(builds==1 and #calls==n,'fresh font list with same fonts invalidated cache')
assert(ov:status().game_fonts[1]=='zh_hans')
RESIDENT.zh_hans=false;frames(1)
assert(builds==2 and #ov:status().game_fonts==0,'unloaded game font retained')
local n=#calls;frames(3);assert(#calls==n and builds==2)
RESIDENT.zh_hans=true;frames(1)
assert(builds==3 and ov:status().game_fonts[1]=='zh_hans','new fallback font not used')
-- Feed updated screen bounds into the builder; size is part of the retained layout key.
W,H=1280,720;ov.screen.width,ov.screen.height=W,H;frames(1)
assert(builds==4 and ov:status().items==2,'resolution change did not rebuild')
local n=#calls;frames(3);assert(#calls==n and builds==4)
return 'ok'
''')

    def test_retained_group_reuses_layout_but_keeps_input_and_ids_correct(self):
        run(HARNESS+r'''
local builds,inputs,extra=0,0,0
O.hooks.game_fonts=function()extra=extra+1;return{}end
local ov=hd2.ui.overlay({owner='mods/t/retained'})
local revision,insert=1,false
ov:draw(function(d)
 inputs=inputs+1
 if insert then d:rect(0,0,5,5,{4,5,6})end
 d:_retain('graph',revision,function(d)
  builds=builds+1
  for i=1,10 do d:rect(20,i*10,20,8,{i,20,30})end
  d:text('Graph label',20,150,{align='right'})
 end)
 d:wrap('ASCII footer',200,{size=12,lines=1})
end)
frames(1);local n=#calls
frames(30)
assert(builds==1 and inputs==31 and #calls==n,'cached layout changed or input stopped')
assert(extra==0,'ASCII wrap queried game language fonts')
-- Positional reconciliation must never mutate cached IDs when a preceding hover item appears.
insert=true;frames(1);insert=false;frames(1)
local ids={}
for i,item in ipairs(ov.drawn)do
 assert(not ids[item.id],'duplicate engine ID after preceding item changed');ids[item.id]=true
 assert(not item._source or item._source.id==nil,'cached geometry holds a mutable engine ID')
end
local n=#calls;frames(1);assert(#calls==n)
revision=2;frames(1);assert(builds==2,'revision did not invalidate')
ov:hide();frames(1);ov:show(true);frames(1);assert(builds==3,'new GUI retained old IDs')
O.hooks.font=function()return fonts.monaco end
frames(1);assert(builds==4,'new role font did not invalidate')
return 'ok'
''')

    def test_monitor_reuses_content_and_still_updates_each_bin(self):
        run(HARNESS+r'''
local perf=require('hd2runtime/runtime/perf_watch')
require('hd2runtime/runtime/metrics').set_clock(os.clock)
local settings=require('hd2runtime/runtime/runtime_settings')
settings.reset_for_tests();settings.select_tab('performance')
O.hooks.game_fonts=function()return{}end
local ov=hd2.ui.overlay({owner='hd2runtime',id='settings',layer=980})
local inputs=0
ov:draw(function(d)inputs=inputs+1;settings.draw(d,nil,{pressed=function()return false end})end)
frames(16);local h=perf.history();assert(h.head>0)
frames(2);local hit=ov.retained_hits or 0;local n=#calls
frames(2);assert(ov.retained_hits==hit+2 and #calls==n,'steady graph rebuilt')
local before=h.head;frames(15);assert(h.head>before and #calls>n,'new graph bin did not draw')
assert(inputs==35)
assert(h.series['runtime:F10 layout'] and h.series['runtime:F10 GUI sync']
 and h.series['runtime:F10 resources/input'],'F10 work is not separated')
return 'ok'
''')

    def test_monitor_keeps_drawing_across_yields_and_view_changes(self):
        run(HARNESS+r'''
local perf=require('hd2runtime/runtime/perf_watch')
require('hd2runtime/runtime/metrics').set_clock(os.clock)
local settings=require('hd2runtime/runtime/runtime_settings')
local panel=require('hd2runtime/runtime/performance_panel')
settings.reset_for_tests();settings.select_tab('performance');panel.select_mode('global')
O.hooks.game_fonts=function()return{}end
local ov=hd2.ui.overlay({owner='hd2runtime',id='settings',layer=980})
ov:draw(function(d)settings.draw(d,nil,{pressed=function()return false end})end)
frames(2)
local co=coroutine.create(function()
 local t=perf.begin();coroutine.yield();perf.finish(t,'mods/test/background','background')
end)
assert(coroutine.resume(co));frames(90)
local h=perf.history();assert(h.head>=5 and ov:status().refused==0)
assert(coroutine.resume(co))
local before=h.head
for i=1,6 do
 panel.select_mode(i%2==0 and 'global'or'runtime');frames(30)
 assert(perf.history()==h and h.head>before,'view switch stopped bins or cleared samples')
 before=h.head;local st=ov:status();assert(st.state=='drawing'and st.refused==0 and st.items<1024)
end
local n=#calls;frames(90);assert(h.head>before and #calls>n,'monitor stopped updating engine geometry')
settings.select_tab('settings');frames(2);assert(not perf.recording())
return 'ok'
''')

    def test_editor_ui_and_work_are_separate_without_double_counting(self):
        run(PRELUDE+r'''
perf.record(true)
local editor='mods/skyeshade/hd2runtime_editor'
local ui={perf_group='ui'}
call(editor,'work',0.001,function()call(editor,ui,0.003)end)
perf.update(0.25)
local h=perf.history()
assert(h.series[editor].name=='HD2R Editor work')
assert(h.series[editor..':ui'].name=='HD2R Editor UI')
assert(math.abs(h.series[editor].values[1]-0.001)<1e-9)
assert(math.abs(h.series[editor..':ui'].values[1]-0.003)<1e-9)
assert(math.abs(h.peaks[1]-0.004)<1e-9,'nested UI counted twice')
return 'ok'
''')

    def test_font_cache_preserves_kerning_sizes_and_missing_glyphs(self):
        run(r'''
local f=require('hd2runtime/runtime/ui_fonts')
local font={em=100,advances={[63]=50,[65]=70,[86]=80},kerning={[65*f.KERN_KEY+86]=-10}}
assert(f.width(font,'AV',20)==28 and f.width(font,'AV',40)==56)
assert(f.has(font,'AV') and not f.has(font,'Z'))
for i=1,700 do f.width(font,tostring(i),12);f.has(font,tostring(i))end
assert(f.width(font,'AV',20)==28 and not f.has(font,'Z'),'bounded cache changed results')
f.reset_for_tests();assert(f.width(font,'AV',40)==56)
return 'ok'
''')
