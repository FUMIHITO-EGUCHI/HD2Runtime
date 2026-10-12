"""ShieldComponent recharge members: the native readers of +88 / +92 / +96. Read-only; nothing writes.

Pins, as exact decoded instructions in the retained snapshots' unpacked game.dll, the code that reads the
ShieldComponentData recharge members, so the FX-12 Shield Generator Relay can expose them next to its already
gameplay-proven radius (+0) and capacity (+76):

* the type lookup 0x4FAE20 (table slot 0xF12768, 344-byte records from +480) and the per-entity resolver 0x4FB390
  (an entity-delta override copy when the entity has one, else the type record);
* the per-frame shield update 0x651050: it resolves the settings record every frame, counts the instance timer
  down by the frame step and, once the timer is out, adds +96 x frame step to the shield health (capped at +76);
* the hit path 0x6524EC: every hit sets the timer to +88, and a hit that empties the shield sets it to +92;
* the two other timer writers (0x650AA0 restart timer, 0x652F56 set-charge) that read the same two members.

The values (exact published SH-32 / SH-51 / FX-12) and the record ownership come from the committed equipment
coverage and entity research; this script cross-checks them and the relay's own record.

Requires the research-only package capstone.  `--check` re-derives and compares with the committed output.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_profile  # noqa: E402
import research_event_state as base  # noqa: E402
import snapshot_image  # noqa: E402

OUTPUT = ROOT / 'research/shield-recharge-F5FEE03DCFDB.json'
EQUIPMENT = ROOT / 'research/equipment-coverage-F5FEE03DCFDB.json'
ENTITY = ROOT / 'research/entity-authoring-runtime-F5FEE03DCFDB.json'
TABLES = ROOT / 'research/entity-component-table-pointers-F5FEE03DCFDB.json'
RELAY = 'FX-12 Shield Generator Relay'
MEMBERS = {88: 'shield.recharge_delay', 92: 'shield.broken_recharge_delay', 96: 'shield.recharge_rate'}

# (rva, exact capstone text, RIP target or None, role)
GAME = {
    'typeLookup_0x4FAE20': [
        (0x4FAE2F, 'mov r10, qword ptr [rax + 0xf12768]', None,
            'the ShieldComponentData table from its component slot (index 94)'),
        (0x4FAE8C, 'imul rax, rcx, 0x158', None, 'record index x 344 (the ShieldComponentData record size)'),
        (0x4FAE93, 'add rax, 0x1e0', None, 'records start at table + 480'),
    ],
    'entityResolver_0x4FB390': [
        (0x4FB432, 'imul rax, rax, 0x158', None, 'the entity has an override copy: its index x 344 ...'),
        (0x4FB439, 'add rax, qword ptr [r11 + 0xa8]', None, '... in the override-copy array'),
        (0x4FB44C, 'jmp 0x4fae20', None, 'otherwise the type record (the record Runtime writes)'),
    ],
    'overrideCopy_0x656850': [
        (0x6568DA, 'mov edx, 0x158', None, 'an override copy is a 344-byte allocation ...'),
        (0x6568F0, 'call 0x4fae20', None, '... filled from the type record when it is created'),
    ],
    'frameUpdate_0x651050': [
        (0x571B4E, 'call 0x651050', None, 'the update is called from the world update 0x571250'),
        (0x65114A, 'call 0x4fb390', None, 'every frame, per shield: resolve the settings record'),
        (0x651158, 'mov qword ptr [rsp + 0x30], rax', None, 'kept for the rest of this shield\'s update'),
        (0x6515F8, 'movss xmm1, dword ptr [r15 + r12 + 0x4c]', None, 'the instance timer (+0x4c of the 0x88 instance)'),
        (0x651608, 'subss xmm1, xmm14', None, 'counted down by the frame step'),
        (0x65160D, 'movss dword ptr [r15 + r12 + 0x4c], xmm1', None, 'stored back'),
        (0x651688, 'mov dword ptr [r15 + r12 + 0x4c], 0', None, 'timer out: cleared ...'),
        (0x65169A, 'mov byte ptr [rax + r14*4 + 2], 0', None, '... the broken flag cleared'),
        (0x6516BC, 'movss xmm0, dword ptr [rbx + 0x4c]', None, 'shield below capacity (+76)?'),
        (0x6516D2, 'mov byte ptr [rax + r14*4 + 3], 1', None, '... then the recharging flag is set'),
        (0x6519D4, 'mov rcx, qword ptr [rsp + 0x30]', None, 'recharging: the settings record resolved this frame'),
        (0x651A10, 'movss xmm0, dword ptr [rcx + 0x60]', None, 'ShieldComponent +96: health restored per second'),
        (0x651A23, 'mulss xmm0, xmm14', None, 'x the frame step'),
        (0x651A28, 'addss xmm0, dword ptr [r13 + r14*4 + 4]', None, '+ the current shield health'),
        (0x651A1E, 'movss xmm1, dword ptr [rcx + 0x4c]', None, 'capacity (+76) ...'),
        (0x651A2F, 'minss xmm1, xmm0', None, '... caps the new health'),
        (0x651A33, 'movss dword ptr [r13 + r14*4 + 4], xmm1', None, 'the new shield health'),
    ],
    'hit_0x6524EC': [
        (0x652552, 'call 0x4fb390', None, 'on a hit: resolve the settings record'),
        (0x652557, 'mov r13, rax', None, 'r13 = the settings record (not reassigned before the reads below)'),
        (0x652938, 'mov eax, dword ptr [r13 + 0x58]', None, 'ShieldComponent +88: the delay after damage ...'),
        (0x65293C, 'mov dword ptr [r12 + 0x4c], eax', None, '... becomes the instance timer'),
        (0x6529AB, 'mov byte ptr [rax + r14*4 + 3], 0', None, 'a hit stops the recharge'),
        (0x652A6F, 'mov byte ptr [rax + r14*4 + 2], 1', None, 'the hit emptied the shield: broken'),
        (0x652AA8, 'mov eax, dword ptr [r13 + 0x5c]', None, 'ShieldComponent +92: the delay after breaking ...'),
        (0x652AAC, 'mov dword ptr [r12 + 0x4c], eax', None, '... becomes the instance timer'),
    ],
    'setCharge_0x652F56': [
        (0x652F75, 'call 0x4fb390', None, 'set the shield charge: resolve the settings record'),
        (0x652F85, 'mov r15, rax', None, 'r15 = the settings record'),
        (0x652FCA, 'mov byte ptr [rax + rbp*4 + 2], 1', None, 'charge 0: broken ...'),
        (0x653015, 'mov eax, dword ptr [r15 + 0x5c]', None, '... timer = +92'),
        (0x6530B4, 'mov eax, dword ptr [r15 + 0x58]', None, 'charge lowered: timer = +88'),
    ],
    'restartTimer_0x650AA0': [
        (0x650B29, 'call 0x4fb390', None, 'resolve the settings record'),
        (0x650B42, 'movss xmm0, dword ptr [rax + 0x58]', None, 'damaged state: +88'),
        (0x650B5B, 'movss xmm0, dword ptr [rax + 0x5c]', None, 'broken state: +92'),
        (0x650B6F, 'movss dword ptr [rsi + 0x4c], xmm0', None, 'the instance timer'),
    ],
}


def derive():
    snap = snapshot_image.Snapshot(build_profile.snapshot_directory() / base.SNAPSHOTS[0])
    game_base, game_data = snap.module_image('game.dll')
    if snap.game_dll_sha256.upper() != base.PROFILE_DLL_SHA:
        raise ValueError('snapshot game.dll is not the profile build')
    snap.close()
    image = base.Image(game_data, game_base, base.TEXT)
    pins = {group: [image.prove(*row) for row in rows] for group, rows in GAME.items()}
    flat = [p for rows in pins.values() for p in rows]
    relocation = {name: base.verify_pins_live(name, flat, []) for name in base.SNAPSHOTS}
    if any(relocation.values()):
        raise ValueError('pinned bytes differ in a snapshot: %r' % relocation)

    tables = json.loads(TABLES.read_text(encoding='utf-8'))
    slot = tables['code']['components']['ShieldComponentData']
    if (slot['index'], slot['slot'], slot['stride'], slot['recordOffset']) != (94, '0xF12768', 344, 480):
        raise ValueError('ShieldComponentData table layout disagrees with the component-table research')
    equipment = json.loads(EQUIPMENT.read_text(encoding='utf-8'))['shields']
    entity = json.loads(ENTITY.read_text(encoding='utf-8'))['shieldRelay']
    consumers = []
    for consumer in equipment['consumers']:
        row = {'consumer': consumer['consumer'], 'entity': consumer['entity'],
            'recordIndex': consumer['ownership']['recordIndex'], 'indexRow': consumer['ownership']['indexRow'],
            'ownerCount': consumer['ownership']['ownerCount'], 'uniqueOwner': consumer['ownership']['uniqueOwner'],
            'members': {}}
        for offset, field in MEMBERS.items():
            native = consumer['values'][str(offset)]
            published = {88: 'rechargeDelay', 92: 'brokenRechargeDelay', 96: 'rechargeRate'}[offset]
            wiki = consumer['wiki'][published]
            if abs(native - wiki) > 1e-6:
                raise ValueError('published value disagrees: %s +%d' % (consumer['consumer'], offset))
            row['members'][field] = {'offset': offset, 'native': native, 'published': wiki}
        consumers.append(row)
    relay = next(c for c in consumers if c['consumer'] == RELAY)
    if (relay['recordIndex'], relay['indexRow']) != (entity['shield']['recordIndex'], entity['shield']['indexRow']) \
            or not entity['shield']['uniqueOwner']:
        raise ValueError('relay shield record disagrees between the equipment and entity research')
    for offset in MEMBERS:
        if entity['shield']['values'][str(offset)] != relay['members'][MEMBERS[offset]]['native']:
            raise ValueError('relay value disagrees at +%d' % offset)

    return {
        'build': 'F5FEE03DCFDB',
        'gameDll': base.PROFILE_DLL_SHA,
        'writes': 0,
        'protectionChanges': 0,
        'snapshotsVerified': list(base.SNAPSHOTS),
        'component': 'ShieldComponentData',
        'slotIndex': 94,
        'recordSize': 344,
        'tableSlot': slot['slot'],
        'recordOffset': slot['recordOffset'],
        'members': {
            'shield.recharge_delay': {'offset': 88, 'storage': 'f32', 'typelibNameLength': 14,
                'semantic': 'seconds after a hit before a damaged shield starts recharging',
                'readers': ['0x652938 (every hit)', '0x6530B4 (charge lowered)', '0x650B42 (restart timer)'],
                'lifecycle': 'read from the resolved settings record at each hit and copied into the instance '
                    'timer; a write applies from the next hit on'},
            'shield.broken_recharge_delay': {'offset': 92, 'storage': 'f32', 'typelibNameLength': 21,
                'semantic': 'seconds after the shield breaks before it restarts',
                'readers': ['0x652AA8 (the breaking hit)', '0x653015 (charge set to 0)', '0x650B5B (restart timer)'],
                'lifecycle': 'read at the breaking hit and copied into the instance timer; a write applies from '
                    'the next break on'},
            'shield.recharge_rate': {'offset': 96, 'storage': 'f32', 'typelibNameLength': 13,
                'semantic': 'shield health restored per second while recharging (x frame step, capped at +76)',
                'readers': ['0x651A10 (every frame while recharging)'],
                'lifecycle': 'read from the settings record resolved every frame; a write applies at once'},
        },
        'resolver': {'function': '0x4FB390',
            'rule': 'an entity-delta override copy when the entity has one (a 344-byte copy taken from the type '
                'record when the override is created, 0x656850), else the type record',
            'consequence': 'Runtime writes the type record: shields read it live unless the entity carries an '
                'override copy made before the write; the relay\'s radius and capacity on the same record are '
                'gameplay-proven by type-record writes (ShieldRelayImprovements)'},
        'sharedManager': 'every ShieldComponent instance (SH-32, SH-51 barrier, FX-12, G-SH-39) runs through the '
            'same update 0x651050 and hit path 0x6524EC; the members are per type record, not per instance',
        'consumers': consumers,
        'relay': {'name': RELAY, 'resource': entity['resource'], 'recordIndex': relay['recordIndex'],
            'indexRow': relay['indexRow'], 'ownerCount': relay['ownerCount'], 'uniqueOwner': relay['uniqueOwner'],
            'values': {field: relay['members'][field]['native'] for field in MEMBERS.values()}},
        'notProven': [
            'ShieldComponent +100 (restart charge lead): no reader found in the shield update or hit path',
            'the frame step register xmm14 is the value that also counts the timer down; its source is not pinned',
            'in-game effect of a changed value (no live A/B yet)',
        ],
        'pins': pins,
    }


def main():
    result = derive()
    text = json.dumps(result, indent=1, sort_keys=False) + '\n'
    if '--check' in sys.argv:
        if OUTPUT.read_text(encoding='utf-8') != text:
            raise SystemExit('research/shield-recharge output differs')
        print('shield recharge research: unchanged')
        return
    OUTPUT.write_text(text, encoding='utf-8')
    print('wrote', OUTPUT.relative_to(ROOT))


if __name__ == '__main__':
    main()
