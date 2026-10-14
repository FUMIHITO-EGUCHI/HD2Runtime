import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import generate_weapon_authoring
import validate_reload_heat_snapshot


class ReloadHeatTests(unittest.TestCase):
    def test_generated_descriptors_current(self):
        self.assertEqual(generate_weapon_authoring.generate(check=True),[])

    def test_changed_writes_and_broken_heat_chains(self):
        result=validate_reload_heat_snapshot.validate()
        self.assertEqual(result['firearms'],77)
        self.assertEqual(result['noReloadAbility'],1)
        self.assertEqual(result['changedWrites'],162)
        self.assertEqual(len(result['rejections']),2)


if __name__=='__main__':unittest.main()
