-- Process-wide diagnostic control for application caches and read pacing.
-- Both modes keep native ownership checks and transaction snapshots.
local M={}
local enabled=true
local clearers={}
function M.enabled()return enabled end
function M.on_change(key,clear)clearers[key]=clear end
function M.configure(value)
    if value==nil then return enabled end
    assert(type(value)=='boolean','application optimizations must be a boolean')
    if value~=enabled then
        enabled=value
        for _,clear in pairs(clearers)do clear()end
    end
    return enabled
end
return M
