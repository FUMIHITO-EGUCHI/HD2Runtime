"""Presentation labels only. Canonical enemy IDs and target identities never change."""
import re

ACRONYMS={'seaf':'SEAF','sam':'SAM','icbm':'ICBM','tcs':'TCS','mg':'MG','hmg':'HMG',
          'rpg':'RPG','ssd':'SSD','sssd':'SSSD','aa':'AA','apc':'APC','pa':'PA'}

def readable(value):
    leaf=value.rsplit('/',1)[-1].rsplit('.',1)[-1]
    leaf=re.sub(r'^(?:(?:cha|gen|cy|il|se|obj|asset|objective|cyborg|illuminate)_)+','',leaf)
    words=leaf.replace('_',' ').split()
    return ' '.join(ACRONYMS.get(w.lower(),w[:1].upper()+w[1:]) for w in words)

def labels(entity,legacy,name,proof):
    match=proof.get(entity['resource'])
    path=entity.get('path');unit=entity.get('unitPath')
    if match:
        result={k:match[k] for k in ('displayName','nameSource','gameName') if k in match}
    elif legacy and legacy.get('wikiName'):
        result=dict(displayName=legacy['wikiName'],nameSource='reviewed_name')
    elif path or unit:
        result=dict(displayName=readable(path or unit),nameSource='resource_path' if path else 'unit_path')
    else:
        components=entity['components']
        role=next((label for component,label in (
            ('AiEnemyComponentData','Enemy'),('HiveMindComponentData','Hive Director'),
            ('BugholeComponentData','Breach'),('ProjectileComponentData','Projectile'),
            ('WeaponComponentData','Weapon'),('HealthComponentData','Damageable Entity')) if component in components),'Entity')
        result=dict(displayName='Unidentified '+role,nameSource='unresolved')
    # A contextual label preserves variant/part differences even when the game reuses one name.
    variant=readable(path) if path else readable(name) if not name.startswith('unnamed_entity_') else None
    if variant and variant.casefold()!=result['displayName'].casefold():result['variantLabel']=variant
    if result['nameSource']=='unresolved' or not path and not variant:
        result['variantLabel']='Entry '+name.rsplit('_',1)[-1]
    if result['displayName'].isupper():
        result['displayName']=readable(result['displayName'].lower())
    # The game reuses generic text for some reviewed variants (e.g. the Spore Burst Bile Titan).
    if legacy and legacy.get('wikiName') and result['nameSource']=='game_text':
        result['displayName']=legacy['wikiName']
        if result['displayName']!=result.get('gameName'):result['nameSource']='reviewed_name'
    if result.get('gameName','').casefold()=='terminal' and path and result['nameSource']=='game_text':
        result['displayName']=readable(path);result['nameSource']='contextual_game_text'
    result['fullDisplayName']=result['displayName']+(' - '+result['variantLabel'] if result.get('variantLabel') else '')
    return result
