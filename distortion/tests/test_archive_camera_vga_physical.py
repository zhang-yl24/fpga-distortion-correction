"""CPU-only archive tests use isolated synthetic data, never live native stages."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import archive_camera_vga_physical as archive


class CameraArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.work = self.root / 'work/camera-vga-output'
        self.results = self.root / 'results'
        self.tools = self.root / 'tools'
        self.results.mkdir(); self.tools.mkdir(); self.work.mkdir(parents=True)
        self.tool = self.tools / 'archive_camera_vga_physical.py'
        self.tool.write_text('# isolated test fixture only\n', encoding='utf-8')
        self.patchers = [patch.object(archive, 'PROJECT', self.root),
                         patch.object(archive, 'WORK', self.work), patch.object(archive, 'TOOL', self.tool)]
        for patcher in self.patchers:
            patcher.start(); self.addCleanup(patcher.stop)
        self.stage = self.work / 'physical-failure-test'
        self.stage.mkdir()
        self.put(self.stage / 'input.adf', b'local database only')
        self.put(self.stage / 'route-dump.txt', b'local full route dump only')
        self.put(self.stage / 'generate_netlist/camera_vga_output_top_sim.v', b'vendor logic only')
        self.put(self.stage / 'compiled/vendor.v', b'staged vendor logic only')
        self.put(self.stage / 'stdout.log', b'preserve failed native execution\n')
        self.put(self.stage / 'stage.tcl', b'mpnr_report_timing -force_to_run\n')
        self.put(self.stage / 'camera_vga_output_top.rtr', b'bounded synthetic recovery report\n' * 100)
        self.receipt = {
            'Schema': 'camera-vga-isolated-query-v1', 'FinishedUTC': '2026-10-31T00:00:00+00:00',
            'ExitCode': 3221225477, 'ExecutionPassed': False, 'HardwareAccessed': False,
            'BitstreamRequested': False, 'Diagnostics': ['synthetic failure'], 'InputDrift': [],
            'Artifacts': {p.relative_to(self.stage).as_posix(): archive.sha(p)
                          for p in self.stage.rglob('*') if p.is_file()}}
        self.write_receipt()
        self.analysis = self.results / 'camera-vga-hold-analysis-test'
        self.analysis.mkdir()
        self.final = self.analysis / 'final-audit.json'
        self.final.write_text(json.dumps({
            'Schema': 'camera-vga-physical-comparison-v1', 'AuditPassed': True,
            'AllInternalChecksMet': False, 'HardwareAccessed': False, 'HardwareReleaseAllowed': False,
            'InputSHA256': {str(self.stage / 'input.adf'): archive.sha(self.stage / 'input.adf')},
            'ToolSHA256': {str(self.tool): archive.sha(self.tool)}}), encoding='utf-8')
        self.config = self.root / 'config.json'
        self.destination = self.results / 'camera-vga-physical-test'
        self.config_data = {
            'Schema': archive.SCHEMA, 'Destination': str(self.destination), 'Stages': [str(self.stage)],
            'FinalAudit': str(self.final), 'EvidenceDirectories': [str(self.analysis)],
            'SourceFiles': [], 'ExtraFiles': []}
        self.write_config()

    def put(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def write_config(self):
        self.config.write_text(json.dumps(self.config_data), encoding='utf-8')

    def write_receipt(self):
        (self.stage / 'result.json').write_text(json.dumps(self.receipt), encoding='utf-8')

    def use_union_audit(self, complete=True):
        proof_path = self.analysis / 'exception-union-comparison.json'
        proof_path.write_text(json.dumps({
            'Schema': 'camera-vga-exception-union-comparison-v1', 'AuditPassed': True,
            'MembershipCompletedFromBothUnions': complete,
            'InputSHA256': {str(self.stage / 'input.adf'): archive.sha(self.stage / 'input.adf')},
            'ToolSHA256': {str(self.tool): archive.sha(self.tool)}}), encoding='utf-8')
        audit = archive.load(self.final)
        audit['Schema'] = 'camera-vga-physical-union-comparison-v1'
        audit['ExceptionUnionComparison'] = {'Proof': str(proof_path), 'ProofSHA256': archive.sha(proof_path)}
        audit['InputSHA256'][str(proof_path)] = archive.sha(proof_path)
        self.final.write_text(json.dumps(audit), encoding='utf-8')
        return proof_path

    def test_preflight_writes_no_archive(self):
        plan = archive.prepare(self.config)
        self.assertFalse(self.destination.exists())
        self.assertEqual(plan['Stages'][0]['ExitCode'], 3221225477)

    def test_roundtrip_preserves_failure_and_references_vendor_payloads(self):
        result = archive.archive(self.config)
        self.assertTrue(result['ReadbackVerified'])
        manifest = archive.load(self.destination / 'manifest.json')
        self.assertEqual(manifest['FailedTrialCount'], 1)
        self.assertFalse(manifest['FinalAudit']['AllInternalChecksMet'])
        self.assertFalse(manifest['HardwareReleaseAllowed'])
        references = {Path(row['LocalPath']).name for row in manifest['LocalReferencesOnly']}
        self.assertTrue({'input.adf', 'route-dump.txt', 'camera_vga_output_top_sim.v', 'vendor.v'} <= references)
        self.assertFalse(any(name.endswith('.adf') or 'generate_netlist/' in name for name in manifest['Files']))
        self.assertTrue(any(name.endswith('.rtr.gz') for name in manifest['Files']))

    def test_incomplete_stage_rejected_without_writing(self):
        del self.receipt['FinishedUTC']; self.write_receipt()
        with self.assertRaisesRegex(ValueError, 'not completed'):
            archive.prepare(self.config)
        self.assertFalse(self.destination.exists())

    def test_changed_receipt_artifact_rejected(self):
        (self.stage / 'stdout.log').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            archive.prepare(self.config)

    def test_final_audit_tool_drift_rejected(self):
        self.tool.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'final audit input drift'):
            archive.prepare(self.config)

    def test_gzip_payload_corruption_detected(self):
        archive.archive(self.config)
        manifest = archive.load(self.destination / 'manifest.json')
        name = next(name for name in manifest['Files'] if name.endswith('.rtr.gz'))
        path = self.destination / name
        path.write_bytes(gzip.compress(b'corrupt payload'))
        manifest['Files'][name]['SHA256'] = archive.sha(path)
        manifest['Files'][name]['Bytes'] = path.stat().st_size
        (self.destination / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'decoded archive content differs'):
            archive.verify_archive(self.destination)

    def test_local_reference_drift_detected(self):
        archive.archive(self.config)
        (self.stage / 'input.adf').write_bytes(b'changed database')
        with self.assertRaisesRegex(ValueError, 'local reference drift'):
            archive.verify_archive(self.destination)

    def test_unlisted_archive_file_detected(self):
        archive.archive(self.config)
        (self.destination / 'unexpected.txt').write_text('unexpected', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unexpected or missing'):
            archive.verify_archive(self.destination)

    def test_stage_traversal_rejected(self):
        self.receipt['Artifacts']['../escaped.log'] = '0' * 64
        self.write_receipt()
        with self.assertRaisesRegex(ValueError, 'parent traversal'):
            archive.prepare(self.config)

    def test_existing_destination_is_never_overwritten(self):
        self.destination.mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh direct'):
            archive.prepare(self.config)

    def test_bound_complete_union_audit_accepted(self):
        self.use_union_audit()
        plan = archive.prepare(self.config)
        self.assertTrue(plan['Audit']['ExceptionUnionProofRevalidated'])

    def test_union_schema_without_proof_rejected(self):
        audit = archive.load(self.final)
        audit['Schema'] = 'camera-vga-physical-union-comparison-v1'
        self.final.write_text(json.dumps(audit), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'explicit bound proof'):
            archive.prepare(self.config)

    def test_incomplete_union_membership_rejected(self):
        self.use_union_audit(complete=False)
        with self.assertRaisesRegex(ValueError, 'complete exception union proof'):
            archive.prepare(self.config)

    def test_changed_union_proof_rejected(self):
        proof_path = self.use_union_audit()
        proof_path.write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'union proof hash differs'):
            archive.prepare(self.config)

    def test_extra_file_already_in_stage_is_copied_once(self):
        self.config_data['ExtraFiles'] = [str(self.stage / 'stdout.log')]
        self.write_config()
        plan = archive.prepare(self.config)
        self.assertEqual(list(plan['Selected'].values()).count(self.stage / 'stdout.log'), 1)


if __name__ == '__main__':
    unittest.main()
