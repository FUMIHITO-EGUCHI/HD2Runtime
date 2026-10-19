# HomingLockOn (development example)

Requires the Runtime extension described in `docs/homing-lock-on.md`. The stock
0.40.0 release safely refuses these new options even though the build profile matches.
Build with `python build.py`; the separately installed SDK is found as in the other
example projects. No Runtime implementation is bundled by this example.

Use solo/host, hold a normal AR-23, acquire up to three targets for 0.3 seconds,
and then fire single shots and bursts. A shot fired before locking stays ordinary.
LOS must be clear; blocked/unknown targets are excluded. The 600 m/s² acceleration
budget produces gentler speed-dependent curves, under the 1440 deg/s cap.

Compare aim press/release and menu transitions, three-target bursts, a blocked
sightline, and acceleration 300/600/1200. Check acquisition/steering and hit outcomes
separately. The HUD is aim-only and defaults to amber acquisition / green lock.
Change `hud:style(...)` from an options callback without recreating gameplay.

This Runtime integration/example is offline-tested, not live-verified. The originating
standalone AR-23 mod was user-confirmed; that does not verify this packaged example.
