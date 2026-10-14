-- Known Runtime-owned payloads only, never the shared Lua heap or process RSS.
-- Weak keys do not prolong allocation lifetimes. Bookkeeping occurs at allocation;
-- aggregation and history sampling occur only when the Memory page draws.
local M={BINS=90}
local allocations=setmetatable({},{__mode='k'})
local holders=setmetatable({},{__mode='k'})
local permanent={}
local history,head,last={},0,nil
function M.buffer(buffer,size,category)
    allocations[buffer]={size=size,category=category or 'Native buffers'}
end
function M.fields(holder,category,fields)
    holders[holder]={category=category,fields=fields}
end
function M.permanent(address,size)permanent[address]=size end
function M.snapshot()
    local categories,total,seen={},0,{}
    local function add(category,size)
        categories[category]=(categories[category]or 0)+size;total=total+size
    end
    for _,entry in pairs(allocations)do add(entry.category,entry.size)end
    -- Prefer the cache category when a snapshot references the very same string.
    for _,category in ipairs({'Cache payloads','Snapshot payloads','Event buffers'})do
        for holder,entry in pairs(holders)do if entry.category==category then
            for _,field in ipairs(entry.fields)do
                local bytes=rawget(holder,field)
                if type(bytes)=='string'and not seen[bytes]then seen[bytes]=true;add(category,#bytes)end
            end
        end end
    end
    for _,size in pairs(permanent)do add('Permanent native pages',size)end
    return {total=total,categories=categories}
end
function M.pause()last=nil end
function M.sample(now)
    if not last or now<last or now-last>=1 then
        last=now;head=head+1
        history[(head-1)%M.BINS+1]=M.snapshot()
    end
    return history,head
end
return M
