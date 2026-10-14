-- Launch-time mission durations. No live countdown writes, hooks, or polling.
local D=require('hd2runtime/domains/missions')
local b=require('hd2runtime/core/bytes')
local ownership=require('hd2runtime/core/ownership')
local discover=require('hd2runtime/runtime/discover')
local entities=require('hd2runtime/core/entity_catalog')
local profile=require('hd2runtime/schemas/current')
local natives=require('hd2runtime/domains/event_natives')
local M={}
local view=setmetatable({components=setmetatable({HiveMindComponentData=D.layout},{__index=profile.components})},
    {__index=profile})
local entries={};for _,m in ipairs(D.missions)do entries[m.id]=m end
-- The host clamps its countdown every frame to the replicated field's range (game object field 0xD3CC92D1:
-- float 0..2500, research mission-countdown-static-rc15). A longer authored duration starts at 2500 s anyway.
local MAX_SECONDS=2500
function M.entry(id)return entries[id]end
local function field(m)
    local s=D.sources[m.source]
    local shared={};for i,id in ipairs(s.missions)do shared[i]=id end
    return {semanticFieldId='mission.duration_seconds',type='number',unit='seconds',currentDefault=s.currentDefault,
        min=60,max=MAX_SECONDS,editable=true,shared=true,acknowledgement='allow_unverified_effect',
        acknowledgementReason='Launch-time timer mapping verified offline; gameplay not yet tested.',
        lifecycle=D.limitations[1],sharedWith=shared,operationGroup='mission/'..m.source,
        target={resource='mission',mission=m.id},
        backing={kind='mission_timer',source=m.source,storage='f32',width=4}}
end
function M.fields(id)return {field(assert(entries[id],'unknown mission'))}end
local function finite(v)return type(v)=='number'and v==v and v>-math.huge and v<math.huge end
local function validate(r,multiple)
    assert(type(r)=='table','mission request required')
    local allowed={id=true,target=true,diagnostic=true,allow_shared=true,allow_unverified_effect=true}
    if multiple then allowed.changes=true else allowed.field=true;allowed.expect=true;allowed.value=true end
    for k in pairs(r)do assert(allowed[k],'unsupported mission option: '..tostring(k))end
    assert(type(r.id)=='string'and#r.id>0 and#r.id<=64 and not r.id:find('[^%w_%-]'),'invalid operation id')
    local t=r.target
    assert(type(t)=='table'and t.resource=='mission','mission target required')
    for k in pairs(t)do assert(k=='resource'or k=='mission','unsupported mission identity')end
    local m=assert(entries[t.mission],'unknown mission identity')
    assert(r.allow_shared==true,'mission timer requires allow_shared=true')
    assert(r.allow_unverified_effect==true,'mission timer requires allow_unverified_effect=true')
    local items=multiple and r.changes or{{field=r.field,expect=r.expect,value=r.value}}
    assert(type(items)=='table'and#items==1,'mission transaction requires exactly one duration change')
    local c=items[1];assert(type(c)=='table','mission change required')
    for k in pairs(c)do assert(k=='field'or k=='expect'or k=='value','unsupported mission change option')end
    local f=field(m)
    assert(c.field==f.semanticFieldId,'unknown mission field')
    assert(finite(c.expect)and finite(c.value),'finite mission duration required')
    assert(c.expect==f.currentDefault,'expect differs from reviewed mission duration')
    assert(c.value>=f.min and c.value<=f.max,
        'mission duration outside reviewed range (60..2500 seconds; the game cuts longer countdowns to 2500)')
    return {kind='mission',id=r.id,mission=m.id,diagnostic=r.diagnostic==true,changes={{field=c.field,
        canonical_field=c.field,descriptor=f,expect=c.expect,value=c.value,
        expected=b.encode(c.expect,'f32'),desired=b.encode(c.value,'f32')}}}
end
function M.validate_patch(r)return validate(r,false)end
function M.validate_transaction(r)return validate(r,true)end
local function image_and_ship(runtime,reader)
    require('hd2runtime/core/fingerprint').require(runtime)
    assert(profile.dll_sha==D.gameDllSha256,'mission catalogue build mismatch')
    local base=runtime.address(assert(runtime.module('game.dll'),'TARGET_UNAVAILABLE: game.dll absent'))
    local image={base=base,size=D.imageSize,type=0x1000000}
    for _,pin in ipairs(D.pins)do
        local expected=b.unhex(pin.bytes)
        assert(reader.read(image,pin.rva,#expected,true)==expected,'mission native code changed: '..pin.role)
    end
    local ptr=b.pointer(reader.read(image,natives.state.game,8,true),0)
    assert(ptr>=65536 and ptr<2^47,'game state pointer invalid')
    local region=reader.query(ptr)
    assert(region and region.state==0x1000,'game state allocation absent')
    local owner={base=region.allocation_base,size=region.base+region.size-region.allocation_base,type=region.type}
    assert(b.u32(reader.read(owner,ptr+natives.state.state-owner.base,4,true),0)==3,
        'TARGET_UNAVAILABLE: mission timer edits require Ship state before launch')
    return image
end
local function delta_offset(reader,region,s)
    local d=profile.entity_deltas;local base=d.header_offset
    local header=reader.read(region,base,80,true)
    for i,name in ipairs({'hashmap','settings','component','delta','data'})do
        assert(b.pointer(header,(i-1)*16)==region.base+base+d[name..'_offset'] and
            b.pointer(header,(i-1)*16+8)==d[name..'_count'],'mission delta relocation/count changed')
    end
    local row=reader.read(region,base+d.hashmap_offset+s.hashmapSlot*16,16,true)
    assert(b.resource(row,0)==s.resource and b.u32(row,8)==s.settingsIndex,'mission delta ownership changed')
    local settings=reader.read(region,base+d.settings_offset+s.settingsIndex*8,8,true)
    local count,first=b.u32(settings,0),b.u32(settings,4)
    assert(count>0 and count<=64 and first+count<=d.component_count,'mission delta settings bounds')
    local cs=reader.read(region,base+d.component_offset+first*12,count*12,true)
    local matches=0
    for i=0,count-1 do
        local component,fd,n=b.u32(cs,i*12),b.u32(cs,i*12+4),b.u32(cs,i*12+8)
        assert(n>0 and n<=64 and fd+n<=d.delta_count,'mission delta bounds')
        if component==s.component then
            local ds=reader.read(region,base+d.delta_offset+fd*12,n*12,true)
            for j=0,n-1 do
                local offset,size,raw=b.u32(ds,j*12),b.u32(ds,j*12+4),b.u32(ds,j*12+8)
                assert(raw+size<=d.data_count,'mission delta data bounds')
                if offset<=s.componentOffset and offset+size>s.componentOffset then
                    assert(offset==s.componentOffset and size==4 and base+d.data_offset+raw==s.dataOffset,
                        'mission timer delta layout changed')
                    matches=matches+1
                end
            end
        end
    end
    assert(matches==1,'mission timer delta is absent or ambiguous')
    return s.dataOffset
end
function M.capture_many(runtime,reader,specs)
    local image=image_and_ship(runtime,reader)
    local need,resources={},{}
    for _,spec in ipairs(specs)do
        local m=assert(entries[spec.mission]);local s=D.sources[m.source]
        if s.kind=='component'then need.entity=true;resources[s.resource]=true else need.entity_deltas=true end
    end
    local roots=discover.locate(runtime,reader,view,need)
    local catalog=need.entity and entities.capture(reader,roots.entity,view,{'HiveMindComponentData'},
        {resources=resources})
    local result={}
    for i,spec in ipairs(specs)do
        local m=entries[spec.mission];local s=D.sources[m.source]
        for _,g in ipairs(m.guards)do
            local expected=b.unhex(g.hex)
            assert(reader.read(image,m.rva+g.offset,#expected,true)==expected,'mission definition identity changed')
        end
        local owner,offset,bytes
        if s.kind=='delta'then owner=roots.entity_deltas;offset=delta_offset(reader,owner,s)
        else
            local candidate
            for _,c in ipairs(catalog.candidates)do if c.resourceHash==s.resource then
                assert(not candidate,'mission entity identity ambiguous');candidate=c
            end end
            assert(candidate and candidate.entityRow==s.entityRow and#candidate.diagnostics==0,
                'mission entity ownership changed')
            local r=catalog.record(candidate,'HiveMindComponentData');local id=r.identity
            assert(id.recordIndex==s.identity.recordIndex and id.indexRow==s.identity.indexRow
                and id.ownerCount==s.identity.ownerCount and id.uniqueOwner==s.identity.uniqueOwner,
                'mission component ownership changed')
            owner=r.owner;offset=r.offset+s.offset;bytes=r.bytes:sub(s.offset+1,s.offset+4)
        end
        result[i]={owner=owner,offset=offset,source=s,mission=m,
            bytes=bytes or reader.read(owner,offset,4,true)}
    end
    return result
end
function M.capture(runtime,reader,spec)return M.capture_many(runtime,reader,{spec})[1]end
function M.prepare(r,reader,spec)
    local c=spec.changes[1];local s=r.source
    return {snapshots=reader.snapshots,notes={D.limitations[1],D.limitations[2]},changes={{
        label=c.field,canonical_field=c.field,semantic_aliases={c.field},owner=r.owner,offset=r.offset,
        field_offset=s.kind=='delta'and s.componentOffset or s.offset,expected=ownership.expected(c,r.bytes),
        desired=c.desired,before=r.bytes,already_desired=r.bytes==c.desired,expect=c.expect,value=c.value,
        packed=s.kind=='delta',identity={component=s.kind=='delta'and'EntityDelta:HiveMindComponentData'or'HiveMindComponentData',
            component_type='semantic',record_index=s.settingsIndex or s.identity.recordIndex,unique_owner=false,
            owner_count=#s.missions,scope=c.descriptor.operationGroup},chain={}}}}
end
return M
