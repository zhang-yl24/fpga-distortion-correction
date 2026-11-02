"""Isolated raw720 build contract tests; native tools are never executed."""
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_camera720_raw as prep
import run_camera720_raw_diagnostic as runner


class Raw720PreparationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roles = prep.validate_sources()
        cls.dependencies = prep.tool_dependencies()
        cls.project = prep.PROJECT
        cls.files = set(cls.roles['Sources']) | set(cls.dependencies) | {
            prep.MANIFEST, prep.sources.PARENT_TOP, prep.sources.PARENT_MANIFEST, prep.FDC, prep.RCF}
        cls.payloads = {name: (cls.project / name).read_bytes() for name in cls.files}

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        scratch_root = (self.project / 'work').resolve()
        scratch_root.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='_r', dir=scratch_root)
        self.root = Path(temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(scratch_root))
        self.addCleanup(temporary.cleanup)
        for name, data in self.payloads.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for module, name, value in (
            (prep, 'PROJECT', self.root), (prep, 'WORK', self.root / 'w'),
            (prep, 'SELF', self.root / 'tools/prepare_camera720_raw.py'),
            (runner, 'SELF', self.root / 'tools/run_camera720_raw_diagnostic.py'),
        ):
            self.stack.enter_context(mock.patch.object(module, name, value))
        self.stack.enter_context(mock.patch.object(prep, 'validate_sources', return_value=copy.deepcopy(self.roles)))
        self.stack.enter_context(mock.patch.object(prep, 'tool_dependencies', return_value=list(self.dependencies)))
        self.pds = self.root / 'pds/bin/pds_shell.exe'
        self.pds.parent.mkdir(parents=True)
        self.pds.write_bytes(b'INERT TEST FILE; NEVER EXECUTE')
        library = self.pds.parent.parent / 'arch/vendor/pango/logos2/common/lib/gtp_lib.v'
        library.parent.mkdir(parents=True)
        library.write_text('''module GTP_INBUF #(parameter IOSTANDARD="DEFAULT", parameter TERM_DDR="ON")
            (output O, input I); endmodule
            module GTP_ZEROHOLDDELAY #(parameter ZHOLD_SET="NODELAY")
            (output DO, input DI); endmodule''', encoding='ascii')
        self.work = prep.WORK / 'build'
        self.plan = prep.prepare(self.work, str(self.pds), 60)
        self.path = self.work / 'plan.json'
        self.native = self.stack.enter_context(mock.patch.object(runner.subprocess, 'Popen'))

    def reject(self, phrase):
        with self.assertRaisesRegex(ValueError, phrase):
            runner.validate_plan(self.path)
        self.native.assert_not_called()

    def test_full_raw_size_preview_and_idf_ownership(self):
        context = runner.validate_plan(self.path)
        self.assertEqual(context['Plan']['RawCaptureContract']['image_size'], [1280, 720])
        self.assertEqual(self.plan['Preview']['SourcePreview'], [160, 90])
        self.assertEqual(self.plan['Preview']['RawPayloadBytes'], 1843200)
        self.assertEqual(sum(Path(n).suffix == '.idf' for n in self.plan['ExplicitDesigns']), 1)
        self.assertFalse(any('/ddr3_test/rtl/' in n for n in self.plan['ExplicitDesigns']))
        self.assertFalse(self.plan['BitstreamRequested'])
        self.assertFalse(self.plan['HardwareAccessed'])
        self.native.assert_not_called()

    def test_compiled_top_tampering_rejected(self):
        path = self.work / 'compiled' / prep.TOP
        path.write_bytes(path.read_bytes() + b'\nwire unexpected;\n')
        self.reject('compiled bytes differ')

    def test_source_drift_rejected(self):
        path = self.root / prep.TOP
        path.write_bytes(path.read_bytes() + b'\n// changed\n')
        self.reject('input drift')

    def test_process_cleanup_dependency_drift_rejected(self):
        name = 'tools/run_camera_vga_output_diagnostic.py'
        self.assertIn(name, self.dependencies)
        path = self.root / name
        path.write_bytes(path.read_bytes() + b'\n# changed cleanup\n')
        self.reject('deterministic recipe')

    def test_added_native_command_rejected(self):
        path = self.work / 'timing.tcl'
        path.write_bytes(path.read_bytes() + b'gen_bit_stream\n')
        self.reject('Tcl recipe drift')

    def test_missing_compiled_header_rejected(self):
        (self.work / 'compiled' / prep.sources.sensor.ROM).unlink()
        self.reject('compiled tree inventory differs')

    def test_plan_command_replacement_rejected(self):
        value = copy.deepcopy(self.plan)
        value['CommandToRunSeparately'] = ['unexpected-hardware-action']
        self.path.write_text(json.dumps(value), encoding='utf-8')
        self.reject('deterministic recipe')

    def test_plan_cannot_claim_optical_or_hardware_acceptance(self):
        for name in ('HardwareAccessed', 'BitstreamRequested', 'TimingAccepted', 'HardwareReleaseAllowed'):
            with self.subTest(field=name):
                value = copy.deepcopy(self.plan)
                value[name] = True
                self.path.write_text(json.dumps(value), encoding='utf-8')
                self.reject('deterministic recipe')

    def test_deadline_cannot_exceed_prepared_limit(self):
        with self.assertRaisesRegex(ValueError, 'deadline exceeds prepared limit'):
            runner.validate_plan(self.path, 61)
        self.native.assert_not_called()


if __name__ == '__main__':
    unittest.main()
