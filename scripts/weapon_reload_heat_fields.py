"""Reviewed reload override and heat-level authoring descriptors."""
import json
from pathlib import Path
import struct
from generate_attachment_authoring import attachment_key

ROOT=Path(__file__).resolve().parents[1]
RESEARCH=ROOT/'research/reload-heat-F5FEE03DCFDB.json'
SICKLE='LAS-17 Double-Edge Sickle'
ACK='Native consumer and ownership reviewed offline; changed gameplay has not been tested in game.'
COMPONENT_FIELDS=[
    ('heat.fire_rate_multiplier_max','Fire rate multiplier at maximum heat',72,'f32','multiplier',0.01,10),
    ('heat.fire_rate_curve_exponent','Heat fire rate curve exponent',76,'f32','factor',0.01,10),
    ('heat.overheat_release_threshold','Overheat release threshold',100,'f32','heat_units',0,10000),
    ('heat.cooling_multiplier_hot','Hot environment cooling multiplier',132,'f32','multiplier',0,10),
    ('heat.cooling_multiplier_cold','Cold environment cooling multiplier',136,'f32','multiplier',0,10),
    ('heat.cool_per_second_overheated','Cooling while charging or overheated',140,'f32','heat_units_per_second',0,10000),
    ('heat.prevent_overheat_cooling','Prevent cooling while charging or overheated',144,'u8',None,0,1),
    ('heat.firing_charge','Wind-up: charge needed to fire',148,'f32','charge',0,10000),
    ('heat.charge_gain_per_second','Wind-up: charge gained per second',152,'f32','charge_per_second',0.01,10000),
    ('heat.charge_loss_per_second','Wind-up: charge lost per second',156,'f32','charge_per_second',0,10000),
    ('heat.reset_charge_after_shot','Wind-up: reset charge after each shot',160,'u8',None,0,1),
]


def definitions(base):
    defs={d['id']:d for d in base}
    result=[]
    for id_,label,offset,storage,unit,lo,hi in COMPONENT_FIELDS:
        result.append(dict(id=id_,display_name=label,type='boolean'if storage=='u8'else'number',unit=unit,
            derived=False,writable=True,component='WeaponHeatComponentData',offset=offset,storage=storage))
    for n in range(1,4):
        for group,prefix in [('projectile','projectile'),('damage','damage'),('self_damage','damage')]:
            for d in base:
                if not d['id'].startswith(prefix+'.')or d.get('settings')!=prefix or d.get('offset')is None:continue
                if not d['writable']or d.get('derived'):continue
                result.append(dict(d,id=f'heat.level_{n}.{group}.'+d['id'].split('.',1)[1],
                    display_name=f'Heat level {n} '+('self damage: 'if group=='self_damage'else'')+d['display_name']))
        result.append(dict(id=f'heat.level_{n}.self_status_duration',display_name=f'Heat level {n} self-status duration',
            type='number',unit='seconds',derived=False,writable=True,settings='status',offset=40,storage='f32'))
    return result


def fields(name,make,defs):
    data=json.loads(RESEARCH.read_text(encoding='utf-8'));out=[]
    def component(identity,name,offset,storage):
        return dict(identity,kind='component',component=name,offset=offset,storage=storage,
                    width=1 if storage=='u8'else 4,uniqueOwner=identity['ownerCount']==1)
    def finish(f,lo,hi,shared=False):
        f.update(min=lo,max=hi,acknowledgement='allow_unverified_effect',acknowledgementReason=ACK,
            effect={'activeSource':'ACTIVE_DIRECT','appliesWhen':'use','instantiationOnly':False,
                    'activeSourceProven':True,'reason':ACK},reviewedReloadHeat=True)
        if shared:f.update(affectsMultipleWeapons=True,dynamicConsumersPossible=True,writeScope='shared_settings')
        if f['backing']['kind']=='component':
            f['effect'].update(activeSource='ACTIVE_AT_INSTANTIATION',appliesWhen='weapon_build',instantiationOnly=True)
        out.append(f)
    r=data['reload'][name]
    if r['present']:
        f=make('reload.duration',r['duration'],component(r['identity'],'WeaponReloadComponentData',56,'f32'))
        f['reloadTiming']={'zeroUsesNative':True,'nativeAbilitySeconds':r['nativeSeconds'],
            'note':'0 uses native timing. Positive seconds rescale the reload ability; partial reloads and repeated stages can finish sooner. Armor speed bonuses still multiply the rate. Existing customization copies may override this source.'}
        finish(f,0,120)
        magazines=json.loads((ROOT/'research/magazine-attachments-F5FEE03DCFDB.json').read_text())
        weapon=next((w for w in magazines['weapons']if w['weapon']==name),None)
        default=next((a for a in magazines['magazineAttachments']if weapon and a['addPath']==weapon['nativeDefault']),None)
        if default and default['effects'].get('reload'):
            f['reloadTiming']['defaultAttachment']=attachment_key(default)
            f['reloadTiming']['defaultSeconds']=default['effects']['reload']['value']
            f.update(editable=False,acceptedForWrites=False,
                reason='The default magazine overrides this base value. Edit attachment.reload_duration on weapon:magazine_attachment().')
            f['effect'].update(activeSource='OVERRIDDEN',activeSourceProven=True,
                reason=f['reason'],appliesWhen='weapon_build',instantiationOnly=True)
        else:
            f['effect'].update(activeSource='ACTIVE_AT_INSTANTIATION',appliesWhen='weapon_build',instantiationOnly=True)
        if r['ability']==0:
            f['reloadTiming']['noReloadAbility']=True
            f.update(editable=False,acceptedForWrites=False,reason='This weapon has no reload ability; reload speed is not applicable.')
            f['effect'].update(activeSource='DORMANT_OR_METADATA',appliesWhen=None,instantiationOnly=False,reason=f['reason'])
    if name!=SICKLE:return out
    h=data['heat'];raw=bytes.fromhex(h['hex'])
    for id_,label,offset,storage,unit,lo,hi in COMPONENT_FIELDS:
        value=bool(raw[offset])if storage=='u8'else struct.unpack_from('<f',raw,offset)[0]
        finish(make(id_,value,component(h['identity'],'WeaponHeatComponentData',offset,storage)),lo,hi)
    for level in h['levels']:
        n=level['index']
        for d in defs.values():
            id_=d['id']
            if not id_.startswith(f'heat.level_{n}.'):continue
            tail=id_.split('.',2)[2];group=tail.split('.')[0]
            kind={'self_damage':'damage','self_status_duration':'status'}.get(group,group)
            node=level[{'self_damage':'selfDamage','self_status_duration':'status'}.get(group,group)]
            b={k:v for k,v in node.items()if k!='hex'}
            b.update(kind='settings',settings=kind,offset=d['offset'],storage=d['storage'],width=4,
                linkage='heat_'+group,heatRecord=h['identity'],heatLevel=n,
                projectileType=level['projectile']['recordType'],statusType=level['status']['recordType'])
            value=struct.unpack_from('<'+{'f32':'f','u32':'I','i32':'i'}[d['storage']],bytes.fromhex(node['hex']),d['offset'])[0]
            hi=1000000 if d['storage']=='i32'else 10000
            if tail.endswith('pellet_count'):hi=128
            if '.ap_'in tail:hi=10
            if tail.endswith('penetration_slowdown'):hi=1
            finish(make(id_,value,b),0,hi,True)
    return out
