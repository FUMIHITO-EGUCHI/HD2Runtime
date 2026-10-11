-- Which mod is slow (docs/runtime-performance.md, "Which mod is slow"): every call the Runtime makes into a mod (event
-- listeners, timers, keybinds, run_as: a mod's main file, custom stratagem and Pelican callbacks) and every scheduler
-- watch (the Runtime's own work, and each mod's operations) is timed with the precise clock, by its own time only (a
-- callback dispatched from inside another is counted once, as the inner one's). Quiet by default:
--   * one call taking at least M.SINGLE_CALL logs one line naming the mod and the callback; the same callback logs
--     again only at twice its last logged time, at most M.SINGLE_CALL_LINES times;
--   * a mod (or a Runtime module) using at least M.SHARE per update on average over M.WINDOW seconds of game time logs
--     one line with its heaviest callbacks, at most once per M.REPEAT seconds.
-- Nothing is formatted on the timing path; without a precise clock (offline) nothing is timed.
local metrics=require('hd2runtime/runtime/metrics')
local M={}
M.SINGLE_CALL=0.008
M.SINGLE_CALL_LINES=3
M.SHARE=0.001
M.WINDOW=10
M.REPEAT=60
M.MAX_CALLBACKS=64           -- per owner and window; the rest are counted as 'other callbacks'
M.MAX_SLOW=32                -- callbacks per owner remembered for the single-call lines

-- The live history (0.31.1, the F10 panel's Performance tab; runtime/performance_panel.lua): only while recording.
-- Each series is one mod (all its callbacks) or one part of the Runtime (a scheduler watch's module, an event source,
-- the Runtime's own overlays); every M.BIN seconds of game time it gets one value, its own time per update averaged
-- over the bin, kept for the last M.BINS bins.
M.BIN=0.25
M.BINS=60
M.MAX_SERIES=48              -- a session's series at most; later parts of the Runtime count as 'other Runtime work'

-- The timing stack: start time and the time of the calls nested in it, per depth (no allocation per call).
local starts,nested,depth={},{},0
local owners={}              -- owner -> {window, calls, total, total_calls, max, max_label, slow={}, slow_n, callbacks}
local window,window_updates,game_time=0,0,0
local recording=false
local history                -- {series = {[id] = series}, list = {series}, bins = {frame seconds}, head, filled, ...}
local runtime_series=setmetatable({},{__mode='k'})   -- callback key -> its Runtime series (labels computed once)
local emit=function(line)require('hd2runtime/runtime/log').emit(line)end

local function owner_state(owner)
    local o=owners[owner]
    if not o then
        o={window=0,calls=0,total=0,total_calls=0,max=0,max_label=nil,slow={},slow_n=0,callbacks={},callback_n=0,
            logged_at=-math.huge,last=nil,mod=type(owner)=='string'and owner:sub(1,5)=='mods/'}
        owners[owner]=o
    end
    return o
end
local function who(owner)
    return owner=='HD2Runtime'and'HD2Runtime (its own work)'or('mod '..tostring(owner))
end
local function ms(seconds)return string.format('%.1f ms',seconds*1000)end

-- A part of the Runtime's name from its callback label: a scheduler watch's module ('update of
-- hd2runtime/runtime/custom_stratagems' -> 'custom stratagems'), a frame or timer of the Runtime's own overlays
-- ('frame (hd2runtime.overlay.settings)' -> 'overlay settings'), else the label itself.
function M.service_name(label)
    label=tostring(label or'')
    local module=label:match('^update of hd2runtime/runtime/(.+)$')or label:match('^update of hd2runtime/api/(.+)$')
    if module then return(module:gsub('_',' '))end
    local inner=label:match('%((.-)%)$')
    if inner then return(inner:gsub('^hd2runtime%.',''):gsub('[._]',' '))end
    if label:match('^[%w_%.%-]+$')then return(label:gsub('^hd2runtime%.',''):gsub('[._]',' '))end
    return label
end
local function new_series(id,name,kind,owner)
    local s={id=id,name=name,kind=kind,owner=owner,values={},peaks={},frame=0,bin=0,peak=0}
    history.series[id]=s
    history.list[#history.list+1]=s
    return s
end
-- The series a timed call adds to: its mod's, or its part of the Runtime's (labelled once per callback key).
local function series_for(o,owner,key,describe)
    local id=o.mod and owner or runtime_series[key]
    if not id then
        -- a named timer or frame callback of the Runtime's own (its id), else its label
        local named=type(key)=='table'and type(key.perf_name)=='string'and key.perf_name
        local ok,label=true,named
        if not named then ok,label=pcall(describe or tostring,key)end
        id='runtime:'..M.service_name(ok and label or key)
        runtime_series[key]=id
    end
    local s=history.series[id]
    if s then return s end
    if #history.list>=M.MAX_SERIES then
        id=o.mod and'mods:other'or'runtime:other'
        return history.series[id]or new_series(id,o.mod and'other mods'or'other Runtime work',o.mod and'mod'or'runtime')
    end
    if o.mod then
        return new_series(id,(tostring(owner):match('([^/]+)$')or tostring(owner)):gsub('_',' '),'mod',owner)
    end
    return new_series(id,id:sub(9),'runtime','HD2Runtime')
end

-- Starts timing one call; returns true when it is timed (pass the same value to M.finish).
function M.begin()
    local now=metrics.now()
    if not now then return false end
    depth=depth+1
    starts[depth],nested[depth]=now,0
    return true
end
-- Ends the call M.begin started: `owner` (a mod id or 'HD2Runtime'), `key` (what identifies the callback: its record,
-- function or watch), `describe(key)` -> its label (called only when a line is logged or a callback is first seen).
function M.finish(timed,owner,key,describe)
    if not timed or depth==0 then return end
    local now=metrics.now()
    local elapsed=now-starts[depth]
    local own=elapsed-nested[depth]
    depth=depth-1
    if depth>0 then nested[depth]=nested[depth]+elapsed end
    if own<0 then own=0 end
    local o=owner_state(owner or'unknown')
    o.window,o.calls=o.window+own,o.calls+1
    if recording then
        local series=series_for(o,owner,key,describe)
        series.frame=series.frame+own
    end
    o.total,o.total_calls=o.total+own,o.total_calls+1
    local c=o.callbacks[key]
    if not c then
        if o.callback_n>=M.MAX_CALLBACKS then
            key='other callbacks';c=o.callbacks[key]
            if not c then c={time=0,calls=0,max=0,label='other callbacks'};o.callbacks[key]=c end
        else
            c={time=0,calls=0,max=0,label=nil,describe=describe};o.callbacks[key]=c;o.callback_n=o.callback_n+1
        end
    end
    c.time,c.calls=c.time+own,c.calls+1
    if own>c.max then c.max=own end
    if own>o.max then
        o.max=own
        local ok,label=pcall(describe or tostring,key)
        o.max_label=ok and tostring(label)or tostring(key)
    end
    if own>=M.SINGLE_CALL then
        local ok,label=pcall(describe or tostring,key)
        label=ok and tostring(label)or tostring(key)
        local s=o.slow[label]
        if not s and o.slow_n<M.MAX_SLOW then s={lines=0,logged=0};o.slow[label]=s;o.slow_n=o.slow_n+1 end
        if s and s.lines<M.SINGLE_CALL_LINES and own>=2*s.logged then
            s.lines,s.logged=s.lines+1,own
            emit(('[HD2Runtime] PERFORMANCE: %s: %s took %s in one call%s'):format(who(owner),label,ms(own),
                s.lines==M.SINGLE_CALL_LINES and' (not logged again for it)'or''))
        end
    end
end

local function top(o,n)
    local list={}
    for key,c in pairs(o.callbacks)do
        if c.calls>0 then
            if not c.label then
                local ok,label=pcall(c.describe or tostring,key)
                c.label=ok and tostring(label)or tostring(key)
            end
            list[#list+1]=c
        end
    end
    table.sort(list,function(a,b)return a.time>b.time end)
    local out={}
    for i=1,math.min(n,#list)do out[i]=list[i]end
    return out
end
-- While recording: this update's time per series into the running bin; a full bin becomes one value per series (the
-- average per update), with the bin's frame time and its largest single-update values.
local function record_update(dt)
    local h=history
    h.time,h.updates=h.time+dt,h.updates+1
    local total=0
    for _,s in ipairs(h.list)do
        local f=s.frame
        if f>0 then
            s.bin=s.bin+f
            if f>s.peak then s.peak=f end
            total=total+f
            s.frame=0
        end
    end
    if total>h.peak then h.peak=total end
    if h.time+1e-6<M.BIN then return end   -- (a sum of frame times never lands exactly on it)
    h.head=h.head+1
    local slot=(h.head-1)%M.BINS+1
    local n=h.updates
    h.frames[slot],h.peaks[slot]=h.time/n,h.peak
    for _,s in ipairs(h.list)do
        s.values[slot],s.peaks[slot]=s.bin/n,s.peak
        s.bin,s.peak=0,0
    end
    h.time,h.updates,h.peak=0,0,0
end
-- Starts (true) or stops recording the live history (stopping drops it). Nothing is recorded unless something shows it.
function M.record(on)
    on=on==true
    if on and not recording then
        history={series={},list={},frames={},peaks={},head=0,time=0,updates=0,peak=0}
    elseif not on then history=nil end
    recording=on
end
function M.recording()return recording end
-- The live history while recording, else nil: {list = {series}, frames, peaks, head}. Bin i of the last
-- n = min(head, M.BINS) (oldest first) is at slot (head - n + i - 1) % M.BINS + 1; series.values[slot] is its average
-- own time per update (nil before it existed), series.peaks[slot] its largest single update, frames[slot] the average
-- frame time and peaks[slot] the largest single-update total. Read-only for the caller.
function M.history()return recording and history or nil end

-- Once per scheduler update (the Runtime's whole tick). Ends the window every M.WINDOW seconds of game time.
function M.update(dt)
    if recording then record_update(dt or 0)end
    window=window+(dt or 0)
    window_updates=window_updates+1
    game_time=game_time+(dt or 0)
    if window+1e-6<M.WINDOW then return end   -- (a sum of frame times never lands exactly on it)
    for owner,o in pairs(owners)do
        local per=window_updates>0 and o.window/window_updates or 0
        local heavy=top(o,3)
        o.last={seconds=window,updates=window_updates,per_update=per,calls=o.calls,heaviest={}}
        for i,c in ipairs(heavy)do
            o.last.heaviest[i]={label=c.label,seconds=c.time,calls=c.calls,max=c.max}
        end
        if per>=M.SHARE and game_time-o.logged_at>=M.REPEAT then
            o.logged_at=game_time
            local parts={}
            for _,c in ipairs(heavy)do
                parts[#parts+1]=('%s avg %s max %s, %d calls'):format(c.label,ms(c.time/c.calls),ms(c.max),c.calls)
            end
            emit(('[HD2Runtime] PERFORMANCE: %s used %s per update over the last %.0f s (%d calls); heaviest: %s')
                :format(who(owner),ms(per),window,o.calls,table.concat(parts,'; ')))
        end
        o.window,o.calls,o.callbacks,o.callback_n=0,0,{},0
    end
    window,window_updates=0,0
end

-- Per owner: {owner, total_seconds, calls, max_seconds, max_label, last_window = {seconds, updates, per_update,
-- calls, heaviest = {{label, seconds, calls, max}}}}, sorted by total time; hd2.diagnostics.performance().
function M.snapshot()
    local out={}
    for owner,o in pairs(owners)do
        out[#out+1]={owner=owner,total_seconds=o.total,calls=o.total_calls,max_seconds=o.max,max_label=o.max_label,
            last_window=o.last}
    end
    table.sort(out,function(a,b)return a.total_seconds>b.total_seconds end)
    return {timed=metrics.now()~=nil,single_call_seconds=M.SINGLE_CALL,share_seconds=M.SHARE,window_seconds=M.WINDOW,
        owners=out}
end
-- The line api/hd2.lua logs when a burst of registered operations was slow to settle: the 3 slowest, each with the
-- time it spent in each state. burst = {handles, elapsed, waits = {[handle] = {[state] = seconds}}, settled_at =
-- {[handle] = seconds}}; a handle has kind, id and perf_owner (its mod).
function M.slowest_operations(burst)
    local list={}
    for _,h in ipairs(burst.handles)do list[#list+1]=h end
    local function at(h)return burst.settled_at[h]or burst.elapsed end
    table.sort(list,function(a,c)return at(a)>at(c)end)
    local parts={}
    for i=1,math.min(3,#list)do
        local h,states=list[i],{}
        for state,seconds in pairs(burst.waits[h]or{})do states[#states+1]=('%s %.1f s'):format(state,seconds)end
        table.sort(states)
        parts[#parts+1]=('%s %s (%s) after %.1f s%s'):format(tostring(h.kind or'operation'),tostring(h.id),
            tostring(h.perf_owner),at(h),#states>0 and(': '..table.concat(states,', '))or'')
    end
    return '[HD2Runtime] PERFORMANCE: the slowest operations to settle: '..table.concat(parts,'; ')
        ..' (hd2.diagnostics.performance() has every mod\'s time)'
end
function M.reset_for_tests()
    starts,nested,depth,owners,window,window_updates,game_time={},{},0,{},0,0,0
    recording,history=false,nil
    runtime_series=setmetatable({},{__mode='k'})
end
return M
