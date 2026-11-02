"""CPU-only binding/query/parser tests; fake ADF fixtures never enter PDS."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_raw_inspect as inspect


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        path.write_bytes(value)
    elif isinstance(value, str):
        path.write_text(value, encoding='utf-8', newline='\n')
    else:
        path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8', newline='\n')


class InspectionBindingTests(unittest.TestCase):
    def setUp(self):
        self.scratches = []
        self.build = self.scratch('inspect-unit-build-')
        self.stage = self.scratch('inspect-unit-stage-')
        # prepare requires an absent stage. The canonical direct child path is
        # retained; cleanup checks it again before recursive removal.
        self.stage.rmdir()
        self.original = self.build/'source.v'
        self.compiled = self.build/'compiled/source.v'
        write(self.original, b'module fixture; endmodule\n')
        write(self.compiled, self.original.read_bytes())
        pds = self.build/'bin/pds_shell.exe'
        write(pds, b'NOT AN EXECUTABLE; CPU TEST ONLY')
        self.adf = self.build/'place_route'/(inspect.prep.TARGET+'_pnr.adf')
        write(self.adf, b'CPU TEST ADF FIXTURE; NEVER NATIVE INPUT')
        write(self.build/'pre-sta-final.adf', self.adf.read_bytes())
        self.adf_sha = inspect.sha(self.adf)
        self.tcl = ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
                    'pnr -optimize_multi_corner_timing -fix_hold_violation\n'
                    'if {[file exists '+inspect.prep.literal(self.adf)+']} {\n'
                    '    file copy '+inspect.prep.literal(self.adf)+' '+inspect.prep.literal(self.build/'pre-sta-final.adf')+'\n}\n'
                    'report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n').encode('ascii')
        write(self.build/'timing.tcl', self.tcl)
        self.library = pds.parent.parent/'arch/vendor/pango/logos2/common/lib/gtp_lib.v'
        write(self.library, b'CPU LIBRARY FIXTURE')
        self.library_proof = {'Path':str(self.library), 'SHA256':inspect.sha(self.library), 'NativeMappingVerified':False}
        library_patch = patch.object(inspect.prep, 'validate_primitive_library', return_value=self.library_proof)
        library_patch.start()
        self.addCleanup(library_patch.stop)
        self.expected = {
            'Schema': inspect.prep.SCHEMA, 'Target': inspect.prep.TARGET,
            'TechnologyPrimitiveSource': self.library_proof,
            'PDS': {'Executable': str(pds), 'ExecutableSHA256': inspect.sha(pds)},
            'MaximumSecondsForExternalExecutor': 300,
            'InputSHA256': {self.original.relative_to(inspect.prep.PROJECT).as_posix(): inspect.sha(self.original)},
            'ExpectedActualStages': ['Compile', 'Synthesize', 'Device Map', 'Place', 'Route', 'Route Optimize', 'Report Timing'],
            'CommandToRunSeparately': [str(pds), '-file', (self.build/'timing.tcl').as_posix()],
        }
        self.plan_path = self.build/'plan.json'
        write(self.plan_path, {**self.expected, 'PreparedUTC': 'fixture-time'})
        self.events = [[stage, event] for stage in self.expected['ExpectedActualStages'] for event in ('started', 'done')]
        write(self.build/'execution-stdout.log', ''.join(f'Process "{stage}" {event}.\n' for stage, event in self.events))
        write(self.build/'execution-stderr.log', '')
        self.result_path = self.build/'execution-result.json'
        self.result = {
            'Schema': 'camera720-current-raw-execution-v1', 'Target': inspect.prep.TARGET,
            'ExecutionCompletedWithoutError': True, 'NativeExitCode': 0, 'SourcesStable': True,
            'ActualStagesComplete': True, 'InputDrift': [], 'Diagnostics': [], 'TimedOut': False,
            'StoppedForUnexpectedStage': False, 'Cleanup': {'Complete': True},
            'Plan': str(self.plan_path), 'PlanSHA256': inspect.sha(self.plan_path), 'EDAExecuted': True,
            'Command': self.expected['CommandToRunSeparately'], 'ActualEvents': self.events,
            'HardwareAccessed': False, 'BitstreamRequested': False, 'TimingAccepted': False, 'HardwareReleaseAllowed': False,
            'ExecutorSHA256': inspect.sha(inspect.diagnostic.__file__),
            'DatabaseSnapshotAudit': {'UnchangedAcrossSTA': True,
                'Snapshot': str(self.build/'pre-sta-final.adf'), 'FinalRoutedDatabase': str(self.adf),
                'SnapshotSHA256': self.adf_sha, 'FinalRoutedDatabaseSHA256': self.adf_sha},
            'LogSHA256': {name: inspect.sha(self.build/name) for name in ('execution-stdout.log', 'execution-stderr.log')},
        }
        write(self.result_path, self.result)
        self.recipe_patch = patch.object(inspect.prep, 'recipe', return_value=(self.expected, {self.compiled: self.original.read_bytes()}, self.tcl))
        self.recipe_patch.start()
        self.addCleanup(self.recipe_patch.stop)
        self.body = self.build/'query.txt'
        write(self.body, inspect.monitor_query_template())

    def scratch(self, prefix):
        root = inspect.prep.WORK
        root.mkdir(parents=True, exist_ok=True)
        scratch = tempfile.TemporaryDirectory(prefix=prefix, dir=root)
        path = Path(scratch.name).resolve()
        self.assertEqual(path.parent, root.resolve())
        self.scratches.append(scratch)
        self.addCleanup(self.safe_cleanup, scratch)
        return path

    def safe_cleanup(self, scratch):
        path = Path(scratch.name).absolute()
        self.assertEqual(path, path.resolve())
        self.assertEqual(path.parent, inspect.prep.WORK.resolve())
        scratch.cleanup()

    def bind(self):
        return inspect.bind(self.plan_path, self.adf, self.adf_sha)

    def prepare(self):
        return inspect.prepare(self.plan_path, self.adf, self.adf_sha, self.stage, 'query', self.body, 120)

    def test_clean_binding_is_read_only(self):
        with patch.object(inspect.subprocess, 'Popen', side_effect=AssertionError('no native process permitted')):
            plan, watched = self.bind()
        self.assertEqual(plan['Target'], 'raw_camera_capture_cam2_current720')
        self.assertIn(self.adf, watched)
        self.assertIn(self.result_path, watched)

    def test_old_build_target_rejected(self):
        value = json.loads(self.plan_path.read_text())
        value['Target'] = 'camera_vga_calibrated_top'
        write(self.plan_path, value)
        with self.assertRaisesRegex(ValueError, 'build identity'):
            self.bind()

    def test_wrong_adf_or_snapshot_cannot_bind(self):
        write(self.build/'pre-sta-final.adf', b'different')
        with self.assertRaisesRegex(ValueError, 'snapshot proof'):
            self.bind()

    def test_stable_receipt_cannot_hide_compiled_drift(self):
        write(self.compiled, b'module altered; endmodule\n')
        with self.assertRaisesRegex(ValueError, 'compiled bytes'):
            self.bind()

    def test_stable_receipt_cannot_hide_actual_stage_order(self):
        write(self.build/'execution-stdout.log', 'Process "Generate Bitstream" started.\n')
        self.result['LogSHA256']['execution-stdout.log'] = inspect.sha(self.build/'execution-stdout.log')
        write(self.result_path, self.result)
        with self.assertRaisesRegex(ValueError, 'exact native stages'):
            self.bind()

    def test_build_execution_command_and_flags_are_checked(self):
        for name, value in (('HardwareAccessed', True), ('EDAExecuted', False), ('Command', ['program'])):
            with self.subTest(name=name):
                altered = copy.deepcopy(self.result)
                altered[name] = value
                write(self.result_path, altered)
                with self.assertRaises(ValueError):
                    self.bind()
        write(self.result_path, self.result)

    def test_query_dummy_and_tcl_are_exact_lf(self):
        stage = self.prepare()
        value, _ = inspect.validate_prepared(stage)
        self.assertEqual(value['ExpectedActualStages'], [])
        self.assertNotIn(b'\r', (self.stage/'dummy.v').read_bytes())
        self.assertNotIn(b'\r', (self.stage/'stage.tcl').read_bytes())
        self.assertFalse(value['TimingAccepted'])
        self.assertFalse(value['OpticalCorrectionAccepted'])

    def test_prepared_tcl_cannot_add_mutation(self):
        stage = self.prepare()
        with (self.stage/'stage.tcl').open('ab') as stream:
            stream.write(b'gen_bitstream\n')
        with self.assertRaisesRegex(ValueError, 'artifact drift'):
            inspect.validate_prepared(stage)

    def test_prepared_directory_must_be_fresh(self):
        stage = self.prepare()
        write(self.stage/'unexpected.txt', 'extra')
        with self.assertRaisesRegex(ValueError, 'reused or contaminated'):
            inspect.validate_prepared(stage)

    def test_query_grammar_excludes_mutations_and_tcl_injection(self):
        for body in ('gen_bitstream\n', 'exec {programmer.exe}\n', 'source {old.tcl}\n',
                     'get_pins -hierarchical -regexp {.*}; exec {bad}\n',
                     'puts {a\\}\nexec {bad}\n', 'set_false_path -from {a} -to {b}\n',
                     'puts {'+inspect.MARKER+'}\n'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                inspect.query_commands(body)
        self.assertTrue(inspect.query_commands(inspect.monitor_query_template()))

    def test_export_selects_exact_input_db_and_real_context(self):
        text = inspect.render('export', self.tcl.decode(), self.build, self.stage)
        self.assertIn('gen_netlist -force_to_run -input_db_file {'+self.stage.as_posix()+'/input.adf}', text)
        self.assertIn('report_timing -force_to_run -input_db_file', text)
        self.assertNotIn('file copy', text)
        self.assertNotIn('gen_bitstream', text)

    def finished_query(self):
        stage_path = self.prepare()
        stage = json.loads(stage_path.read_text())
        write(self.stage/'stdout.log', inspect.MARKER+'\n')
        write(self.stage/'stderr.log', '')
        artifacts = {p.relative_to(self.stage).as_posix(): inspect.sha(p)
                     for p in self.stage.rglob('*') if p.is_file()
                     and p.suffix in ('.tcl', '.log', '.rtr', '.v', '.gnr', '.txt', '.fdc')}
        value = {**stage, 'StagePlanSHA256': inspect.sha(stage_path), 'EDAExecuted': True,
                 'ExecutionPassed': True, 'ExitCode': 0, 'TimedOut': False,
                 'StoppedForUnexpectedStage': False, 'InputDrift': [], 'Diagnostics': [],
                 'CompletionMarker': True, 'InputADFUnchanged': True, 'Cleanup': {'Complete': True},
                 'ActualEvents': [], 'Artifacts': artifacts}
        path = self.stage/'result.json'
        write(path, value)
        return path

    def test_finished_receipt_rebinds_every_native_artifact(self):
        path = self.finished_query()
        value, watched = inspect.bind_receipt(path)
        self.assertTrue(value['ExecutionPassed'])
        self.assertIn(self.stage/'dummy.v', watched)
        write(self.stage/'dummy.v', 'mutated')
        with self.assertRaisesRegex(ValueError, 'dummy context drift'):
            inspect.bind_receipt(path)

    def test_finished_receipt_cannot_hide_extra_report(self):
        path = self.finished_query()
        write(self.stage/'unbound.rtr', 'unbound report')
        with self.assertRaisesRegex(ValueError, 'artifact inventory'):
            inspect.bind_receipt(path)

    def test_finished_receipt_cannot_claim_timing_acceptance(self):
        path = self.finished_query()
        value = json.loads(path.read_text())
        value['TimingAccepted'] = True
        write(path, value)
        with self.assertRaises(ValueError):
            inspect.bind_receipt(path)

    def fake_native(self, log, exit_code):
        class Process:
            pid = 424242  # fixture identity, never passed to a real cleanup
            returncode = exit_code

            def poll(self):
                return self.returncode

            def wait(self, timeout):
                if self.returncode is None:
                    raise inspect.subprocess.TimeoutExpired('CPU fixture', timeout)
                return self.returncode

        process = Process()

        def start(*args, **kwargs):
            self.assertIs(kwargs['shell'], False)
            self.assertEqual(Path(kwargs['cwd']), self.stage)
            kwargs['stdout'].write(log.encode('ascii'))
            kwargs['stdout'].flush()
            return process

        def cleanup(actual, work, reason):
            self.assertIs(actual, process)
            self.assertEqual(work, self.stage)
            process.returncode = -1
            return {'Complete': True, 'OwnedPID': process.pid, 'FixtureOnly': True}

        return process, start, cleanup

    def test_mock_success_does_not_grant_timing_or_hardware_authority(self):
        stage = self.prepare()
        _, start, cleanup = self.fake_native(inspect.MARKER+'\n', 0)
        with patch.object(inspect.subprocess, 'Popen', side_effect=start), \
             patch.object(inspect.diagnostic.cleanup, 'stop_owned_tree', side_effect=cleanup) as stop:
            value = inspect.execute(stage)
        self.assertTrue(value['ExecutionPassed'])
        self.assertFalse(value['HardwareReleaseAllowed'])
        self.assertFalse(value['TimingAccepted'])
        stop.assert_not_called()

    def test_timeout_only_passes_the_owned_fixture_to_cleanup(self):
        stage = self.prepare()
        process, start, cleanup = self.fake_native('', None)
        with patch.object(inspect.subprocess, 'Popen', side_effect=start), \
             patch.object(inspect.time, 'monotonic', side_effect=[0, 121, 122]), \
             patch.object(inspect.diagnostic.cleanup, 'stop_owned_tree', side_effect=cleanup) as stop:
            value = inspect.execute(stage)
        self.assertTrue(value['TimedOut'])
        self.assertFalse(value['ExecutionPassed'])
        self.assertIs(stop.call_args[0][0], process)

    def test_unexpected_native_stage_stops_the_owned_fixture(self):
        stage = self.prepare()
        process, start, cleanup = self.fake_native('Process "Generate Bitstream" started.\n', None)
        with patch.object(inspect.subprocess, 'Popen', side_effect=start), \
             patch.object(inspect.time, 'monotonic', side_effect=[0, 1, 2]), \
             patch.object(inspect.diagnostic.cleanup, 'stop_owned_tree', side_effect=cleanup) as stop:
            value = inspect.execute(stage)
        self.assertTrue(value['StoppedForUnexpectedStage'])
        self.assertFalse(value['ExecutionPassed'])
        self.assertIs(stop.call_args[0][0], process)

    def test_export_exit_zero_without_placed_netlist_is_not_success(self):
        stage = inspect.prepare(self.plan_path, self.adf, self.adf_sha, self.stage, 'export', None, 120)
        log = ''.join(f'Process "{name}" {event}.\n' for name in ('Report Timing', 'Generate Netlist')
                      for event in ('started', 'done'))+inspect.MARKER+'\n'
        _, start, cleanup = self.fake_native(log, 0)
        with patch.object(inspect.subprocess, 'Popen', side_effect=start), \
             patch.object(inspect.diagnostic.cleanup, 'stop_owned_tree', side_effect=cleanup):
            value = inspect.execute(stage)
        self.assertFalse(value['NativeNetlistWithFFloc'])
        self.assertFalse(value['ExecutionPassed'])


    def test_transport_and_vga_native_receipts_rejected(self):
        for schema in ('camera720-output-diagnostic-execution-v1', 'raw-camera-delay-diagnostic-execution-v1'):
            with self.subTest(schema=schema):
                altered = {**self.result, 'Schema':schema}
                write(self.result_path, altered)
                with self.assertRaisesRegex(ValueError, 'receipt identity'):
                    self.bind()

    def test_critical_build_log_is_failure_even_if_receipt_claims_clean(self):
        path = self.build/'report_timing/nested/run.log'
        write(path, 'C:STA-3006 invalid endpoint\n')
        self.result['LogSHA256'][path.relative_to(self.build).as_posix()] = inspect.sha(path)
        write(self.result_path, self.result)
        with self.assertRaisesRegex(ValueError, 'critical/error'):
            self.bind()

    def test_unbound_build_log_is_rejected(self):
        write(self.build/'extra/run.log', 'W: harmless warning\n')
        with self.assertRaisesRegex(ValueError, 'log inventory'):
            self.bind()

    def test_finished_receipt_does_not_hide_bound_critical_diagnostic(self):
        path = self.finished_query()
        critical = self.stage/'report_path_timing/report_timing/run.log'
        write(critical, 'C:STA-3006 invalid endpoint\n')
        value = json.loads(path.read_text())
        value['Artifacts'][critical.relative_to(self.stage).as_posix()] = inspect.sha(critical)
        write(path, value)
        with self.assertRaisesRegex(ValueError, 'critical/error'):
            inspect.bind_receipt(path)

    def test_mock_exit_zero_critical_remains_failure(self):
        stage = self.prepare()
        _, start, cleanup = self.fake_native('C:STA-3006 invalid endpoint\n'+inspect.MARKER+'\n', 0)
        with patch.object(inspect.subprocess, 'Popen', side_effect=start), \
             patch.object(inspect.diagnostic.cleanup, 'stop_owned_tree', side_effect=cleanup):
            value = inspect.execute(stage)
        self.assertFalse(value['ExecutionPassed'])
        self.assertEqual(len(value['Diagnostics']), 1)

    def test_current_hierarchies_and_launch_qualified_query_supported(self):
        body = inspect.monitor_query_template()
        self.assertIn('camera/monitor/', body)
        self.assertIn('camera/initializer/bus/', body)
        self.assertNotIn('camera_configuration', body)
        query = ('report_path_timing -delay_type min_max -max_path 1000 -nworst 8 '
                 '-report_exception TRUE -from {a/CLK} -through {a/L6Q} -to {b/I0}')
        self.assertEqual(inspect.query_commands(query), [query])
        for bad in (query+'; gen_bitstream', query.replace('-max_path 1000', '-max_path 1001')):
            with self.assertRaises(ValueError):
                inspect.query_commands(bad)

    def test_technology_and_cleanup_dependencies_are_bound(self):
        _, watched = self.bind()
        self.assertEqual(watched[self.library], inspect.sha(self.library))
        self.assertIn(Path(inspect.diagnostic.cleanup.__file__).resolve(), watched)
        self.assertIn(Path(sys.executable).resolve(), watched)

    def test_placed_netlist_requires_this_exact_single_target(self):
        netlist = self.stage.with_name(self.stage.name+'-netlist.v')
        self.addCleanup(lambda: netlist.unlink(missing_ok=True))
        write(netlist, 'module raw_camera_capture_cam2_current720\nV_FF /* CLMS_1_2 */\nendmodule\n')
        self.assertTrue(inspect.native_netlist_valid(netlist))
        write(netlist, 'module raw_camera_capture_cam2_delay\nV_FF /* CLMS_1_2 */\nendmodule\n')
        self.assertFalse(inspect.native_netlist_valid(netlist))


class FailedBuildReviewTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix='failed-review-fixture-',dir=inspect.prep.WORK)
        self.addCleanup(scratch.cleanup)
        self.build = Path(scratch.name).resolve()
        self.plan = self.build/'plan.json'
        self.receipt = self.build/'execution-result.json'
        self.adf = self.build/'candidate.adf'
        write(self.plan, {'FixtureOnly':True})
        write(self.adf, b'CPU TEST ADF FIXTURE; NEVER NATIVE INPUT')
        items = [f'{log}: C: Sdm-3003: [fixture/monitor.v(line number: {i+1})] Reduce accumulator count_{i} size from 32 to 22. If this is not intended behavior, please drive count_{i} with valid values.'
                 for log in ('compile/run.log','execution-stdout.log','flow.log','run.log') for i in range(15)]
        self.result = {'ExecutionCompletedWithoutError':False,'Diagnostics':items,'LogSHA256':{}}
        write(self.receipt,self.result)
        identity = {'PlanSHA256':inspect.sha(self.plan),'ReceiptSHA256':inspect.sha(self.receipt),
                    'ADFSHA256':inspect.sha(self.adf),
                    'DiagnosticsSHA256':hashlib.sha256(json.dumps(sorted(items),separators=(',',':')).encode()).hexdigest()}
        mocked = patch.object(inspect,'READONLY_FAILED_BUILD',identity)
        mocked.start()
        self.addCleanup(mocked.stop)

    def test_exact_exception_preserves_failed_build_and_unresolved_diagnostics(self):
        review = inspect.readonly_review_payload(self.plan, self.receipt, self.adf, self.result)
        self.assertEqual(len(review['Diagnostics']), 60)
        for key in ('BuildExecutionCompletedWithoutError', 'BuildDiagnosticsCleared', 'TimingAccepted', 'HardwareReleaseAllowed'):
            self.assertIs(review[key], False)

    def test_failed_build_without_explicit_review_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'explicit exact read-only'):
            inspect.bind_diagnostic_review(self.plan, self.receipt, self.adf, self.result, None, None, {})

    def test_different_critical_or_missing_diagnostic_cannot_use_exception(self):
        for diagnostics in (self.result['Diagnostics'][:-1],
                            [self.result['Diagnostics'][0].replace('Sdm-3003', 'STA-3006'), *self.result['Diagnostics'][1:]]):
            with self.subTest(count=len(diagnostics)), self.assertRaises(ValueError):
                inspect.readonly_review_payload(self.plan, self.receipt, self.adf, {**self.result,'Diagnostics':diagnostics})

    def test_another_adf_or_receipt_cannot_use_exception(self):
        with self.assertRaisesRegex(ValueError, 'exact reviewed candidate'):
            inspect.readonly_review_payload(self.plan, self.plan, self.adf, self.result)

    def test_bound_review_must_not_clear_diagnostics(self):
        review = inspect.readonly_review_payload(self.plan, self.receipt, self.adf, self.result)
        root = inspect.prep.WORK
        with tempfile.TemporaryDirectory(prefix='review-fixture-',dir=root) as folder:
            path = Path(folder).resolve()/'review.json'
            write(path, review)
            watched = {}
            inspect.bind_diagnostic_review(self.plan,self.receipt,self.adf,self.result,path,inspect.sha(path),watched)
            self.assertEqual(watched[path],inspect.sha(path))
            for key in ('BuildDiagnosticsCleared','HardwareReleaseAllowed'):
                altered = {**review,key:True}
                write(path,altered)
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'differs from exact'):
                    inspect.bind_diagnostic_review(self.plan,self.receipt,self.adf,self.result,path,inspect.sha(path),{})


if __name__ == '__main__': unittest.main()
