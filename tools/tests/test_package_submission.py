"""Guard the source-package boundary and read-only exported verifier."""
import importlib.util
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

FILE = Path(__file__).resolve().parents[1] / "package_submission.py"
SPEC = importlib.util.spec_from_file_location("package_submission", FILE)
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class SubmissionPackageTests(unittest.TestCase):
    def test_current_archive_is_kept_as_a_whole(self):
        for name in ("a.json", "evidence/test.raw.bin", "evidence/test.log", "old.zip"):
            self.assertTrue(PACKAGE.select_file(PACKAGE.CURRENT_PACKAGE + name)[0])

    def test_code_is_not_removed_with_historical_data(self):
        for name in ("distortion/results/old/input.v", "distortion/captures/calibrate.py",
                     "vendor/board/example/constraints.fdc", "handoff/baseline/fixture.mem",
                     "delivery/old/evidence/rtl/old.sv", "distortion/platform/ip/model.vp"):
            self.assertTrue(PACKAGE.select_file(name)[0], name)
        self.assertFalse(PACKAGE.select_file("distortion/results/old/route.adf")[0])
        self.assertFalse(PACKAGE.select_file("distortion/captures/old/image.png")[0])

    def test_bound_bit_overrides_historical_data_exclusion(self):
        name = "distortion/results/old/artifacts/final.sbit"
        self.assertFalse(PACKAGE.select_file(name)[0])
        self.assertTrue(PACKAGE.select_file(name, {name})[0])

    def test_expanded_delivery_is_kept_but_nested_archive_is_listed(self):
        self.assertTrue(PACKAGE.select_file("delivery/old/evidence/huge.json")[0])
        self.assertFalse(PACKAGE.select_file("delivery/old/release.zip")[0])
        self.assertFalse(PACKAGE.select_file(".git/config")[0])
        self.assertFalse(PACKAGE.select_file("distortion/__pycache__/a.pyc")[0])

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
