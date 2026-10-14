"""Promote reviewed melee ownership, geometry and stamina into runtime/SDK catalogues."""
import argparse
import json
from pathlib import Path
import struct

from scan import tables
from migration.build_view import from_snapshot
import build_profile
from generate_enemy_controls import layout, identity
from reference_format import lua

ROOT=Path(__file__).resolve().parents[1]
ACK='Native ownership and consumers proven offline; changed gameplay effects have not been tested in game.'


def definitions():
    fields=[]
    for axis,off in zip('xyz',[0x28,0x2C,0x30]):
        fields.append(dict(id='melee.volume_'+axis,label='Hit volume '+axis.upper(),offset=off,min=0.001,max=20,unit='meters'))
    for axis,off in zip('xyz',[0x38,0x3C,0x40]):
        fields.append(dict(id='melee.offset_'+axis,label='Hit volume local offset '+axis.upper(),offset=off,min=-20,max=20,unit='meters'))
    fields.append(dict(id='melee.repeat_hit_interval',label='Repeat-hit interval (0 once per attack)',offset=0xAC,min=0,max=60,unit='seconds'))
    fields.append(dict(id='melee.stamina_cost',label='Stamina cost per attack',offset=8,min=0,max=1,unit='fraction'))
    return fields


def outputs():
    src=json.loads((ROOT/'research/knife-melee-F5FEE03DCFDB.json').read_text(encoding='utf-8'))
    t=tables.pinned();v=from_snapshot(build_profile.SNAPSHOT)
    names=['MeleeWeaponComponentData','MeleeAttackComponentData']
    player_names={e['name'] for e in json.loads((ROOT/'schemas/player_weapon_authoring_catalog.json').read_text(encoding='utf-8'))['weapons']}
    data=dict(build=src['build'],gameDllSha256=src['gameDllSha256'],imageSize=src['imageSize'],
              acknowledgementReason=ACK,pins=src['pins'],components={n:layout(t,t.component(n)) for n in names},entries={})
    public=dict(version=(ROOT/'VERSION').read_text().strip(),build=src['build'],fields=[{k:v for k,v in d.items() if k!='offset'} for d in definitions()],entries=[])
    damage_defs=[d for d in json.loads((ROOT/'schemas/throwable_fields.json').read_text())['fields']
                 if d['id'].startswith('damage.') and 'status_' not in d['id']]
    def field(d,raw,backing,shared,lifecycle):
        storage=d.get('storage','f32');value=struct.unpack_from('<'+{'f32':'f','u32':'I','i32':'i'}[storage],raw,d['offset'])[0]
        low,high=d.get('range',[d.get('min'),d.get('max')])
        return dict(semanticFieldId=d['id'],displayName=d.get('label',d.get('display_name')),currentDefault=value,
            type='number' if storage=='f32' else 'integer',min=low,max=high,unit=d['unit'],editable=True,
            shared=shared,acknowledgement='allow_unverified_effect',acknowledgementReason=ACK,lifecycle=lifecycle,
            operationGroup=backing['kind']+':'+str(backing.get('component',backing.get('settings')))+':'+str(backing.get('recordIndex',backing.get('recordType'))),
            backing=dict(backing,offset=d['offset'],width=4,storage=storage))
    for name,entry in src['melee'].items():
        resource=int(entry['resource'],16)
        e=dict(name=name,resource=entry['resource'],ownerResource='player_weapon' if name in player_names else 'support_weapon',
               entityRow=v.entity_rows[resource],components={},targets={})
        for n in entry['components']: e['components'][n]=identity(t.component(n),resource)
        if 'MeleeWeaponComponentData' in e['components']:
            n='MeleeWeaponComponentData';raw=bytes.fromhex(entry['components'][n]['hex']);d=definitions()[-1]
            f=field(d,raw,dict(kind='component',**e['components'][n]),False,'Read when an attack spends stamina.')
            e['targets']['tuning']=dict(key='tuning',label='Melee stamina',fields={d['id']:f},links=[],pins=[])
        zone_keys=sorted({k for s in entry['sources'] for k in s['zones']})
        for index,key in enumerate(zone_keys,1):
            z=src['zones'][key];raw=bytes.fromhex(z['hex'])
            target=dict(key=f'zone_{index}',label=f'Hit volume {index}',shape=z['shape'],fields={},rva=z['rva'],
                hex=z['hex'],consumers=z['consumers'],links=[],pins=z['pins'],guards=[])
            used=[s for s in entry['sources'] if key in s['zones']]
            for s in used:
                target['links'].append({k:s[k] for k in ['component','offset','ability']})
                target['pins'].extend([s['dispatch'],s['call']])
            target['abilities']=sorted({s['ability'] for s in used})
            for d in definitions()[:-1]:
                f=field(d,raw,dict(kind='native',component='MeleeHitVolume',recordIndex=z['rva']),True,
                    'Copied at attack activation; the next attack uses the edited geometry.')
                target['fields'][d['id']]=f
            damage=v.settings_table('damage').row_for_type(z['damageType'])
            assert len(damage)==1
            row,draw=damage[0]
            for d in damage_defs:
                f=field(d,draw,dict(kind='settings',settings='damage',recordType=z['damageType'],group=v.settings_table('damage').group,row=row),True,
                    'Global DamageInfo definition, read for each hit; also affects other attacks using this damage row.')
                target['fields'][d['id']]=f
            # Every noneditable byte identifies the complete native template; runtime-owned copies are never patched.
            mutable={i for f in target['fields'].values() if f['backing']['kind']=='native' for i in range(f['backing']['offset'],f['backing']['offset']+4)}
            start=None
            for i in range(len(raw)+1):
                keep=i<len(raw) and i not in mutable
                if keep and start is None: start=i
                if not keep and start is not None:
                    target['guards'].append(dict(offset=start,hex=raw[start:i].hex()));start=None
            e['targets'][target['key']]=target
        if not e['targets']: continue
        data['entries'][name]=e
        public['entries'].append(dict(name=name,targets=[dict(key=k,label=target['label'],consumers=target.get('consumers',[name]),
            fields=[{a:b for a,b in f.items() if a not in ('backing','operationGroup')} for f in target['fields'].values()]) for k,target in e['targets'].items()]))
    public['summary']=dict(weapons=len(data['entries']),hitVolumes=len(src['zones']),
        fields=sum(len(t['fields']) for e in data['entries'].values() for t in e['targets'].values()))
    data['summary']=public['summary']
    return {ROOT/'domains/melee_authoring.lua':'-- Generated by scripts/generate_melee_authoring.py.\nreturn '+lua(data)+'\n',
            ROOT/'sdk/MeleeAuthoringCapabilities.json':json.dumps(public,indent=2)+'\n'}


def generate(check=False):
    changed=[]
    for p,s in outputs().items():
        if not p.exists() or p.read_text(encoding='utf-8')!=s:
            changed.append(str(p.relative_to(ROOT)))
            if not check:p.write_text(s,encoding='utf-8',newline='\n')
    if check and changed:raise RuntimeError('Stale melee outputs: '+str(changed))
    return changed


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();print(generate(a.check))
