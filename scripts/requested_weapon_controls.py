"""Reviewed exceptions to the conservative weapon-function classification."""
import json
from pathlib import Path

SOURCE='research/dev11-weapon-controls-F5FEE03DCFDB.json'
ROOT=Path(__file__).resolve().parents[1]
WARRANT='P-92 Warrant'
VARIABLE='VG-70 Variable'

def evidence():
    return json.loads((ROOT/SOURCE).read_text(encoding='utf-8'))

def selectors(rows):
    proof=evidence()['weapons'][WARRANT]
    assert proof['inputs']==[8,0] and proof['modes']==[3,0,0,0]
    rows[('player',WARRANT)]={'kind':'player','weapon':WARRANT,'state':'addable',
        'maxModes':3,'bindableInputs':['right']}

def modes(rows):
    row=rows[('player',WARRANT)]
    assert row['slots']==[3,0,0,0] and not row['specialStruct'] and not row['functionTable']
    assert row['selector']['leftValue']==8 and row['selector']['rightValue']==0
    row.update(state='addable',reason=None,maxModes=3,bindableInputs=['right'])

def rates(rows):
    row=rows[('player',VARIABLE)]
    rate=row['fireRate']
    assert [rate['slots'][k] for k in ('x','y','z')]==evidence()['weapons'][VARIABLE]['rpm']
    assert rate['selectorBound'] and rate['selectorInput']=='right' and rate['uniqueOwner']
    rate.update(state='selectable',reason=None,maxModes=3,bindableInputs=[])
