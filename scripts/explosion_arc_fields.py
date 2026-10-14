"""Authoring metadata for reviewed explosion-created arcs."""
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[1]
RESEARCH=ROOT/'research/explosion-arcs-F5FEE03DCFDB.json'
ACK='Typed explosion-to-arc ownership verified in retained memory; changed gameplay has not been tested in game.'

def load():return json.loads(RESEARCH.read_text(encoding='utf-8'))['items']
def value(node,offset,storage='f32'):
    return struct.unpack_from({'f32':'<f','u32':'<I','i32':'<i'}[storage],bytes.fromhex(node['hex']),offset)[0]
def record(node):return {k:node[k] for k in ('group','row','recordType','settingsType')}

def augment_support(source):
    name='GL-52 De-Escalator';item=load()[name]
    weapon=next(w for w in source['weapons'] if w['name']==name)
    assert weapon['attackResource']==item['resource']
    candidate=source['candidates'][item['resource']]
    owner=candidate['ownership'][item['component']]
    assert all(owner[k]==item['identity'][k] for k in ('recordIndex','indexRow','ownerCount'))
    parent=next(a for a in candidate['attacks'] if a['role']=='primary_impact')
    assert parent['explosionSettings']==record(item['explosion'])
    role='primary_impact_arc';status_role=role+'_status_37'
    extra=dict(parentRole='primary',phase='impact',explosionType=item['explosion']['recordType'],
        arcType=item['arc']['recordType'])
    values={}
    for suffix,key,offset in [('velocity','arc_velocity',4),('range','arc_range',8),
        ('distance_at_max_spread','arc_spread',12),('distance_at_max_spread_first_shot','arc_first_spread',16),
        ('max_angle_spread','arc_chain_spread',20),('max_angle_spread_first_shot','arc_first_angle',24),
        ('chain_count','arc_chain_count',28),('max_split','arc_max_split',32)]:
        values[key]=value(item['arc'],offset,'u32' if offset>=28 else 'f32')
    for index,key in enumerate(['standard_damage','durable_damage','ap_direct','ap_slight','ap_large',
        'ap_extreme','demolition','stagger','push_force']):
        values[key]=value(item['damage'],4+4*index,'i32' if index<2 else 'u32')
    status=item['statuses'][0];assert status['recordType']==37 and status['slot']==1
    arc=dict(role=role,kind='Arc',parentRole='primary_impact',arcSettings=record(item['arc']),
        damageInfo=record(item['damage']),resolvedFields=values,explosionArc=extra,
        statusEffects=[dict(type=37,strength=status['strength'])])
    st=dict(role=status_role,kind='Status',parentRole=role,statusType=37,statusSettings=record(status),
        resolvedFields=dict(status_strength=status['strength'],status_duration=value(status,40)))
    candidate['attacks'] += [arc,st]
    for branch in weapon['attackGraph']:
        if branch['name'] in ('GL-52 P IE A','Stun Small'):
            branch.update(state='RESOLVED',unresolvedReason=None,resolvedBy='typed_explosion_arc',
                runtimeMatch=dict(runtimeAttackRole=role if branch['kind']=='Arc' else status_role,
                    runtimeAttackKind=branch['kind'],mismatchedFields=[]))
    weapon['unresolvedLinks']=[]
    return source
