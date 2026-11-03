"""Portable CPU-only source-binding regressions and meaningful tamper cases.

Run: python -B -m unittest discover -s delivery/20261103-hdmi1080-stable30/tests -p test_candidate.py
All mutations occur in temporary copies; no package/build/source input is changed.
FPGA_TEST_TMP may select a roomy temporary directory on local Windows hosts.
"""
from contextlib import contextmanager
from pathlib import Path
import json
import os
import shutil
import tempfile
import types
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
FROZEN = PACKAGE.parent / '20261103-hdmi1080-demo-source'
VERIFY_FILE = PACKAGE / 'tools/verify_candidate.py'
verifier = types.ModuleType('candidate_verifier_test')
verifier.__file__ = str(VERIFY_FILE)
exec(compile(VERIFY_FILE.read_bytes(), str(VERIFY_FILE), 'exec'), verifier.__dict__)


@contextmanager
def replaced(path, blob):
    original = path.read_bytes()
    try:
        path.write_bytes(blob)
        yield
    finally:
        path.write_bytes(original)


class CandidateBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='stable30-tests-', dir=os.environ.get('FPGA_TEST_TMP'))
        parent = Path(cls.temp.name)
        cls.root, cls.base = parent / PACKAGE.name, parent / FROZEN.name
        cls.root.mkdir()
        # Only package inputs used by the verifier are needed in this test copy.
        for folder in ['rtl', 'overlay', 'constraints']:
            shutil.copytree(PACKAGE / folder, cls.root / folder)
        for rel in ['OVERLAYS.json', 'tools/prepare_candidate.py',
                    'tests/tb_engine_throughput.sv', 'evidence/scheduler-source-manifest.json',
                    'evidence/engine/report.json']:
            dest = cls.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PACKAGE / rel, dest)
        shutil.copytree(FROZEN, cls.base, ignore=shutil.ignore_patterns('__pycache__', '_build', '.pytest_cache'))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_unsealed_development_checks_pass_without_input_writes(self):
        before = {str(p): verifier.file_sha(p) for root in [self.root, self.base]
                  for p in root.rglob('*') if p.is_file()}
        result = verifier.verify(self.root, require_seal=False)
        self.assertTrue(result['passed'])
        self.assertFalse(result['sealed_package_verified'])
        self.assertFalse(result['board']['verified'])
        self.assertEqual(result['identity']['param_id_hex'], '8c73465e')
        after = {str(p): verifier.file_sha(p) for root in [self.root, self.base]
                 for p in root.rglob('*') if p.is_file()}
        self.assertEqual(before, after, 'Read-only verification created or modified a file')

    def test_default_verifier_requires_seal(self):
        with self.assertRaisesRegex(ValueError, 'Missing FILE_MANIFEST'):
            verifier.verify(self.root)

    def test_rebound_overlay_is_rejected(self):
        path = self.root / 'OVERLAYS.json'
        data = verifier.read_json(path)
        key = next(iter(verifier.SCHEDULER))
        data[key] = 'rtl/ddr_read_return_register.v'
        with replaced(path, json.dumps(data).encode()):
            with self.assertRaisesRegex(ValueError, 'Unexpected overlay binding'):
                verifier.verify_overlays(self.root, self.base)

    def test_changed_scheduler_overlay_is_rejected(self):
        rel = 'overlay/source/rtl/experimental/hdmi1080_input_dma.v'
        path = self.root / rel
        with replaced(path, path.read_bytes() + b'\n// unexpected mutation\n'):
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                verifier.verify_overlays(self.root, self.base)

    def test_readstage_standalone_divergence_is_rejected(self):
        path = self.root / 'rtl/ddr_read_return_register.v'
        with replaced(path, path.read_bytes().replace(b"8'h40", b"8'h42", 1)):
            with self.assertRaisesRegex(ValueError, 'appended readstage differs'):
                verifier.verify_overlays(self.root, self.base)

    def test_readstage_appended_divergence_is_rejected(self):
        path = self.root / 'overlay' / verifier.TOP
        with replaced(path, path.read_bytes().replace(b"8'h40", b"8'h42", 1)):
            with self.assertRaisesRegex(ValueError, 'appended readstage differs'):
                verifier.verify_overlays(self.root, self.base)

    def test_extra_clock_exception_changes_identity_and_is_rejected(self):
        path = self.root / 'constraints/ddr-ip-clock-relations.fdc'
        bad = path.read_bytes() + b'\nset_false_path -from [all_clocks] -to [all_clocks]\n'
        with replaced(path, bad):
            with self.assertRaisesRegex(ValueError, 'Candidate source/constraint identity differs'):
                verifier.candidate_identity(self.root)

    def test_missing_priority_route_changes_identity_and_is_rejected(self):
        path = self.root / 'constraints/vendor-ddr.rcf'
        with replaced(path, b'# removed route requirement\n'):
            with self.assertRaisesRegex(ValueError, 'Candidate source/constraint identity differs'):
                verifier.candidate_identity(self.root)

    def test_changed_writer_cannot_reuse_engine_receipt(self):
        path = self.root / 'rtl/ddr_adaptive_result_writer.v'
        with replaced(path, path.read_bytes() + b'\n// changed after simulation\n'):
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                verifier.verify_engine(self.root, self.base)

    def test_evidence_windows_paths_resolve_on_current_platform(self):
        original = 'D:\\old-host\\repo\\delivery\\' + self.root.name + '\\rtl\\ddr_read_return_register.v'
        self.assertEqual(verifier.delivered_source(self.root, self.base, original),
                         self.root / 'rtl/ddr_read_return_register.v')
        with self.assertRaisesRegex(ValueError, 'Invalid relative path'):
            verifier.delivered_source(self.root, self.base,
                'D:/old/delivery/' + self.root.name + '/../escape.v')

    def test_seal_rejects_modified_or_extra_payload(self):
        with tempfile.TemporaryDirectory(prefix='seal-fixture-', dir=Path(self.temp.name)) as folder:
            root = Path(folder)
            payload = root / 'payload.v'
            payload.write_bytes(b'module example; endmodule\n')
            manifest = {'files': {'payload.v': verifier.file_sha(payload)}}
            (root / 'FILE_MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')
            self.assertEqual(verifier.verify_seal(root)['files'], 1)
            with replaced(payload, b'module replaced; endmodule\n'):
                with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                    verifier.verify_seal(root)
            (root / 'unlisted.v').write_bytes(b'extra')
            with self.assertRaisesRegex(ValueError, 'file inventory differs'):
                verifier.verify_seal(root)

    def test_wrong_board_source_id_and_input_sha_are_rejected(self):
        manifest, sources, identity = verifier.candidate_identity(self.root)
        board = self.root / 'evidence/board'
        board.mkdir()
        try:
            rows = []
            for row in manifest['files']:
                value = verifier.sha(sources[row['path']]) if row['path'] in sources else row['sha256']
                rows.append({'path': row['path'], 'input_sha256': value, 'compile_sha256': value})
            extras = []
            for name in sorted(verifier.CONSTRAINTS):
                rel = 'stable-constraints/' + name
                value = verifier.file_sha(self.root / 'constraints' / name)
                extras.append(rel)
                rows.append({'path': rel, 'input_sha256': value, 'compile_sha256': value})
            prep = dict(identity, source_count=132, files=rows, additional_constraint_paths=extras)
            summary = dict(identity)
            (board / 'preparation.json').write_text(json.dumps(prep), encoding='utf-8')
            summary['param_id_hex'] = 'deadbeef'
            (board / 'summary.json').write_text(json.dumps(summary), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Board evidence source identity differs'):
                verifier.verify_board(self.root, manifest, sources, identity)
            summary['param_id_hex'] = identity['param_id_hex']
            (board / 'summary.json').write_text(json.dumps(summary), encoding='utf-8')
            prep['files'][-1]['input_sha256'] = '0' * 64
            (board / 'preparation.json').write_text(json.dumps(prep), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Board input SHA256 differs'):
                verifier.verify_board(self.root, manifest, sources, identity)
        finally:
            shutil.rmtree(board)


if __name__ == '__main__':
    unittest.main()
