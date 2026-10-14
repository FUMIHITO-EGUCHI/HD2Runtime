import unittest
from support import ROOT
import json
import validate_throwable_status_slots


class ThrowableStatusSlotsTests(unittest.TestCase):
    def test_four_statuses_public_transactions_plans_and_guards(self):
        r=validate_throwable_status_slots.validate()
        self.assertEqual(r['status'],'VALIDATED')
        self.assertEqual(len(r['scenarios']),7)
        self.assertEqual(r['rejections'].count('STATUS_SLOT_GAP'),2)
        self.assertIn('live status table no longer names',r['rejections'])

    def test_all_supported_targets_publish_four_type_strength_pairs(self):
        catalog=json.loads((ROOT/'sdk/ThrowableAuthoringCapabilities.json').read_text())
        targets=0
        for item in catalog['throwables']:
            for target in item['targets']:
                fields=[f for f in target['fields'] if f.get('statusSlot') and f['editable']]
                if not fields: continue
                self.assertEqual(len(fields),8,item['name']+'/'+target['path'])
                self.assertEqual({f['statusSlot'] for f in fields},{1,2,3,4})
                self.assertTrue(all(f['scope']['shared'] for f in fields))
                targets+=1
        self.assertEqual(targets,25)
