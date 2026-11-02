"""Adversarial CPU tests of 720p build preparation; no EDA/hardware is run.

Every mutated file is a private copy under a verified workspace scratch root.
The only executable in the fixtures is an inert file; Popen is always mocked.
"""
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_camera720_output as prep
import run_camera720_output_diagnostic as runner
import run_camera720_control_sim as control


class Camera720PreparationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live_project = prep.PROJECT
        cls.live_work = prep.WORK
        cls.live_work.mkdir(parents=True, exist_ok=True)
        # Keep the private tree short enough for Windows' legacy MAX_PATH:
        # inherited DDR IP contains filenames over 100 characters below root.
        cls.temporary = tempfile.TemporaryDirectory(prefix='_t', dir=cls.live_work)
        cls.scratch = Path(cls.temporary.name).resolve()
        if not cls.scratch.is_relative_to(cls.live_work.resolve()):
            raise AssertionError('test workspace escaped allowed root')
        # The inventory recipe needs a real file identity, not an installed EDA.
        # Create the inert private tool before the first recipe call on every OS.
        cls.pds = cls.scratch/'fake-tool/pds_shell.exe'
        cls.pds.parent.mkdir(parents=True)
        cls.pds.write_bytes(b'INERT CPU TEST FILE; NEVER EXECUTE\n')
        # Reconstruct a fresh recipe rather than trusting build-a or editing it.
        cls.recipe_plan, _, _ = prep.recipe(
            cls.live_work/'_audit_inventory_only', str(cls.pds))
        cls.baseline_roles = prep.previous.validate_sources()
        cls.project = cls.scratch
        for name in cls.recipe_plan['InputSHA256']:
            destination = cls.project/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cls.live_project/name, destination)
        cls.originals = {name: (cls.project/name).read_bytes()
                         for name in cls.recipe_plan['InputSHA256']}
        cls.counter = 0

    @classmethod
    def tearDownClass(cls):
        resolved = cls.scratch.resolve()
        if resolved != cls.scratch or not resolved.is_relative_to(cls.live_work.resolve()):
            raise AssertionError('refuse cleanup outside verified scratch root')
        cls.temporary.cleanup()

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, payload in self.originals.items():
            (self.project/name).write_bytes(payload)
        for module, name, value in (
            (prep, 'PROJECT', self.project),
            (prep, 'WORK', self.project/'w'),
            (prep, 'SELF', self.project/'tools/prepare_camera720_output.py'),
            (runner, 'SELF', self.project/'tools/run_camera720_output_diagnostic.py'),
        ):
            self.stack.enter_context(mock.patch.object(module, name, value))
        # Verify the immutable VGA predecessor once, then use that snapshot as
        # this unit's dependency. New 720p sources and every compiled byte are
        # still re-read and hashed by the real validators on every test case.
        self.stack.enter_context(mock.patch.object(
            prep.previous, 'validate_sources', return_value=copy.deepcopy(self.baseline_roles)))
        type(self).counter += 1
        self.work = prep.WORK/f'case-{self.counter}'
        self.plan = prep.prepare(self.work, str(self.pds), 60)
        self.path = self.work/'plan.json'
        self.popen = self.stack.enter_context(mock.patch.object(runner.subprocess, 'Popen'))
        # Only this module sees a Windows executor while Popen is mocked.
        # Do not mutate os.name globally: pathlib must retain host semantics.
        self.stack.enter_context(mock.patch.object(
            runner, 'os', SimpleNamespace(name='nt')))

    def save_plan(self, plan):
        self.path.write_text(json.dumps(plan, indent=2)+'\n', encoding='utf-8', newline='\n')

    def expect_rejected(self, pattern):
        with self.assertRaisesRegex(ValueError, pattern):
            runner.validate_plan(self.path)
        self.popen.assert_not_called()

    def test_valid_plan_is_read_only_and_exact_compile_roles(self):
        context = runner.validate_plan(self.path)
        self.popen.assert_not_called()
        self.assertFalse(context['Plan']['HardwareReleaseAllowed'])
        self.assertFalse(context['Plan']['OpticalCorrectionAccepted'])
        self.assertEqual(len(self.plan['ExplicitDesigns']), 31)
        self.assertEqual(sum(Path(p).suffix == '.idf' for p in self.plan['ExplicitDesigns']), 1)
        self.assertEqual(len(set(self.plan['ExplicitDesigns'])), 31)
        self.assertFalse(any(Path(p).suffix in ('.vh', '.vp') for p in self.plan['ExplicitDesigns']))
        expanded = {(self.work/'compiled'/p).as_posix() for p in self.plan['IDFExpandedSourcesNotAdded']}
        self.assertFalse(expanded.intersection(self.plan['ExplicitDesigns']))
        inputs = self.plan['InputSHA256']
        self.assertTrue(all(p['Source'] in inputs for p in self.plan['CompiledInputs']))

    def test_command_cannot_be_replaced_with_hardware_action(self):
        altered = copy.deepcopy(self.plan)
        altered['CommandToRunSeparately'] = [str(self.pds), '-file', 'program.tcl']
        self.save_plan(altered)
        self.expect_rejected('differs from current deterministic recipe')

    def test_scope_cannot_claim_hardware_or_optical_acceptance(self):
        for field in ('HardwareReleaseAllowed', 'OpticalCorrectionAccepted', 'TimingAccepted', 'BitstreamRequested'):
            with self.subTest(field=field):
                altered = copy.deepcopy(self.plan)
                altered[field] = True
                self.save_plan(altered)
                self.expect_rejected('differs from current deterministic recipe')

    def test_input_hash_omission_is_rejected(self):
        altered = copy.deepcopy(self.plan)
        del altered['InputSHA256']['rtl/experimental/dvp_mode_admission_monitor.v']
        self.save_plan(altered)
        self.expect_rejected('differs from current deterministic recipe')

    def test_expanded_idf_body_cannot_be_added_twice(self):
        altered = copy.deepcopy(self.plan)
        altered['ExplicitDesigns'].append((self.work/'compiled'/altered['IDFExpandedSourcesNotAdded'][0]).as_posix())
        self.save_plan(altered)
        self.expect_rejected('differs from current deterministic recipe')

    def test_manifest_drift_is_rejected(self):
        manifest = self.project/prep.MANIFEST
        data = json.loads(manifest.read_text(encoding='utf-8'))
        data['Geometry'] = [640, 480]
        manifest.write_text(json.dumps(data), encoding='utf-8')
        self.expect_rejected('manifest differs')

    def test_sensor_frontend_source_drift_is_rejected(self):
        source = self.project/'rtl/experimental/ov5640_current720_frontend.v'
        source.write_bytes(source.read_bytes()+b'\n// changed after freeze\n')
        self.expect_rejected('manifest differs')

    def test_compiled_include_rewrite_cannot_escape(self):
        candidate = self.work/'compiled'/prep.TOP
        original = candidate.read_bytes()
        self.assertIn(b'camera720-identity.vh', original)
        candidate.write_bytes(original.replace(b'camera720-identity.vh', b'other-camera.vh'))
        self.expect_rejected('compiled bytes differ')

    def test_extra_compiled_file_is_rejected(self):
        (self.work/'compiled/extra.v').write_text('module extra; endmodule\n', encoding='ascii')
        self.expect_rejected('compiled tree inventory differs')

    def test_missing_compiled_file_is_rejected(self):
        (self.work/'compiled'/prep.HEADER).unlink()
        self.expect_rejected('compiled tree inventory differs')

    def test_tcl_cannot_append_bitstream_or_shell_command(self):
        tcl = self.work/'timing.tcl'
        tcl.write_bytes(tcl.read_bytes()+b'generate_bitstream\nexec unexpected-tool\n')
        self.expect_rejected('Tcl recipe drift')

    def test_nonfresh_work_is_rejected(self):
        (self.work/'execution-result.json').write_text('{}', encoding='ascii')
        self.expect_rejected('fresh prepared')

    def test_tool_drift_is_rejected(self):
        original = self.pds.read_bytes()
        try:
            self.pds.write_bytes(original+b'changed')
            self.expect_rejected('differs from current deterministic recipe')
        finally:
            self.pds.write_bytes(original)

    def test_deadline_cannot_exceed_prepared_limit_or_be_boolean(self):
        for maximum in (61, True, 0, -1):
            with self.subTest(maximum=maximum):
                with self.assertRaisesRegex(ValueError, 'deadline exceeds prepared limit'):
                    runner.validate_plan(self.path, maximum)
        self.popen.assert_not_called()

    def test_directory_and_tcl_path_escape_rejected(self):
        for work in (prep.WORK/'nested/stage', prep.WORK.parent/'outside', prep.WORK/'bad;name'):
            with self.subTest(work=work):
                with self.assertRaisesRegex(ValueError, 'canonical direct'):
                    prep.work_path(work)
        with self.assertRaisesRegex(ValueError, 'escaped project'):
            prep.literal(self.scratch.parent/'outside-project.tcl')

    def test_successful_mocked_native_run_does_not_authorize_hardware(self):
        expected = [(stage, action) for stage in self.plan['ExpectedActualStages']
                    for action in ('started', 'done')]
        transcript = '\n'.join(f'Process "{stage}" {action}.' for stage, action in expected)+'\n'
        fake = mock.Mock(pid=123456)
        fake.poll.return_value = 0

        def launch(command, **kwargs):
            self.assertEqual(command, self.plan['CommandToRunSeparately'])
            self.assertFalse(kwargs['shell'])
            kwargs['stdout'].write(transcript.encode())
            kwargs['stdout'].flush()
            (self.work/'place_route').mkdir()
            (self.work/'pre-sta-final.adf').write_bytes(b'SYNTHETIC DB')
            (self.work/'place_route'/(prep.TARGET+'_pnr.adf')).write_bytes(b'SYNTHETIC DB')
            return fake

        self.popen.side_effect = launch
        result = runner.execute(self.path)
        self.assertTrue(result['ExecutionCompletedWithoutError'])
        self.assertFalse(result['TimingAccepted'])
        self.assertFalse(result['HardwareReleaseAllowed'])
        self.assertFalse(result['HardwareAccessed'])
        self.assertFalse(result['BitstreamRequested'])
        self.popen.assert_called_once()

    def test_real_nonwindows_execution_guard_is_retained(self):
        with mock.patch.object(runner, 'os', SimpleNamespace(name='posix')):
            with self.assertRaisesRegex(ValueError, 'requires Windows'):
                runner.execute(self.path)
        self.popen.assert_not_called()

    def test_timeout_stops_only_owned_process(self):
        fake = mock.Mock(pid=123456)
        state = {'code': None}
        fake.poll.side_effect = lambda: state['code']
        self.popen.return_value = fake

        def stop(process, work, reason):
            self.assertIs(process, fake)
            self.assertEqual(work, self.work)
            self.assertEqual(reason, 'timeout')
            state['code'] = -1
            return {'Complete': True, 'OwnedPID': fake.pid, 'Required': True}

        with mock.patch.object(runner.cleanup, 'stop_owned_tree', side_effect=stop) as owned_stop:
            with mock.patch.object(runner.time, 'monotonic', side_effect=[0, 61, 62]):
                result = runner.execute(self.path)
        owned_stop.assert_called_once()
        self.assertTrue(result['TimedOut'])
        self.assertFalse(result['ExecutionCompletedWithoutError'])
        self.assertFalse(result['HardwareReleaseAllowed'])

    def test_control_stub_interfaces_match_six_actual_modules(self):
        bindings = control.header_bindings()
        self.assertEqual(set(bindings), {'bringup_pll', 'hdmi_tx_init', 'ddr3_test',
                         'ov5640_current720_frontend', 'raw_camera_input_delay', 'camera_vga_video_system'})
        self.assertTrue(all(not entry['ProductionBodyCompiled'] for entry in bindings.values()))

    def test_header_inventory_matches_current_closure(self):
        roles = prep.roles()
        self.assertEqual(set(roles['Headers']),
                         {name for name in roles['Sources'] if Path(name).suffix == '.vh'})
        self.assertIn(prep.HEADER, roles['Headers'])
        self.assertNotIn(prep.previous.HEADER, roles['Headers'])
        self.assertNotIn('board/board1080-synthetic.vh', roles['Headers'])


if __name__ == '__main__':
    unittest.main()
