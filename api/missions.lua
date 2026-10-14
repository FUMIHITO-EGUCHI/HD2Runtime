-- Mission identities resolve to shared launch-time definitions or mission deltas.
local D=require('hd2runtime/domains/missions')
local W=require('hd2runtime/domains/mission_writes')
local M={}
local function copy(x)
    if type(x)~='table'then return x end
    local r={};for k,v in pairs(x)do r[k]=copy(v)end;return r
end
local function describe(m)
    local s=D.sources[m.source]
    return {id=m.id,name=m.name,faction=m.faction,description=m.description,nameSource=m.nameSource,
        timerGroup=m.source,sharedWith=copy(s.missions),fields=W.fields(m.id),limitations=copy(D.limitations)}
end
function M.get(id)
    local m=assert(W.entry(id),'unknown mission identity: '..tostring(id))
    return setmetatable({resource='mission',mission=m.id},{__index={describe=function()return describe(m)end}})
end
function M.list(filter)
    assert(filter==nil or type(filter)=='table','mission filter must be a table')
    for k,v in pairs(filter or{})do
        assert(k=='faction','unsupported mission filter')
        assert(v=='terminids'or v=='automatons'or v=='illuminate','unknown mission faction')
    end
    local out={}
    for _,m in ipairs(D.missions)do
        if not filter or not filter.faction or m.faction==filter.faction then out[#out+1]=describe(m)end
    end
    return out
end
return M
