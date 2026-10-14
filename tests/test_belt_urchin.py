import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import validate_belt_urchin_snapshot
class BeltUrchinTests(unittest.TestCase):
    def test_swaps_inverse_host_shape_and_payload_array_guards(self):
        r=validate_belt_urchin_snapshot.validate()
        self.assertEqual(r['changedWrites'],3)
        self.assertEqual(r['rejections'],5)
        self.assertEqual(r['rollbackFailures'],2)
        self.assertEqual(r['ownedTransitions'],2)
if __name__=='__main__':unittest.main()
