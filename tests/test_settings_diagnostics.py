"""Bounded F10 breadcrumbs must distinguish layout from successful engine submission."""
import unittest

from support import run
from test_ui_overlay import HARNESS


SETTINGS = r'''
local settings=require('hd2runtime/runtime/runtime_settings')
settings.reset_for_tests()
settings.hooks.store=function()return nil end
settings.hooks.block=function()return true end
settings.hooks.sound=function()return true end
'''


class SettingsDiagnosticsTests(unittest.TestCase):
    def test_view_transitions_log_once_and_closed_menu_is_quiet(self):
        self.assertEqual(run(HARNESS + SETTINGS + r'''
settings.open();frames(1)
assert(count('settings layout begin: settings')==1)
assert(count('F10 settings GUI sync begin:')==1)
assert(count('F10 settings GUI sync complete:')==1)
frames(60)
assert(count('settings layout begin: settings')==1 and count('F10 settings GUI sync begin:')==1)
settings.select_tab('performance');frames(1)
assert(count('settings tab requested: settings -> performance')==1)
assert(count('F10 performance/runtime GUI sync complete:')==1)
frames(60)
assert(count('F10 performance/runtime GUI sync begin:')==1,'graph updates must not spam logs')
settings.close();frames(1)
local n=#logged;frames(60);assert(#logged==n,'closed menu must not log')
settings.open('settings');frames(1)
assert(count('F10 settings GUI sync complete:')==2,'reopening must trace the new GUI')
return 'ok'
'''), b'ok')

    def test_failed_engine_submission_never_reports_success(self):
        self.assertEqual(run(HARNESS + SETTINGS + r'''
local rect=stingray.Gui.rect
stingray.Gui.rect=function()error('simulated engine call failure')end
settings.open();frames(1)
assert(count('F10 settings GUI sync begin:')==1)
assert(count('F10 settings GUI sync complete:')==0)
assert(count('engine GUI call failed:')==1)
stingray.Gui.rect=rect;frames(1)
assert(count('F10 settings GUI sync complete:')==1,'retry must report successful submission')
return 'ok'
'''), b'ok')


if __name__ == '__main__':
    unittest.main()
