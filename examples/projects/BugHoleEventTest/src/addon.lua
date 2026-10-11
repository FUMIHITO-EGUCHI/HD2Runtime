local hd2=require('mods/skyeshade/hd2runtime')
-- Live test for the bughole_destroyed event (docs/events.md#bug-holes, experimental). Every bug hole the game closes
-- is logged with its kind, level, position and owner, and shown on screen for 8 seconds. The source's status is
-- logged when a mission starts.
--
-- What to check: close a normal bug hole (a grenade) and a Bile Titan hole (a Hellbomb or 500kg) as host, then as a
-- client. Each closing must log exactly one line; nothing else may log one.
assert(hd2.events and hd2.ui,'BugHoleEventTest needs an HD2Runtime build with the bughole_destroyed event')
local mod=hd2.mod()
local closed,banner,remaining=0,nil,0

local function where(position)
    if not position then return'position unreadable'end
    return string.format('at %.1f, %.1f, %.1f',position.x,position.y,position.z)
end
hd2.events.on('bughole_destroyed',function(event)
    closed=closed+1
    local line=string.format('bug hole closed #%d: %s (level %d, entity %d, %s, %s)',closed,event.hole,event.level,
        event.entity_id,where(event.position),event.owned and'owned here: host'or'not owned here: client')
    mod:log(line)
    banner=string.upper('Bug hole closed: '..event.hole..(event.bile_titan and' (Bile Titan)'or''))
    remaining=8
end,{id='bughole_destroyed'})
hd2.events.on('mission_started',function(event)
    closed=0
    local status=hd2.events.status().bughole_destroyed
    mod:log('mission started (host '..tostring(event.host)..'): bughole_destroyed '..tostring(status and status.status)
        ..(status and status.reason and(' - '..tostring(status.reason))or''))
end,{id='mission_started'})

local overlay=hd2.ui.overlay({id='bug_holes'})
overlay:draw(function(d,dt)
    if not banner then return end
    remaining=remaining-dt
    if remaining<=0 then banner=nil;return end
    local text=banner
    local size=26*d.scale
    local w=overlay:text_width(text,size,'title')+40*d.scale
    d:rect((d.width-w)/2,d.height*0.18,w,size+20*d.scale,{0,0,0,170})
    d:text(text,d.width/2,d.height*0.18+10*d.scale,{size=size,font='title',align='center',colour={255,220,60}})
end)
overlay:show(true)

mod:log('loaded: close bug holes in a Terminid mission; each closing logs one line and shows a banner')
