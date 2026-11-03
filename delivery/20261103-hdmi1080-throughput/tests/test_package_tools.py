"""CPU-only regression for the exact portable rebuild.py embedded in the ZIP.

Subprocess calls are mocked. These tests do not run PDS or access hardware.
"""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "tools"))
import package_board_delivery as packaging


class RebuildWrapperTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.wrapper = self.root / "rebuild.py"
        self.wrapper.write_text(packaging.REBUILD_SCRIPT, encoding="utf-8")
        self.module = runpy.run_path(str(self.wrapper), run_name="portable_rebuild_test")
        self.pds = self.root / "pds_shell.exe"
        self.pds.touch()
        self.output = self.root / "build"
        self.work = self.output / "cache-test"
        self.calls = []
        self.argv = [str(self.wrapper), "--pds-shell", str(self.pds),
                     "--output-root", str(self.output), "--variant", "cache",
                     "--run-name", "cache-test", "--seed", "7", "--timeout-seconds", "60"]

    def invoke(self, fake_run):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", self.argv), patch.object(subprocess, "run", side_effect=fake_run), \
                redirect_stdout(out), redirect_stderr(err):
            code = self.module["main"]()
        return code, out.getvalue(), err.getvalue()

    def record(self, command, **kwargs):
        self.assertEqual(kwargs, {"cwd": self.root, "check": True})
        self.assertTrue(all(isinstance(value, str) for value in command))
        self.assertEqual(command[:2], [sys.executable, "-B"])
        self.assertEqual(Path(command[2]), self.root / "delivery/20261103-hdmi1080-throughput/tools/build_board_candidate.py")
        stage = "prepare" if command[3] == "prepare" else command[command.index("--stage") + 1]
        self.calls.append((stage, command))
        return stage

    def test_five_stage_success_preserves_diagnostic_label(self):
        def fake_run(command, **kwargs):
            stage = self.record(command, **kwargs)
            if stage == "bitstream":
                self.work.mkdir(parents=True)
                receipt = {"stage_completed": True, "label": "DIAGNOSTIC_NOT_TIMING_SIGNOFF",
                           "artifacts": {"exported_bitstream": {"path": str(self.work / "test.sbit"),
                                                                 "sha256": "synthetic"}}}
                (self.work / "bitstream-result.json").write_text(json.dumps(receipt), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0)

        code, output, errors = self.invoke(fake_run)
        self.assertEqual(code, 0)
        self.assertEqual(errors, "")
        self.assertEqual([stage for stage, _ in self.calls], ["prepare", "map", "route", "sta", "bitstream"])
        prepare = self.calls[0][1]
        self.assertEqual(Path(prepare[prepare.index("--dependency-native") + 1]), self.root / "native-dependencies")
        self.assertEqual(prepare[prepare.index("--variant") + 1], "cache")
        self.assertEqual(prepare[prepare.index("--mode") + 1], "corrected")
        for stage, command in self.calls[1:]:
            self.assertEqual(Path(command[command.index("--work") + 1]), self.work)
            self.assertEqual(Path(command[command.index("--pds-shell") + 1]), self.pds)
            self.assertEqual(command[command.index("--seed") + 1], "7")
            self.assertEqual(command[command.index("--timeout-seconds") + 1], "60")
            self.assertEqual("--diagnostic-bit" in command, stage == "bitstream")
        result = json.loads(output[output.index('{\n'):])
        self.assertEqual(result["label"], "DIAGNOSTIC_NOT_TIMING_SIGNOFF")
        self.assertTrue(result["completed"])
        self.assertFalse(result["hardware_verified"])
        self.assertFalse(result["hardware_programmed"])

    def test_map_failure_stops_before_route(self):
        def fake_run(command, **kwargs):
            stage = self.record(command, **kwargs)
            if stage == "map":
                raise subprocess.CalledProcessError(23, command)
            return subprocess.CompletedProcess(command, 0)

        code, output, errors = self.invoke(fake_run)
        self.assertEqual(code, 23)
        self.assertEqual([stage for stage, _ in self.calls], ["prepare", "map"])
        self.assertIn("Build stopped.", errors)
        self.assertIn(str(self.work), errors)
        self.assertNotIn('"completed": true', output)
        self.assertFalse((self.work / "bitstream-result.json").exists())


if __name__ == "__main__":
    unittest.main()
