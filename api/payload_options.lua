-- Payload options (0.31.2; docs/explosions.md "Payload options"; scripts/generate_payload_options.py ->
-- domains/payload_options.lua): every value a projectile payload field takes, grouped by source family, for an editor's
-- picker. hd2.explosions.payload_options(filter) lists every catalogued explosion a payload accepts;
-- hd2.explosions.payload_options(terminal, filter) (or terminal:payload_options(filter)) lists what one payload field
-- (a primary, secondary or support weapon's terminal action) takes: its own explosion, none and every option it does not
-- refuse, each with its value handle and the acknowledgements a write of it needs. Offline: no game reads, no raw ids.
local options=require('hd2runtime/domains/payload_options')
local catalogue=require('hd2runtime/domains/explosion_catalogue')
local catalogue_api=require('hd2runtime/api/explosion_catalogue')
local M={}

local function copy(value)
    if type(value)~='table'then return value end
    local out={}
    for key,item in pairs(value)do out[key]=copy(item)end
    return out
end
local GROUP_LABEL={}
for _,group in ipairs(options.groups)do GROUP_LABEL[group.id]=group.label end

local function public(name)
    local o=options.options[name]
    return {name=o.name,label=o.label,owner=o.owner,group=o.group,group_label=GROUP_LABEL[o.group],family=o.family,
        damage=o.damage,durable_damage=o.durableDamage,inner_radius=o.innerRadius,outer_radius=o.outerRadius,
        statuses=copy(o.statuses),lingering_field=o.lingeringField,fire=o.fire,shrapnel=o.shrapnel,arc=o.arc,
        warnings=copy(o.warnings),shared_row=o.sharedRow,
        package={mission=o.package.mission,loaded_by_runtime=o.package.loadedByRuntime,via=o.package.via},
        acknowledgements=copy(o.acknowledgements)}
end
-- Filter keys: group (a group id), search (a substring of the name, label or owner, case-insensitive), warning (keep
-- only options with this warning code), without_warning (drop options with this warning code).
local FILTERS={group=true,search=true,warning=true,without_warning=true}
local function keep(o,filter)
    if filter.group~=nil and o.group~=filter.group then return false end
    if filter.search~=nil then
        local text=tostring(filter.search):lower()
        if not(o.name:find(text,1,true)or o.label:lower():find(text,1,true)or o.owner:lower():find(text,1,true))then
            return false
        end
    end
    local function has(code)for _,item in ipairs(o.warnings)do if item==code then return true end end return false end
    if filter.warning~=nil and not has(filter.warning)then return false end
    if filter.without_warning~=nil and has(filter.without_warning)then return false end
    return true
end
local function check_filter(filter)
    assert(filter==nil or type(filter)=='table','payload_options(filter): filter must be a table or nil')
    for key in pairs(filter or{})do assert(FILTERS[key],'unsupported payload option filter: '..tostring(key))end
    if filter and filter.group~=nil then
        assert(GROUP_LABEL[filter.group],'unknown payload option group: '..tostring(filter.group))
    end
    return filter or{}
end
local function union(...)
    local seen,out={},{}
    for _,list in ipairs({...})do
        for _,item in ipairs(list)do if not seen[item]then seen[item]=true;out[#out+1]=item end end
    end
    table.sort(out)
    return out
end

-- {id, label, count} in display order (count: options in the group).
function M.groups()
    local counts={}
    for _,name in ipairs(options.order)do
        local group=options.options[name].group
        counts[group]=(counts[group]or 0)+1
    end
    local out={}
    for index,group in ipairs(options.groups)do out[index]={id=group.id,label=group.label,count=counts[group.id]or 0}end
    return out
end
-- {code = text} of every warning an option may carry.
function M.warnings()return copy(options.warnings)end
-- Every catalogued explosion a payload accepts, in group order, each with its value handle hd2.explosion(name).
function M.list(filter)
    filter=check_filter(filter)
    local out={}
    for _,name in ipairs(options.order)do
        local o=options.options[name]
        if keep(o,filter)then
            local item=public(name)
            item.value=catalogue_api.handle(name)
            out[#out+1]=item
        end
    end
    return out
end

-- The payload field a terminal action handle writes: kind, the domain entry and the field descriptor.
local function field_of(target)
    assert(type(target)=='table'and rawget(target,'path')=='terminal_action',
        'payload_options(target): target must be weapon:attack(role):projectile():terminal_action(phase)')
    local kind=rawget(target,'resource')
    local database=kind=='player_weapon'and require('hd2runtime/domains/player_weapon_authoring')
        or kind=='support_weapon'and require('hd2runtime/domains/support_weapon_authoring')
    assert(database,'payload_options(target): a primary, secondary or support weapon terminal action')
    local weapon=assert(database.weapons[rawget(target,'weapon')],'unknown weapon: '..tostring(rawget(target,'weapon')))
    local id='terminal.'..tostring(rawget(target,'attack'))..'.'..tostring(rawget(target,'phase'))..'.explosion'
    for _,field in ipairs(weapon.fields)do
        if field.semanticFieldId==id then return kind,weapon,field end
    end
    error('no payload field '..id..' on '..weapon.name,2)
end
-- Explosion type -> another primary or secondary weapon's terminal explosion handle that names it (a player payload
-- takes that handle without the catalogue's acknowledgements: docs/explosions.md "Explosions as payloads").
local weapon_handles
local function weapon_handle(explosion_type)
    if not weapon_handles then
        weapon_handles={}
        local database=require('hd2runtime/domains/player_weapon_authoring')
        local names={}
        for name in pairs(database.weapons)do names[#names+1]=name end
        table.sort(names)
        for _,name in ipairs(names)do
            local weapon=database.weapons[name]
            for _,field in ipairs(weapon.fields)do
                local current=field.type=='explosion_reference'and field.currentDefault.explosionType or 0
                if current~=0 and not weapon.ordinaryWritesBlocked and field.editable and not weapon_handles[current]then
                    weapon_handles[current]={weapon=name,attack=field.referenceRole,phase=field.referencePhase}
                end
            end
        end
    end
    return weapon_handles[explosion_type]
end
local by_type
local function name_of(explosion_type)
    if not by_type then
        by_type={}
        for id,entry in pairs(catalogue.explosions)do by_type[entry.type]=id end
    end
    return by_type[explosion_type]
end

-- Everything one payload field takes: {field, resource, weapon, attack, phase, current, current_label, editable,
-- reason, shared, acknowledgements {own, none, catalogue}, own {value, name, label, acknowledgements} (nil without an
-- explosion of its own), none {value, acknowledgements}, options (as list(), each with value and acknowledgements),
-- excluded {name, label, reason}, groups (as groups(), counting this field's options)}.
function M.for_target(target,filter)
    filter=check_filter(filter)
    local kind,weapon,field=field_of(target)
    local base={}
    if field.acknowledgement then base[#base+1]=field.acknowledgement end
    if field.affectsMultipleWeapons then base[#base+1]='allow_shared'end
    base=union(base)
    local catalogue_acks=union(base,{'allow_unverified_reference','allow_unverified_effect'})
    local current_type=field.currentDefault.explosionType
    local current=current_type~=0 and name_of(current_type)or nil
    local excluded_by=(options.fields[kind..':'..weapon.name..':'..field.semanticFieldId]or{}).excluded or{}
    local result={field='terminal.explosion',resource=kind,weapon=weapon.name,attack=rawget(target,'attack'),
        phase=rawget(target,'phase'),current=current,
        current_label=current and catalogue.explosions[current].label or nil,
        editable=field.editable==true and not weapon.ordinaryWritesBlocked,
        reason=weapon.ordinaryWritesBlocked and weapon.blockReason or field.reason,
        shared=field.affectsMultipleWeapons==true,
        acknowledgements={own=copy(base),none=copy(base),catalogue=catalogue_acks},
        none={value=target:no_explosion(),acknowledgements=copy(base)},options={},excluded={}}
    if current_type~=0 then
        result.own={value=target:explosion(),name=current,label=result.current_label,acknowledgements=copy(base)}
    end
    local counts={}
    for _,name in ipairs(options.order)do
        local o=options.options[name]
        if name~=current and keep(o,filter)then
            if excluded_by[name]then
                result.excluded[#result.excluded+1]={name=name,label=o.label,reason=excluded_by[name]}
            else
                local item=public(name)
                item.value=catalogue_api.handle(name)
                item.acknowledgements=copy(catalogue_acks)
                local handle=kind=='player_weapon'and weapon_handle(catalogue.explosions[name].type)
                if handle then
                    -- Another primary's own explosion: its terminal handle needs only this field's acknowledgements.
                    item.value=require('hd2runtime/api/hd2').weapon(handle.weapon):attack(handle.attack):projectile()
                        :terminal_action(handle.phase):explosion()
                    item.acknowledgements=copy(base)
                    item.via='weapon_handle'
                end
                result.options[#result.options+1]=item
                counts[o.group]=(counts[o.group]or 0)+1
            end
        end
    end
    result.groups={}
    for index,group in ipairs(options.groups)do
        result.groups[index]={id=group.id,label=group.label,count=counts[group.id]or 0}
    end
    return result
end

-- hd2.explosions.payload_options([target,] filter): a terminal action handle first lists that field's values, else
-- every payload option.
function M.payload_options(target,filter)
    if type(target)=='table'and rawget(target,'path')=='terminal_action'then return M.for_target(target,filter)end
    assert(filter==nil,'payload_options(filter) or payload_options(terminal, filter)')
    return M.list(target)
end
return M
