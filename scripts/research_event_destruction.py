"""Bug holes and their destruction: what the `bughole_destroyed` event reads (runtime/event_sources.lua, 0.31.1).

Read-only. Proves, on build F5FEE03DCFDB:

1. The Destructible component manager (game+0x3326550): create (0x526640) appends instance `count` (+0xC) and stores
   its descriptor pointer at +0x4030 + 8i; remove (0x526710) moves the last instance down and decrements the count. Its
   post-create (0x883200) registers the entity's unit in the destruction world (0x13E0760) and stores the returned
   record index at +0x6030 + 4i. The descriptor is the generic component descriptor the health research proved
   ({+0 entity resource, +8 entity, +0xC unit, +0x14 flags, bit 0 = this machine owns it}); the destroyed-callback
   0x883500 reads its unit (+0xC) and its owned bit (+0x14) exactly so.
2. The destruction world (game+0x346D528): one 12-byte record per registered unit at +0xC5F78 + 12i
   ({u32 unit, u16 definition, u8, u8 stage, u8 flags}); the stage getter 0x13E1B50 reads the stage byte (+7). The
   destruction update 0x13E1DC0 writes the new stage (+7) and ORs the level bit into the flags (+8); an enqueue only
   happens for a level above the current one (0x13E163D), so the stage only grows. The network handler 0xBBA520
   enqueues the same destruction on the receiving peer, so every machine's world record reaches the same stage.
   Destroying the entity clears the record's flags (0x526932).
3. The destroyed-callback only destroys the entity when the definition's +0x90 bit 0 is set; every bug hole
   definition has it clear: a closed hole stays an entity at a stage above 0.
4. The Bile Titan holes' units are another unit class (vtable exe+0x16770E0) whose scene-graph accessor (vtable slot
   +0xE8, exe+0x2CAC50) is `lea rax, [rcx + 0x48]; ret` instead of the reviewed +0x60 one. The engine's own
   Unit.world_position (pinned in research/event-state-F5FEE03DCFDB.json: call [vtable + 0xE8], then +0x28 poses, +0x30
   translation) does not depend on the class, so the same read through +0x48 is the engine's. In every snapshot every
   hole's root pose read so is an orthonormal rotation with a [0, 0, 0, 1] last column.
5. In every retained mission snapshot the bug holes (Destructible instances whose entity resource is a
   content/env_bugs/assets/gameplay/bug_spawner_* entity) all link: the world record at their index carries their
   unit and is registered (flags bit 0). None is closed (stage 0) in any snapshot.

Not proven here: that closing a hole in play moves its stage from 0 (the event is experimental until a live test),
and who closed it (the record keeps no creditor).

Requires the research-only package capstone.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/scan'))
import build_profile  # noqa: E402
import research_event_state as base  # noqa: E402
import snapshot_image  # noqa: E402
from scan import tables  # noqa: E402

OUTPUT = ROOT / 'research/event-destruction-F5FEE03DCFDB.json'
MISSION = ['F5FEE03DCFDB-20260929T172647Z-mission-host.hd2snap',
    'F5FEE03DCFDB-20260929T172918Z-mission-host-alive.hd2snap',
    'F5FEE03DCFDB-20260929T173206Z-mission-host-after-reinforce.hd2snap',
    'F5FEE03DCFDB-20261008T162919Z-weapon-roots-scythe-dagger.hd2snap',
    'F5FEE03DCFDB-20261008T163453Z-weapon-roots-defender-etool.hd2snap']
OTHER = ['F5FEE03DCFDB-20260926T222226Z.hd2snap', 'F5FEE03DCFDB-20260927T155654Z.hd2snap',
    'F5FEE03DCFDB-20260927T160033Z.hd2snap', 'F5FEE03DCFDB-20260929T173443Z-mission-end-transition.hd2snap']
SNAPSHOTS = MISSION + OTHER
MANAGER = 0x3326550
WORLD = 0x346D528
COUNT, DESCRIPTORS, WORLD_INDEX = 0xC, 0x4030, 0x6030
RECORDS, STRIDE, STAGE, FLAGS = 0xC5F78, 12, 7, 8
DEFINITIONS = 0x20
DESTROYS_ENTITY = 0x90
PREFIX = 'content/env_bugs/assets/gameplay/bug_spawner_'
X_UNIT_REGISTRY, UNIT_OBJECTS, UNIT_ID = 0x1A100F0, 0x88, 0x08
UNIT_VTABLES = {0x1676D80: (0x2BD870, '488d4160c3', 0x60), 0x16770E0: (0x2CAC50, '488d4148c3', 0x48)}
POSES = 0x28

EXE_PROOFS = {
    'levelUnit': [
        (0x2CAC50, 'lea rax, [rcx + 0x48]', None, 'level unit class: the scene graph at +0x48'),
        (0x2CAC54, 'ret', None, 'level unit class: the accessor returns it'),
        (0x2BD870, 'lea rax, [rcx + 0x60]', None, 'unit class: the scene graph at +0x60 (the reviewed one)'),
    ],
}

GAME_PROOFS = {
    'manager': [
        (0x526646, 'mov rbx, qword ptr [rip + {rip}]', MANAGER, 'Destructible create: the manager'),
        (0x526691, 'inc dword ptr [rbx + 0xc]', None, 'create: one more instance (count +0xC)'),
        (0x5266A0, 'mov r9, qword ptr [rip + {rip}]', MANAGER, 'create: the manager again'),
        (0x5266F0, 'mov qword ptr [r9 + r8*8 + 0x4030], r10', None, 'create: instance i descriptor at +0x4030 + 8i'),
        (0x5266C8, 'mov dword ptr [r9 + r8*4 + 0x6030], eax', None, 'create: instance i world index +0x6030 + 4i'),
        (0x526719, 'mov rbx, qword ptr [rip + {rip}]', MANAGER, 'Destructible remove: the manager'),
        (0x52672C, 'mov r8d, dword ptr [rbx + 0xc]', None, 'remove: the instance count'),
        (0x526736, 'mov dword ptr [rbx + 0xc], r8d', None, 'remove: one instance fewer'),
        (0x8832FD, 'call 0x13e0760', None, 'post-create: registers the unit in the destruction world'),
        (0x88330B, 'mov dword ptr [r14 + rsi*4 + 0x6030], eax', None, 'post-create: the world record index'),
    ],
    'descriptor': [
        (0x883522, 'mov r11, qword ptr [rip + {rip}]', MANAGER, 'destroyed-callback: the manager'),
        (0x8835AB, 'mov rax, qword ptr [r11 + rax*8 + 0x4030]', None, 'destroyed-callback: the instance descriptor'),
        (0x8835CB, 'mov edx, dword ptr [rax + 0xc]', None, 'descriptor +0xC: the unit'),
        (0x88382D, 'test byte ptr [rax + 0x14], 1', None, 'descriptor +0x14 bit 0: this machine owns the entity'),
        (0x88384C, 'mov edx, dword ptr [rax + 8]', None, 'descriptor +8: the entity'),
        (0x88383F, 'test byte ptr [rcx + 0x90], 1', None, 'definition +0x90 bit 0: destroy the entity'),
    ],
    'world': [
        (0x13E1B64, 'mov r11, qword ptr [rip + {rip}]', WORLD, 'stage getter: the destruction world'),
        (0x13E1BDF, 'lea rax, [rcx + rcx*2]', None, 'record stride 12 (3 x 4)'),
        (0x13E1BE3, 'movzx eax, byte ptr [r11 + rax*4 + 0xc5f7f]', None, 'record +7: the stage'),
        (0x13E2161, 'mov ebx, dword ptr [rsi + rdx*4 + 0xc5f78]', None, 'record +0: the unit'),
        (0x13E2037, 'mov byte ptr [r15 + 7], al', None, 'destruction update: the new stage'),
        (0x13E205B, 'or byte ptr [r15 + 8], al', None, 'destruction update: the level bit in the flags'),
        (0x13E163D, 'jge 0x13e1719', None, 'enqueue only for a level above the current one'),
        (0xBBA6EE, 'call 0x13e15c0', None, 'network handler: the same destruction on the receiving peer'),
        (0x526932, 'mov byte ptr [rax + rcx*4 + 0xc5f80], 0', None, 'entity destroyed: the record flags cleared'),
    ],
}


def pose(mem, unit):
    """The unit's class and root pose through its own scene-graph accessor: {vtable, position, orthonormal}."""
    registry = mem.ptr(mem.exe + X_UNIT_REGISTRY)
    obj = mem.ptr(mem.ptr(registry + UNIT_OBJECTS) + 8 * (unit & 0x3FFFFF))
    if not obj or mem.u32(obj + UNIT_ID) != unit:
        return None
    vtable = mem.ptr(obj) - mem.exe
    known = UNIT_VTABLES.get(vtable)
    if not known or mem.ptr(mem.ptr(obj) + 0xE8) != mem.exe + known[0] or mem.read(mem.exe + known[0], 5).hex() != known[1]:
        return {'vtable': vtable, 'reviewed': False}
    m = struct.unpack('<16f', mem.read(mem.ptr(obj + known[2] + POSES), 64))
    rows = [m[0:3], m[4:7], m[8:11]]
    dot = lambda a, c: sum(x * y for x, y in zip(a, c))
    ortho = all(abs(dot(rows[i], rows[j]) - (i == j)) < 1e-3 for i in range(3) for j in range(3))
    return {'vtable': vtable, 'reviewed': True, 'position': [round(v, 2) for v in m[12:15]],
        'orthonormal': ortho and (m[3], m[7], m[11], m[15]) == (0, 0, 0, 1)}


def observe(name, names):
    mem = base.Mem(name)
    manager = mem.ptr(mem.game + MANAGER)
    world = mem.ptr(mem.game + WORLD)
    out = {'snapshot': name, 'manager': bool(manager), 'world': bool(world)}
    if not manager or not world:
        mem.close()
        return out
    count = mem.u32(manager + COUNT)
    definitions = mem.ptr(world + DEFINITIONS)
    holes, linked, unlinked = [], 0, []
    for i in range(count):
        pointer = mem.ptr(manager + DESCRIPTORS + 8 * i)
        raw = pointer and mem.read(pointer, 0x18)
        if not raw:
            unlinked.append(i)
            continue
        resource, entity, unit, _, flags = struct.unpack('<QIIII', raw)
        index = struct.unpack('<i', mem.read(manager + WORLD_INDEX + 4 * i, 4))[0]
        record = mem.read(world + RECORDS + STRIDE * index, STRIDE) if index >= 0 else None
        if not record or struct.unpack_from('<I', record, 0)[0] != unit or not record[FLAGS] & 1:
            unlinked.append(i)
            continue
        linked += 1
        path = names.name(resource) or ''
        if path.startswith(PREFIX):
            definition = struct.unpack_from('<H', record, 4)[0]
            pointer = mem.ptr(definitions + 8 * definition)
            destroys = mem.read(pointer + DESTROYS_ENTITY, 1)[0] & 1
            holes.append({'hole': path[len(PREFIX):], 'resource': '%016X' % resource, 'entity': entity,
                'unit': unit, 'worldIndex': index, 'definition': definition, 'stage': record[STAGE],
                'flags': record[FLAGS], 'owned': bool(flags & 1), 'destroysEntity': bool(destroys),
                'pose': pose(mem, unit)})
    mem.close()
    out.update({'count': count, 'linked': linked, 'unlinked': unlinked, 'holes': len(holes),
        'byHole': dict(sorted(collections.Counter(h['hole'] for h in holes).items())),
        'stages': dict(collections.Counter(str(h['stage']) for h in holes)),
        'definitions': dict(sorted(collections.Counter('%s:%d' % (h['hole'], h['definition']) for h in holes).items())),
        'destroysEntity': sum(h['destroysEntity'] for h in holes), 'owned': sum(h['owned'] for h in holes),
        'unitClasses': dict(collections.Counter('%s:%X' % (h['hole'], h['pose']['vtable']) for h in holes
            if h['pose'])),
        'posesOrthonormal': sum(bool(h['pose'] and h['pose'].get('orthonormal')) for h in holes),
        'worldIndexRange': [min(h['worldIndex'] for h in holes), max(h['worldIndex'] for h in holes)] if holes else None,
        'sample': holes[:3]})
    return out


def main():
    snap = snapshot_image.Snapshot(build_profile.snapshot_directory() / MISSION[1])
    if snap.game_dll_sha256.upper() != base.PROFILE_DLL_SHA:
        raise ValueError('snapshot fingerprint differs from the pinned profile')
    image_base, data = snap.module_image('game.dll')
    exe_base, exe_data = snap.module_image([k for k in snap.modules if k.endswith('.exe')][0])
    snap.close()
    image = base.Image(data, image_base, base.TEXT)
    exe = base.Image(exe_data, exe_base, base.EXE_TEXT)
    proofs = {group: [image.prove(*row) for row in rows] for group, rows in GAME_PROOFS.items()}
    exe_proofs = {group: [exe.prove(*row) for row in rows] for group, rows in EXE_PROOFS.items()}
    for vtable, (method, _, _) in UNIT_VTABLES.items():
        if exe.pointer_rva(vtable + 0xE8) != method:
            raise ValueError('unit class %X: the scene-graph slot changed' % vtable)
    pins = [p for rows in proofs.values() for p in rows]
    exe_pins = [p for rows in exe_proofs.values() for p in rows]
    relocation = {name: base.verify_pins_live(name, pins, exe_pins) for name in SNAPSHOTS}
    if any(relocation.values()):
        raise ValueError('pinned bytes differ in a snapshot: %r' % relocation)
    names = tables.pinned()
    observations = [observe(name, names) for name in SNAPSHOTS]
    for o in observations:
        if o['snapshot'] in MISSION:
            if not o.get('holes') or o['unlinked'] or o['destroysEntity'] or o['stages'] != {'0': o['holes']}:
                raise ValueError('bug holes not as expected in ' + o['snapshot'])
            if o['posesOrthonormal'] != o['holes']:
                raise ValueError('a hole without a readable orthonormal pose in ' + o['snapshot'])
            if o['owned'] != o['holes']:
                raise ValueError('a host snapshot with a hole this machine does not own: ' + o['snapshot'])
    # Every bug_spawner_* entity with a Destructible component in the entity tables (the holes the snapshots hold, and
    # the rest of the family).
    destructible = set(names.with_component('DestructibleComponentData'))
    holes = {'%016X' % value: path[len(PREFIX):] for value, path in sorted(names.paths.items())
        if path.startswith(PREFIX) and value in destructible}
    seen = {h['resource'] for o in observations for h in o.get('sample', [])}
    if not seen <= set(holes):
        raise ValueError('a hole in a snapshot is not in the bug_spawner family: %r' % (seen - set(holes)))
    report = {'schemaVersion': 1, 'build': build_profile.BUILD_ID,
        'gameDll': {'sha256': base.PROFILE_DLL_SHA, 'imageSize': base.IMAGE_SIZE},
        'layout': {'manager': MANAGER, 'count': COUNT, 'descriptors': DESCRIPTORS, 'worldIndex': WORLD_INDEX,
            'maxInstances': (WORLD_INDEX - DESCRIPTORS) // 8, 'world': WORLD, 'records': RECORDS, 'stride': STRIDE,
            'unit': 0, 'stage': STAGE, 'flags': FLAGS},
        'holes': holes,
        'levelUnit': {'vtableRva': 0x16770E0, 'slot': 0xE8, 'methodRva': 0x2CAC50, 'bytes': '488d4148c3',
            'sceneGraphOffset': 0x48},
        'proofs': proofs, 'exeProofs': exe_proofs, 'pinnedBytesMismatchPerSnapshot': relocation, 'observations': observations,
        'findings': {
            'link': 'In every mission snapshot every Destructible instance links: the destruction world record at its '
                '+0x6030 index carries its descriptor\'s unit and is registered (flags bit 0).',
            'holes': 'The bug holes are the instances whose entity resource is a bug_spawner_* entity: %s.'
                % ', '.join('%d in %s' % (o['holes'], o['snapshot'][13:-8]) for o in observations if o.get('holes')),
            'stage': 'Every hole is at stage 0 in every snapshot (none was closed). The stage only grows (the enqueue '
                'refuses a level at or below the current one) and the destroyed-callback keeps the entity (definition '
                '+0x90 bit 0 clear for every hole definition), so a closed hole is an entity at a stage above 0.',
            'position': "The Bile Titan holes' units are the level unit class (scene graph at +0x48); every other hole's "
                "unit is the reviewed class (+0x60). Through its own class's accessor every hole's root pose is an "
                'orthonormal rotation, and each Bile Titan hole lies among other holes.',
            'machines': 'The network handler 0xBBA520 applies a destruction on the receiving peer through the same '
                'enqueue: host and clients reach the same stage in their own world records.',
        },
        'unproven': [
            'That closing a hole in play moves its stage from 0 (no snapshot holds a closed hole): the event is '
            'experimental until a live test.',
            'Who closed a hole: the record keeps no creditor.',
            'The stage a closed hole reaches (1..3) per hole definition.',
        ],
        'writes': 0, 'protectionChanges': 0}
    OUTPUT.write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'pins': len(pins), 'holes': len(holes), 'observations': [
        (o['snapshot'][13:-8], o.get('count'), o.get('holes'), o.get('byHole')) for o in observations]}, indent=1))


if __name__ == '__main__':
    main()
