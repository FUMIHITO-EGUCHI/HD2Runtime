-- Build-pinned director data and destruction templates, through normal guarded transactions.
local D=require('hd2runtime/domains/enemy_director')
local b=require('hd2runtime/core/bytes')
local ownership=require('hd2runtime/core/ownership')
local profile=require('hd2runtime/schemas/current')
local natives=require('hd2runtime/domains/event_natives')
local protection=require('hd2runtime/core/page_protection')
local M={}
local compat=require('hd2runtime/runtime/spawn_compatibility')
-- The native squad deferred-spawn queue has 32 entries. A 33rd entry overwrites
-- its own count; a subsequent append writes outside the allocation.
M.MAX_COMPOSITION_COUNT=32
local function count_field(id)return id:match('^composition%.group_%d+_count$')~=nil end
local function validate_counts(row,values,changed)
    if row.kind~='composition'or not changed then return end
    local total=0
    for _,f in ipairs(row.fields)do if count_field(f.id)then total=total+values[f.id]end end
    assert(total<=M.MAX_COMPOSITION_COUNT,
        'SPAWN_CAPACITY: composition exceeds the native 32-enemy squad queue; reduce total group counts')
end
local IMAGE,PRIVATE=0x1000000,0x20000
local function finite(v)return type(v)=='number'and v==v and v>-math.huge and v<math.huge end
local function same(a,c)return finite(a)and finite(c)and math.abs(a-c)<=math.max(1e-6,math.abs(c)*1e-6)end
function M.row(target)
    assert(type(target)=='table'and target.resource=='enemy_director','enemy director target required')
    for key in pairs(target)do assert(key=='resource'or key=='path'or key=='key','unsupported director identity')end
    assert(type(target.path)=='string'and type(target.key)=='string','director kind and key required')
    return assert(D.rows[target.path..'/'..target.key],'unknown reviewed director target')
end
local function descriptor(row,f)
    return {semanticFieldId=f.id,currentDefault=f.currentDefault,type=f.storage=='f32'and'number'or'integer',
        min=f.min,max=f.max,editable=f.editable,reason=f.reason,shared=true,acknowledgement='allow_unverified_effect',
        acknowledgementReason=D.acknowledgementReason,lifecycle=row.lifecycle,
        backing={kind='native',component='EnemyDirector',storage=f.storage,width=4},
        target={resource='enemy_director',path=row.kind,key=row.key},operationGroup='enemy_director/'..row.kind..'/'..row.key}
end
function M.fields(row)
    local out={};for _,f in ipairs(row.fields)do out[#out+1]=descriptor(row,f)end;return out
end
local function validate(request,multiple)
    assert(type(request)=='table','director patch or transaction requires a descriptor')
    local allowed={id=true,target=true,diagnostic=true,allow_shared=true,allow_unverified_effect=true}
    if multiple then allowed.changes=true else allowed.field=true;allowed.expect=true;allowed.value=true end
    for k in pairs(request)do assert(allowed[k],'unsupported director option: '..tostring(k))end
    assert(type(request.id)=='string'and#request.id>0 and#request.id<=64 and not request.id:find('[^%w_%-]'),'invalid operation id')
    assert(request.allow_shared==true,'director fields require allow_shared=true')
    assert(request.allow_unverified_effect==true,'director fields require allow_unverified_effect=true')
    local row=M.row(request.target)
    local items=multiple and request.changes or{{field=request.field,expect=request.expect,value=request.value}}
    assert(type(items)=='table'and#items>0 and#items<=32,'transaction requires one to 32 changes')
    local result={kind='enemy_director',row=row.kind..'/'..row.key,id=request.id,resource='enemy_director',
        diagnostic=request.diagnostic==true,changes={},field=request.field,expect=request.expect,value=request.value}
    local seen={};local counts={};local counts_changed=false
    for _,f in ipairs(row.fields)do counts[f.id]=f.currentDefault end
    for _,item in ipairs(items)do
        assert(type(item)=='table','change descriptor required')
        for k in pairs(item)do assert(k=='field'or k=='expect'or k=='value','unsupported change option')end
        local field
        for _,f in ipairs(row.fields)do if f.id==item.field then field=f;break end end
        assert(field,'field is not writable on this director target: '..tostring(item.field))
        assert(field.editable,'field is read-only: '..tostring(field.reason))
        assert(not seen[item.field],'duplicate director field');seen[item.field]=true
        assert(finite(item.expect)and finite(item.value),'finite expected and desired values required')
        if field.storage~='f32'then assert(item.expect%1==0 and item.value%1==0,'integer director field required')end
        assert(same(item.expect,field.currentDefault),'expect differs from reviewed baseline')
        assert(item.value>=field.min and item.value<=field.max,'value outside reviewed director range')
        counts[field.id]=item.value
        if count_field(field.id)and item.value~=field.currentDefault then counts_changed=true end
        result.changes[#result.changes+1]={field=field.id,canonical_field=field.id,offset=field.offset,
            storage=field.storage,descriptor=descriptor(row,field),expect=item.expect,value=item.value,
            expected=b.encode(item.expect,field.storage),desired=b.encode(item.value,field.storage)}
    end
    validate_counts(row,counts,counts_changed)
    return result
end
function M.validate_patch(r)return validate(r,false)end
function M.validate_transaction(r)return validate(r,true)end
local function owner_at(reader,address,label)
    assert(type(address)=='number'and address>=65536 and address<2^47,label..' pointer invalid')
    local r=reader.query(address)
    assert(r.state==0x1000 and r.allocation_base>0,label..' allocation absent')
    return {base=r.allocation_base,size=r.base+r.size-r.allocation_base,type=r.type,protect=r.protect}
end
local function capture_image(runtime,reader)
    require('hd2runtime/core/fingerprint').require(runtime)
    assert(profile.dll_sha==D.gameDllSha256,'director build differs from runtime profile')
    local handle=assert(runtime.module('game.dll'),'TARGET_UNAVAILABLE: game.dll absent')
    local base=runtime.address(handle)
    local h=reader.read({base=base,size=4096,type=IMAGE},0,4096)
    local pe=b.u32(h,60)
    assert(h:sub(1,2)=='MZ'and pe>=64 and pe+88<=#h and h:sub(pe+1,pe+4)=='PE\0\0'
        and b.u16(h,pe+24)==0x20B and b.u32(h,pe+80)==D.imageSize,'director image framing changed')
    local image={base=base,size=D.imageSize,type=IMAGE}
    for _,pin in ipairs(D.pins)do
        local want=b.unhex(pin.hex)
        assert(reader.read(image,pin.rva,#want)==want,'director native code changed: '..pin.label)
    end
    return image
end
local function require_ship(reader,image)
    local S=natives.state
    local ptr=b.pointer(reader.read(image,S.game,8,true),0)
    local owner=owner_at(reader,ptr,'game state')
    local state=b.u32(reader.read(owner,ptr+S.state-owner.base,4,true),0)
    assert(state==3,'TARGET_UNAVAILABLE: source spawn edits require Ship state before mission compilation')
end
function M.capture_many(runtime,reader,specs)
    for _,spec in ipairs(specs)do
        local row=assert(D.rows[spec.row],'reviewed director row absent')
        compat.require({resource='enemy_director',path=row.kind})
    end
    local image=capture_image(runtime,reader);local results={};local ship=false;local templates
    for i,spec in ipairs(specs)do
        local row=assert(D.rows[spec.row],'reviewed director row absent');local owner,offset
        compat.require({resource='enemy_director',path=row.kind})
        if row.kind=='demolition_template'then
            if not templates then
                local manager=b.pointer(reader.read(image,D.destructionGlobal,8,true),0)
                local mo=owner_at(reader,manager,'destruction manager')
                assert(mo.type==PRIVATE,'destruction manager is not private memory')
                local head=reader.read(mo,manager+0x30-mo.base,16,true)
                assert(b.u32(head,8)==D.templateCount,'destruction template count changed')
                local ptr=b.pointer(head,0);local o=owner_at(reader,ptr,'destruction templates')
                assert(o.type==PRIVATE,'destruction templates are not private memory')
                templates={owner=o,offset=ptr-o.base}
            end
            owner=templates.owner;offset=templates.offset+row.index*16
        else
            if not ship then require_ship(reader,image);ship=true end
            local r=reader.query(image.base+row.rva)
            assert(r.type==IMAGE and r.allocation_base==image.base,'director source row is outside game.dll')
            owner={base=image.base,size=image.size,type=IMAGE,protect=r.protect};offset=row.rva
            if row.descriptor then
                local d=reader.read(image,row.descriptor.rva,12,true)
                assert(b.pointer(d,0)==image.base+row.descriptor.rows and b.u32(d,8)==row.descriptor.count,
                    'roster descriptor changed')
            end
        end
        local bytes=reader.read(owner,offset,#row.hex/2,true)
        for _,g in ipairs(row.guards)do
            local want=b.unhex(g.hex)
            assert(bytes:sub(g.offset+1,g.offset+#want)==want,'director row identity changed')
        end
        results[i]={row=row,owner=owner,offset=offset,bytes=bytes}
    end
    return results
end
function M.capture(runtime,reader,spec)return M.capture_many(runtime,reader,{spec})[1]end
function M.prepare(resolved,reader,spec)
    local plan={changes={},snapshots=reader.snapshots,notes={resolved.row.lifecycle}}
    local final={}
    for _,f in ipairs(resolved.row.fields)do final[f.id]=b.value(resolved.bytes,f.offset,f.storage)end
    local counts_changed=false
    for _,change in ipairs(spec.changes)do
        final[change.field]=change.value
        if count_field(change.field)then counts_changed=true end
    end
    -- Recheck the complete effective row, including values held by other mods
    -- and fields applied in separate editor operations.
    validate_counts(resolved.row,final,counts_changed)
    if resolved.row.kind=='composition'then
        assert(final['composition.minimum_tech_level']<=final['composition.maximum_tech_level'],'minimum tech exceeds maximum')
        assert(final['composition.minimum_players']<=final['composition.maximum_players'],'minimum players exceeds maximum')
    end
    for _,c in ipairs(spec.changes)do
        local current=resolved.bytes:sub(c.offset+1,c.offset+4)
        local expected=ownership.expected(c,current)
        local at=resolved.offset+c.offset
        if resolved.owner.protect==protection.REVIEWED_EXECUTABLE then
            protection.register_executable_data(resolved.owner.base+at,4,'reviewed enemy director field '..c.field)
        end
        plan.changes[#plan.changes+1]={label=c.field,canonical_field=c.canonical_field,semantic_aliases={c.field},
            compatibility_scope=compat.scope(c.descriptor.target,c.field),
            owner=resolved.owner,offset=at,field_offset=c.offset,expected=expected,desired=c.desired,before=current,
            already_desired=current==c.desired,expect=c.expect,value=c.value,
            -- The decoded destruction DL blob can place its template array at a byte-packed address.
            packed=resolved.row.kind=='demolition_template',
            identity={component='EnemyDirector',component_type='native',record_index=resolved.row.index or 0,
                unique_owner=false,owner_count=0,scope=c.descriptor.operationGroup},chain={}}
    end
    return plan
end
return M
