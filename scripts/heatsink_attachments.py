"""Publish reviewed magazine-slot heatsink deltas through the existing guarded attachment writer."""
import json
from pathlib import Path

def build(runtime,root,g):
    evidence=json.loads((root/'research/heatsink-attachments-F5FEE03DCFDB.json').read_text())
    assert evidence['writes']==0 and not evidence['processAccess']
    base=json.loads((root/'sdk/PlayerWeaponAuthoringCapabilities.json').read_text())
    definitions={f['semanticFieldId']:f for w in base['weapons']for f in w['fields']}
    attachments,instances=[],[]
    for item in evidence['items']:
        semantic=g.generic_key(item)
        assert semantic not in runtime['attachments']
        known=sorted(set(item['nativeDefaultOf']+item['unlockListedFor']))
        target=dict(resource='weapon_attachment',attachment=semantic,path='magazine')
        operation='operation:'+g.digest({'object':'backing:'+g.digest({'entityDelta':item['addPath']}),'target':semantic})
        fields={}
        for native in item['fields']:
            field=native['id']
            if field.startswith('attachment.'):
                definition=next(f for f in json.loads(g.FIELDS.read_text())['fields']if f['id']==field)
                label,unit=definition['display_name'],definition['unit']
            else:
                definition=definitions[field];label,unit=definition['displayName'],definition.get('unit')
                b=definition['backing'];assert b['offset']==native['componentOffset'] and b['storage']==native['storage']
            lo,hi=definition.get('min'),definition.get('max')
            instance=semantic.replace('weapon-attachment/v1/','attachment:')+':'+field
            f=dict(instanceKey=instance,component=native['component'],storage=native['storage'],
                componentOffset=native['componentOffset'],dataOffset=native['dataOffset'],
                currentDefault=native['value'],operationGroup=operation,min=lo,max=hi,
                displayName=label,unit=unit,backing=dict(kind='entity_delta',component={266:'WeaponHeatComponentData',113:'WeaponReloadComponentData',236:'WeaponDataComponentData'}[native['component']]))
            if native.get('guard'):f['guard']=native['guard']
            fields[field]=f
            instances.append(dict(instanceKey=instance,semanticFieldId=field,displayName=label,unit=unit,
                type='integer'if native['storage']=='u32'else'number',currentDefault=native['value'],
                min=lo,max=hi,editable=True,target=target,operationGroup=operation,shared=True,
                acknowledgement='allow_unverified_effect',allowSharedRequired=True,reviewedScopeComplete=False,
                apiFieldConstant='hd2.fields.'+field,gameplayWriteEffect='unproven'))
        entry=dict(semanticId=semantic,name=item['debugName'],slot='magazine',kind='heatsink',
            resource=item['addPath'],hashmapSlot=item['hashmapSlot'],settingsIndex=item['settingsIndex'],
            fields=fields,compatibleWeapons=known)
        runtime['attachments'][semantic]=entry;runtime['names'][entry['name']]=semantic
        attachments.append(dict(semanticId=semantic,name=entry['name'],nameUnique=True,slot='magazine',kind='heatsink',
            compatibleWeapons=known,fieldInstanceKeys=[f['instanceKey']for f in fields.values()],
            consumers=dict(nativeDefaultOf=item['nativeDefaultOf'],unlockListedFor=item['unlockListedFor'])))
        for name in known:
            slot=runtime['weapons'].setdefault(name,dict(options=[]))
            default=name in item['nativeDefaultOf']
            if default:
                assert not slot.get('default')or slot['default']==semantic
                slot['default']=semantic
            slot['options'].append(dict(attachment=semantic,name=entry['name'],
                relationship='native_resource_default'if default else'unlock_listed'))
    return dict(contract='hd2runtime.weapon_attachment.heatsink.v1',schemaVersion=1,
        hd2RuntimeVersion=(root/'VERSION').read_text().strip(),attachments=attachments,fieldInstances=instances,
        summary=dict(attachments=len(attachments),fieldInstances=len(instances),selectionWritable=False),
        lifecycle='Shared attachment definitions; equip/rebuild the weapon to consume edits. Live reapplication is unproven.',
        scope='Only native default and observed unlock-list relationships are assigned to weapons. Other variants remain independently addressable.',
        safety=dict(rawResourceIdentifiers=False,runtimeAddresses=False,writesDuringGeneration=0))
