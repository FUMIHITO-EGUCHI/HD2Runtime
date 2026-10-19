-- Pre-fire homing support, extracted from the user-tested AR-23 Homing Lab 0.4.1.
-- The generic Runtime integration is not yet live-tested.
-- Read-only menu gate. UI stack constants are from Mod Options Menu v1.2
-- src/view.lua, verified there for build 25480438 (same SHA256s as Runtime .40).
-- Called only with event_world.open()'s fingerprint-proven game.dll base.
-- This is independent of HUD z ordering and never changes acquisition.
local M={}
local UI_STATE,STACK,ENTRIES,ESCAPE=0x347ce28,0x429c,5,1
local function u32(s,i)
    local a,b,c,d=s:byte(i+1,i+4)
    return a and d and(a+b*256+c*65536+d*16777216)or nil
end
local function cursor_visible()
    local S=rawget(_G,'stingray');local W=type(S)=='table'and S.Window
    local f=type(W)=='table'and W.show_cursor
    if f then local ok,value=pcall(f);return ok and value==true end
    return false
end
local function read(world,aim_only)
    local ok,settings=pcall(require,'hd2runtime/runtime/runtime_settings')
    if ok and type(settings.visible)=='function'then
        local got,shown=pcall(settings.visible)
        if got and shown==true then return true,'runtime_settings'end
    end
    -- Also conservatively hide over a map/terminal/other UI exposing its cursor.
    -- Cursor visibility is not used as proof that a specific menu is open.
    if cursor_visible()then return true,'cursor_visible'end
    if not world then
        local W=require('hd2runtime/runtime/event_world');world=W.open()
    end
    if not world or not world.game or not world.view then return true,'menu_state_unavailable'end
    local p=world.view.pointer(world.game+UI_STATE)
    local bytes=p and world.view.read(p+STACK,4*(ENTRIES+1))
    if type(bytes)~='string'or#bytes~=24 then return true,'menu_state_unavailable'end
    local depth=u32(bytes,4*ENTRIES)
    if not depth or depth>ENTRIES then return true,'menu_state_unavailable'end
    for i=0,depth-1 do if u32(bytes,i*4)==ESCAPE then return true,'escape_menu'end end
    if aim_only~=false then
        local aiming,why=require('hd2runtime/runtime/homing_aim_state').active(world)
        if aiming~=true then return true,aiming==false and'not_aiming'or(why or'aim_state_unavailable')end
    end
    return false
end
function M.blocked(world,aim_only)
    local ok,hidden,why=pcall(read,world,aim_only)
    if not ok then return true,'menu_state_unavailable'end
    return hidden,why
end
return M
