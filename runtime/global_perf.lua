-- Optional Lua callback watchdog. Installed only while Global is visible; no debug hooks, JIT changes, or native
-- detours. Attribute exposed mod functions by their resource chunk and follow saved callback chains across owners.
-- Functions hidden in native hooks, anonymous chunks and asset-only work cannot be attributed by this observer.
local perf=require('hd2runtime/runtime/perf_watch')
local M={}
local active=false
local session
local links,wrapped,ours,seen={},{},{},{}
local nodes,visited,cells={},0,0
M.MAX_FUNCTIONS=4096;M.MAX_TABLE_CELLS=65536
local report={callbacks=0,limited=false}
local getinfo,getupvalue,setupvalue=debug and debug.getinfo,debug and debug.getupvalue,debug and debug.setupvalue
local pcall,error,type,next,rawget,rawset=pcall,error,type,next,rawget,rawset
local function original(fn)
    while ours[fn]do fn=ours[fn]end
    return fn
end
local function owner(fn)
    local info=getinfo(fn,'S')
    if not info or info.what=='C'then return nil end
    local source=(info.source or''):gsub('\\','/'):gsub('^[@=]',''):gsub('%.lua$','')
    if source:match('^hd2runtime/')or source=='mods/skyeshade/hd2runtime'then return 'HD2Runtime' end
    local mod=source:match('(mods/[%w_%-]+/[%w_%-]+)')
    if mod then return mod end
    if source:match('^[@=]?core/')or source:match('^[@=]?scripts/')then return false end
    return nil -- anonymous/stripped chunks with no resource identity cannot be assigned safely
end
local function replace(container,key,fn,upvalue)
    local original=upvalue and select(2,getupvalue(container,key))or rawget(container,key)
    if original==fn then return end
    links[#links+1]={container=container,key=key,original=original,wrapper=fn,upvalue=upvalue}
    if upvalue then setupvalue(container,key,fn)else rawset(container,key,fn)end
end
local function wrap(fn,id,label)
    if wrapped[fn]then return wrapped[fn]end
    local key={perf_name=label,perf_external=true}
    local recording=session
    local node=seen[fn]
    local function describe(k)return k.perf_name end
    -- Preserve every return (including trailing nil) and rethrow the original error object after unwinding timing.
    local function done(timed,ok,...)
        local charged=node and node.incomplete and'global:unattributed'or(id and(id=='HD2Runtime'and id or'global:'..id)or false)
        perf.finish(timed,charged,key,describe)
        if not ok then error((...),0)end
        return ...
    end
    local function callback(...)
        if not recording.active then return fn(...)end
        return done(perf.begin(),pcall(fn,...))
    end
    wrapped[fn],ours[callback]=callback,fn
    if id then report.callbacks=report.callbacks+1 end
    return callback
end
local native_resume=coroutine.resume
local function coroutine_call(fn)
    if fn==native_resume then return true end
    if getinfo(fn,'S').what=='C'then
        local _,value=getupvalue(fn,1)
        return type(value)=='thread'
    end
    return false
end
local walk
local function instrumentation(fn)
    local source=(getinfo(fn,'S').source or ''):gsub('\\','/'):gsub('^[@=]',''):gsub('%.lua$','')
    return source=='hd2runtime/runtime/perf_watch'or source=='hd2runtime/runtime/global_perf'
        or source=='hd2runtime/runtime/metrics'
end
local function node_for(value)
    local n=seen[value]
    if not n then n={deps={}};seen[value]=n;nodes[#nodes+1]=n end
    return n
end
local function limited(n)n.incomplete=true;report.limited=true end
local function dependency(n,child)if child then n.deps[#n.deps+1]=child end end
local function ordered(t)
    local keys={};for k in next,t do keys[#keys+1]=k end
    table.sort(keys,function(a,b)
        local ta,tb=type(a),type(b)
        if ta~=tb then return ta<tb end
        if ta=='string'or ta=='number'then return a<b end
        if ta=='boolean'then return not a and b end
        return false -- do not invoke a foreign table/userdata __tostring metamethod
    end)
    return keys
end
-- Discovery never mutates the graph it is inspecting. Install the gathered boundaries afterwards.
local boundaries={}
local function boundary(container,key,fn,id,upvalue,label,conditional)
    boundaries[#boundaries+1]={container,key,fn,id,upvalue,label,conditional}
end
local function walk_table(t,id,level)
    if t==_G or t==package or t==debug or t==math or t==string or t==table then return nil end
    if seen[t]then return seen[t]end
    local n=node_for(t)
    if level>8 or cells>=M.MAX_TABLE_CELLS then limited(n);return n end
    local functions,tables={},{}
    -- Scalar data is not a callback. Keep its budget separate from the function-chain budget.
    for key,value in next,t do
        cells=cells+1
        if cells>M.MAX_TABLE_CELLS then limited(n);break end
        if type(value)=='function'then functions[#functions+1]={key,original(value)}
        elseif type(value)=='table'then tables[#tables+1]=value end
    end
    for _,item in ipairs(functions)do
        local key,value=item[1],item[2];local other=coroutine_call(value)and'unattributed'or owner(value)
        if other~=nil and not instrumentation(value)then
            walk(value,0)
            boundary(t,key,value,other,false,'saved callback',other==id)
        end
    end
    for _,child in ipairs(tables)do dependency(n,walk_table(child,id,level+1))end
    return n
end
walk=function(fn,level)
    if instrumentation(fn)or coroutine_call(fn)then return nil end
    if seen[fn]then return seen[fn]end
    local n=node_for(fn);visited=visited+1
    if level>96 or visited>M.MAX_FUNCTIONS then limited(n);return n end
    local id=owner(fn)
    if id==nil or id==false then return n end -- vanilla is excluded as one boundary, not recursively instrumented
    local tables={}
    for i=1,64 do
        local name,value=getupvalue(fn,i)
        if not name then break end
        if type(value)=='function'then
            value=original(value);local other=coroutine_call(value)and'unattributed'or owner(value)
            if other~=nil and not instrumentation(value)then
                walk(value,level+1)
                boundary(fn,i,value,other,true,'callback chain',other==id)
            end
        elseif type(value)=='table'and id~='HD2Runtime'then tables[#tables+1]=value end
    end
    -- Always finish the saved function chain before inspecting a mod's arbitrary private data.
    for _,t in ipairs(tables)do dependency(n,walk_table(t,id,0))end
    return n
end
function M.start()
    if active then return report end
    report={callbacks=0,limited=false}
    if not(getinfo and getupvalue and setupvalue)then report.unavailable=true;return report end
    active=true;session={active=true};visited,cells=0,0;nodes,boundaries={},{}
    local roots={{coroutine,'resume',original(coroutine.resume),'unattributed',false,'coroutine resume'}}
    local function inspect(t,prefix)
        for _,key in ipairs(ordered(t))do
            local fn=rawget(t,key)
            if type(fn)=='function'then
                fn=original(fn);local id=owner(fn)
                if id and id~='HD2Runtime'or t==_G and(key=='update'or key=='render')then
                    if id~=nil then roots[#roots+1]={t,key,fn,id,false,prefix..tostring(key)}end
                end
            end
        end
    end
    -- Update/render must not depend on Lua table hash order or unrelated mod globals.
    for _,key in ipairs({'update','render'})do
        local fn=rawget(_G,key)
        if type(fn)=='function'then
            fn=original(fn);local id=owner(fn)
            if id~=nil then roots[#roots+1]={_G,key,fn,id,false,key}end
        end
    end
    inspect(_G,'')
    for _,name in ipairs(ordered(_G))do
        local t=rawget(_G,name)
        if type(t)=='table'and t~=_G and name~='package'and name~='debug'and name~='jit'then
            inspect(t,tostring(name)..'.')
            if name=='stingray'then
                for _,key in ipairs(ordered(t))do
                    local child=rawget(t,key)
                    if type(child)=='table'then inspect(child,'stingray.'..tostring(key)..'.')end
                end
            end
        end
    end
    for _,r in ipairs(roots)do walk(r[3],0)end
    -- Only uninspected table contents taint their containing function. A discovered function gets its own
    -- boundary when incomplete (including same-owner helpers), so its caller's exclusive remainder stays known.
    local changed=true
    while changed do
        changed=false
        for _,n in ipairs(nodes)do if not n.incomplete then
            for _,child in ipairs(n.deps)do if child.incomplete then n.incomplete=true;changed=true;break end end
        end end
    end
    for _,r in ipairs(roots)do boundaries[#boundaries+1]=r end
    for _,r in ipairs(boundaries)do
        if not r[7]or(seen[r[3]]and seen[r[3]].incomplete)then
            replace(r[1],r[2],wrap(r[3],r[4],r[6]),r[5])
        end
    end
    -- Preserve native wrap's return/error semantics while measuring only each synchronous resume.
    local old_wrap=coroutine.wrap
    replace(coroutine,'wrap',function(...)
        return wrap(old_wrap(...),'unattributed','coroutine resume')
    end,false)
    boundaries={};nodes={}
    return report
end
function M.stop()
    active=false
    if session then session.active=false end
    -- Respect replacements made by another mod while recording. Dormant wrappers kept by a new chain pass through.
    for i=#links,1,-1 do
        local l=links[i]
        local current=l.upvalue and select(2,getupvalue(l.container,l.key))or rawget(l.container,l.key)
        if current==l.wrapper then
            if l.upvalue then setupvalue(l.container,l.key,l.original)else rawset(l.container,l.key,l.original)end
        end
    end
    links,wrapped,seen={},{},{}
    nodes,boundaries={},{}
    -- Remember the original behind retained pass-through wrappers when another mod kept one in its chain.
    setmetatable(ours,{__mode='k'})
end
function M.status()return report end
return M
