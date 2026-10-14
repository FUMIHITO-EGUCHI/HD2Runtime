import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import validate_wasp_projectiles_snapshot
class WaspProjectileTests(unittest.TestCase):
    def test_two_modes_apply_inverse_and_reject_changed_missile_hosts(self):
        result=validate_wasp_projectiles_snapshot.validate()
        self.assertEqual(result['changedWrites'],4)
        self.assertEqual(result['rejections'],24)
if __name__=='__main__':unittest.main()
