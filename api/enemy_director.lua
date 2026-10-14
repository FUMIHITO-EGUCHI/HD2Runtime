-- Offline descriptions and identity-only targets; writes use patch/transaction/ensure.
local D=require('hd2runtime/domains/enemy_director')
local W=require('hd2runtime/domains/enemy_director_writes')
local M={}
function M.spawn_compatibility()return require('hd2runtime/runtime/spawn_compatibility').status()end
function M.spawn_control_reason(target,field)return require('hd2runtime/runtime/spawn_compatibility').reason(target,field)end
function M.open_spawn_picker(before_open)return require('hd2runtime/runtime/spawn_compatibility').open_gui(before_open)end
local function copy(v)
    if type(v)~='table'then return v end
    local o={};for k,x in pairs(v)do o[k]=copy(x)end;return o
end
local function target(kind,key)
    assert(type(key)=='string'or type(key)=='number','director target identity required')
    local row=assert(D.rows[kind..'/'..tostring(key)],'unknown '..kind..' target: '..tostring(key))
    local methods={}
    function methods.describe()return {id=row.key,kind=row.kind,metadata=copy(row.metadata),
        lifecycle=row.lifecycle,fields=W.fields(row)}end
    return setmetatable({resource='enemy_director',path=kind,key=row.key},{__index=methods})
end
function M.difficulty(level)return target('difficulty',level)end
function M.composition(id)return target('composition',id)end
function M.roster(id)return target('roster',id)end
function M.demolition_template(name)return target('demolition_template',name)end
local function list(kind,filter)
    assert(filter==nil or type(filter)=='table','filter must be a table')
    local out={}
    for _,r in pairs(D.rows)do
        local match=r.kind==kind
        for k,v in pairs(filter or{})do
            assert(k=='faction'or k=='family'or k=='roster','unsupported director filter')
            if r.metadata[k]~=v then match=false end
        end
        if match then out[#out+1]=target(kind,r.key):describe()end
    end
    table.sort(out,function(a,c)return a.id<c.id end);return out
end
function M.compositions(filter)return list('composition',filter)end
function M.rosters(filter)return list('roster',filter)end
function M.demolition_templates()return list('demolition_template')end
function M.destruction_models()return copy(D.models)end
-- A preview/recipe, never a second writer. Consumers stage these ordinary
-- composition fields or submit the returned transactions through hd2.ensure.
-- Scale authored counts, not relative roster weights (scaling all weights
-- equally would leave selection probabilities unchanged).
local function factor(multiplier)
    assert(type(multiplier)=='number'and multiplier==multiplier and multiplier>=0.1 and multiplier<=5,
        'spawn multiplier must be between 0.1 and 5')
end
local function faction_name(faction)
    assert(faction=='terminids'or faction=='automatons'or faction=='illuminate','unknown enemy faction')
end
function M.spawn_multiplier(faction,multiplier,channel)
    faction_name(faction);factor(multiplier)
    channel=channel or'all'
    assert(channel=='all'or channel=='patrol'or channel=='reinforcement'or channel=='map','unknown spawn channel')
    local result={faction=faction,multiplier=multiplier,scope='composition_counts',transactions={},
        channel=channel,fields=0,clamped=0,cappedCompositions=0,maxCompositionCount=W.MAX_COMPOSITION_COUNT,
        authoredCount=0,desiredCount=0,
        lifecycle='Apply aboard the ship before the next mission. Counts round to whole enemies and each composition is capped at 32 total to protect the native squad queue; transport capacity, budgets and fallback spawns still apply.'}
    if channel=='map'then
        result.scope='composition_budget'
        result.lifecycle='Apply before launch. Divides map guard composition costs, increasing effective budget without scaling native 999 fill limits; not an exact head count.'
    end
    local keys={}
    for key,row in pairs(D.rows)do
        if row.kind=='composition'and row.metadata.faction==faction
            and((channel=='all'and(row.metadata.role=='patrol'or row.metadata.role=='reinforcement'))
                or row.metadata.role==channel)then keys[#keys+1]=key end
    end
    table.sort(keys)
    for _,key in ipairs(keys)do
        local row=D.rows[key]
        local tx={id='spawn-scale-'..faction..'-'..(#result.transactions+1),target=M.composition(row.key),
            allow_shared=true,allow_unverified_effect=true,changes={}}
        for _,f in ipairs(row.fields)do
            if f.editable and((channel=='map'and f.id=='composition.cost_multiplier')
                or(channel~='map'and f.id:match('^composition%.group_%d+_count$')))then
                local wanted=channel=='map'and f.currentDefault/multiplier or math.floor(f.currentDefault*multiplier+0.5)
                local value=channel=='map'and math.max(f.min,math.min(f.max,wanted))or wanted
                if value~=wanted then result.clamped=result.clamped+1 end
                tx.changes[#tx.changes+1]={field=f.id,expect=f.currentDefault,value=value}
                result.fields=result.fields+1
            end
        end
        if channel~='map'then
            local total=0
            for _,c in ipairs(tx.changes)do total=total+c.value end
            if total>W.MAX_COMPOSITION_COUNT then
                -- Largest-remainder apportionment preserves the requested mix and
                -- uses all 32 slots without rounding the sum above capacity.
                local order,used={},0
                for i,c in ipairs(tx.changes)do
                    local quota=c.value*W.MAX_COMPOSITION_COUNT/total
                    local value=math.floor(quota)
                    order[#order+1]={index=i,fraction=quota-value,wanted=c.value}
                    c.value=value;used=used+value
                end
                table.sort(order,function(a,b)
                    if a.fraction==b.fraction then return a.index<b.index end
                    return a.fraction>b.fraction
                end)
                for i=1,W.MAX_COMPOSITION_COUNT-used do
                    local c=tx.changes[order[i].index];c.value=c.value+1
                end
                for _,item in ipairs(order)do
                    if tx.changes[item.index].value~=item.wanted then result.clamped=result.clamped+1 end
                end
                result.cappedCompositions=result.cappedCompositions+1
            end
            for _,c in ipairs(tx.changes)do
                result.authoredCount=result.authoredCount+c.expect;result.desiredCount=result.desiredCount+c.value
            end
        end
        if#tx.changes>0 then result.transactions[#result.transactions+1]=tx end
    end
    return result
end
-- Scale exactly one factor in the native multiplicative patrol-clock formula.
-- Mission progress, player-count balance, boosters and proximity remain intact.
function M.patrol_frequency(faction,multiplier)
    faction_name(faction);factor(multiplier)
    local result={faction=faction,multiplier=multiplier,scope='patrol_frequency',transactions={},fields=0,clamped=0,
        lifecycle='Apply on the ship before launch. Speeds up the patrol clock; population caps and mission gates remain.'}
    for _,mode in ipairs(D.spawnModes)do if mode.faction==faction then
        local tx={id='patrol-rate-'..faction..'-'..(#result.transactions+1),
            target={resource='enemy',enemy=mode.enemy,path='entity'},allow_shared=true,allow_unverified_effect=true,changes={}}
        for _,f in ipairs(mode.fields)do
            local wanted=f.currentDefault*multiplier
            local value=math.max(f.min,math.min(f.max,wanted))
            if value~=wanted then result.clamped=result.clamped+1 end
            tx.changes[#tx.changes+1]={field=f.id,expect=f.currentDefault,value=value}
            result.fields=result.fields+1
        end
        result.transactions[#result.transactions+1]=tx
    end end
    return result
end
-- Difficulty-specific native controls, selected by the game at installation.
-- Budgets affect eligible selections; they are not a literal enemy count scale.
function M.difficulty_multiplier(level,channel,multiplier)
    factor(multiplier)
    local target_=M.difficulty(level)
    local ids={encounter_budget='difficulty.encounter_points',map_budget='difficulty.guardforce_points',
        spawner_frequency='difficulty.shared_spawner_cooldown'}
    local id=assert(ids[channel],'unknown difficulty channel')
    local result={difficulty=tonumber(level),channel=channel,multiplier=multiplier,scope='difficulty',fields=1,clamped=0,
        lifecycle='Apply on the ship before launch. Budgets and shared spawner cooldown for this difficulty only.'}
    for _,f in ipairs(D.rows['difficulty/'..target_.key].fields)do if f.id==id then
        local wanted=channel=='spawner_frequency'and f.currentDefault/multiplier or f.currentDefault*multiplier
        local value=math.max(f.min,math.min(f.max,wanted))
        result.clamped=value~=wanted and 1 or 0
        result.transactions={{id='difficulty-'..target_.key..'-'..channel,target=target_,allow_shared=true,
            allow_unverified_effect=true,changes={{field=id,expect=f.currentDefault,value=value}}}}
        return result
    end end
    error('difficulty field unavailable')
end
return M
