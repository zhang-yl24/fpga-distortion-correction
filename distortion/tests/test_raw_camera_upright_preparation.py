"""Negative preflight tests: never launch EDA or touch the connected board."""
import json
from pathlib import Path
import sys
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_raw_camera_upright as prep
import run_raw_camera_upright_diagnostic as runner


@unittest.skipUnless(Path('D:/pango/PDS_2023.2/bin/pds_shell.exe').is_file(), 'local PDS fixture required; never executed')
class RawPreflightTests(unittest.TestCase):
    def setUp(self):
        self.work = prep.WORK / ('test-' + uuid4().hex[:8])
        prep.prepare(self.work)
        self.plan = self.work / 'plan.json'

    def test_valid_plan_is_raw_only_and_no_hardware(self):
        context = runner.validate_plan(self.plan)
        self.assertFalse(context['Plan']['HardwareAccessed'])
        self.assertFalse(context['Plan']['BitstreamRequested'])
        self.assertEqual(context['Plan']['RawCaptureContract']['image_size'], [640, 480])
        text = (self.work / 'timing.tcl').read_text()
        self.assertNotIn('gen_bit_stream', text)
        self.assertEqual(text.count('add_design '), 17)

    def test_rejects_command_injection_into_plan(self):
        record = json.loads(self.plan.read_text())
        record['CommandToRunSeparately'] += ['-command', 'gen_bit_stream']
        self.plan.write_text(json.dumps(record), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'plan differs'):
            runner.validate_plan(self.plan)

    def test_rejects_silent_pin_constraint_change(self):
        fdc = self.work / 'compiled/board/raw-camera-upright-diagnostic.fdc'
        fdc.write_bytes(fdc.read_bytes().replace(b'{C24}', b'{C22}'))
        with self.assertRaisesRegex(ValueError, 'compiled bytes differ'):
            runner.validate_plan(self.plan)

    def test_rejects_changed_compiled_sensor_table(self):
        table = self.work / 'compiled/board/ov5640_cadence_trial_commands.vh'
        table.write_bytes(table.read_bytes() + b'\n// unexpected change\n')
        with self.assertRaisesRegex(ValueError, 'compiled bytes differ'):
            runner.validate_plan(self.plan)

    def test_rejects_old_build_commands(self):
        tcl = self.work / 'timing.tcl'
        tcl.write_bytes(tcl.read_bytes() + b'gen_bit_stream\n')
        with self.assertRaisesRegex(ValueError, 'Tcl recipe drift'):
            runner.validate_plan(self.plan)

    def test_rejects_reusing_executed_directory(self):
        (self.work / 'execution-start.json').write_text('{}', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'fresh prepared'):
            runner.validate_plan(self.plan)

    def test_rejects_extended_deadline(self):
        with self.assertRaisesRegex(ValueError, 'deadline exceeds'):
            runner.validate_plan(self.plan, 1801)

    def test_rejects_long_windows_paths_before_writing(self):
        path = prep.WORK / ('too-long-' + uuid4().hex)
        with self.assertRaisesRegex(ValueError, 'Windows native path limit'):
            prep.prepare(path)
        self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
