import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import explosion_arc_fields
import validate_explosion_arcs_snapshot

class ExplosionArcTests(unittest.TestCase):
    def test_typed_links_and_distinct_damage(self):
        for name,item in explosion_arc_fields.load().items():
            self.assertEqual(explosion_arc_fields.value(item['explosion'],120,'u32'),item['arc']['recordType'])
            self.assertEqual(explosion_arc_fields.value(item['arc'],36,'u32'),item['damage']['recordType'])
            self.assertNotEqual(explosion_arc_fields.value(item['explosion'],4,'u32'),item['damage']['recordType'])

    def test_changed_support_writes_restore_and_reject_broken_links(self):
        result=validate_explosion_arcs_snapshot.validate()
        self.assertEqual(result['changedWrites'],22)  # includes the two later empty status-slot strengths
        self.assertEqual([x['link']for x in result['rejections']],['projectile','explosion','arc'])

    def test_grenade_arc_has_all_eight_controls_and_four_status_slots(self):
        catalog=json.loads((ROOT/'sdk/ThrowableAuthoringCapabilities.json').read_text())
        grenade=next(e for e in catalog['throwables'] if e['name']=='G-31 Arc')
        arc=next(t for t in grenade['targets'] if t['path']=='arc')
        ids={f['semanticFieldId']for f in arc['fields']}
        self.assertEqual(len([i for i in ids if i.startswith('arc.')]),8)
        for slot in range(1,5):
            self.assertIn(f'damage.status_{slot}_type',ids)
            self.assertIn(f'damage.status_{slot}_strength',ids)
        self.assertFalse(any('arc child' in b['what'] for b in grenade['blocked']))

if __name__=='__main__':unittest.main()
