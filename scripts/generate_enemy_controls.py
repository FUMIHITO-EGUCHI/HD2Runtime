"""Promote reviewed enemy/structure controls into the guarded API; research stays private.

The runtime owns native identities. The SDK gets semantic fields, defaults, scopes,
and unresolved-name evidence, never process addresses. No live reads or writes.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import re
import struct

from scan import tables, settings
from reference_format import lua
from entity_display_names import labels

ROOT = Path(__file__).resolve().parents[1]
BUILD = 'F5FEE03DCFDB'
ACK = 'Native-code or prior-reviewed mapping; enemy gameplay changes have not been live-tested.'
LIFECYCLE = 'Shared authored type settings; existing instances with private copies keep their copies.'


def load(stem):
    return json.loads((ROOT / 'research' / f'{stem}-{BUILD}.json').read_text(encoding='utf-8'))


def layout(t, c):
    pos = c.frame_offset
    return dict(offset=pos, header=t.entities[pos:pos+28].hex(),
                index=struct.unpack_from('<I', t.entities, pos-4)[0], indices=c.capacity,
                records=c.count, record_offset=c.records_offset, stride=c.record_size, type=c.type_hash)


def identity(c, resource):
    rows = [(row, idx) for row, owner, idx in c.rows() if owner == resource]
    assert len(rows) == 1, (c.name, resource, rows)
    row, idx = rows[0]
    owners = c.owners(idx)
    return dict(component=c.name, recordIndex=idx, indexRow=row,
                ownerCount=len(owners), uniqueOwner=len(owners) == 1)


def definitions():
    out = []
    def add(id_, component, offset, storage='f32', bounds=(0, 10000), writable=True,
            grade='native_code_proven', semantics='', lifecycle=LIFECYCLE, zone=False):
        out.append(dict(id=id_, component=component+'ComponentData', offset=offset, storage=storage,
                        type='number' if storage == 'f32' else 'integer', min=bounds[0], max=bounds[1],
                        writable=writable, grade=grade, semantics=semantics, lifecycle=lifecycle, zone=zone))
    for f in load('enemy-control-fields')['fields']:
        if not f['structure'].endswith('Component'):
            continue
        component=f['structure'].removesuffix('Component');name=f['id'];count=f['count']
        storage={'FP32':'f32','UINT32':'u32','ENUM_UINT32':'u32','UINT8':'u8'}[f['storage']]
        if name.startswith('hive_'): name='hive.'+name[5:];bounds=(0,10)
        elif name.startswith('spawner_'):
            name='spawner.'+name[8:];bounds=(0,16) if storage=='u32' else (0,3600)
            if name in ('spawner.primary_group','spawner.fallback_group'):bounds=(0,4294967295)
            if name=='spawner.alternate_roster':bounds=(0,1)
            if name=='spawner.delay_variance':bounds=(0,1)
        elif name.startswith('transport_'):name='transport.'+name[10:];bounds=(1,16)
        elif name.startswith('passenger_'):name='transport.'+name;bounds=(1,16)
        elif name.startswith('behavior_'):name='behavior.'+name[9:];bounds=(0,4294967295)
        elif name=='bughole_emission_radius':name='breach.emission_radius';bounds=(0,100)
        else:name='unit.'+name;bounds=(0.05,10) if 'scale' in name else (0,1000)
        writable=f['confidence']=='STRONG' and name not in {
            'behavior.id','spawner.primary_group','spawner.fallback_group','transport.formation_id'}
        for n in range(count):
            add(name+(f'_{n+1}' if count>1 else ''),component,f['offset']+4*n,storage,bounds,writable,
                f['confidence'],f['semanticScope'],
                'Creation-time uniform XYZ scale; does not resize existing units or prove physics scaling.'
                if name=='unit.scale_min' else LIFECYCLE)
    for name,off,hi in [('health',0x4C,1000000),('armor',0x50,10),('radius',0,1000),
                        ('recharge_cooldown_after_hit',0x58,3600),('recharge_cooldown_when_broken',0x5C,3600),
                        ('recharge_per_second',0x60,1000000)]:
        add('shield.'+name,'Shield',off,bounds=(0,hi),semantics='ShieldComponent '+name.replace('_',' '))
    add('jammer.radius','StratagemBlocker',12,bounds=(0.01,10000),
        semantics='3D radius, strict inside test. Nonpositive native values bypass distance, not disable.')
    add('jammer.initially_enabled','StratagemBlocker',16,'u8',(0,1),
        semantics='Initial enabled byte; behavior and existing per-instance state are separate.',lifecycle='Initialization only.')
    # Known health/zone fields also cover classes absent from the old anatomy catalogue.
    for d in json.loads((ROOT/'schemas/enemy_fields.json').read_text())['fields']:
        if not d['id'].startswith(('entity.','zone.')):continue
        zone='zoneOffset' in d;off=d.get('zoneOffset',d.get('offset'))
        bounds=(1,10000000) if d['id'].endswith('.health') else (0,10000000) if 'constitution' in d['id'] else (0,10)
        if d['id']=='entity.constitution_rate':bounds=(-1000000,1000000)
        add(d['id'],'Health',off,d['storage'],bounds,grade='prior_reviewed',zone=zone)
    for d in load('enemy-structure-atlas')['fieldAliases']['DamageableZoneInfo']:
        if d['name'] not in {'fatal','downsOnDeath','mainHealthCapped'}:continue
        name={'fatal':'fatal','downsOnDeath':'downs_on_death','mainHealthCapped':'main_health_capped'}[d['name']]
        add('zone.'+name,'Health',d['offset'],'u8',(0,1),grade=d['evidence'],zone=True)
    # Dev9: native Health update and initialization paths now prove six former leads.
    health_proof=load('enemy-health-controls-dev9')
    from scan.xref import CodeImage
    image=CodeImage.from_snapshot()
    assert image.sha256==health_proof['gameDllSha256']
    for pin in health_proof['pins']:
        assert image.data[pin['rva']:pin['rva']+len(bytes.fromhex(pin['bytes']))].hex()==pin['bytes'].lower()
    for d in health_proof['fields']:
        add(d['id'],'Health',d['offset'],d['storage'],(d['min'],d['max']),
            semantics=d['semantics'],lifecycle=d['lifecycle'])
    patrol_proof=load('spawn-channels-dev10')
    assert image.sha256==patrol_proof['gameDllSha256']
    for pin in patrol_proof['pins']:
        assert image.data[pin['rva']:pin['rva']+len(bytes.fromhex(pin['bytes']))].hex()==pin['bytes'].lower()
    for player in range(4):
        add(f'hive.patrol_clock_rate_players_{player+1}','HiveMind',0x1F0+player*4,bounds=(0,100),
            semantics='Patrol timer speed for this player count. Higher means faster scheduling; capacity and mission gates still apply.',
            lifecycle='Authored mission-mode settings. Apply on the ship before launch; existing private copies may persist.')
    # Remaining recovered aliases are inspection leads, not proven writable controls.
    atlas=load('enemy-structure-atlas')
    occupied={(d['component'],d['offset'],d['zone']) for d in out}
    for typ,prefix,component,zone in [('HealthComponent','entity','Health',False),
                                    ('DamageableZoneInfo','zone','Health',True)]:
        for d in atlas['fieldAliases'][typ]:
            if (component+'ComponentData',d['offset'],zone) in occupied or d['name']=='nameHash':continue
            name=re.sub(r'(?<!^)(?=[A-Z])','_',d['name']).lower()
            add(prefix+'.'+name,component,d['offset'],{'i':'i32','I':'u32','f':'f32','B':'u8'}[d['storage']],
                (-10000000,4294967295),False,d['evidence'],'Inspection only; field semantics or write scope incomplete.',zone=zone)
    assert len({d['id'] for d in out})==len(out)
    return out


def attach_attacks(t,entries,layouts,entity_rows):
    """Typed settings edges, including recursive mounts, with every edge re-proven at write time."""
    links=load('enemy-structure-damage-links');s=settings.SettingsView(t)
    refs=defaultdict(list);mounts=defaultdict(list);edges=defaultdict(list)
    for ref in links['componentReferences']:
        for owner in ref['owners']:refs[owner].append(ref)
    for m in links['mounts']:
        if m['childDefinitionPresent']:mounts[m['parent']].append(m)
    for edge in links['settingsLinks']:edges[edge['kind'],edge['type']].append(edge)
    schema=[d for d in json.loads((ROOT/'schemas/enemy_fields.json').read_text())['fields'] if d.get('settings')]
    from generate_enemy_authoring import RANGES
    for entry in entries.values():
        reachable={entry['resource']:[]};pending=deque([entry['resource']])
        entry['attacks']=[]
        while pending:
            owner=pending.popleft()
            for m in mounts[owner]:
                if m['child'] in reachable:continue
                step=identity(t.component('MountComponentData'),int(owner,16))|dict(resource=owner,
                    entityRow=entity_rows[int(owner,16)],offset=m['offset'],expect=m['child'])
                reachable[m['child']]=reachable[owner]+[step];pending.append(m['child'])
        entry['mountedEntities']=[dict(name=next((e['name'] for e in entries.values() if e['resource']==r),None),
                                      depth=len(chain)) for r,chain in reachable.items() if chain]
        for owner,chain in reachable.items():
            for ref in refs[owner]:
                c=t.component(ref['component']);layouts[c.name]=layout(t,c)
                source=identity(c,int(owner,16))|dict(resource=owner,entityRow=entity_rows[int(owner,16)],
                                                     offset=ref['offset'],expect=ref['nativeType'])
                queue=deque([(ref['kind'],ref['nativeType'],[])]);seen=set()
                while queue:
                    kind,typ,path=queue.popleft()
                    if (kind,typ) in seen:continue
                    seen.add((kind,typ));raw=s.row(kind,typ)
                    if raw is None:continue
                    fs=[d for d in schema if d['settings']==kind]
                    if fs:
                        id_='mapped_'+str(len(entry['attacks'])+1)
                        attack=dict(id=id_,role=kind,sourceComponent=c.name.removesuffix('ComponentData'),
                            sourceMember=ref['memberPath'],mountChain=chain,source=source,settingsLinks=path,
                            wikiAttacks=[],rowWikiMatches=[],reviewedClassesReachingRow=[],
                            note='Typed authored reference; availability and behavior may prevent this slot from executing.')
                        entry['attacks'].append(attack)
                        for d in fs:
                            value=struct.unpack_from('<'+{'i32':'i','u32':'I','f32':'f'}[d['storage']],raw,d['offset'])[0]
                            low,high=RANGES[d['id']]
                            entry['fields'].append(dict(id=d['id'],path='attack',attack=id_,currentDefault=value,
                                editable=low<=value<=high,reason=None if low<=value<=high else 'Native sentinel outside the supported editing range.',
                                backing=dict(kind='settings',settings=kind,recordType=typ,offset=d['offset'],storage=d['storage'],width=4)))
                    for edge in edges[kind,typ]:
                        queue.append((edge['targetKind'],edge['targetType'],path+[dict(settings=kind,recordType=typ,
                            offset=edge['offset'],expect=edge['targetType'])]))
    if any(e['mountedEntities'] for e in entries.values()):layouts['MountComponentData']=layout(t,t.component('MountComponentData'))


def build():
    atlas=load('enemy-structure-atlas');old=load('enemy-authoring');destruction=load('structure-destruction')
    name_proof=load('entity-display-names')['names']
    t=tables.pinned();defs=definitions()
    assert atlas['source']['gameDllSha256'] in (ROOT/'schemas/current.lua').read_text()
    present={e['resource'] for e in atlas['entities']}
    for component in ['HiveMindComponentData','BugholeComponentData']:
        for _,resource,_ in t.component(component).rows():
            key=f'0x{resource:016X}'
            if key in present:continue
            present.add(key)
            atlas['entities'].append(dict(resource=key,path=t.name(resource),components=t.entity(resource),
                factionFromPath=None,factionFromUnitPath=None,placedDestructionCandidates=[],destructionRecord=None))
    atlas['entities'].sort(key=lambda e:e['resource'])
    old_names={c['resource']:c['wikiName'] or c['className'] for c in old['classes']}
    old_classes={c['resource']:c for c in old['classes']}
    leaves=Counter((e['path'] or '').rsplit('/',1)[-1] for e in atlas['entities'])
    names={e['resource']:old_names.get(e['resource']) or
           ((e['path'].rsplit('/',1)[-1] if leaves[e['path'].rsplit('/',1)[-1]]==1 else e['path'])
            if e['path'] else f'unnamed_entity_{i+1:04}') for i,e in enumerate(atlas['entities'])}
    assert len(set(names.values()))==len(names)
    # Physical entity map rows, separate from the component index rows.
    entity_rows={struct.unpack_from('<Q',t.entities,28+i*32)[0]:i for i in range(4096)}
    components={d['component'] for d in defs}
    layouts={n:layout(t,t.component(n)) for n in sorted(components)}
    schema={d['id']:{k:v for k,v in d.items() if k not in ('component','offset','zone','writable')}
            |dict(acknowledgement='allow_unverified_effect',acknowledgementReason=ACK) for d in defs}
    entries={};aliases={};public=[]
    formats={'f32':'f','u32':'I','i32':'i','u8':'B'}
    for e in atlas['entities']:
        name=names[e['resource']];resource=int(e['resource'],16);legacy=old_classes.get(e['resource'])
        kind=legacy['kind'] if legacy else 'enemy' if 'AiEnemyComponentData' in e['components'] else (
            'structure' if e['path'] and (e['path'].startswith('content/env_') or e['path'].startswith('content/objectives/')) else 'entity')
        entry=dict(name=name,className=legacy['className'] if legacy else name,kind=kind,
                   faction=e['factionFromPath'] or e['factionFromUnitPath'] or 'unresolved',
                   semanticId='enemy/v2/'+name,resource=e['resource'],entityRow=entity_rows[resource],
                   requiresAcknowledgement=not bool(legacy),
                   fields=[],zones=[],components=sorted(e['components']))
        entry.update(labels(e,legacy,name,name_proof))
        h=atlas['healthRecords'][e['components']['HealthComponentData']] if 'HealthComponentData' in e['components'] else None
        if h:
            entry['health']=identity(t.component('HealthComponentData'),resource)
            for z in h['zones']:
                cs=z['nameCandidates'];observed=[c for c in cs if c['observedInSource']]
                entry['zones'].append(dict(id=f"zone_{z['slot']}",index=z['slot'],
                    name=z['name'] if len(observed)==1 and len(cs)==1 else None,
                    nameCandidates=[dict(name=c['name'],observedInSource=c['observedInSource']) for c in cs],
                    actors=[dict(name=a['name'],nameCandidates=[c['name'] for c in a['nameCandidates']]) for a in z['actors']]))
        for d in defs:
            if d['component'] not in e['components']:continue
            c=t.component(d['component']);ident=identity(c,resource);raw=c.raw(ident['recordIndex'])
            for z in h['zones'] if d['zone'] and h else [None] if not d['zone'] else []:
                offset=d['offset']+(z['recordOffset'] if z else 0);storage=d['storage'];width=struct.calcsize(formats[storage])
                value=struct.unpack_from('<'+formats[storage],raw,offset)[0]
                editable=d['writable'] and d['min']<=value<=d['max']
                # A nonpositive jammer radius is valid to inspect, but new writes must be positive.
                if d['id']=='jammer.radius':editable=True
                field=dict(id=d['id'],path='damage_zone' if z else 'entity',currentDefault=value,
                    editable=editable,backing=ident|dict(offset=offset,storage=storage,width=width))
                if not editable:field['reason']='Unresolved field semantics or native sentinel; inspection only.'
                if z:
                    field['zone']=f"zone_{z['slot']}"
                    field['backing']['guards']=[dict(offset=z['recordOffset']+96,hex=struct.pack('<I',z['nameHash']).hex())]
                if d['id'].startswith('transport.grid_dimension_'):
                    field['max']=value;field['semantics']='Authored grid dimension. Only reductions are supported; passenger count depends on footprints.'
                entry['fields'].append(field)
        entry['transport']=next(({k:v for k,v in x.items() if k in ('dimensions','capacityCells','footprintBoundsNote')}
                                 |dict(footprints=[dict(dimensions=f['dimensions'],enemies=[names.get(r,'unresolved') for r in f['owners']],
                                      areaOnlyUpperBound=f['areaOnlyUpperBound'],fixedOrientationGridUpperBound=f['fixedOrientationGridUpperBound'])
                                      for f in x['matchingFootprints']]) for x in atlas['transports'] if e['resource'] in x['owners']),None)
        ids=set(e['placedDestructionCandidates'])
        if e['destructionRecord'] is not None:ids.add(e['destructionRecord'])
        entry['demolition']=[dict(modelPaths=destruction['records'][i]['unitPaths'],
            association='direct_unit' if i==e['destructionRecord'] else 'embedded_model_reference',
            stages=[dict(index=s['stageIndex'],template=s['requiredTemplateName'],force=s['demolitionStrength'],effects=s['effectCount'])
                    for s in destruction['records'][i]['stages']]) for i in sorted(ids)]
        entries[name]=entry
        if e['path']:
            aliases[e['path']]=name
            leaf=e['path'].rsplit('/',1)[-1]
            if leaves[leaf]==1 and leaf not in names.values():aliases[leaf]=name
        public.append({k:v for k,v in entry.items() if k not in ('resource','entityRow','health','fields')}|
            dict(fields=[{k:v for k,v in f.items() if k!='backing'}|dict(shared=not f['backing']['uniqueOwner'],
                acknowledgement='allow_unverified_effect') for f in entry['fields']]))
    attach_attacks(t,entries,layouts,entity_rows)
    # Refresh the public field view after following the typed attack links.
    for p in public:
        e=entries[p['name']]
        p['fields']=[{k:v for k,v in f.items() if k!='backing'}|dict(
            shared=f['backing'].get('kind')=='settings' or not f['backing'].get('uniqueOwner',True),
            acknowledgement='allow_unverified_effect') for f in e['fields']]
        p['attacks']=[{k:v for k,v in a.items() if k in ('id','role','sourceComponent','sourceMember','note')} for a in e['attacks']]
        p['mountedEntities']=e['mountedEntities']
    runtime=dict(source=atlas['source'],schema=schema,enemies=entries,aliases=aliases,layouts=layouts)
    catalog=dict(schemaVersion=1,runtimeVersion=(ROOT/'VERSION').read_text().strip(),build=BUILD,
                 summary=dict(entities=len(entries),zones=sum(len(e['zones']) for e in entries.values()),
                              fieldInstances=sum(len(e['fields']) for e in entries.values())),
                 fields=[{k:v for k,v in d.items() if k not in ('offset','component','storage')} for d in defs],entities=public,
                 limitations=['Type edits do not update private instance copies.',
                              'Unresolved identities are build-specific unnamed entries, not identified enemy species.',
                              'Damage-zone name candidates are not accepted as unique anatomy without observed source evidence.',
                              'A demolition stage force is not a universal destruction threshold.'])
    return runtime,catalog


def outputs():
    runtime,catalog=build()
    entries=runtime.pop('enemies')
    # One constructor per entity keeps Lua 5.1's per-function constant limit bounded.
    body='-- Generated by scripts/generate_enemy_controls.py; do not edit.\nlocal D='+lua(runtime)+'\nD.enemies={}\n'
    for name,entry in entries.items():
        fields=entry.pop('fields')
        body+='D.enemies['+lua(name)+']=(function() local e='+lua(entry)+';e.fields=function()return '+lua(fields)+' end;return e end)()\n'
    return {'domains/enemy_controls.lua':body+'\nreturn D\n',
            'sdk/EnemyControlCapabilities.json':json.dumps(catalog,indent=1,ensure_ascii=True)+'\n'}


def generate(check=False):
    changed=[]
    for name,body in outputs().items():
        p=ROOT/name
        if not p.exists() or p.read_text(encoding='utf-8')!=body:
            changed.append(name)
            if not check:p.write_text(body,encoding='utf-8',newline='\n')
    if check and changed:raise RuntimeError('Stale enemy controls: '+', '.join(changed))
    return changed


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    print(', '.join(generate(p.parse_args().check)) or 'up to date')
