local memory=require('hd2runtime/runtime/memory_watch')
local metrics=require('hd2runtime/runtime/metrics')
local i18n=require('hd2runtime/runtime/i18n')
local T=i18n.t
local M={}
local categories={'Cache payloads','Snapshot payloads','Event buffers','Native buffers','Permanent native pages'}
local chart=require('hd2runtime/runtime/performance_chart')
local colours=chart.PALETTE
local frame
local function mib(bytes)return ('%.3f MiB'):format(bytes/1048576)end
function M.draw(ctx,box,k)
    local history,head=memory.sample(metrics.now()or os.clock())
    local language=i18n.language()
    if not(frame and frame.head==head and frame.x==box.x and frame.y==box.y and frame.w==box.w
        and frame.k==k and frame.language==language)then
        local ops={}
        local function text(s,x,y,size,c,font,align)ops[#ops+1]={text={s,x,y,size,c,font or'body',align}}end
        local function rect(x,y,w,h,c,z)ops[#ops+1]={rect={x,y,w,h,c,z}}end
        local C,S=ctx.C,ctx.S
        local x,y,w=box.x,box.y+38*k,box.w
        local current=history[(head-1)%memory.BINS+1]
        local peak,peaks=0,{}
        for _,sample in pairs(history)do
            peak=math.max(peak,sample.total)
            for category,value in pairs(sample.categories)do peaks[category]=math.max(peaks[category]or 0,value)end
        end
        text(T('Tracked Runtime memory: %s',mib(current.total)),x,y+12*k,S.body*k,C.text)
        text(T('Visible history peak: %s',mib(peak)),x,y+32*k,S.small*k,C.dim)
        local top=0.05
        for _,scale in ipairs({0.05,0.1,0.2,0.5,1,2,5,10,20,50,100,200,500,1000})do
            top=scale;if top*1048576>=peak*1.15 then break end
        end
        top=math.max(top*1048576,peak*1.15)
        local columns={}
        local filled=math.min(head,memory.BINS)
        for column=1,memory.BINS do
            local n=filled-memory.BINS+column
            local sample=n>=1 and history[(head-filled+n-1)%memory.BINS+1]
            local values={}
            for index,category in ipairs(categories)do values[index]=sample and sample.categories[category]or 0 end
            columns[column]=values
        end
        local function axis(bytes)return ('%.2f MiB'):format(bytes/1048576)end
        local ty=chart.draw(rect,text,C,S,box,k,top,axis,columns,memory.BINS,colours)
        text(T('CURRENT'),x+w-120*k,ty,S.tiny*k,C.gold_dim,'title','right')
        text(T('PEAK'),x+w,ty,S.tiny*k,C.gold_dim,'title','right')
        ty=ty+24*k
        local most=0
        for _,value in pairs(current.categories)do most=math.max(most,value)end
        for index,category in ipairs(categories)do
            local cy=ty+(index-1)*26*k
            rect(x,cy-5*k,10*k,10*k,colours[index],5)
            text('HD2R',x+18*k,cy,S.tiny*k,C.gold_dim,'title')
            local label=T(category)
            local lines=ctx.d:wrap(label,w*0.45,{size=S.small*k,lines=1})
            text(lines[1]or label,x+70*k,cy,S.small*k,C.text)
            local value=current.categories[category]or 0
            local bw=most>0 and w*0.18*value/most or 0
            if bw>=1 then rect(x+w*0.56,cy-3*k,bw,6*k,colours[index],4)end
            text(mib(value),x+w-120*k,cy,S.small*k,C.dim,'body','right')
            text(mib(peaks[category]or 0),x+w,cy,S.small*k,C.faint,'body','right')
        end
        rect(x,y+382*k,w,math.max(1,k),C.line,4)
        text(T('One sample per second while this view is open.'),x,y+404*k,S.small*k,C.dim)
        text(T('Known payloads only; not total Runtime RAM.'),x,y+428*k,S.tiny*k,C.faint)
        text(T('Excludes Lua object overhead, engine/GPU allocations and other mods.'),x,y+458*k,S.tiny*k,C.faint)
        frame={head=head,x=box.x,y=box.y,w=box.w,k=k,language=language,ops=ops}
    end
    local function replay(d)
        for _,op in ipairs(frame.ops)do
            if op.rect then d:rect(unpack(op.rect))else ctx.text(d,unpack(op.text))end
        end
    end
    if ctx.d._retain then ctx.d:_retain('runtime-memory',frame,replay)else replay(ctx.d)end
end
return M
