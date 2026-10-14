# Mission timers

`hd2.missions({faction='terminids'})` lists mission definitions for Terminids, Automatons, or Illuminate. Omit the filter for all 162 definitions in the supported build. `hd2.mission(id):describe()` supplies the duration, timer group, shared mission identities, and lifecycle notes. IDs are stable; names are presentation only. `hd2.text.name('mission', id)` reads the game's name in its current language, with the same availability handling as other game texts.

```lua
local mission = hd2.mission('automatons/a41d64ac') -- Blitz: Search and Destroy
hd2.patch {
    id = 'longer-blitz', target = mission,
    field = hd2.fields.mission.duration_seconds,
    expect = 720, value = 1200,
    allow_shared = true, allow_unverified_effect = true,
}
```

Apply aboard the ship before launching. This edits the authored starting duration, in seconds (60–2500), rather than repeatedly modifying a live countdown. 2500 seconds (41:40) is the game's own ceiling: the host clamps its running countdown every frame to the range of the replicated mission-timer field (0–2500). A longer authored duration would still show its full length on the ship's mission selector but start at 41:40 in the mission, so values above 2500 are refused. The game copies it when creating the mission director; existing mission copies retain their values. The configured duration also participates in elapsed-time and mission-progress calculations, so this is not a promise that changing it leaves patrol escalation unchanged.

## Freezing the timer (experimental, the host controls it)

`hd2.freeze_mission_timer{frozen = true, allow_unverified_effect = true}` freezes the running mission countdown; `frozen = false` resumes it. It sets the game's own timer pause, the one Evacuate High-Value Assets missions spawn with until the evacuation starts. While it is set, the game's update skips the countdown, so there is no 41:40 ceiling and the timer never reaches zero. Everything the game derives from the countdown waits with it: mission progress, elapsed time and the five-minute warnings. Mission creation clears the pause, so the next mission starts normally.

Each call checks its preconditions again and keeps nothing between calls:
- the host, in a mission, with exactly one active timer;
- the reviewed code;
- the instance identity.

In a lobby with other players, the host's Runtime publishes the freeze under its own lobby member-data key `hd2mt` (`hd2mt/1;<0|1>;<seq>`). Every other Runtime in the mission reads the host's value every two seconds and sets its own countdown's pause the same way, through the same guarded write (`mission timer sync` log lines). The host publishes `0` once it leaves the mission, so a freeze never carries into the next mission. A player without HD2Runtime only sees what the game itself replicates.

Other cases are refused:
- `HOST_ONLY` when this machine is not the host: the host controls the mission timer.
- `NOT_APPLICABLE` for Evacuate High-Value Assets timers, which the mission releases itself, and for a timer that has already run out.

It returns `{status = 'APPLIED' | 'UNCHANGED', frozen, remainingSeconds, source, verified}`, or `nil`, a code and a reason. `hd2.diagnostics.mission_timer()` reports `active.paused` and `active.expired`. Not yet gameplay-tested.

There are 19 distinct timer sources behind the 162 definitions. Regular missions often share a faction's 40-minute timer; Blitz uses 12-minute sources. Specific missions use entity-delta overrides instead, including the 20-minute High-Value Asset timer. The API resolves that override rather than offering an ineffective base edit. Some delta timers are shared across factions. Consult `timerGroup` and `sharedWith` before changing one. Contradictory writes to the same source conflict through normal ownership checks.

The editor's **Missions** group contains the three fronts, faction icons, filters for identified/unidentified missions, and a shared-timer explanation on every page. Shared pages use one canonical row: pending values, application, reset, saved presets, and exports remain synchronized and count the edit once. The game's localized names are used when available and enabled.

The catalogue includes dormant event/developer variants and does not claim current Galactic War availability. 127 names were recovered offline; 35 fall back to explicitly unidentified labels unless live game text resolves them. Only the duration is newly writable in this pass. Rewards, objectives, mission availability, extraction countdowns, and live elapsed time have not been exposed as speculative controls.

Validation is offline: all mission links, guarded write/rollback round trips for every distinct timer, unchanged surrounding bytes and restored page protection, foreign-value/identity refusal, and active-mission refusal. In-game launch/expiry behavior and multiplayer behavior still need testing. No background timer loop or native callback is installed.
