-- Shared passive definitions. Existing f32 values only; never resize arrays or change keys/effect packages.
local D=require('hd2runtime/domains/armor_perks')
local b=require('hd2runtime/core/bytes')
local ownership=require('hd2runtime/core/ownership')
local natives=require('hd2runtime/domains/event_natives')
local M={}
local entries={};for _,e in ipairs(D.entries)do entries[e.id]=e end
-- Check nearby native instructions in one read. This keeps a plan editing every perk below the context limit.
local pin_groups={}
for _,pin in ipairs(D.pins)do
    local group=pin_groups[#pin_groups];local page=math.floor(pin.rva/4096)
    if not group or group.page~=page then
        group={page=page,first=pin.rva,last=pin.rva,pins={}};pin_groups[#pin_groups+1]=group
    end
    local bytes=b.unhex(pin.hex)
    group.last=math.max(group.last,pin.rva+#bytes)
    group.pins[#group.pins+1]={rva=pin.rva,bytes=bytes,label=pin.label}
end
function M.entry(id)return entries[id]end
function M.fields(id)return assert(entries[id],'unknown armor perk').fields end
local function finite(v)return type(v)=='number'and v==v and v>-math.huge and v<math.huge end
local function validate(r,multiple)
    assert(type(r)=='table','armor perk request required')
    local allowed={id=true,target=true,diagnostic=true,allow_shared=true,allow_unverified_effect=true}
    if multiple then allowed.changes=true else allowed.field=true;allowed.expect=true;allowed.value=true end
    for k in pairs(r)do assert(allowed[k],'unsupported armor perk option: '..tostring(k))end
    assert(type(r.id)=='string'and#r.id>0 and#r.id<=64 and not r.id:find('[^%w_%-]'),'invalid operation id')
    local t=r.target;assert(type(t)=='table'and t.resource=='armor_perk','armor perk target required')
    for k in pairs(t)do assert(k=='resource'or k=='armor_perk','unsupported armor perk identity')end
    local e=assert(entries[t.armor_perk],'unknown armor perk')
    assert(r.allow_shared==true,'armor perk requires allow_shared=true')
    assert(r.allow_unverified_effect==true,'armor perk requires allow_unverified_effect=true')
    local items=multiple and r.changes or{{field=r.field,expect=r.expect,value=r.value}}
    assert(type(items)=='table'and#items>0 and#items<=#e.fields,'invalid armor perk change count')
    local out={kind='armor_perk',id=r.id,armor_perk=e.id,diagnostic=r.diagnostic==true,changes={}}
    local seen={}
    for _,c in ipairs(items)do
        assert(type(c)=='table','armor perk change required')
        for k in pairs(c)do assert(k=='field'or k=='expect'or k=='value','unsupported armor perk change option')end
        local f;for _,v in ipairs(e.fields)do if v.semanticFieldId==c.field then f=v end end
        assert(f,'unknown armor perk field: '..tostring(c.field))
        assert(not seen[c.field],'duplicate armor perk field');seen[c.field]=true
        assert(finite(c.expect)and finite(c.value),'finite armor perk value required')
        assert(b.encode(c.expect,'f32')==b.encode(f.currentDefault,'f32'),'expect differs from reviewed armor perk')
        assert(c.value>=f.min and c.value<=f.max,'armor perk value outside reviewed range')
        if f.unit=='count'or f.type=='integer'then assert(c.value%1==0,'armor perk value must be an integer')end
        out.changes[#out.changes+1]={field=c.field,canonical_field=c.field,descriptor=f,expect=c.expect,value=c.value,
            expected=b.encode(f.currentDefault,'f32'),desired=b.encode(c.value,'f32')}
    end
    return out
end
function M.validate_patch(r)return validate(r,false)end
function M.validate_transaction(r)return validate(r,true)end
local function pointer(raw,offset)
    local p=b.pointer(raw,offset)
    assert(p>=65536 and p<2^47,'TARGET_UNAVAILABLE: armor perk pointer absent or invalid');return p
end
local function read(reader,address,size,writable)
    local r=reader.query(address)
    assert(r and r.state==0x1000 and r.allocation_base>0 and address>=r.base and address+size<=r.base+r.size,
        'TARGET_UNAVAILABLE: armor perk allocation unavailable')
    if writable then assert(r.type==0x20000 and r.protect==4,'armor perk values must be private read-write data')end
    local owner={base=r.allocation_base,size=r.base+r.size-r.allocation_base,type=r.type,protect=r.protect}
    return reader.read(owner,address-owner.base,size,true),owner
end
function M.capture_many(runtime,reader,specs)
    require('hd2runtime/core/fingerprint').require(runtime)
    assert(D.gameDllSha256==natives.source.gameDllSha256,'armor perk build mismatch')
    assert(D.gameDllSha256==require('hd2runtime/schemas/current').dll_sha,'armor perk profile mismatch')
    local base=runtime.address(assert(runtime.module('game.dll'),'TARGET_UNAVAILABLE: game.dll absent'))
    local image={base=base,size=natives.source.imageSize,type=0x1000000}
    for _,group in ipairs(pin_groups)do
        local raw=reader.read(image,group.first,group.last-group.first,true)
        for _,pin in ipairs(group.pins)do
            local off=pin.rva-group.first
            assert(raw:sub(off+1,off+#pin.bytes)==pin.bytes,'armor perk code changed: '..pin.label)
        end
    end
    local m=D.manager
    local manager=pointer(reader.read(image,m.globalRva,8,true),0)
    local head=read(reader,manager+m.passives,16)
    local count=b.u32(head,8);assert(count==#D.entries and b.u32(head,12)==0,'armor perk table count changed')
    local array=pointer(head,0)
    local index=read(reader,manager+m.passiveIndex,m.passiveIds*4)
    local pointers=read(reader,array,count*8)
    local common={};for i,s in ipairs(reader.snapshots)do common[i]=s end
    local cached,out={},{}
    for n,spec in ipairs(specs)do
        local e=assert(entries[spec.armor_perk])
        local resolved=cached[e.id]
        if not resolved then
            local first=#reader.snapshots+1
            local slot=b.u32(index,e.id*4);assert(slot<count,'armor perk index changed')
            local address=pointer(pointers,slot*8)
            local row=read(reader,address,0x34)
            assert(b.u32(row,0)==e.id and b.u32(row,4)==tonumber(e.nameId,16)
                and b.resource(row,8)=='0x'..e.icon and b.u32(row,0x30)==tonumber(e.package,16),
                'armor perk identity changed')
            resolved={entry=e,parts={}}
            for _,part in ipairs({'modifier','stat'})do
                local data=part=='modifier'and e.modifiers or e.stats
                local off=part=='modifier'and 0x10 or 0x20
                local stride=part=='modifier'and 16 or 12
                assert(b.u32(row,off+8)==#data and b.u32(row,off+12)==0,'armor perk array count changed')
                if#data>0 then
                    local ptr=pointer(row,off)
                    local raw,owner=read(reader,ptr,#data*stride,true)
                    for i,item in ipairs(data)do
                        local pos=(i-1)*stride
                        if part=='modifier'then
                            local types={Set=0,Add=1,Multiply=2,Time=3}
                            assert(b.u32(raw,pos)==tonumber(item.key,16)and b.u32(raw,pos+4)==types[item.type],
                                'armor perk modifier identity changed')
                        else assert(b.u32(raw,pos)==item.stat,'armor perk stat identity changed')end
                    end
                    resolved.parts[part]={owner=owner,offset=ptr-owner.base,bytes=raw}
                end
            end
            resolved.snapshots={}
            for i,s in ipairs(common)do resolved.snapshots[i]=s end
            for i=first,#reader.snapshots do resolved.snapshots[#resolved.snapshots+1]=reader.snapshots[i]end
            cached[e.id]=resolved
        end
        out[n]=resolved
    end
    return out
end
function M.capture(runtime,reader,spec)return M.capture_many(runtime,reader,{spec})[1]end
function M.prepare(r,reader,spec)
    local out={snapshots=r.snapshots,notes={},changes={}}
    for _,c in ipairs(spec.changes)do
        local f=c.descriptor;local backing=f.backing;local p=r.parts[backing.part]
        local before=p.bytes:sub(backing.offset+1,backing.offset+4)
        out.notes[#out.notes+1]=f.lifecycle
        out.changes[#out.changes+1]={label=c.field,canonical_field=c.field,semantic_aliases={c.field},
            owner=p.owner,offset=p.offset+backing.offset,field_offset=backing.offset,
            expected=ownership.expected(c,before),desired=c.desired,before=before,already_desired=before==c.desired,
            expect=c.expect,value=c.value,identity={component='ArmorPerk:'..backing.part,component_type='semantic',
                record_index=r.entry.id,unique_owner=false,owner_count=r.entry.armorKits,scope=f.operationGroup},chain={}}
    end
    return out
end
return M
