"""Foreign callback chains: exclusive attribution, return/error semantics and reversible observation."""
import unittest
from support import run

PRELUDE = r'''
local perf=require('hd2runtime/runtime/perf_watch')
local monitor=require('hd2runtime/runtime/global_perf')
local panel=require('hd2runtime/runtime/performance_panel')
local metrics=require('hd2runtime/runtime/metrics')
local T=0
metrics.set_clock(function()return T end)
local function advance(n)T=T+n end
local function chunk(source,body,...)
    return assert(loadstring(body,'@'..source))()(...)
end
local function near(a,b)assert(math.abs((a or -1)-b)<1e-9,tostring(a)..' ~= '..b)end
local function totals()
    local out={};for _,o in ipairs(perf.snapshot().owners)do out[o.owner]=o.total_seconds end;return out
end
'''

class GlobalPerfTests(unittest.TestCase):
    def test_yielding_background_callback_cannot_freeze_bins_or_charge_wait_time(self):
        self.check(r"""
Worker=chunk('mods/test/worker', 'return function(add)return {run=function()add(0.003);coroutine.yield();add(0.004)end}end',advance)
update=chunk('mods/test/scheduler','return function()return function(co)assert(coroutine.resume(co))end end')
perf.record(true);monitor.start()
local co=coroutine.create(function()Worker.run()end)
update(co);perf.update(0.25)
assert(perf.history().head==1,'suspended coroutine held the frame open')
advance(20);update(co);perf.update(0.25)
assert(perf.history().head==2,'resumed coroutine broke the stack')
local t=totals();near(t['global:unattributed'],0.007)
perf.record(false);advance(10);assert(not perf.recording())
""")

    def test_cached_resume_and_native_wrap_preserve_yields_returns_and_errors(self):
        self.check(r"""
local resume,make=coroutine.resume,coroutine.wrap
local err={original=true}
local function body()advance(0.003);coroutine.yield('first',nil);advance(0.004);error(err)end
local cached=make(body)
update=chunk('mods/test/scheduler',[[return function(resume,cached,add)return function(co)
    add(0.001);if co then return resume(co)end;return cached()
end end]],resume,cached,advance)
perf.record(true);monitor.start()
local function yielded(...)assert(select('#',...)==2 and (...)=='first')end
yielded(update());perf.update(0.25);assert(perf.history().head==1)
advance(10);local ok,why=pcall(update);assert(not ok and why==err);perf.update(0.25)
local co=coroutine.create(body)
local ok,value=update(co);assert(ok and value=='first');perf.update(0.25)
advance(10);local ok,why=update(co);assert(not ok and why==err);perf.update(0.25)
local newer=coroutine.wrap(body);yielded(newer());perf.update(0.25)
advance(10);local ok,why=pcall(newer);assert(not ok and why==err);perf.update(0.25)
assert(perf.history().head==6)
local t=totals();near(t['global:unattributed'],0.021);near(t['global:mods/test/scheduler'],0.004)
perf.record(false);assert(coroutine.resume==resume and coroutine.wrap==make)
local calls=0;metrics.set_clock(function()calls=calls+1;return 0 end)
local co=coroutine.create(function()coroutine.yield()end)
update(co);assert(calls==0,'closed observer queried the clock')
""")

    def test_changing_views_preserves_history_and_session(self):
        self.check(r"""
perf.record(true);local t=perf.begin();advance(0.002);perf.finish(t,'mods/test/x','x');perf.update(0.25)
local h=perf.history();panel.select_mode('global');assert(perf.history()==h and h.head==1)
panel.select_mode('runtime');assert(perf.history()==h and h.head==1)
""")

    def check(self, body):
        self.assertEqual(run(PRELUDE+body+"\nreturn 'ok'"), b'ok')

    def test_runtime_wrappers_and_private_saved_callback_tables_remain_exclusive(self):
        self.check(r"""
local vanilla=chunk('core/game','return function(add)return function()add(0.050)end end',advance)
local mod=chunk('mods/test/inner','return function(old,add)return function()add(0.003);old()end end',vanilla,advance)
local middle=chunk('hd2runtime/runtime/events','return function(old,add)return function()add(0.002);old()end end',mod,advance)
local core=chunk('hd2runtime/runtime/scheduler','return function(old,add)return function()add(0.001);old()end end',middle,advance)
local saved={previous=core}
saved.self=saved -- cycles must not recurse forever
update=chunk('mods/test/outer','return function(saved,add)return function()add(0.004);saved.previous()end end',saved,advance)
perf.record(true);monitor.start();update();perf.update(0.25)
local t=totals();near(t.HD2Runtime,0.003);near(t['global:mods/test/inner'],0.003)
near(t['global:mods/test/outer'],0.004)
monitor.stop();assert(saved.previous==core)
""")

    def test_profiler_bookkeeping_is_not_charged_to_the_enclosing_core_or_mod(self):
        self.check(r"""
perf.record(true)
local outer=perf.begin();advance(0.002)
local inner=perf.begin();advance(0.001)
perf.finish(inner,'mods/test/inner','slow label',function()advance(0.004);return 'label'end)
perf.finish(outer,'HD2Runtime','outer');perf.update(0.25)
local h=perf.history('global')
near(h.series.HD2Runtime.values[1],0.002)
near(h.series['mods/test/inner'].values[1],0.001)
near(h.series['HD2Runtime:menu'].values[1],0.004)
""")

    def test_large_private_data_cannot_hide_the_saved_update_chain_on_reopen(self):
        self.check(r"""
local data={};for i=1,6000 do data[i]=i end
local vanilla=chunk('core/game','return function(add)return function()add(0.040)end end',advance)
local inner=chunk('mods/test/inner','return function(old,add)return function()add(0.002);old()end end',vanilla,advance)
update=chunk('mods/test/outer',[[return function(data,old,add)return function()
 assert(data[6000]==6000);add(0.001);old()
end end]],data,inner,advance)
local original=update
for i=1,5 do
 perf.record(true);monitor.start();update();perf.update(0.25)
 local t=totals();near(t['global:mods/test/outer'],0.001);near(t['global:mods/test/inner'],0.002)
 assert(not monitor.status().limited,'ordinary scalar data consumed the function budget')
 perf.record(false);assert(update==original)
end
""")

    def test_truncated_callback_work_is_never_blame_assigned_to_an_outer_mod(self):
        self.check(r"""
monitor.MAX_FUNCTIONS=1
local vanilla=chunk('core/game','return function(add)return function()add(0.040)end end',advance)
local inner=chunk('mods/test/inner','return function(old,add)return function()add(0.002);old()end end',vanilla,advance)
update=chunk('mods/test/outer','return function(old,add)return function()add(0.001);old()end end',inner,advance)
perf.record(true);monitor.start();update();perf.update(0.25)
assert(monitor.status().limited)
local t=totals();near(t['global:mods/test/outer'],0.001);assert(t['global:mods/test/inner']==nil)
near(t['global:unattributed'],0.042)
local h=perf.history('global');assert(h.series.unattributed.kind=='unattributed')
""")

    def test_incomplete_private_table_does_not_taint_other_mods_or_same_owner_callers(self):
        self.check(r"""
monitor.MAX_TABLE_CELLS=8
local data={};for i=1,100 do data[i]=i end
local unknown=chunk('mods/test/noisy',[[return function(data,add)return function()
 assert(data[100]==100);add(0.006)
end end]],data,advance)
local helper=chunk('mods/test/noisy','return function(old,add)return function()add(0.002);old()end end',unknown,advance)
update=chunk('mods/test/outer','return function(old,add)return function()add(0.001);old()end end',helper,advance)
local saved=update
for i=1,3 do
 perf.record(true);monitor.start();update();perf.update(0.25)
 local t=totals();near(t['global:mods/test/outer'],0.001);near(t['global:mods/test/noisy'],0.002)
 near(t['global:unattributed'],0.006)
 perf.record(false);assert(update==saved)
end
""")

    def test_f10_is_excluded_from_core_mod_totals_and_pinned_separately(self):
        self.check(r'''
panel.select_mode('global');perf.record(true)
local outer=perf.begin();advance(0.001)
local menu=perf.begin();advance(0.020)
perf.finish(menu,'HD2Runtime',{perf_group='runtime_menu',perf_name='F10 layout'})
local editor=perf.begin();advance(0.004);perf.finish(editor,'mods/skyeshade/hd2runtime_editor','work')
perf.finish(outer,'HD2Runtime','core');perf.update(0.25)
local h=perf.history('global')
near(h.series.HD2Runtime.values[1],0.001)
near(h.series['HD2Runtime:menu'].values[1],0.020)
near(h.series['mods/skyeshade/hd2runtime_editor'].values[1],0.004)
local s=panel.stats(h);assert(#s.rows==2 and s.menu.name=='F10 menu')
near(s.total,0.005);near(s.menu.average,0.020)
for _,row in ipairs(s.rows)do assert(row.kind~='menu')end
''')

    def test_mod_chain_excludes_vanilla_and_runtime_mods_from_the_core(self):
        self.check(r'''
local vanilla=chunk('core/game','return function(add)return function(...)add(0.050);return ... end end',advance)
local a=chunk('mods/test/alpha','return function(old,add)return function(...)add(0.003);return old(...)end end',vanilla,advance)
local editor='mods/skyeshade/hd2runtime_editor'
local core=chunk('hd2runtime/runtime/scheduler',[[return function(old,add,perf,editor)return function(...)
    local timed=perf.begin();add(0.004);perf.finish(timed,editor,'editor')
    add(0.002);return old(...)
end end]],a,advance,perf,editor)
local b=chunk('mods/test/beta','return function(old,add)return function(...)add(0.001);return old(...)end end',core,advance)
update=b
perf.record(true);monitor.start()
local function results(...)assert(select('#',...)==4);local a,b,c,d=...;assert(a==0.25 and b==nil and c=='ok'and d==nil)end
results(update(0.25,nil,'ok',nil));perf.update(0.25)
local t=totals();near(t['global:mods/test/alpha'],0.003);near(t['global:mods/test/beta'],0.001)
near(t.HD2Runtime,0.002);near(t[editor],0.004)
local h=perf.history('global');near(h.series.HD2Runtime.values[1],0.002);near(h.series[editor].values[1],0.004)
near(h.peaks[1],0.010)
monitor.stop();assert(update==b)
local before=T;update(0.25);near(T-before,0.060);near(totals().HD2Runtime,0.002)
''')

    def test_errors_unwind_and_original_error_objects_survive(self):
        self.check(r'''
local err={reason='original'}
update=chunk('mods/test/fail',[[return function(add,err)return function()add(0.003);error(err)end end]],advance,err)
local original=update
perf.record(true);monitor.start()
local ok,why=pcall(update,0.25);assert(not ok and why==err)
local timed=perf.begin();advance(0.002);perf.finish(timed,'HD2Runtime','after error')
local t=totals();near(t['global:mods/test/fail'],0.003);near(t.HD2Runtime,0.002)
perf.record(false);assert(update==original)
''')

    def test_closing_does_not_overwrite_later_hooks_and_retained_wrappers_go_idle(self):
        self.check(r'''
update=chunk('mods/test/one','return function(add)return function()add(0.003)end end',advance)
perf.record(true);monitor.start()
local captured=update
local replacement=function(...)return captured(...)end
update=replacement
perf.record(false);assert(update==replacement)
update();assert(next(totals())==nil,'closed observer kept timing')
''')

    def test_global_groups_ui_and_work_with_true_combined_frame_peaks_and_idle_inventory(self):
        self.check(r'''
CowboyBingusModLoader={modules={['mods/test/asset']='loaded',['mods/test/missing']='not installed'}}
panel.select_mode('global');perf.record(true)
local ed='mods/skyeshade/hd2runtime_editor'
local function call(key,n)local t=perf.begin();advance(n);perf.finish(t,ed,key)end
call('work',0.005);call({perf_group='ui'},0.001);perf.update(0.125)
call('work',0.001);call({perf_group='ui'},0.004);perf.update(0.125)
local h=perf.history('global');near(h.series[ed].values[1],0.0055);near(h.series[ed].peaks[1],0.006)
local st=panel.stats(h);assert(#st.rows==2 and st.rows[1].kind=='mod')
assert(st.rows[2].id=='mods/test/asset'and st.rows[2].unmeasured)
panel.select_mode('runtime');assert(perf.history().head==1 and panel.mode()=='runtime')
''')

    def test_engine_api_hook_is_observed_without_replacing_native_functions(self):
        self.check(r'''
stingray={Application={hook=chunk('mods/test/hook','return function(add)return function(x)add(0.002);return x end end',advance), native=math.sin}}
local original=stingray.Application.hook
perf.record(true);monitor.start();assert(stingray.Application.native==math.sin)
assert(stingray.Application.hook('value')=='value')
near(totals()['global:mods/test/hook'],0.002)
monitor.stop();assert(stingray.Application.hook==original)
''')

    def test_scheduler_bin_waits_for_outer_mod_callbacks_to_finish(self):
        self.check(r'''
local core=chunk('hd2runtime/runtime/scheduler',[[return function(add,perf)return function(dt)
    local t=perf.begin();add(0.002);perf.finish(t,'HD2Runtime','service');perf.update(dt)
end end]],advance,perf)
update=chunk('mods/test/outer',[[return function(old,add)return function(dt)
    add(0.001);old(dt);add(0.003)
end end]],core,advance)
perf.record(true);monitor.start();update(0.25)
local h=perf.history('global');assert(h.head==1)
near(h.series['mods/test/outer'].values[1],0.004);near(h.peaks[1],0.006)
monitor.stop()
''')

    def test_more_than_48_mods_keep_individual_rows(self):
        self.check(r'''
perf.record(true)
for i=1,80 do
    local t=perf.begin();advance(0.0001);perf.finish(t,'global:mods/test/mod_'..i,'tick')
end
perf.update(0.25)
local h=perf.history('global');assert(#h.list==80);near(h.peaks[1],0.008)
''')

    def test_reopening_flattens_retained_observers_without_losing_mod_attribution(self):
        self.check(r'''
update=chunk('mods/test/one','return function(add)return function()add(0.003)end end',advance)
perf.record(true);monitor.start()
update=chunk('mods/test/two','return function(old,add)return function()add(0.002);return old()end end',update,advance)
perf.record(false);perf.record(true);monitor.start();update();perf.update(0.25)
local h=perf.history('global')
near(h.series['mods/test/one'].values[1],0.003);near(h.series['mods/test/two'].values[1],0.002)
perf.record(false)
''')

    def test_switching_view_inside_a_timed_callback_cannot_leak_old_global_costs(self):
        self.check(r'''
panel.select_mode('global');perf.record(true)
local t=perf.begin();advance(0.001)
panel.select_mode('runtime')
advance(0.002);perf.finish(t,'global:mods/test/old','old callback');perf.update(0.25)
local st=panel.stats(perf.history())
assert(#st.rows==0,'external Global recording leaked into Runtime view')
local sum=0;for _,v in ipairs(st.columns[perf.BINS]or{})do sum=sum+v end;near(sum,0)
''')

if __name__=='__main__':unittest.main()
