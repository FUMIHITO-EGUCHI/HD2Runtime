-- The F10 panel's Performance tab (0.31.1; runtime/runtime_settings.lua draws the window around it): a live stacked
-- graph of the time HD2Runtime and its mods take per update, and the parts that take the most. The numbers are
-- runtime/perf_watch.lua's own-time measurements (a callback inside another counts once, as the inner one's), which
-- only record while this tab is shown: each mod is one series (every callback of it), each part of the Runtime another
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
M.PALETTE={{255,199,44,255},{64,196,255,255},{120,220,130,255},{255,110,170,255},{176,140,255,255}}
M.REST={120,126,134,255}
M.CLEAR={0,0,0,0}
M.ROWS=8                   -- rows of the table
M.RECENT=4                 -- bins of the summary line (one second)
M.RANK=8                   -- bins the ranking and peaks cover (two seconds)
M.SCALES={0.05,0.1,0.2,0.5,1,2,5,10,20,50,100,200,500,1000}   -- graph tops, ms
M.HEIGHT=510               -- the tab's content height at scale 1 (the window keeps room for it)

local state={head=-1,colour={},owner={},stats=nil}
function M.reset()state={head=-1,colour={},owner={},stats=nil}end

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
    if state.stats and state.head==h.head then return state.stats end
    local recent,rank=slots(h,M.RECENT),slots(h,M.RANK)
    local rows,total={},0
    for _,s in ipairs(h.list)do
        local row={series=s,id=s.id,name=s.name,kind=s.kind,average=mean(s.values,recent),ranked=mean(s.values,rank),
            peak=largest(s.peaks,rank)}
        total=total+row.average
        rows[#rows+1]=row
    end
    table.sort(rows,function(a,c)
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
        for _,s in ipairs(h.list)do sum=sum+(s.values[slot]or 0)end
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
            for _,s in ipairs(h.list)do sum=sum+(s.values[slot]or 0)end
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
    state.head=h.head
    state.stats={rows=rows,total=total,frame=mean(h.frames,recent),peak=largest(h.peaks,rank),top=top/1000,
        filled=filled,columns=columns}
    return state.stats
end
function M.colour(id)local index=state.colour[id];return index and M.PALETTE[index]or M.REST end

-- Draws the tab into box {x, y, w, h} at scale k. ctx = {d, text(d, s, x, cy, size, colour, font, align), C, S}.
function M.draw(ctx,box,k)
    local d,text,C,S=ctx.d,ctx.text,ctx.C,ctx.S
    local x,y,w=box.x,box.y,box.w
    perf.record(true)
    if not metrics.now()then
        text(d,T('No precise clock: nothing can be measured.'),x,y+20*k,S.body*k,C.dim,'body')
        return
    end
    local h=perf.history()
    if not h or h.head==0 then
        text(d,T('Measuring...'),x,y+20*k,S.body*k,C.dim,'body')
        return
    end
    local st=M.stats(h)
    -- The summary: the total per update, its share of the frame time and the frame rate.
    text(d,T('Runtime and mods: %s per frame',ms(st.total)),x,y+12*k,S.body*k,C.text,'body')
    local share=st.frame>0 and st.total/st.frame*100 or 0
    local fps=st.frame>0 and math.floor(1/st.frame+0.5)or 0
    text(d,T('%s of the frame time  |  %d FPS',('%.1f%%'):format(share),fps),x,y+32*k,S.small*k,C.dim,'body')
    -- The graph: a gutter with the scale on the left, three grid lines, one column per bin.
    local gutter=62*k
    local gx,gy,gw,gh=x+gutter,y+52*k,w-gutter,190*k
    d:rect(gx,gy,gw,gh,C.header,3)
    for n=0,2 do
        local ly=gy+gh-gh*n/2
        d:rect(gx,ly-math.max(1,k)/2,gw,math.max(1,k),n==0 and C.line_strong or C.line,4)
        text(d,ms(st.top*n/2),gx-8*k,ly,S.tiny*k,C.faint,'body','right')
    end
    local columns=perf.BINS
    local cw=gw/columns
    local gap=cw>4*k and math.max(1,k)or 0
    for i=1,columns do
        local column=st.columns[i]
        local cx=gx+(i-1)*cw
        local base=gy+gh
        -- the five coloured series in palette order, then the rest in grey: always six rectangles
        for index=1,#M.PALETTE+1 do
            local v=column and column[index]or 0
            local sh=math.min(gh,v/st.top*gh)
            if sh>=0.5 then
                base=base-sh
                d:rect(cx,base,cw-gap,sh,index<=#M.PALETTE and M.PALETTE[index]or M.REST,5)
            else
                d:rect(cx,gy+gh-1,cw-gap,1,M.CLEAR,5)
            end
        end
    end
    -- The table: the heaviest series of the last two seconds.
    local ty=gy+gh+28*k
    text(d,T('AVERAGE'),x+w-120*k,ty,S.tiny*k,C.gold_dim,'title','right')
    text(d,T('PEAK'),x+w,ty,S.tiny*k,C.gold_dim,'title','right')
    ty=ty+24*k
    local most=st.rows[1]and st.rows[1].average or 0
    for i=1,math.min(M.ROWS,#st.rows)do
        local row=st.rows[i]
        local ry=ty+(i-1)*26*k
        d:rect(x,ry-5*k,10*k,10*k,M.colour(row.id),5)
        local tag=row.kind=='mod'and i18n.upper(T('MOD'))or'HD2R'
        text(d,tag,x+18*k,ry,S.tiny*k,row.kind=='mod'and C.faint or C.gold_dim,'title')
        local lines=d:wrap(row.name,w*0.45,{size=S.small*k,lines=1})
        text(d,lines[1]or row.name,x+70*k,ry,S.small*k,C.text,'body')
        -- a bar for its share of the heaviest
        local bw=most>0 and(w*0.18)*row.average/most or 0
        if bw>=1 then d:rect(x+w*0.56,ry-3*k,bw,6*k,M.colour(row.id),4)end
        text(d,ms(row.average),x+w-120*k,ry,S.small*k,C.dim,'body','right')
        text(d,ms(row.peak),x+w,ry,S.small*k,C.faint,'body','right')
    end
end
return M
