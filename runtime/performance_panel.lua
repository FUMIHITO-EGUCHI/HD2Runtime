-- The F10 panel's Performance tab (0.31.1; runtime/runtime_settings.lua draws the window around it): a live stacked
-- graph of the time HD2Runtime and its mods take per update, and the parts that take the most. The numbers are
-- runtime/perf_watch.lua's own-time measurements (a callback inside another counts once, as the inner one's), which
-- only record while this tab is shown: each mod has work and overlay series, each part of the Runtime another
-- (a scheduler watch's module, an event source, the Runtime's own overlays). The game's own work is not in them.
--
-- The graph has one column per perf_watch bin (M.BINS of M.BIN seconds, newest on the right) and changes only when a
-- bin completes; every column always draws the same number of rectangles (an empty segment is transparent), so a new
-- bin updates rectangles in place instead of rebuilding the frame. The five heaviest series of the last two seconds
-- keep their colour while they stay among the five; the rest are drawn grey.
local perf=require('hd2runtime/runtime/perf_watch')
local metrics=require('hd2runtime/runtime/metrics')
local i18n=require('hd2runtime/runtime/i18n')
local T=i18n.t
local M={}
local chart=require('hd2runtime/runtime/performance_chart')
M.PALETTE,M.REST,M.CLEAR=chart.PALETTE,chart.REST,chart.CLEAR
M.ROWS=7                   -- rows of the table
M.RECENT=4                 -- bins of the summary line (one second)
M.RANK=8                   -- bins the ranking and peaks cover (two seconds)
M.SCALES={0.05,0.1,0.2,0.5,1,2,5,10,20,50,100,200,500,1000}   -- graph tops, ms
M.HEIGHT=510               -- the tab's content height at scale 1 (the window keeps room for it)

local NAV_BG,NAV_HOVER={10,13,17,255},{38,44,51,255}
local mode,page='runtime',1
local function page_rows()return mode=='global'and 5 or M.ROWS end
local state={head=-1,colour={},owner={},stats=nil}
function M.reset()require('hd2runtime/runtime/memory_watch').pause();state={head=-1,colour={},owner={},stats=nil};page=1 end
function M.mode()return mode end
function M.select_mode(value)
    assert(value=='runtime'or value=='global'or value=='memory','unknown performance mode')
    if value==mode then return end
    pcall(require('hd2runtime/runtime/log').emit,'[HD2Runtime] settings performance mode requested: '..mode..' -> '..value)
    -- Both views consume the same history. Changing the filter must not erase samples or an active timing stack.
    if value~='global'then require('hd2runtime/runtime/global_perf').stop()end
    mode=value;M.reset()
end
function M.controls(box,k)
    return {
        {id='global',label=T('Global'),x=box.x,y=box.y,w=100*k,h=28*k},
        {id='runtime',label=T('Runtime'),x=box.x+106*k,y=box.y,w=100*k,h=28*k},
        {id='memory',label=T('Memory'),x=box.x+212*k,y=box.y,w=100*k,h=28*k},
        {id='previous',label='<',x=box.x+148*k,y=box.y+482*k,w=36*k,h=28*k},
        {id='next',label='>',x=box.x+190*k,y=box.y+482*k,w=36*k,h=28*k},
    }
end

local function ms(seconds)
    local v=seconds*1000
    if v>=10 then return('%.1f ms'):format(v)end
    if v>=0.01 then return('%.2f ms'):format(v)end
    if v>0 then return '<0.01 ms'end
    return '0 ms'
end
M.ms=ms

-- The last n bins' slots, oldest first.
local function slots(h,n)
    local filled=math.min(h.head,perf.BINS)
    n=math.min(n,filled)
    local out={}
    for i=1,n do out[i]=(h.head-n+i-1)%perf.BINS+1 end
    return out
end
local function mean(values,list)
    if #list==0 then return 0 end
    local sum=0
    for _,slot in ipairs(list)do sum=sum+(values[slot]or 0)end
    return sum/#list
end
local function largest(values,list)
    local top=0
    for _,slot in ipairs(list)do local v=values[slot]or 0;if v>top then top=v end end
    return top
end

-- Everything the tab shows, recomputed once per bin: {rows, total, frame, peak, top (graph max), colours}.
function M.stats(h)
    if state.stats and state.head==h.head and state.series==h.series then return state.stats end
    local recent,rank=slots(h,M.RECENT),slots(h,M.RANK)
    local rows,total,menu={},0,nil
    for _,s in ipairs(h.list)do if mode=='global'or s.kind~='external'then
        local row={series=s,id=s.id,name=s.name,kind=s.kind,average=mean(s.values,recent),ranked=mean(s.values,rank),
            peak=largest(s.peaks,rank)}
        if mode=='global'and s.kind=='menu'then menu=row
        else total=total+row.average;rows[#rows+1]=row end
    end end
    if mode=='global'then
        for owner in pairs(perf.inventory())do
            if not h.series[owner]then rows[#rows+1]={id=owner,name=perf.mod_name(owner),
                kind=perf.runtime_mod(owner)and'mod'or'external',average=0,ranked=0,peak=0,unmeasured=true}end
        end
    end
    table.sort(rows,function(a,c)
        if not not a.unmeasured~=not not c.unmeasured then return not a.unmeasured end
        if a.ranked~=c.ranked then return a.ranked>c.ranked end
        return a.id<c.id
    end)
    -- Colours: a series keeps its colour while it stays among the five heaviest; a newcomer takes a free one.
    local keep={}
    for i=1,math.min(#M.PALETTE,#rows)do if rows[i].ranked>0 then keep[rows[i].id]=true end end
    for index,id in pairs(state.owner)do
        if not keep[id]then state.owner[index]=nil;state.colour[id]=nil end
    end
    for id in pairs(keep)do
        if not state.colour[id]then
            for index=1,#M.PALETTE do
                if not state.owner[index]then state.owner[index]=id;state.colour[id]=index;break end
            end
        end
    end
    -- The graph's top: the next scale above the tallest column (stacked total) in view.
    local tallest=0
    for _,slot in ipairs(slots(h,perf.BINS))do
        local sum=0
        for _,s in ipairs(h.list)do if (mode=='global'and s.kind~='menu')or(mode=='runtime'and s.kind~='external')then sum=sum+(s.values[slot]or 0)end end
        if sum>tallest then tallest=sum end
    end
    local top=M.SCALES[#M.SCALES]
    for _,v in ipairs(M.SCALES)do if v/1000>=tallest*1.15 then top=v;break end end
    -- Each column's six segments (the palette's series, then the rest), oldest column first; nil before the data.
    local filled=math.min(h.head,perf.BINS)
    local columns={}
    for i=1,perf.BINS do
        local b=filled-perf.BINS+i
        if b>=1 then
            local slot=(h.head-filled+b-1)%perf.BINS+1
            local column,shown,sum={},0,0
            for _,s in ipairs(h.list)do if (mode=='global'and s.kind~='menu')or(mode=='runtime'and s.kind~='external')then sum=sum+(s.values[slot]or 0)end end
            for index=1,#M.PALETTE do
                local id=state.owner[index]
                local s=id and h.series[id]
                column[index]=s and s.values[slot]or 0
                shown=shown+column[index]
            end
            column[#M.PALETTE+1]=math.max(0,sum-shown)
            columns[i]=column
        end
    end
    state.head=h.head;state.series=h.series
    state.stats={rows=rows,menu=menu,total=total,frame=mean(h.frames,recent),peak=largest(h.peaks,rank),top=top/1000,
        filled=filled,columns=columns}
    return state.stats
end
function M.colour(id)local index=state.colour[id];return index and M.PALETTE[index]or M.REST end

-- What the tab draws for one bin, in drawing order: {{rect = {x, y, w, h, colour, z}} | {text = {s, x, cy, size, colour,
-- font, align}}}. 0.31.2: built once per bin (and per box, scale and language) and replayed every frame: the numbers,
-- the translated labels, each row's fitted name and the graph's rectangles change only when a bin completes, and the
-- F10 panel used to format, translate and fit them again at every frame (about 0.8 ms a frame while the tab was shown).
local function build(d,C,S,box,k,st)
    local ops={}
    local function rect(x,y,w,h,c,z)ops[#ops+1]={rect={x,y,w,h,c,z}}end
    local function text(s,x,cy,size,colour,font,align)ops[#ops+1]={text={s,x,cy,size,colour,font,align}}end
    local x,y,w=box.x,box.y+38*k,box.w
    -- The summary: the total per update, its share of the frame time and the frame rate.
    text(mode=='global'and T('Observed callbacks: %s per frame',ms(st.total))or T('Runtime and mods: %s per frame',ms(st.total)),x,y+12*k,S.body*k,C.text,'body')
    local share=st.frame>0 and st.total/st.frame*100 or 0
    local fps=st.frame>0 and math.floor(1/st.frame+0.5)or 0
    local coverage=''
    if mode=='global'then
        local measured,mods=0,0
        for _,row in ipairs(st.rows)do if row.kind~='runtime'and row.kind~='unattributed'then
            mods=mods+1;if not row.unmeasured then measured=measured+1 end
        end end
        coverage=T(' | %d / %d mods measured',measured,mods)
        local status=require('hd2runtime/runtime/global_perf').status()
        if status.limited or status.unavailable then coverage=coverage..T(' (partial coverage)')end
    end
    text(T('%s of the frame time  |  %d FPS',('%.1f%%'):format(share),fps)..coverage,x,y+32*k,S.small*k,C.dim,'body')
    local colours={unpack(M.PALETTE)};colours[#colours+1]=M.REST
    local ty=chart.draw(rect,text,C,S,box,k,st.top,ms,st.columns,perf.BINS,colours)
    -- The table: the heaviest series of the last two seconds.
    text(T('AVERAGE'),x+w-120*k,ty,S.tiny*k,C.gold_dim,'title','right')
    text(T('PEAK'),x+w,ty,S.tiny*k,C.gold_dim,'title','right')
    ty=ty+24*k
    local most=st.rows[1]and st.rows[1].average or 0
    for i=1,math.min(page_rows(),#st.rows-(page-1)*page_rows())do
        local row=st.rows[(page-1)*page_rows()+i]
        local ry=ty+(i-1)*26*k
        rect(x,ry-5*k,10*k,10*k,M.colour(row.id),5)
        local tag=row.kind=='unattributed'and'?'or row.kind=='mod'and'[R]'or(row.kind=='external'and i18n.upper(T('MOD'))or'HD2R')
        text(tag,x+18*k,ry,S.tiny*k,row.kind=='mod'and C.faint or C.gold_dim,'title')
        local label=row.kind=='unattributed'and T('Unattributed callback work')or row.name
        local lines=d:wrap(label,w*0.45,{size=S.small*k,lines=1})
        text(lines[1]or label,x+70*k,ry,S.small*k,C.text,'body')
        -- a bar for its share of the heaviest
        local bw=most>0 and(w*0.18)*row.average/most or 0
        if bw>=1 then rect(x+w*0.56,ry-3*k,bw,6*k,M.colour(row.id),4)end
        text(row.unmeasured and T('Not measured')or ms(row.average),x+w-120*k,ry,S.small*k,C.dim,'body','right')
        text(row.unmeasured and'-'or ms(row.peak),x+w,ry,S.small*k,C.faint,'body','right')
    end
    if mode=='global'then
        rect(x,y+382*k,w,math.max(1,k),C.line,4)
        text(T('F10 menu'),x,y+404*k,S.small*k,C.dim,'body')
        text(ms(st.menu and st.menu.average or 0),x+w-120*k,y+404*k,S.small*k,C.dim,'body','right')
        text(ms(st.menu and st.menu.peak or 0),x+w,y+404*k,S.small*k,C.faint,'body','right')
        text(T('Menu and performance display only; no rendering or profiling while closed.'),
            x,y+428*k,S.tiny*k,C.faint,'body')
    end
    text(T('Page %d / %d',page,math.max(1,math.ceil(#st.rows/page_rows()))),x,y+458*k,S.small*k,C.dim,'body')
    text(T('[R] Runtime mod | ? Unresolved game/mod work | Exclusive time'),x+w,y+458*k,S.tiny*k,C.faint,'body','right')
    return ops
end

-- Draws the tab into box {x, y, w, h} at scale k. ctx = {d, text(d, s, x, cy, size, colour, font, align), C, S}.
function M.draw(ctx,box,k,mouse,press)
    local d,text,C,S=ctx.d,ctx.text,ctx.C,ctx.S
    local x,y=box.x,box.y
    local controls=M.controls(box,k)
    for _,button in ipairs(controls)do
        if mode~='memory'or(button.id~='previous'and button.id~='next')then
        local hover=mouse and mouse.x and mouse.y and mouse.x>=button.x and mouse.x<button.x+button.w
            and mouse.y>=button.y and mouse.y<button.y+button.h
        if press and hover then
            if ctx.sound then ctx.sound('click')end
            if button.id=='global'or button.id=='runtime'or button.id=='memory'then M.select_mode(button.id)
            else
                local count=state.stats and#state.stats.rows or 0
                page=math.max(1,math.min(math.max(1,math.ceil(count/page_rows())),page+(button.id=='next'and 1 or-1)))
                state.frame=nil
            end
        end
        local navigation=button.id=='previous'or button.id=='next'
        local bg=navigation and(hover and NAV_HOVER or NAV_BG)or(mode==button.id and C.header or(hover and C.hover or C.panel))
        d:rect(button.x,button.y,button.w,button.h,bg,3)
        if navigation then d:rect(button.x,button.y,button.w,math.max(1,k),C.line_strong,4)end
        text(d,button.label,button.x+button.w/2,button.y+button.h/2,S.small*k,
            mode==button.id and C.gold or C.dim,'body','center')
    end
    end
    perf.record(mode~='memory')
    if mode=='memory'then require('hd2runtime/runtime/memory_panel').draw(ctx,box,k);return end
    if not metrics.now()then
        text(d,T('No precise clock: nothing can be measured.'),x,y+58*k,S.body*k,C.dim,'body')
        return
    end
    if mode=='global'then require('hd2runtime/runtime/global_perf').start()end
    local h=perf.history(mode)
    if not h or h.head==0 then
        text(d,T('Measuring...'),x,y+58*k,S.body*k,C.dim,'body')
        return
    end
    local st=M.stats(h)
    page=math.min(page,math.max(1,math.ceil(#st.rows/page_rows())))
    local language=i18n.language()
    local f=state.frame
    if not(f and f.stats==st and f.k==k and f.x==x and f.y==y and f.w==box.w and f.language==language)then
        f={stats=st,k=k,x=x,y=y,w=box.w,language=language,ops=build(d,C,S,box,k,st)}
        state.frame=f
    end
    local function replay(builder)
        for _,op in ipairs(f.ops)do
            local r=op.rect
            if r then builder:rect(r[1],r[2],r[3],r[4],r[5],r[6])
            else
                local t=op.text
                text(builder,t[1],t[2],t[3],t[4],t[5],t[6],t[7])
            end
        end
    end
    if d._retain then d:_retain('runtime-performance',f,replay)else replay(d)end
end
return M
