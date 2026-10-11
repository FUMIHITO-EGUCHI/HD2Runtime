"""0.31.2: hd2.attack_output(id):stats() and :owner_projectile(): the read-only vanilla stats of the projectile an
output fires (domains/projectile_stats.lua, generated from research/projectile-stats-F5FEE03DCFDB.json, itself checked
against research/projectile-components and the explosion catalogue research)."""
import json
import sys
import unittest
from pathlib import Path

from support import run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import generate_projectile_stats  # noqa: E402


class ProjectileStatsTests(unittest.TestCase):
    def test_generated_domain_is_current(self):
        self.assertEqual(generate_projectile_stats.generate(check=True), [])

    def test_research_agrees_with_the_component_catalogue(self):
        research = json.loads((ROOT / 'research/projectile-stats-F5FEE03DCFDB.json').read_text(encoding='utf-8'))
        components = {r['type']: r['components'] for r in json.loads(
            (ROOT / 'research/projectile-components-F5FEE03DCFDB.json').read_text(encoding='utf-8'))['rows']}
        self.assertEqual((research['writes'], research['summary']['types']), (0, 350))
        for key, row in research['rows'].items():
            ballistics = components[int(key)]['ballistics']['values']
            self.assertAlmostEqual(row['flight']['velocity'], ballistics['speed'], places=3)
            self.assertAlmostEqual(row['flight']['mass'], ballistics['mass'], places=3)
            impact = components[int(key)]['impact_explosion']['values']['impact_explosion']
            self.assertEqual((row['impact'] or {}).get('type', 0), impact)

    def test_api(self):
        self.assertEqual(run(r'''
local hd2=require('hd2runtime/api/hd2')
-- The LAS-99 Quasar's bolt: 1300 m/s, 6 s, 2000 direct damage, its impact explosion.
local s=assert(hd2.attack_output('LAS-99 Quasar Cannon'):stats())
assert(s.output=='output/v1/projectile/las-99-quasar-cannon'and s.owner.name=='LAS-99 Quasar Cannon'and s.values=='vanilla')
assert(s.flight.velocity==1300 and s.flight.lifetime==6 and s.flight.mass==12 and s.flight.pellet_count==1)
assert(s.direct_damage.standard_damage==2000 and s.direct_damage.ap_direct==6 and s.direct_damage.ap_extreme==3)
assert(s.impact.name=='support_weapon/las99_quasar_cannon/impact'and s.impact.outer_radius==3 and s.expiry==nil)
assert(s.impact.damage.standard_damage==150)
-- The S-11 Speargun: an expiry explosion and no impact.
local spear=assert(hd2.attack_output('S-11 Speargun'):stats())
assert(spear.impact==nil and spear.expiry.name=='support_weapon/s11_speargun/expiry')
-- Every projectile output has stats; a copy (mutating it changes nothing).
local catalog=require('hd2runtime/domains/attack_outputs')
local n=0
for id,o in pairs(catalog.outputs)do
 if o.family=='projectile'and type(o.currentDefault)=='number'then assert(hd2.attack_output(id):stats(),id);n=n+1 end
end
assert(n>=100,n)
s.flight.velocity=1
assert(hd2.attack_output('LAS-99 Quasar Cannon'):stats().flight.velocity==1300)
-- Other families: refused with a code.
local none,code=hd2.attack_output('LAS-98 Laser Cannon'):stats()
assert(none==nil and code=='NOT_A_PROJECTILE')
-- The owner's own projectile handle.
local h=assert(hd2.attack_output('EAT-17 Expendable Anti-Tank'):owner_projectile())
assert(h.resource=='support_weapon'and h.path=='projectile_reference'and h.weapon=='EAT-17 Expendable Anti-Tank')
local p=assert(hd2.attack_output('SMG-32 Reprimand'):owner_projectile())
assert(p.resource=='player_weapon'and p.path=='projectile_reference')
-- A projectile output that is not established (the Punisher fires through its rounds feed): no stats, with why.
none,code=hd2.attack_output('output/v1/projectile/sg-8-punisher'):stats()
assert(none==nil and code=='NO_STATS',tostring(code))
none,code=hd2.attack_output('Eagle 500kg Bomb'):owner_projectile()
assert(none==nil and code=='NO_OWNER_PROJECTILE',tostring(code))
return 'ok'
'''), b'ok')


if __name__ == '__main__':
    unittest.main()
