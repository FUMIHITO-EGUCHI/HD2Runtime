import unittest
from support import run


class MemoryWatchTests(unittest.TestCase):
    def test_real_overlay_accepts_memory_geometry_and_retains_it(self):
        from test_ui_overlay import HARNESS
        run(HARNESS+r'''
local panel=require('hd2runtime/runtime/performance_panel')
local settings=require('hd2runtime/runtime/runtime_settings')
require('hd2runtime/runtime/metrics').set_clock(os.clock)
settings.reset_for_tests();settings.select_tab('performance');panel.select_mode('memory')
O.hooks.game_fonts=function()return{}end
local ov=hd2.ui.overlay({owner='hd2runtime',id='settings',layer=980})
ov:draw(function(d)settings.draw(d,nil,{pressed=function()return false end})end)
frames(3)
assert(ov:status().refused==0,tostring(ov:status().refused))
assert(ov:status().items<1024)
return 'ok'
''')

    def test_payloads_deduplicate_and_do_not_hold_dead_allocations(self):
        run(r'''
local m=require('hd2runtime/runtime/memory_watch')
local ffi=require('ffi')
local buffer=ffi.new('uint8_t[?]',1024)
local cache={map=('unique cache data'):rep(100)}
local snapshot={bytes=cache.map}
m.buffer(buffer,1024,'Event buffers')
m.fields(cache,'Cache payloads',{'map'})
m.fields(snapshot,'Snapshot payloads',{'bytes'})
m.permanent(65536,4096);m.permanent(65536,4096)
local s=m.snapshot()
assert(s.total==1024+4096+#cache.map)
assert(s.categories['Cache payloads']==#cache.map and not s.categories['Snapshot payloads'])
cache=nil;buffer=nil;collectgarbage();collectgarbage()
s=m.snapshot();assert(s.total==4096+#snapshot.bytes and not s.categories['Event buffers'])
snapshot=nil;collectgarbage();collectgarbage();assert(m.snapshot().total==4096)
return 'ok'
''')

    def test_history_is_bounded_sampled_on_demand_and_never_forces_gc(self):
        run(r'''
local m=require('hd2runtime/runtime/memory_watch')
collectgarbage=function()error('no shared heap query or forced collection')end
local h,n=m.sample(0);assert(n==1)
for i=1,99 do local _,n=m.sample(i/100);assert(n==1)end
local _,n=m.sample(1);assert(n==2)
m.pause();local _,n=m.sample(1000);assert(n==3,'closed time must not fill history')
for i=1,200 do h,n=m.sample(1000+i)end
assert(#h==m.BINS and n==203)
return 'ok'
''')

    def test_graph_retains_geometry_stops_cpu_profiling_and_handles_mode_switch(self):
        run(r'''
local p=require('hd2runtime/runtime/performance_panel')
local m=require('hd2runtime/runtime/memory_watch')
local perf=require('hd2runtime/runtime/perf_watch')
local now=0
require('hd2runtime/runtime/metrics').set_clock(function()return now end)
local calls=0;local snapshot=m.snapshot
m.snapshot=function()calls=calls+1;return snapshot()end
local retained,draws={},0
local colour={255,255,255,255}
local ctx={C=setmetatable({},{__index=function()return colour end}),S={small=12,body=16,tiny=10},text=function()end,
 d={wrap=function(self,s)return{s}end,rect=function()end,_retain=function(self,key,revision,draw)
  if retained[key]~=revision then retained[key]=revision;draw(self);draws=draws+1 end
 end}}
p.select_mode('memory');p.draw(ctx,{x=0,y=0,w=900},1)
assert(calls==1 and draws==1)
for _=1,20 do p.draw(ctx,{x=0,y=0,w=900},1)end
assert(calls==1 and draws==1,'unchanged UI rebuilt')
now=1;p.draw(ctx,{x=0,y=0,w=900},1);assert(calls==2 and draws==2)
p.reset();now=120;assert(calls==2,'closed menu sampled memory')
p.draw(ctx,{x=0,y=0,w=900},1);assert(calls==3)
p.select_mode('runtime');p.draw(ctx,{x=0,y=0,w=900},1);assert(calls==3)
return 'ok'
''')
