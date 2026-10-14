"""Cooperative read-only inspection: bounded reads/CPU work and unchanged ownership outcomes."""
import unittest
from support import run
from test_multi_mod_composition import snapshot_run, build_profile


class ReaderPacingTests(unittest.TestCase):
    def test_cooperative_reads_and_cpu_work_yield_without_dropping_verification(self):
        self.assertEqual(run(r'''
local t,queries,reads=0,0,0
require('hd2runtime/runtime/metrics').set_clock(function()return t end)
local Reader=require('hd2runtime/runtime/reader')
local owner={base=4096,size=4096,type=0x20000}
local r=Reader.new({query=function()
 queries=queries+1;t=t+0.0001
 return{base=4096,size=4096,allocation_base=4096,state=0x1000,type=0x20000,protect=4}
end,read=function(at,n)reads=reads+1;return string.rep('x',n)end},{cooperative=true})
local co=coroutine.create(function()
 for _=1,50 do r.read(owner,0,1,true)end
 r.verify()
end)
local frames=0
repeat
 local before=queries;r.begin_slice()
 local ok,why=coroutine.resume(co);assert(ok,tostring(why))
 assert(queries-before<=6,'read budget failed')
 frames=frames+1
until coroutine.status(co)=='dead'
assert(reads==100 and#r.snapshots==50 and frames>10,'verification was skipped')
local count=0
co=coroutine.create(function()for _=1,40 do count=count+1;t=t+0.0002;r.cooperate()end end)
frames=0
repeat
 local before=count;r.begin_slice()
 local ok,why=coroutine.resume(co);assert(ok,tostring(why))
 assert(count-before<=3,'CPU parsing ran past its budget')
 frames=frames+1
until coroutine.status(co)=='dead'
assert(count==40 and frames>10)
assert(not Reader.new({}).cooperate,'ordinary writes acquired a new CPU yield path')
return 'ok'
'''), b'ok')

    @unittest.skipUnless(build_profile.SNAPSHOT.is_file(), 'retained snapshot required')
    def test_cancelled_inspection_stops_reads_and_uses_callers_perf_owner(self):
        result=snapshot_run(r'''
update=function()end
local job,callbacks
callbacks=0
events.run_as('mods/skyeshade/hd2runtime_editor',function()
 job=hd2.inspect({target=hd2.vehicle('TD-110 Maelstrom'),fields={'entity.health'},
 on_result=function()callbacks=callbacks+1 end})
end)
local m=require('hd2runtime/runtime/metrics')
local function queries()return m.snapshot().counters['reader.queries']or 0 end
frames(0.1);local before=queries();job.cancel();frames(1)
return json.encode({state=job.status,callbacks=callbacks,reads=queries()-before,owner=job.perf_owner,
 writes=counts.writes,protects=counts.protection_changes})
''')
        self.assertEqual(result,dict(state='cancelled',callbacks=0,reads=0,
            owner='mods/skyeshade/hd2runtime_editor',writes=0,protects=0))
