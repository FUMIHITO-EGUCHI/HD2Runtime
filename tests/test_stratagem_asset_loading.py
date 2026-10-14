import unittest

from support import ROOT, run
from reference_format import lua


class StratagemAssetLoadingTests(unittest.TestCase):
    def test_complete_call_in_sets_and_loading(self):
        run(r'''
local hd2=require('hd2runtime/api/hd2')
local api=require('hd2runtime/api/assets')
local assets=require('hd2runtime/core/assets')
local catalog=require('hd2runtime/domains/stratagem_authoring').stratagems
local names={'Eagle Strafing Run','MG-43 Machine Gun'}
local wanted={}
for _,name in ipairs(names)do
    local info=hd2.asset_dependency(hd2.stratagem(name))
    assert(info.known and info.autoLoadSupported and not info.liveTested,info.blocker)
    local deps=assets.dependencies_for_stratagem(catalog[name].root.id,name)
    assert(info.packages==#deps)
    for _,dep in ipairs(deps)do wanted[dep.package]=true end
end
-- Support weapons must resolve their weapon package, even without a root package.
assert(not assets.dependency_for_stratagem(catalog['MG-43 Machine Gun'].root.id))
assets.reset()
local calls,loaded={},{}
assets.prove=function()return {instance=1,request=2,capacity=1024}end
local runtime={mode='simulated',read=function(_,n)return string.rep('\0',n)end,
    package_request=function(_,_,package)calls[package]=(calls[package]or 0)+1 end,
    package_state=function(package)return loaded[package]and'resident'or'queued'end}
local watch=api.start(runtime,function()end,{id='stratagem-assets',targets={
    hd2.stratagem(names[1]),hd2.stratagem(names[2]),hd2.stratagem(names[1])}})
watch.tick(0.3);assert(watch.status=='waiting_for_assets')
local count=0
for package in pairs(wanted)do
    count=count+1;assert(calls[assets.id_bytes(package)]==1)
end
assert(#assets.holdings()==count)
local first=next(wanted);loaded[first]=true
watch.tick(0.3);assert(watch.status=='waiting_for_assets')
for package in pairs(wanted)do loaded[package]=true end
watch.tick(0.3);assert(watch.status=='complete'and watch.result.status=='RESIDENT')
local timeout=api.start(runtime,function()end,{id='stratagem-timeout',target=hd2.stratagem(names[1])})
loaded={};timeout.tick(91)
assert(timeout.status=='rejected'and timeout.result.code=='ASSET_UNAVAILABLE')
assets.reset()
return 'ok'
''')

    def test_incomplete_and_unknown_are_refused(self):
        run(r'''
local hd2=require('hd2runtime/api/hd2')
local api=require('hd2runtime/api/assets')
local function rejected(target)
    local info=api.describe(target)
    assert(not info.known and not info.autoLoadSupported and info.blocker)
    local ok,why=pcall(api.start,{},function()end,{id='refuse',target=target})
    assert(not ok and tostring(why):find('ASSET_UNAVAILABLE',1,true),tostring(why))
end
rejected(hd2.stratagem('Resupply'))
rejected({resource='stratagem',path='stratagem',stratagem='Unknown stratagem'})
local info=api.describe(hd2.stratagem('Eagle Strafing Run'):eagle_rearm())
assert(not info.known)
return 'ok'
''')

    def test_example_registers_a_stratagem_request(self):
        source = (ROOT / 'examples/projects/EagleStrafingRunAssets/src/addon.lua').read_text()
        run(r'''
local hd2=require('hd2runtime/api/hd2')
package.loaded['mods/skyeshade/hd2runtime']=hd2
hd2.require_assets=function(request)
    assert(request.id=='example-eagle-strafing-run-assets')
    assert(#request.targets==1)
    local t=request.targets[1]
    assert(t.resource=='stratagem'and t.stratagem=='Eagle Strafing Run')
    return {status='waiting_for_assets'}
end
local watch=assert(loadstring(''' + lua(source) + r'''))()
assert(watch.status=='waiting_for_assets')
return 'ok'
''')


if __name__ == '__main__':
    unittest.main()
