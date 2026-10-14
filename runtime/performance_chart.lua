-- Shared geometry and palette for the CPU and memory performance views.
local M={}
M.PALETTE={{255,199,44,255},{64,196,255,255},{120,220,130,255},{255,110,170,255},{176,140,255,255}}
M.REST={120,126,134,255}
M.CLEAR={0,0,0,0}
function M.draw(rect,text,C,S,box,k,top,format,columns,count,colours)
    local gx,gy,gw,gh=box.x+62*k,box.y+90*k,box.w-62*k,155*k
    rect(gx,gy,gw,gh,C.header,3)
    for n=0,2 do
        local ly=gy+gh-gh*n/2
        rect(gx,ly-math.max(1,k)/2,gw,math.max(1,k),n==0 and C.line_strong or C.line,4)
        text(format(top*n/2),gx-8*k,ly,S.tiny*k,C.faint,'body','right')
    end
    local cw=gw/count
    local gap=cw>4*k and math.max(1,k)or 0
    for i=1,count do
        local column=columns[i]
        local cx,base=gx+(i-1)*cw,gy+gh
        for index,colour in ipairs(colours)do
            local value=column and column[index]or 0
            local height=math.min(gh,value/top*gh)
            if height>=0.5 then
                base=base-height
                rect(cx,base,cw-gap,height,colour,5)
            else rect(cx,gy+gh-1,cw-gap,1,M.CLEAR,5)end
        end
    end
    return gy+gh+28*k
end
return M
