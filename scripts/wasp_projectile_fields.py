"""Reviewed W.A.S.P. carried projectile selectors, retaining both missile entities.

The shot passes +0/+576 through spawn info +0x424 to SeekingMissile. Its
+173 flag registers the carried row with the projectile system, while +176=0
selects the shot's type. These swaps change hit behavior, not missile flight.
"""
import missile_fields

NAME = 'StA-X3 W.A.S.P. Launcher'
RESOURCE = '0xCC786F6491FE7E65'
NOTE = ('Changes missile damage and impact effects. Missile flight and appearance remain controlled by the '
        'missile entity. Call in a new weapon after applying. Not yet gameplay-tested.')


def proof():
    out = []
    for spawn in missile_fields.spawns(RESOURCE):
        missile = spawn['missile']
        sm = missile['seekingMissile']
        values = sm['values']
        assert values['movement_should_be_processed_by_projectile_system'] == 1
        assert values['projectile_type_to_process'] == 0
        pw = spawn['projectileWeapon']
        out.append({'component': missile_fields.SM, **{k: sm[k] for k in ('recordIndex', 'indexRow', 'ownerCount')},
                    'link': {'component': missile_fields.PW, 'offset': spawn['member'],
                             **{k: pw[k] for k in ('recordIndex', 'indexRow', 'ownerCount')},
                             'entity': missile['resource'], 'entityRow': missile['entityRow']}})
    assert len(out) == 2 and {x['link']['offset'] for x in out} == {40, 584}
    return out


def hosts(items):
    proof()
    for item in items:
        if item['weapon'] == NAME:
            item.update(componentHost=True, status='ACTIVE_DIRECT', mechanism='component', reason=NOTE)
    return items


def modes(rows):
    row = rows[('support', NAME)]
    assert row['functionAmmo']['projectile'] == 330 and row['functionAmmo']['entity']
    row['functionAmmo'].update(state='native', reason=NOTE)


def annotate(field):
    field.update(missileProjectileHost=proof(), acknowledgement='allow_unverified_effect',
                 acknowledgementReason=NOTE, missileProjectileNote=NOTE)
    field.pop('liveEvidence', None)
    return field
