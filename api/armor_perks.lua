local D=require('hd2runtime/domains/armor_perks')
local M={}
local function copy(x)
    if type(x)~='table'then return x end
    local out={};for k,v in pairs(x)do out[k]=copy(v)end;return out
end
function M.get(identity)
    local entry
    for _,e in ipairs(D.entries)do
        if e.id==identity or type(identity)=='string'and e.name:lower()==identity:lower()then entry=e;break end
    end
    assert(entry,'unknown armor perk: '..tostring(identity))
    local methods={}
    function methods.fields()return copy(entry.fields)end
    function methods.describe()
        return {id=entry.id,name=entry.name,description=entry.description,icon=entry.icon,
            armorKits=entry.armorKits,fields=copy(entry.fields),liveTested=false}
    end
    return setmetatable({resource='armor_perk',armor_perk=entry.id},{__index=methods})
end
return M
