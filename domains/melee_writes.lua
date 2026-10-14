-- Melee source templates and their DamageInfo, through the normal guarded writer.
local D=require('hd2runtime/domains/melee_authoring')
local b=require('hd2runtime/core/bytes')
local ownership=require('hd2runtime/core/ownership')
local profile=require('hd2runtime/schemas/current')
local entities=require('hd2runtime/core/entity_catalog')
local discover=require('hd2runtime/runtime/discover')
local protection=require('hd2runtime/core/page_protection')
local M={}
local IMAGE=0x1000000
local function finite(v)return type(v)=='number'and v==v and v>-math.huge and v<math.huge end
function M.entry(target)
    assert(type(target)=='table'and target.resource=='melee','melee target required')
    for k in pairs(target)do assert(k=='resource'or k=='melee'or k=='path','unsupported melee identity')end
    local e=assert(D.entries[target.melee],'unknown reviewed melee weapon')
    return e,assert(e.targets[target.path],'unknown reviewed melee target')
end
local function validate(r,multiple)
    assert(type(r)=='table','melee request required')
    local allowed={id=true,target=true,diagnostic=true,allow_shared=true,allow_unverified_effect=true}
    if multiple then allowed.changes=true else allowed.field=true;allowed.expect=true;allowed.value=true end
    for k in pairs(r)do assert(allowed[k],'unsupported melee option: '..tostring(k))end
    assert(type(r.id)=='string'and#r.id>0 and#r.id<=64 and not r.id:find('[^%w_%-]'),'invalid operation id')
    local e,t=M.entry(r.target)
    local items=multiple and r.changes or{{field=r.field,expect=r.expect,value=r.value}}
    assert(type(items)=='table'and#items>0 and#items<=32,'transaction requires one to 32 changes')
    local spec={kind='melee',id=r.id,melee=e.name,path=t.key,diagnostic=r.diagnostic==true,changes={},
        field=r.field,expect=r.expect,value=r.value}
    local seen={}
    for _,item in ipairs(items)do
        assert(type(item)=='table','change descriptor required')
        for k in pairs(item)do assert(k=='field'or k=='expect'or k=='value','unsupported change option')end
        local f=assert(t.fields[item.field],'field absent on melee target: '..tostring(item.field))
        assert(f.editable,'field is read-only: '..tostring(f.reason))
        assert(not seen[item.field],'duplicate melee field');seen[item.field]=true
        assert(not f.shared or r.allow_shared==true,'shared melee field requires allow_shared=true')
        assert(r.allow_unverified_effect==true,'melee fields require allow_unverified_effect=true')
        assert(finite(item.expect)and finite(item.value),'finite expected and desired values required')
        if f.type=='integer'then assert(item.expect%1==0 and item.value%1==0,'integer melee field required')end
        assert(math.abs(item.expect-f.currentDefault)<=math.max(1e-6,math.abs(f.currentDefault)*1e-6),'expect differs from reviewed baseline')
        assert(item.value>=f.min and item.value<=f.max,'value outside reviewed melee range')
        spec.changes[#spec.changes+1]={field=item.field,canonical_field=item.field,descriptor=f,
            expect=item.expect,value=item.value,expected=b.encode(item.expect,f.backing.storage),desired=b.encode(item.value,f.backing.storage)}
    end
    return spec
end
function M.validate_patch(r)return validate(r,false)end
function M.validate_transaction(r)return validate(r,true)end
local function pins(reader,image,list)
    for _,pin in ipairs(list)do
        local want=b.unhex(pin.hex)
        assert(reader.read(image,pin.rva,#want)==want,'melee native code changed: '..pin.label)
    end
end
local function component(catalog,candidate,e,name)
    local want=assert(e.components[name],'component not reviewed')
    local r=assert(catalog.record(candidate,name),'melee component absent')
    assert(r.identity.recordIndex==want.recordIndex and r.identity.indexRow==want.indexRow
        and r.identity.ownerCount==want.ownerCount,'melee component ownership changed')
    return r
end
function M.capture_many(runtime,reader,specs)
    require('hd2runtime/core/fingerprint').require(runtime)
    assert(profile.dll_sha==D.gameDllSha256,'melee build differs from runtime profile')
    local base=runtime.address(assert(runtime.module('game.dll'),'game.dll absent'))
    local image={base=base,size=D.imageSize,type=IMAGE}
    local header=reader.read(image,0,4096);local pe=b.u32(header,60)
    assert(header:sub(1,2)=='MZ'and pe>=64 and pe+88<=#header and header:sub(pe+1,pe+4)=='PE\0\0'
        and b.u16(header,pe+24)==0x20B and b.u32(header,pe+80)==D.imageSize,'melee image framing changed')
    pins(reader,image,D.pins)
    local needed={entity=true}
    for _,s in ipairs(specs)do for _,c in ipairs(s.changes)do
        if c.descriptor.backing.kind=='settings'then needed.damage=true end
    end end
    local roots=discover.locate(runtime,reader,profile,needed)
    local p={map_header=profile.map_header,map_rows=profile.map_rows,components=D.components,dll_sha=profile.dll_sha}
    local catalog=entities.capture(reader,roots.entity,p,{'MeleeWeaponComponentData','MeleeAttackComponentData'})
    local results={}
    for i,s in ipairs(specs)do
        local e=D.entries[s.melee];local t=e.targets[s.path];local candidate
        for _,c in ipairs(catalog.candidates)do if c.resourceHash==e.resource then
            assert(not candidate,'ambiguous melee entity');candidate=c end end
        assert(candidate and candidate.entityRow==e.entityRow and#candidate.diagnostics==0,'melee entity identity changed')
        for name in pairs(e.components)do component(catalog,candidate,e,name)end
        for _,link in ipairs(t.links)do
            local r=component(catalog,candidate,e,link.component)
            assert(b.u32(r.bytes,link.offset)==link.ability,'melee ability link changed')
        end
        local owner,bytes
        if t.rva then
            pins(reader,image,t.pins)
            local region=reader.query(base+t.rva)
            assert(region.type==IMAGE and region.allocation_base==base,'melee template outside game.dll')
            owner={base=base,size=D.imageSize,type=IMAGE,protect=region.protect}
            bytes=reader.read(owner,t.rva,#t.hex/2,true)
            for _,g in ipairs(t.guards)do local want=b.unhex(g.hex)
                assert(bytes:sub(g.offset+1,g.offset+#want)==want,'melee template identity changed')end
        end
        results[i]={entry=e,target=t,catalog=catalog,candidate=candidate,roots=roots,owner=owner,bytes=bytes}
    end
    return results
end
function M.capture(runtime,reader,spec)return M.capture_many(runtime,reader,{spec})[1]end
function M.prepare(r,reader,spec)
    local plan={changes={},snapshots=reader.snapshots}
    for _,c in ipairs(spec.changes)do
        local f=c.descriptor;local backing=f.backing;local owner,raw,offset
        if backing.kind=='native'then owner=r.owner;raw=r.bytes;offset=r.target.rva
        elseif backing.kind=='component'then
            local record=component(r.catalog,r.candidate,r.entry,backing.component)
            owner=record.owner;raw=record.bytes;offset=record.offset
        else
            local root=assert(r.roots.damage,'damage settings absent')
            local record=assert(root.records[backing.recordType],'melee DamageInfo absent')
            assert(record.group==backing.group and record.row==backing.row,'melee DamageInfo identity changed')
            assert(b.u32(r.bytes,4)==backing.recordType,'melee damage link changed')
            owner=root.owner;raw=record.bytes;offset=record.offset
        end
        assert(backing.offset+4<=#raw,'melee field outside record')
        local current=raw:sub(backing.offset+1,backing.offset+4)
        local expected=ownership.expected(c,current);local at=offset+backing.offset
        if owner.protect==protection.REVIEWED_EXECUTABLE then
            protection.register_executable_data(owner.base+at,4,'reviewed melee field '..c.field)
        end
        plan.changes[#plan.changes+1]={label=c.field,canonical_field=c.field,semantic_aliases={c.field},owner=owner,
            offset=at,field_offset=backing.offset,expected=expected,desired=c.desired,before=current,
            already_desired=current==c.desired,expect=c.expect,value=c.value,
            identity={component=backing.component or'damage',component_type='semantic',record_index=backing.recordIndex or backing.row,
                unique_owner=not f.shared,owner_count=backing.ownerCount or 0,scope='melee/'..spec.melee..'/'..spec.path},chain={}}
    end
    return plan
end
return M
