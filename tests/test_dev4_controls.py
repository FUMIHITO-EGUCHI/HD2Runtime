import unittest
from support import ROOT
import validate_dev4_controls_snapshot
class Dev4ControlsTests(unittest.TestCase):
 def test_changed_writes_restore_and_acknowledgements(self):
  result=validate_dev4_controls_snapshot.validate()
  self.assertEqual(result['roundTrips'],18)
  self.assertEqual(result['rejections'],19)
