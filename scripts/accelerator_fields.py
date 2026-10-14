"""PLAS-39 charge controls from the reviewed common charge consumer."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NAME='PLAS-39 Accelerator Rifle'
RESEARCH=ROOT/'research/dev4-controls-F5FEE03DCFDB.json'
ACK='Reviewed native charge consumer; edits have not been gameplay-tested. Unsafe mode can destroy the weapon at the overcharge time when explosion is enabled.'
FIELDS=[
 ('charge.level_1','Minimum charge time',0,'f32','seconds',0,60),
 ('charge.level_2','Full charge time',24,'f32','seconds',0.01,60),
 ('charge.level_3','Overcharge time',48,'f32','seconds',0.01,60),
 ('charge.speed_multiplier_min','Minimum charge speed multiplier',72,'f32','multiplier',0,10),
 ('charge.speed_multiplier_overcharge','Overcharge speed multiplier',76,'f32','multiplier',0,10),
 ('charge.damage_multiplier_min','Minimum charge damage multiplier',80,'f32','multiplier',0,10),
 ('charge.damage_multiplier_overcharge','Overcharge damage multiplier',84,'f32','multiplier',0,10),
 ('charge.penetration_multiplier_min','Minimum charge penetration multiplier',88,'f32','multiplier',0,10),
 ('charge.penetration_multiplier_overcharge','Overcharge penetration multiplier',92,'f32','multiplier',0,10),
 ('charge.auto_fire_at_full','Fire automatically at full charge',184,'u8',None,0,1),
 ('charge.explode_at_overcharge','Unsafe: explode and destroy weapon at overcharge',185,'u8',None,0,1),
 ('charge.burst_shots','Shots per charged burst',188,'u32','shots',0,10),
 ('charge.burst_interval_seconds','Charged burst interval',192,'f32','seconds',0,10),
 ('charge.overcharge_limit_seconds','Unsafe: overcharge hold limit (0 disables)',208,'f32','seconds',0,60)]
def definitions():
 return [dict(id=id,display_name=label,type='boolean'if storage=='u8'else'integer'if storage=='u32'else'number',
  unit=unit,derived=False,writable=True)for id,label,off,storage,unit,lo,hi in FIELDS]
def fields(name,make):
 if name!=NAME:return []
 data=json.loads(RESEARCH.read_text())['charge'];out=[]
 for id,label,off,storage,unit,lo,hi in FIELDS:
  value=data['values'][str(off)];value=bool(value)if storage=='u8'else value
  backing=dict(data['identity'],kind='component',component='WeaponChargeComponentData',offset=off,
    storage=storage,width=1 if storage=='u8'else 4)
  f=make(id,value,backing)
  f.update(min=lo,max=hi,acknowledgement='allow_unverified_effect',acknowledgementReason=ACK,
   effect=dict(activeSource='ACTIVE_DIRECT',activeSourceProven=True,appliesWhen='next_frame',
    instantiationOnly=False,gameplayEffectProven=False,reason=ACK),reviewedAcceleratorCharge=True)
  out.append(f)
 return out
def mode_row(row):
 proof=json.loads(RESEARCH.read_text())['weapon']
 assert row['slots']==[2,0,0,0] and row['selectorBound'] and row['ownerUnique']
 assert proof['values']['188']==3
 return dict(row,state='selectable',reason=None,maxModes=2,
  allowedModeValues={'single':2,'unsafe':6},chargeSelector=True)
