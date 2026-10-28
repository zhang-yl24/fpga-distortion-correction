"""Synthetic small CPU-only sequence tests; never an RTL or physical result."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import uuid

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))
import generate_continuous1080_vectors as seq

INPUTS = [ROOT/f"build/offline-20261024/parallel-1031-20261027-a/integration/core-small-vectors{i}/vectors.json" for i in (0, 1)]


class ContinuousVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not seq.APPROVED.is_dir() or any(not path.is_file() for path in INPUTS):
            raise unittest.SkipTest("approved scratch or existing small CPU vector artifacts are absent")
        cls.work = seq.APPROVED/("cpu-unit-"+uuid.uuid4().hex[:12])
        cls.work.mkdir()  # Root explicitly authorized descendants here; leave all evidence intact.

    def child(self):
        path = self.work/uuid.uuid4().hex[:12]
        path.mkdir()
        return path

    def altered(self, index, field, value):
        path = self.child()/"synthetic-altered-vectors.json"
        record = json.loads(INPUTS[index].read_text()); record[field] = value
        path.write_text(json.dumps(record), encoding="utf-8")
        return path

    def test_fixed_third_texture_changes_every_pixel_without_mutating_original(self):
        source = np.arange(512, dtype=np.uint16).reshape(16, 32)
        original = source.copy()
        changed = seq.third_source(source)
        self.assertTrue(np.array_equal(source, original))
        self.assertTrue(np.all(changed != source))
        self.assertTrue(np.array_equal(np.bitwise_xor(changed, np.uint16(0x5A3C)), source))
        self.assertEqual(changed.dtype, np.uint16)

    def test_legacy_source_reference_and_mask_preserved_then_new_source_remapped(self):
        source, old_expected, masks, _ = seq.cpu.render_frame(32, 16, 0)
        expected, old_masks, _ = seq.remap_source(source, seq.cpu.parameters(32, 16), 2*seq.cpu.Q)
        self.assertTrue(np.array_equal(expected, old_expected))
        self.assertTrue(np.array_equal(old_masks, masks))
        third, third_masks, stats = seq.remap_source(seq.third_source(source), seq.cpu.parameters(32, 16), 2*seq.cpu.Q)
        self.assertTrue(np.array_equal(third_masks, masks))
        self.assertGreater(stats["ScalarCoordinateCrosschecks"], 0)
        self.assertTrue(np.all(third[third_masks] == 0))
        self.assertFalse(np.array_equal(third, np.bitwise_xor(old_expected, np.uint16(0x5A3C))))
        self.assertTrue(np.any(third != old_expected))

    def test_complete_small_sequence_has_three_ids_banks_crcs_and_original_bytes(self):
        out = self.child()
        before = {str(path): seq.sha(path) for path in INPUTS}
        result = seq.generate_sequence(*INPUTS, out)
        self.assertEqual(result["FrameIDs"], [1, 2, 3])
        self.assertEqual(result["BankExpected"], [0, 1, 0])
        self.assertEqual(result["PayloadLengths"], [1024, 1024, 1024])
        self.assertEqual(len(result["Frames"]), 3)
        for i, path in enumerate(INPUTS):
            original = json.loads(path.read_text())
            for name, dst in (("source.mem", "source"), ("expected.mem", "expected"), ("masks.mem", "masks"), ("crcs.mem", "crc")):
                self.assertEqual((out/f"{dst}{i}.mem").read_bytes(), Path(original["Files"][name]["Path"]).read_bytes())
            self.assertEqual((out/f"frame{i}-origin-vectors.json").read_bytes(), path.read_bytes())
        for i, frame in enumerate(result["Frames"]):
            for name in seq.MEM_NAMES:
                self.assertEqual(seq.sha(out/f"{name}{i}.mem"), frame["Files"][name]["SHA256"])
            words = seq._words(out/f"source{i}.mem", 512)
            self.assertEqual(seq.cpu.pixel_crc(words), frame["SourcePixelCRC32"])
            self.assertEqual((out/f"sourcecrc{i}.mem").read_text().strip().upper(), frame["SourcePixelCRC32"])
            self.assertEqual((out/f"crc{i}.mem").read_text().strip().upper(), frame["ExpectedPixelCRC32"])
        self.assertEqual(before, {str(path): seq.sha(path) for path in INPUTS})
        self.assertEqual(result["ReferenceSHA256"], result["ReferenceSHA256After"])
        self.assertFalse(result["HardwareAccessed"])
        self.assertFalse(result["SimulationExecuted"])
        self.assertFalse(result["CalibrationAccepted"])
        self.assertNotIn("TextureVariant", result["Frames"][2])

    def test_refuses_overwrite_before_any_other_output(self):
        out = self.child(); existing = out/"source2.mem"
        existing.write_bytes(b"preserved synthetic marker\n")
        with self.assertRaisesRegex(ValueError, "no overwrite"):
            seq.generate_sequence(*INPUTS, out)
        self.assertEqual(existing.read_bytes(), b"preserved synthetic marker\n")
        self.assertEqual(len(list(out.iterdir())), 1)

    def test_legacy_variant_two_cannot_bypass_variant_guard(self):
        altered = self.altered(1, "TextureVariant", 2)
        out = self.child()
        with self.assertRaisesRegex(ValueError, "variant2"):
            seq.generate_sequence(INPUTS[0], altered, out)
        self.assertEqual(list(out.iterdir()), [])

    def test_model_or_reference_tamper_is_rejected(self):
        record = json.loads(INPUTS[1].read_text())
        altered = copy.deepcopy(record["IntegerConfig"]); altered[-1] += 1
        for field, value in (("IntegerConfig", altered), ("ReferenceSHA256", {})):
            with self.subTest(field=field):
                modified = self.altered(1, field, value); out = self.child()
                with self.assertRaises(ValueError):
                    seq.generate_sequence(INPUTS[0], modified, out)
                self.assertEqual(list(out.iterdir()), [])

    def test_old_fixture_sha_tamper_is_rejected(self):
        record = json.loads(INPUTS[1].read_text())
        files = copy.deepcopy(record["Files"]); files["expected.mem"]["SHA256"] = "0"*64
        altered = self.altered(1, "Files", files); out = self.child()
        with self.assertRaisesRegex(ValueError, "file/hash/length"):
            seq.generate_sequence(INPUTS[0], altered, out)
        self.assertEqual(list(out.iterdir()), [])

    def test_budget_types_and_source_shape_are_strict(self):
        for budget in (True, -1, 0, 181, float("inf"), float("nan")):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                seq.generate_sequence(*INPUTS, self.work, maximum_seconds=budget)
        with self.assertRaises(ValueError):
            seq.third_source(np.zeros((16, 32), dtype=np.uint32))
        with self.assertRaises(ValueError):
            seq.remap_source(np.zeros((16, 32), dtype=np.uint16), [0]*13, 2*seq.cpu.Q)


if __name__ == "__main__":
    unittest.main()
