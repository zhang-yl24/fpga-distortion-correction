"""Guard the source-package boundary and read-only exported verifier."""
import importlib.util
import json
import hashlib
import gzip
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / "package_submission.py"
SPEC = importlib.util.spec_from_file_location("package_submission", FILE)
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class SubmissionPackageTests(unittest.TestCase):
    def test_only_two_selected_deliveries_are_kept(self):
        for prefix in (PACKAGE.CAMERA720_DELIVERY, PACKAGE.DIRECT_SUBMISSION, PACKAGE.DIRECT_REPORTS):
            for name in ("source/platform/ddr.vp", "source/board/route.rcf", "reports/fast.rtr.gz"):
                self.assertTrue(PACKAGE.select_file(prefix + name)[0])
        for name in ("delivery/20261103-hdmi-camera-fisheye-tile8/verify_source.py",
                     "delivery/20261103-hdmi-camera-fisheye-c/release.zip",
                     "delivery/20261104-hdmi-camera-fisheye-tile8-directfill/verify_stage_d_portable.py",
                     "distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/next-d/df8/old.sbit"):
            self.assertFalse(PACKAGE.select_file(name)[0], name)

    def test_720p_primary_archive_keeps_bitstream_and_external_summary(self):
        for name in ("candidate/camera720_view_toggle_top.sbit.gz", "candidate/camera720_view_toggle_top.adf.gz",
                     "manifest.json", "uart/live-a/session.json", "native/build-a/stdout.log.gz"):
            self.assertTrue(PACKAGE.select_file(PACKAGE.CAMERA720_PACKAGE + name)[0], name)
        self.assertTrue(PACKAGE.select_file(PACKAGE.CAMERA720_SUMMARY)[0])
        self.assertFalse(PACKAGE.select_file(PACKAGE.CAMERA720_PACKAGE.rstrip('/')+'-other/candidate/a.sbit.gz')[0])

    def test_primary_source_and_timing_gzip_reports_are_retained(self):
        for name in (PACKAGE.CAMERA720_DELIVERY + 'reports/slow.rtr.gz',
                     PACKAGE.CAMERA720_DELIVERY + 'bitstreams/camera720_view_toggle_top.sbit',
                     PACKAGE.CAMERA720_DELIVERY + 'source/compiled/board/top.v',
                     PACKAGE.DIRECT_REPORTS + 'reports/fast.rtr.gz'):
            self.assertTrue(PACKAGE.select_file(name)[0], name)
        text = PACKAGE.startup('test-commit')
        self.assertIn('1280×720', text)
        self.assertIn('1920×1080', text)
        self.assertIn('verify_bundle.py', text)
        self.assertIn(PACKAGE.CAMERA720_BIT_SHA, text)
        self.assertIn(PACKAGE.DIRECT_BIT_SHA, text)
        self.assertIn(PACKAGE.CAMERA720_DELIVERY + 'verify_selected.py', text)
        self.assertIn(PACKAGE.DIRECT_SUBMISSION + 'verify_selected.py', text)
        self.assertNotIn('verify_stage_d_portable.py', text)
        self.assertNotIn('project.py', text)

    def test_other_route_code_is_audited_without_claiming_full_repository(self):
        for name in ("distortion/results/old/input.v", "distortion/captures/calibrate.py",
                     "vendor/board/example/constraints.fdc", "handoff/baseline/fixture.mem",
                     "delivery/old/evidence/rtl/old.sv", "distortion/platform/ip/model.vp"):
            keep, reason = PACKAGE.select_file(name)
            self.assertFalse(keep, name)
            self.assertIn('other-route/historical code', reason)
        self.assertFalse(PACKAGE.select_file("distortion/results/old/route.adf")[0])
        self.assertFalse(PACKAGE.select_file("distortion/captures/old/image.png")[0])

    def test_bound_bit_overrides_historical_data_exclusion(self):
        name = "distortion/results/old/artifacts/final.sbit"
        self.assertFalse(PACKAGE.select_file(name)[0])
        self.assertTrue(PACKAGE.select_file(name, {name})[0])

    def test_report_support_is_kept_and_old_deliveries_are_excluded(self):
        for name in ('submission/report/report.pdf', 'submission/evidence/original.png',
                     'distortion/tools/calibrate_kb_tangential.py', 'tools/package_submission.py'):
            self.assertTrue(PACKAGE.select_file(name)[0], name)
        self.assertFalse(PACKAGE.select_file("delivery/old/evidence/huge.json")[0])
        self.assertFalse(PACKAGE.select_file("delivery/old/release.zip")[0])
        self.assertFalse(PACKAGE.select_file(".git/config")[0])
        self.assertFalse(PACKAGE.select_file("distortion/__pycache__/a.pyc")[0])

    def test_only_selected_bitstream_identities_are_allowed(self):
        raw720, raw1080 = b'720 bit', b'1080 bit'
        with patch.object(PACKAGE, 'CAMERA720_BIT_SHA', hashlib.sha256(raw720).hexdigest()), \
             patch.object(PACKAGE, 'DIRECT_BIT_SHA', hashlib.sha256(raw1080).hexdigest()):
            PACKAGE.check_bitstream(PACKAGE.CAMERA720_BIT_GZ, gzip.compress(raw720))
            PACKAGE.check_bitstream(PACKAGE.CAMERA720_DELIVERY + 'bitstream/test.sbit', raw720)
            PACKAGE.check_bitstream(PACKAGE.DIRECT_SUBMISSION + 'bitstream/test.sbit', raw1080)
            for name, data in ((PACKAGE.DIRECT_SUBMISSION + 'bitstream/old.sbit', raw720),
                               (PACKAGE.CAMERA720_DELIVERY + 'old.bit.gz', gzip.compress(raw1080)),
                               ('submission/third.sbit', raw1080)):
                with self.assertRaises(ValueError, msg=name):
                    PACKAGE.check_bitstream(name, data)

    def test_manifest_inputs_are_bound_and_cannot_escape(self):
        name = 'delivery/test/source-manifest.json'
        original = b'module example; endmodule'
        digest = hashlib.sha256(original).hexdigest()
        manifest = {'schema': 'test-v1', 'files': [{'path': 'source/top.v', 'bytes': len(original), 'sha256': digest}]}
        class Reader:
            def read(self, oid):
                return json.dumps(manifest).encode()
        entries = {name: {'GitBlob': 'manifest'}, 'delivery/test/source/top.v': {'Bytes': len(original)}}
        protected, hashes = set(), {}
        PACKAGE.bound_manifest(Reader(), entries, name, 'test-v1', protected, hashes, 1)
        self.assertEqual(hashes['delivery/test/source/top.v'], digest)
        self.assertIn(name, protected)
        for relative in ('../outside.v', '/absolute.v', 'missing.v'):
            manifest['files'][0]['path'] = relative
            with self.assertRaises(ValueError, msg=relative):
                PACKAGE.bound_manifest(Reader(), entries, name, 'test-v1', set(), {})
        manifest['files'][0]['path'] = 'source/top.v'
        manifest['files'][0]['bytes'] += 1
        with self.assertRaisesRegex(ValueError, 'size differs'):
            PACKAGE.bound_manifest(Reader(), entries, name, 'test-v1', set(), {})

    def test_paths_cannot_escape_destination(self):
        for name in ("../escape", "/escape", "a/../../escape", "C:/escape", "a\\escape", "a\nname"):
            with self.assertRaises(ValueError, msg=name):
                PACKAGE.safe_relative(name)

    def test_existing_destination_is_refused_before_git_access(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "already exists"):
                PACKAGE.export(Path(directory) / "not-a-repository", "HEAD", directory)

    def test_standalone_verifier_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = b"known source\r\n"
            (root / "source.v").write_bytes(original)
            (root / "VERIFY_SUBMISSION.py").write_text(PACKAGE.VERIFY_SCRIPT, encoding="utf-8")
            manifest = {"SourceCommit": "test", "DirectfillBitstreamSHA256": PACKAGE.DIRECT_BIT_SHA,
                        "IncludedFiles": [{"Path": "source.v", "Bytes": len(original),
                                           "SHA256": hashlib.sha256(original).hexdigest()}]}
            (root / "SUBMISSION_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(root / "VERIFY_SUBMISSION.py")], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            (root / "source.v").write_bytes(original.replace(b"known", b"other"))
            result = subprocess.run([sys.executable, "-B", str(root / "VERIFY_SUBMISSION.py")], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"SHA256 mismatch", result.stderr)

    def test_export_and_verify_paths_beyond_windows_max_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = PACKAGE.filesystem_path(directory)
            relative = ("long-folder-" * 14) + "/" + ("another-" * 12) + "/source.v"
            source = root.joinpath(*Path(relative).parts)
            source.parent.mkdir(parents=True)
            source.write_bytes(b"module test; endmodule")
            (root / "VERIFY_SUBMISSION.py").write_text(PACKAGE.VERIFY_SCRIPT, encoding="utf-8")
            manifest = {"SourceCommit": "test", "DirectfillBitstreamSHA256": PACKAGE.DIRECT_BIT_SHA,
                        "IncludedFiles": [{"Path": relative, "Bytes": source.stat().st_size,
                                           "SHA256": hashlib.sha256(source.read_bytes()).hexdigest()}]}
            (root / "SUBMISSION_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(root / "VERIFY_SUBMISSION.py")], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            # Remove only this test's known leaf before TemporaryDirectory cleanup.
            source.unlink()
            source.parent.rmdir()
            source.parent.parent.rmdir()


if __name__ == "__main__":
    unittest.main()
