"""Guard the native-delay candidate against budget, wiring or source changes."""
from pathlib import Path
import sys
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_raw_camera_delay as prep
import prepare_raw_camera_reset as parent
import run_raw_camera_delay_diagnostic as runner


class DelaySourceTests(unittest.TestCase):
    def setUp(self):
        self.base = (prep.PROJECT / prep.BASE_TOP).read_text()
        self.top = (prep.PROJECT / prep.TOP).read_text()
        self.wrapper = (prep.PROJECT / prep.DELAY_MODULE).read_text()

    def test_capture_and_preview_both_use_same_delayed_bus(self):
        prep.validate_top_changes(self.base, self.top)
        self.assertEqual(self.top.count('.data(capture_data)'), 2)

    def test_one_bypassed_consumer_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'two-consumer rewiring'):
            prep.validate_top_changes(self.base, self.top.replace('.data(capture_data)', '.data(cam_data)', 1))

    def test_clock_rewiring_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'two-consumer rewiring'):
            prep.validate_top_changes(self.base, self.top.replace('.cam_clk(cam_pclk)', '.cam_clk(core_clk)', 1))

    def test_wrong_delay_or_missing_bit_is_rejected(self):
        for changed in (self.wrapper.replace('1500ps', 'NODELAY'), self.wrapper.replace('bit_index<8', 'bit_index<7')):
            with self.subTest(changed=changed[-40:]):
                with self.assertRaisesRegex(ValueError, 'eight direct'):
                    prep.validate_delay_module(changed)

    def test_internal_inversion_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'eight direct'):
            prep.validate_delay_module(self.wrapper.replace('.DI(buffered_data)', '.DI(~buffered_data)'))

    def test_external_timing_and_pin_constraints_are_byte_identical(self):
        self.assertEqual(prep.constraint_bytes(), parent.constraint_bytes())


@unittest.skipUnless(Path('D:/pango/PDS_2023.2/bin/pds_shell.exe').is_file(), 'local PDS fixture; never executed')
class DelayPlanTests(unittest.TestCase):
    def setUp(self):
        self.work = prep.WORK / ('td' + uuid4().hex[:6])
        prep.prepare(self.work)

    def test_native_plan_binds_all_sources_and_installed_primitive_definitions(self):
        context = runner.validate_plan(self.work / 'plan.json')
        plan = context['Plan']
        self.assertEqual(len(plan['ExplicitDesigns']), 19)
        self.assertEqual(len(plan['CompiledInputs']), 99)  # 98 sources + RCF
        primitive = plan['TechnologyPrimitiveSource']
        self.assertEqual(context['Watched'][Path(primitive['Path'])], primitive['SHA256'])
        self.assertEqual(plan['InputDelay']['Bits'], list(range(8)))
        self.assertFalse(plan['InputDelay']['SamplingEdgeChanged'])
        self.assertFalse(plan['InputDelay']['ExternalInputBudgetChanged'])
        self.assertFalse(plan['HardwareAccessed'])
        self.assertFalse(plan['BitstreamRequested'])
        self.assertNotIn('gen_bit_stream', (self.work / 'timing.tcl').read_text())

    def test_changed_compiled_primitive_setting_is_rejected(self):
        path = self.work / 'compiled' / prep.DELAY_MODULE
        path.write_bytes(path.read_bytes().replace(b'1500ps', b'1000ps'))
        with self.assertRaisesRegex(ValueError, 'compiled bytes differ'):
            runner.validate_plan(self.work / 'plan.json')


if __name__ == '__main__':
    unittest.main()
