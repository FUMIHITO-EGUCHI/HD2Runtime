-- Named melee source records, including gun bashes and per-stance hit volumes.
local M={}
local function data()return require('hd2runtime/domains/melee_authoring')end
function M.names()
    local out={};for name in pairs(data().entries)do out[#out+1]=name end;table.sort(out);return out
end
function M.target(name,path)
    local e=assert(data().entries[name],'unknown reviewed melee weapon: '..tostring(name))
    local methods={}
    function methods.describe()
        local t=e.targets[path or'tuning'];local fields={};local zones={}
        if t then for _,f in pairs(t.fields)do fields[#fields+1]={semanticFieldId=f.semanticFieldId,displayName=f.displayName,
            currentDefault=f.currentDefault,min=f.min,max=f.max,editable=f.editable,shared=f.shared,lifecycle=f.lifecycle}end end
        for k,v in pairs(e.targets)do if k~='tuning'then zones[#zones+1]={key=k,label=v.label,consumers=v.consumers}end end
        table.sort(fields,function(a,b)return a.semanticFieldId<b.semanticFieldId end)
        table.sort(zones,function(a,b)return a.key<b.key end)
        return {name=name,path=path or'tuning',fields=fields,zones=zones,consumers=t and t.consumers,
            note='Hit volume axes are local to the animated bone. Reach depends on the animation and volume together.'}
    end
    function methods.zone(_,id)
        if type(id)=='number'then id='zone_'..id end
        assert(id~='tuning'and e.targets[id],'unknown reviewed melee hit volume: '..tostring(id))
        return M.target(name,id)
    end
    function methods.zones()
        local out={};for _,z in ipairs(methods.describe().zones)do out[#out+1]=M.target(name,z.key)end;return out
    end
    return setmetatable({resource='melee',melee=name,path=path or'tuning'},{__index=methods})
end
return setmetatable(M,{__call=function(_,name)return M.target(name)end})
