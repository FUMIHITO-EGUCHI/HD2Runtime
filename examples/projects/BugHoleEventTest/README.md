# BugHoleEventTest

Live test for the `bughole_destroyed` event (`docs/events.md#bug-holes`). The event is experimental.

## How it works

- A bug hole is a `bug_spawner_*` entity with a Destructible component. When the game closes it, the hole's record in
  the game's destruction world goes from stage 0 to 1, 2 or 3. The entity itself stays
  (`research/event-destruction-F5FEE03DCFDB.json`).
- Runtime checks 4 times a second and reports each hole once. Holes that are already closed when Runtime starts
  watching are not reported.
- The game does not record who closed a hole.

## How to test

1. Start a Terminid mission as host. The log shows `mission started (host true): bughole_destroyed active`.
2. Close a normal bug hole with a grenade. You get exactly one log line `bug hole closed #1: warrior (level ...,
   owned here: host)` and a yellow banner.
3. Close a Bile Titan hole (Hellbomb or 500kg). The line says `bile_titan` and has a position.
4. Repeat as a client in someone else's game. The lines must say `not owned here: client`.

Report:

- a closing that logged nothing;
- a line logged without a closing;
- a wrong hole kind;
- a position far from the hole.
