# Eagle Strafing Run assets

Preloads every catalogued call-in package for **Eagle Strafing Run**, so its assets are available when an extra-slot mod supplies the stratagem even if nobody selected it in their loadout. This only loads assets; your extra-slot mod still supplies the stratagem.

Requires **the updated Runtime built from this checkout** and Bingus Shared Loader v15+. Previously released Runtimes do not accept stratagem handles in `hd2.require_assets`; the example checks support and reports a useful error. `schemas/weapon_mapper.lua` is unrelated to package loading and needs no changes.

Build from the repository root:

```powershell
py -3 examples/projects/EagleStrafingRunAssets/build.py
```

Install the generated addon ZIP from this project's `build` folder alongside the updated HD2Runtime through your usual Bingus mod installation. Start the game with the addon enabled. Look for `[HD2Runtime] assets for example-eagle-strafing-run-assets resident` in the log before calling the stratagem. Requests are asynchronous, can take up to 90 seconds, and retain the packages for the game session.

To load another stratagem, change the name in `src/addon.lua` or add more `hd2.stratagem('...')` handles to `targets` (up to 16 per request). Runtime uses the same catalogued call-in package set as the mission loader, including the weapon package for support weapons. Unknown or incomplete sets are rejected. The shared session budget is 64 distinct packages, so this is not an unrestricted load-all-stratagems addon.

Offline validation covers package selection, loading completion, duplicate requests, and failures. The missing pink model, VFX, and SFX case still needs an in-game check: launch a mission with nobody equipping Eagle Strafing Run, wait for the resident log, then call it through the extra slot. Loading on players without Runtime is not guaranteed.
