"""CPU provenance tests for the independent retained-source sensor port."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_camera720_sensor as sensor


class Camera720SensorPortTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="camera720-sensor-test-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        for name in (*sensor.RETAINED, sensor.INIT, sensor.FRONTEND):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sensor.ROOT / name, path)

    def test_port_verifies_without_historical_build_proposal(self):
        self.assertFalse((self.root / "build").exists())
        report = sensor.verify(self.root)
        self.assertTrue(report["Passed"])
        self.assertFalse(report["HistoricalGeneratorReproduced"])
        self.assertEqual(report["RegisterActionCount"], 403)

    def test_initializer_changes_only_name_and_include(self):
        original = (self.root / sensor.BASE_INIT).read_bytes()
        port = (self.root / sensor.INIT).read_bytes()
        restored = port.replace(b"module ov5640_current720_init #(", b"module ov5640_rgb565_720_init #(")
        restored = restored.replace(b'`include "board/ov5640_rgb565_720_commands.vh"',
                                    b'`include "D:/English/FPGA/distortion/board/ov5640_rgb565_720_commands.vh"')
        self.assertEqual(restored, original)

    def test_all_retained_inputs_are_hash_bound(self):
        for name in sensor.RETAINED:
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                with self.assertRaisesRegex(ValueError, "Retained sensor source hash changed"):
                    sensor.verify(self.root)
                path.write_bytes(original)

    def test_initializer_logic_drift_is_rejected(self):
        path = self.root / sensor.INIT
        path.write_bytes(path.read_bytes().replace(b"FINISHED:configured<=1;", b"FINISHED:configured<=0;"))
        with self.assertRaisesRegex(ValueError, "beyond module name/include"):
            sensor.verify(self.root)

    def test_returning_to_machine_absolute_include_is_rejected(self):
        path = self.root / sensor.INIT
        path.write_bytes(path.read_bytes().replace(b'`include "board/', b'`include "D:/English/FPGA/distortion/board/'))
        with self.assertRaisesRegex(ValueError, "beyond module name/include"):
            sensor.verify(self.root)

    def test_integrity_report_cannot_be_mistaken_for_hardware_measurement(self):
        report = sensor.verify(self.root)
        self.assertIsNone(report["MeasuredFPS"])
        self.assertFalse(report["HardwareReleaseAllowed"])
        self.assertFalse(report["HardwareAccessed"])
        self.assertFalse(report["PDSAccessed"])
        self.assertEqual(report["RequiredCompleteGoodFrames"], 2)
        self.assertEqual(report["StartupGraceRefCycles"], 27000000)


if __name__ == "__main__":
    unittest.main()
