"""0.31.3: a custom stratagem's pick never writes a carrier this account does not own (a player report of 2026-10-12,
HD2Runtime (12).log and (13).log: with custom multiplayer the EAT-23 Expendable EMS and the EAT-40 Expendable Gas picks
wrote the EAT-411 Leveller and the EAT-700 Expendable Napalm, which that account does not own; the stratagem selector
refused every click, TOKEN_NOT_OWNED, nothing written). runtime/custom_stratagems.lua pick_plan:
  * solo: the allocation ranks only owned carriers; an expendable whose carrier weapon's own stratagem is not owned
    takes a separate support carrier this account owns; a carrier known from an older view that this account does not
    own is never written; with no owned carrier for it at all the pick is refused once with why (nothing written);
  * custom multiplayer: the lobby's carrier for an id is ranked without ownership (every machine alike). When this
    account does not own it, the pick takes an owned carrier of the definition's pool, which this player's slot then
    pins for every machine (the same carrier map on an account that owns other things); none: refused, explained once in
    the panel (never a loop of TOKEN_NOT_OWNED);
  * the selector's ownership guard is unchanged: a direct write of an unowned carrier or token is still refused."""
import unittest

from support import run
from test_stratagem_calldown_code import WORLD
from test_custom_stratagem_groups import HARNESS as GROUPS
import test_carrier_in_slot as carrier_in_slot


# The plan's inputs as stubs (the allocator itself is real): this account's catalogue (OWNED), the discovery of two
# blue support carriers (eligible only when owned; a lobby ranks the unowned ones anyway), the condensed verdict of a
# carrier weapon's own stratagem (owned or not), one or two players and the synced lobby table.
PLAN = GROUPS + r"""
local I=custom.internals_for_tests()
local world_module=require('hd2runtime/runtime/event_world')
local sync=require('hd2runtime/runtime/custom_mp_sync')
local loadout=require('hd2runtime/runtime/stratagem_loadout')
local selector=require('hd2runtime/runtime/stratagem_selector');selector.reset_for_tests()
local function sid(name)return catalog.stratagems[name].root.id end
local STALWART,AC8,PRECISION=sid('M-105 Stalwart'),sid('AC-8 Autocannon'),sid('Orbital Precision Strike')
local OWNED={}
local function own(...)OWNED={[PRECISION]=true};for _,id in ipairs({...})do OWNED[id]=true end;custom.reset_pick_plans()end
slots.owned=function(world,id)return OWNED[id]==true end
local SUPPORT={'M-105 Stalwart','AC-8 Autocannon'}
slots.discover_carriers=function(world,token,opts)
    local ex={}
    for _,n in ipairs(opts.exclude or{})do ex[n]=true end
    local out={}
    for _,n in ipairs(SUPPORT)do
        local c=cand(n)
        if ex[n]then c.eligible=false;c.codes={'donor'};c.reasons={'excluded'}
        elseif opts.present and opts.present[c.id]then c.eligible=false;c.codes={'in_loadout'};c.reasons={'in the loadout'}
        elseif not OWNED[c.id]then c.eligible=false;c.codes={'not_owned'};c.reasons={'not owned'}end
        out[#out+1]=c
    end
    return {ready=true,candidates=out}
end
slots.validate_carrier=function(world,token,weapon,opts)
    local c=cand(weapon,{type=16})
    if OWNED[c.id]then return {ready=true,valid=true,candidate=c}end
    c.eligible=false;c.codes={'not_owned'};c.reasons={'not owned'}
    return {ready=true,valid=false,candidate=c,reasons={'not owned'},codes={'not_owned'}}
end
loadout.saved=function()return {pairs={}}end
slots.records=function()return {}end
local GAME={}
world_module.open=function()return GAME end
local PLAYERS={{}}
world_module.players=function()return PLAYERS end
local VIEW=nil
sync.view=function()return VIEW end
-- A lobby: this player (ME) and another (THEM); picks = {ME = {[0] = id or false, ...}, THEM = ...}.
local function lobby(picks)
    PLAYERS={{},{}}
    local t={}
    for _,peer in ipairs({'ME','THEM'})do
        t[peer]={}
        for slot=0,3 do t[peer][slot]=(picks and picks[peer]and picks[peer][slot])or false end
    end
    VIEW={status='enabled',table=t,local_peer='ME',table_hash='H'..tostring(math.random(1,1e9)),peers={}}
    custom.reset_pick_plans()
end
local function solo()PLAYERS={{}};VIEW=nil;custom.reset_pick_plans()end
-- (every step re-evaluates: the offline clock does not move here)
custom.AVAILABILITY_EVERY,custom.REVALIDATE_EVERY=-1,-1
local function avail_step()I.availability_step(GAME,VIEW)end
"""


class PickPlanTests(unittest.TestCase):
    def lua(self, body):
        self.assertEqual(run(WORLD + PLAN + body + "\nreturn 'ok'"), b'ok')

    def test_solo_an_unowned_condensed_carrier_takes_an_owned_support_carrier(self):
        # Solo, the EAT-40's carrier weapon is the EAT-700 Expendable Napalm (its pool's first); this account does not
        # own the EAT-700's stratagem: the pick writes a support carrier it owns, never the EAT-700.
        self.lua(r"""
custom.register(eat17g('eat17g_clone'),'mods/test/one')
own(STALWART)
solo()
local plan=custom.pick_plan(GAME,'eat17g_clone')
assert(plan.carrier and plan.carrier.id==STALWART and plan.carrier.name=='M-105 Stalwart',J(plan))
local c,why=custom.probe_carrier('eat17g_clone')
assert(c and c.id==STALWART and why==nil,J(c))
assert(count('EAT-700 Expendable Napalm')==0 or count('its pick writes EAT-700')==0)
-- The availability says what the pick writes.
avail_step()
assert(count('AVAILABILITY (eat17g_clone): AVAILABLE: its carrier weapon is EAT-700 Expendable Napalm when it is picked '
    ..'(fallback: its beacon carrier is M-105 Stalwart when it is picked, because EAT-700 Expendable Napalm cannot carry '
    ..'it: not owned)')==1,said('AVAILABILITY'))
-- Owning the EAT-700 too: condensed, its own stratagem (one vanilla stratagem).
own(STALWART,ID700)
avail_step()
plan=custom.pick_plan(GAME,'eat17g_clone')
assert(plan.carrier and plan.carrier.id==ID700,J(plan))
""")

    def test_solo_a_stale_unowned_carrier_is_never_written(self):
        # A carrier from an older view (here the ship cache says the EAT-700) that this account does not own: the
        # allocation is asked again for this pick.
        self.lua(r"""
custom.register(eat17g('eat17g_clone'),'mods/test/one')
own(STALWART)
solo()
I.ship().alloc={assignments={eat17g_clone={stable_id=ID700,carrier=EAT700}},refused={},order={'eat17g_clone'}}
local plan=custom.pick_plan(GAME,'eat17g_clone')
assert(plan.carrier and plan.carrier.id==STALWART,J(plan))
-- No owned carrier at all: refused with why (nothing written), never the EAT-700, never the token for nothing.
own()
I.ship().alloc=nil
local c,why=custom.probe_carrier('eat17g_clone')
assert(c==nil and why and why:find('no separate support carrier is free',1,true),tostring(why))
assert(count('eat17g_clone: its pick is REFUSED (nothing written)')==1,said('CARRIER-IN-SLOT'))
avail_step()
assert(custom.unavailable('eat17g_clone')and custom.unavailable('eat17g_clone'):find('^UNAVAILABLE: its carrier weapon '
    ..'EAT%-700 Expendable Napalm cannot carry its beacon %(not owned%) and no separate support carrier is free'),
    tostring(custom.unavailable('eat17g_clone')))
-- No allocation can run yet (the discovery is not ready): the token, as before.
own(STALWART)
I.ship().alloc=nil
local discover=slots.discover_carriers
slots.discover_carriers=function()return {ready=false,reason='not filled yet'}end
assert(custom.probe_carrier('eat17g_clone')==nil)
slots.discover_carriers=discover
""")

    def test_lobby_an_unowned_condensed_carrier_takes_an_owned_carrier_that_every_machine_agrees_on(self):
        # The (13).log report: custom multiplayer, nobody picked anything; the lobby's carrier for the EAT-40 is the
        # EAT-700 Expendable Napalm's own stratagem (condensed), which this account does not own.
        self.lua(r"""
local d=custom.register(eat17g('eat17g_clone'),'mods/test/one')
own(STALWART)
lobby({})
avail_step()
local text=said('AVAILABILITY (eat17g_clone)')
assert(text:find('AVAILABLE: its carrier weapon is EAT-700 Expendable Napalm when it is picked (its beacon carrier is '
    ..'M-105 Stalwart when it is picked (a support carrier this account owns: the lobby\'s condensed carrier EAT-700 '
    ..'Expendable Napalm is not owned by this account))',1,true),text)
local c,why=custom.probe_carrier('eat17g_clone')
assert(c and c.id==STALWART and c.name=='M-105 Stalwart'and why==nil,J(c)..' '..tostring(why))
assert(count('the lobby\'s carrier for it is EAT-700 Expendable Napalm, which this account does not own: its pick writes '
    ..'M-105 Stalwart, a carrier of its pool this account owns')==1,said('CARRIER-IN-SLOT'))
-- After the pick every machine reads this player's slot (M-105 Stalwart) as the id's pin: the lobby's allocation gives
-- it that carrier (a separate support carrier; the EAT-700 stays its carrier weapon, the clone) on this machine ...
local pins={eat17g_clone=STALWART}
local mine=I.allocate(GAME,{},{},'test',{'eat17g_clone'},nil,true,pins)
local x=mine.assignments.eat17g_clone
assert(x and x.stable_id==STALWART and not x.condensed and x.weapon.weapon==EAT700 and not x.local_refused,J(x))
-- ... and on a machine whose account owns the EAT-700 and the AC-8 but not the M-105 Stalwart: the same map.
own(ID700,AC8)
local theirs=I.allocate(GAME,{},{},'test',{'eat17g_clone'},nil,true,pins)
assert(theirs.assignments.eat17g_clone.stable_id==STALWART,J(theirs.assignments.eat17g_clone))
assert(J(I.carrier_map(mine,{'eat17g_clone'}))==J(I.carrier_map(theirs,{'eat17g_clone'})))
-- Without that pin (no slot holds it) the lobby keeps the condensed EAT-700 for every machine, as before.
local plain=I.allocate(GAME,{},{},'test',{'eat17g_clone'},nil,true,{})
assert(plain.assignments.eat17g_clone.condensed and plain.assignments.eat17g_clone.stable_id==ID700)
-- A pin on the condensed carrier itself changes nothing either.
local same=I.allocate(GAME,{},{},'test',{'eat17g_clone'},nil,true,{eat17g_clone=ID700})
assert(same.assignments.eat17g_clone.condensed)
""")

    def test_lobby_an_unowned_group_carrier_takes_an_owned_member_of_its_group(self):
        # A group definition (support): the lobby ranks its members without ownership; the first is not owned here.
        self.lua(r"""
local d=custom.register(kit('support_kit',{carrier={group='support'},delivery={family='support',
    items={{donor='MG-43 Machine Gun'}}}}),'mods/test/one')
own(STALWART,AC8)
lobby({})
local first=I.allocate(GAME,{},{},'test',{'support_kit'},nil,true,{}).assignments.support_kit
assert(first and first.stable_id,'a carrier for it')
local other=first.stable_id==STALWART and AC8 or STALWART
own(other)
avail_step()
local plan=custom.pick_plan(GAME,'support_kit')
assert(plan.carrier and plan.carrier.id==other and plan.lobby==first.carrier,J(plan))
assert(count('AVAILABILITY (support_kit): AVAILABLE: its carrier is '..plan.carrier.name..' (group support): the lobby\'s '
    ..'carrier '..first.carrier..' is not owned by this account; its pick writes this one, which it owns')==1,
    said('AVAILABILITY'))
local a=I.allocate(GAME,{},{},'test',{'support_kit'},nil,true,{support_kit=other})
assert(a.assignments.support_kit.stable_id==other and not a.assignments.support_kit.local_refused)
""")

    def test_lobby_no_owned_carrier_refuses_the_pick_once_with_why(self):
        # The (12).log report: another player's EAT-40 holds the EAT-700; this player's EAT-23 then gets the EAT-411
        # Leveller, which this account does not own, and it owns no support carrier either: refused with why (every
        # click before wrote nothing and logged TOKEN_NOT_OWNED again).
        self.lua(r"""
custom.register(eat17g('eat17g_clone'),'mods/test/one')
custom.register(eat17g('eat23_ems',{code={'down','down','left','right','right'}}),'mods/test/two')
own()
lobby({THEM={[0]='eat17g_clone'}})
avail_step()
local why=custom.unavailable('eat23_ems')
assert(why and why:find('UNAVAILABLE: the lobby\'s carrier for it is EAT-411 Leveller, which this account does not own, '
    ..'and no carrier of its pool that this account owns is free for it',1,true),tostring(why))
local c,refusal=custom.probe_carrier('eat23_ems')
assert(c==nil and refusal and refusal:find('EAT-411 Leveller, which this account does not own',1,true),tostring(refusal))
-- Owning a support carrier: picked with it.
own(AC8)
avail_step()
assert(custom.unavailable('eat23_ems')==nil,tostring(custom.unavailable('eat23_ems')))
c=custom.probe_carrier('eat23_ems')
assert(c and c.id==AC8,J(c))
""")

    def test_another_players_slot_decides_the_lobbys_carrier(self):
        # Another player's slot already holds the id with a carrier this account does not own: that is the lobby's
        # carrier for it (the lowest peer's holder decides for every machine): refused here, never remapped.
        self.lua(r"""
custom.register(eat17g('eat17g_clone'),'mods/test/one')
own(STALWART)
lobby({THEM={[0]='eat17g_clone'}})
local ship_pins=custom.ship_pins
custom.ship_pins=function()return {eat17g_clone=ID700}end
I.ship().alloc={assignments={eat17g_clone={stable_id=ID700,carrier=EAT700,local_refused='not owned'}},refused={},
    order={'eat17g_clone'}}
local c,why=custom.probe_carrier('eat17g_clone')
assert(c==nil and why:find('another player\'s slot holds it with EAT-700 Expendable Napalm',1,true),tostring(why))
custom.ship_pins=ship_pins
""")


class FlowTests(unittest.TestCase):
    flow = carrier_in_slot.FlowTests.flow

    def test_lobby_an_unowned_lobby_carrier_is_never_written_its_owned_alternative_is(self):
        # Custom multiplayer, the Orbital Gas Barrage (group any_red): the lobby's carrier for it is not owned by this
        # account. The pick writes another member of its group that it owns (the selector never refuses it), and the
        # lobby's carrier for it then follows this player's slot.
        self.flow(carrier_in_slot.FlowTests.MP_SETUP + r'''
local AUTH=require('hd2runtime/domains/stratagem_authoring').stratagems
-- (its latest availability line: the lobby's carrier for it now)
local lobby_name=lines('AVAILABILITY (orbital_gas_barrage)'):match('.*its carrier is (.-) %(group')
assert(lobby_name,lines('AVAILABILITY'))
assert(AUTH[lobby_name],'not catalogued: '..lobby_name)
local lobby_id=AUTH[lobby_name].root.id
local owned={[PRECISION_ID]=2,[BIG_ID]=2,[NAPALM_ID]=2,[BIG380_ID]=2,[WALK_ID]=2,[EMS_ID]=2,[GATLING_ID]=2}
owned[lobby_id]=0
W.catalogue(owned)
custom.reset_pick_plans()
tick(200)
local text=lines('AVAILABILITY (orbital_gas_barrage)')
local alt=text:match('.*AVAILABLE: its carrier is (.-) %(group any_red%): the lobby\'s carrier '..lobby_name:gsub('%p','%%%0')
    ..' is not owned by this account; its pick writes this one, which it owns')
assert(alt and alt~=lobby_name,text)
select_into(0)
SCREEN.set('selecting',false);tick(8)
local V=require('hd2runtime/runtime/stratagem_selector').virtual_slots()
assert(AUTH[alt],'not catalogued: '..alt)
assert(V and V.slots[0]and V.slots[0].carrier and V.slots[0].token==AUTH[alt].root.id,
    lines('SELECTED')..' | '..lines('CARRIER-IN-SLOT')..' | '..lines('REFUSED'))
assert(count('TOKEN_NOT_OWNED')==0,lines('TOKEN_NOT_OWNED'))
assert(count('which this account does not own: its pick writes '..alt)==1,lines('CARRIER-IN-SLOT'))
-- The lobby's carrier for it is now the one this player's slot holds (its pin): nothing moves, nothing refused.
tick(200)
local all=lines('CUSTOM MP CARRIERS (aboard the ship, preview')
local last=all:match('.*(orbital_gas_barrage = .-%(stable id %d+%))')
assert(last and last:find(alt,1,true)and not all:match('.*orbital_gas_barrage = [^,]-NOT OWNED here'),all)
assert(count('stratagem selector MOVED')==0,lines('MOVED'))
return 'ok'
''')

    def test_lobby_no_owned_carrier_is_explained_once_and_nothing_is_written(self):
        # The report's loop: custom multiplayer, the EAT-40's lobby carrier is the EAT-700 Expendable Napalm's own
        # stratagem, which this account does not own, and this world owns no support carrier: unavailable, said once,
        # the selector never asked (no TOKEN_NOT_OWNED), however often the tile is clicked.
        from support import lua as lua_literal
        from test_custom_mp_mission import example_addon
        g, g_addon = example_addon('EAT17GExample')
        self.flow('local G_ADDON=' + lua_literal(g_addon) + '\nlocal G_RESOURCE=' + lua_literal(g) + r'''
rawset(_G,'ModOptionsMenu',MENU)
local channel=require('hd2runtime/runtime/peer_channel');channel.reset_for_tests()
local sync=require('hd2runtime/runtime/custom_mp_sync');sync.reset_for_tests()
local VERSION=require('hd2runtime/domains/metadata').version
assert(loadstring(G_ADDON,'@'..G_RESOURCE))()
local conv=require('hd2runtime/runtime/stratagem_slot_conversion')
conv.validate_carrier=function(world,token,weapon,opts)
    return {ready=true,valid=false,candidate={id=1813634375,name=weapon,beaconCategory='support',eligible=false,
        codes={'not_owned'},reasons={'not owned'}},reasons={'not owned'},codes={'not_owned'}}
end
local ME,THEM='1111222233334444','5555666677778888'
W.players({{peer=ME,avatar=100},{peer=THEM}},ME)
W.lobby({members={ME,THEM},host=THEM})
W.lobby_values[THEM]=('hd2rt/1;%s;%s;%d;%s'):format(VERSION,custom.registry_hash(),1,'-,-,-,-')
tick(40)
ship({})
tick(120)
assert(count('custom multiplayer ENABLED')>=1,lines('CUSTOM MP'))
assert(count('AVAILABILITY (eat17g_clone): UNAVAILABLE: the lobby\'s carrier for it is EAT-700 Expendable Napalm, which '
    ..'this account does not own')==1,lines('AVAILABILITY'))
SCREEN.set('selecting',false);tick(2)
SCREEN.set('editedSlot',0);SCREEN.set('selecting',true);tick(6)
press('F7')
for _=1,4 do press('F7');tick(4)end
assert(count('F7 on eat17g_clone REFUSED (nothing written): UNAVAILABLE: the lobby\'s carrier for it is EAT-700')==1,
    lines('REFUSED'))
assert(count('SHIP: selection REFUSED')==1,lines('SHIP: selection'))
assert(count('TOKEN_NOT_OWNED')==0 and count('stratagem selector REFUSED')==0,lines('REFUSED'))
assert(require('hd2runtime/runtime/stratagem_selector').virtual_slots()==nil,'nothing selected')
return 'ok'
''')


class SelectorGuardTests(unittest.TestCase):
    def test_a_direct_write_of_an_unowned_carrier_or_token_is_still_refused(self):
        from test_stratagem_selector import SELECT
        self.assertEqual(run(WORLD + SELECT + r'''
SCREEN=W.loadout_screen({entries={{type=22}},editedSlot=1})
tick(2)
-- The carrier (the 120mm) not owned by this account: refused, nothing written.
W.catalogue({[PRECISION_ID]=2,[BIG_ID]=0})
tick(2)
local before=#W.runtime.writes
local refused=settle_job(selector.select('orbital_gas_barrage',nil,{carrier={id=BIG_ID,name='Orbital 120mm HE Barrage'}}))
assert(refused.status=='refused'and refused.code=='TOKEN_NOT_OWNED'and#W.runtime.writes==before,tostring(refused.code))
-- The token itself not owned: refused too.
W.catalogue({[PRECISION_ID]=0,[BIG_ID]=2})
before=#W.runtime.writes
refused=settle_job(selector.select('orbital_gas_barrage'))
assert(refused.status=='refused'and refused.code=='TOKEN_NOT_OWNED'and#W.runtime.writes==before,tostring(refused.code))
return 'ok'
'''), b'ok')


if __name__ == '__main__':
    unittest.main()
