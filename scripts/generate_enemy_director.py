"""Generate guarded spawn-director targets and destruction-template controls."""
import argparse
import json
import struct
from pathlib import Path
from reference_format import lua
from scan import xref
from generate_enemy_controls import load, BUILD, ROOT, ACK
from entity_display_names import labels, readable


def build():
    source=load('enemy-spawn-director');destruction=load('structure-destruction')
    difficulty_names=load('hud-difficulties')['difficulty']
    proof=load('entity-display-names')['names']
    legacy={e['resource']:e for e in load('enemy-authoring')['classes']}
    display={e['resource']:labels(e,legacy.get(e['resource']),e['path'] or 'unnamed_entity',proof)
             for e in load('enemy-structure-atlas')['entities']}
    im=xref.CodeImage.from_snapshot();assert im.sha256==source['source']['gameDllSha256']
    channels=load('spawn-channels-dev10')
    capacity=load('spawn-capacity-dev11')
    assert capacity['gameDllSha256']==im.sha256 and capacity['maximumCompositionCount']==32
    assert im.sha256==channels['gameDllSha256']
    for pin in channels['pins']+capacity['pins']:
        assert im.data[pin['rva']:pin['rva']+len(bytes.fromhex(pin['bytes']))].hex()==pin['bytes'].lower()
    rows={};definitions={}
    def field(row,id_,off,storage='f32',low=0,high=10000):
        definitions.setdefault(id_,dict(id=id_,type='number' if storage=='f32' else 'integer',min=low,max=high))
        value=struct.unpack_from('<'+('f' if storage=='f32' else 'I'),bytes.fromhex(row['hex']),off)[0]
        row['fields'].append(dict(id=id_,offset=off,storage=storage,currentDefault=value,min=low,max=high,
            editable=low<=value<=high,reason=None if low<=value<=high else 'Authored value outside the supported write range; inspection only.'))
    for d in source['difficulty']['baseRows']:
        key=str(d['difficulty']);raw=im.data[d['rva']:d['rva']+source['difficulty']['baseStride']]
        assert raw.hex()==d['rawHex']
        row=dict(key=key,kind='difficulty',rva=d['rva'],hex=raw.hex(),fields=[],
                 metadata=dict(difficulty=d['difficulty'],techLevel=d['techLevel'],
                    displayName=difficulty_names[key]['name'],iconName=key),
                 lifecycle='Source budgets for subsequent director installation; existing compiled selections are not rebuilt.')
        field(row,'difficulty.encounter_points',0xE4,high=100000)
        field(row,'difficulty.guardforce_points',0xE8,high=100000)
        field(row,'difficulty.shared_spawner_cooldown',0x104,high=3600)
        rows['difficulty/'+key]=row
    for family in source['compositions']:
        for r in family['rows']:
            key=f"{family['faction']}/family_{family['descriptorOffset']//16-1}/row_{r['index']}"
            row=dict(key=key,kind='composition',rva=r['rva'],hex=im.data[r['rva']:r['rva']+280].hex(),fields=[],
                     metadata=dict(faction=family['faction'],family=family['descriptorOffset']//16-1,
                        row=r['index'],role=channels['roles'].get(str(family['descriptorOffset']//16-1),'unresolved'),groups=[dict(slot=g['slot'],count=g['count'],
                            emissionTime=g['emissionTimeSecondsBugholePath'],candidates=g['rosterCandidates']) for g in r['groups'] if g['group']!='00000000']),
                     lifecycle='Source composition: applied before the next installation/compilation, never advertised as an immediate wave edit.')
            for id_,off,storage,low,high in [('weight',0xE0,'f32',0,10000),('cost_multiplier',0xE4,'f32',0.01,100),
                ('post_schedule_duration',0xE8,'f32',0,3600),('minimum_tech_level',0xEC,'u32',1,10),
                ('maximum_tech_level',0xF0,'u32',1,10),('minimum_players',0xF4,'u32',1,4),('maximum_players',0xF8,'u32',1,4)]:
                field(row,'composition.'+id_,off,storage,low,high)
            for g in r['groups']:
                if g['group']=='00000000':continue
                field(row,f"composition.group_{g['slot']}_count",g['slot']*12+4,'u32',0,32)
                field(row,f"composition.group_{g['slot']}_emission_time",g['slot']*12+8,high=3600)
            for slot,weight in enumerate(r['difficultyWeightOverrides']):
                if 1<=weight['difficulty']<=10:field(row,f'composition.weight_override_{slot}',0xA4+slot*8)
            rows['composition/'+key]=row
    factions={e['resource']:e.get('factionFromPath')or e.get('factionFromUnitPath')or'unknown'
              for e in load('enemy-structure-atlas')['entities']}
    for roster in source['rosters']:
        for r in roster['rows']:
            key=f"{roster['name']}/row_{r['index']}"
            row=dict(key=key,kind='roster',rva=r['rva'],hex=im.data[r['rva']:r['rva']+128].hex(),fields=[],
                descriptor=dict(rva=roster['descriptorRva'],rows=roster['rowsRva'],count=roster['count']),
                metadata=dict(roster=roster['name'],row=r['index'],path=r['path'],group=r['group'],
                    faction=roster['name'] if roster['name'] in ('terminids','automatons','illuminate') else factions.get(r['entity'],'unknown')),
                lifecycle='Weighted selection; zero excludes normal positive-weight picks, with native bypasses and direct-squad exceptions.')
            row['metadata'].update(display.get(r['entity'],dict(displayName=readable(r['path']) if r['path'] else 'Unidentified Enemy',nameSource='unresolved')))
            for d in range(10):field(row,f'spawn.weight_{d+1}',0x30+4*d)
            rows['roster/'+key]=row
    for template in destruction['templates']:
        i=template['index'];v=template['valuesByOffset']
        row=dict(key=template['name'],kind='demolition_template',index=i,
                 hex=struct.pack('<4I',v['0'],v['4'],v['8'],v['12:bit0']).hex(),fields=[],
                 metadata=dict(name=template['name'],shared=True),
                 lifecycle='Shared template used by every referencing destruction stage. Threshold equality passes; stages are traversed in order.')
        if i not in (0,10):field(row,'demolition.force',4,'u32',1,255)
        rows['demolition_template/'+template['name']]=row
    # Retain all immutable bytes as identity guards; changed fields are conflict-checked separately.
    for row in rows.values():
        mask=set(o for f in row['fields'] if f['editable'] for o in range(f['offset'],f['offset']+4));raw=bytes.fromhex(row['hex'])
        guards=[];start=None
        for i in range(len(raw)+1):
            if i<len(raw) and i not in mask:
                if start is None:start=i
            elif start is not None:guards.append(dict(offset=start,hex=raw[start:i].hex()));start=None
        row['guards']=guards
    pins=load('enemy-control-native')['pins']
    if isinstance(pins,dict):pins=[p for group in pins.values() for p in group]
    pins+=destruction['nativePins']+channels['pins']+capacity['pins']
    pins={p['rva']:dict(rva=p['rva'],hex=p['bytes'],label=p['role']) for p in pins}
    old_names={c['resource']:c['wikiName'] or c['className'] for c in load('enemy-authoring')['classes']}
    paths={e['resource']:e['path'] or 'unresolved' for e in load('enemy-structure-atlas')['entities']}
    for row in rows.values():
        for g in row['metadata'].get('groups',[]):
            g['candidateNames']=[display.get(r,{}).get('fullDisplayName','Unidentified Enemy') for r in g['candidates']]
            g['candidates']=[old_names.get(r,paths.get(r,'unresolved')) for r in g['candidates']]
    models=[dict(id=f"model_{r['index']:04}",paths=r['unitPaths'],
                 stages=[dict(index=s['stageIndex'],template=s['requiredTemplateName'],force=s['demolitionStrength'],effects=s['effectCount']) for s in r['stages']]) for r in destruction['records']]
    # Canonical identities only: the enemy write domain re-proves the actual component.
    mode_factions={m['record']:{2:'terminids',8:'automatons',4:'illuminate'}.get(m['factionValue'])
                   for m in source['difficulty']['hiveMindModes']}
    from scan.tables import pinned
    hive=pinned().component('HiveMindComponentData')
    mode_names={}
    for _,resource,index in hive.rows():
        mode_names[f'0x{resource:016X}']=mode_factions.get(index)
    # Public entities intentionally omit hashes; private atlas order/name rules remain
    # owned by the control generator. Resolve through its generated runtime model.
    from generate_enemy_controls import build as build_controls
    control_runtime,_=build_controls()
    modes=[dict(enemy=e['name'],faction=mode_names[e['resource']],fields=[
        dict(id=f['id'],currentDefault=f['currentDefault'],min=0,max=100)
        for f in e['fields'] if f['id'].startswith('hive.patrol_clock_rate_players_')])
        for e in control_runtime['enemies'].values() if mode_names.get(e['resource'])]
    assert all(len(m['fields'])==4 for m in modes)
    runtime=dict(build=BUILD,gameDllSha256=im.sha256,imageSize=load('enemy-spawn-weights')['gameDll']['imageSize'],
                 rows=rows,definitions=definitions,pins=[pins[k] for k in sorted(pins)],models=models,
                 spawnModes=modes,
                 destructionGlobal=0x346D528,templateCount=11,acknowledgementReason=ACK)
    public=dict(schemaVersion=1,runtimeVersion=(ROOT/'VERSION').read_text().strip(),build=BUILD,
                fields=list(definitions.values()),rows=[dict(id=r['key'],kind=r['kind'],metadata=r['metadata'],
                    lifecycle=r['lifecycle'],fields=[{k:v for k,v in f.items() if k not in ('offset','storage')} for f in r['fields']]) for r in rows.values()],
                structures=models,spawnModes=modes,limitations=['Source spawn edits require the ship state and affect subsequent compilation.',
                    'No global enemy blacklist; roster weight bypasses and direct authored squads remain.',
                    'Template edits affect all users; per-structure resolved-pointer overrides are not implemented.'])
    return runtime,public


def outputs():
    runtime,public=build();rows=runtime.pop('rows')
    body='-- Generated by scripts/generate_enemy_director.py; do not edit.\nlocal D='+lua(runtime)+'\nD.rows={}\n'
    body+='\n'.join('D.rows['+lua(k)+']=(function()return '+lua(v)+' end)()' for k,v in rows.items())
    return {'domains/enemy_director.lua':body+'\nreturn D\n',
            'sdk/EnemyDirectorCapabilities.json':json.dumps(public,indent=1,ensure_ascii=True)+'\n'}


def generate(check=False):
    changed=[]
    for name,body in outputs().items():
        p=ROOT/name
        if not p.exists() or p.read_text(encoding='utf-8')!=body:
            changed.append(name)
            if not check:p.write_text(body,encoding='utf-8',newline='\n')
    if check and changed:raise RuntimeError('Stale enemy director: '+', '.join(changed))
    return changed


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    print(', '.join(generate(p.parse_args().check)) or 'up to date')
