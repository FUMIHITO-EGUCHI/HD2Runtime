local hd2 = require('mods/skyeshade/hd2runtime')

-- Preload the Eagle Strafing Run for an extra-slot mod, even if nobody equipped it.
-- Add other hd2.stratagem('...') handles here to load their call-in packages too.
local targets = {
    hd2.stratagem('Eagle Strafing Run'),
}

-- Gives a useful error on older Runtimes that cannot preload stratagem handles,
-- or when a stratagem's complete package set is not known for this game build.
for _, target in ipairs(targets) do
    local info = hd2.asset_dependency(target)
    assert(info.autoLoadSupported,
        'EagleStrafingRunAssets needs a Runtime with stratagem asset loading: '
        .. tostring(info.blocker))
end

-- Runtime schedules this automatically; do not poll or call watch.tick yourself.
-- waiting_for_assets -> complete (RESIDENT), or rejected (ASSET_UNAVAILABLE).
-- Packages stay loaded for the game session, including after mission transitions.
return hd2.require_assets({
    id = 'example-eagle-strafing-run-assets',
    targets = targets,
})
