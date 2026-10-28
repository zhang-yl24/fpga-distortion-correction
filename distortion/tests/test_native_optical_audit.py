"""Guard physical audit provenance and geometry exclusion semantics."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
spec=importlib.util.spec_from_file_location('native_audit',ROOT/'tools/native_optical_audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
SOURCE=ROOT/'captures/gamma-triplets/grid-center-20261009'
TEST_WORKDIR=Path(os.environ.get('FPGA_TEST_WORKDIR',str(ROOT/'build'))).resolve()

class NativeAuditTests(unittest.TestCase):
    def test_corrected_optical_capture(self):
        summary,comparison,images=audit.load_group(SOURCE/'group-00000001')
        self.assertTrue(summary['passed'])
        self.assertEqual(images['raw'].shape,(480,640))

    def test_pattern_is_not_optical(self):
        with self.assertRaisesRegex(ValueError,'physical optical'):
            audit.load_group(ROOT/'captures/gamma-triplets/sensor-colorbars-d5-fixed-20261008/group-00000001')

    def test_old_d5_is_not_current_optical(self):
        with self.assertRaisesRegex(ValueError,'physical optical'):
            audit.load_group(ROOT/'captures/gamma-triplets/physical-bright-warmed-20261008/group-00000001')

    def test_rgb565_neutral_quantization(self):
        result=audit.color_stats(np.array([[0x8410]],dtype=np.uint16))
        self.assertEqual(result['mean_rgb_code'],[132.,130.,132.])
        self.assertEqual(result['green_minus_red_code'],-2.)

    def test_exclusion_mask_semantics_and_bounds(self):
        mask=np.zeros((10,10),dtype=bool);mask[4,5]=True
        self.assertTrue(audit.corners_in_valid_domain([[3.,3.]],mask))
        self.assertFalse(audit.corners_in_valid_domain([[5.,4.]],mask))
        self.assertFalse(audit.corners_in_valid_domain([[-1.,3.]],mask))
        self.assertFalse(audit.corners_in_valid_domain([[10.,3.]],mask))

    def fixture(self,root):
        dest=Path(root)/'capture';dest.mkdir()
        shutil.copy2(SOURCE/'summary.json',dest/'summary.json')
        shutil.copytree(SOURCE/'group-00000001',dest/'group-00000001')
        return dest/'group-00000001'

    def test_changed_pixels_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEST_WORKDIR,prefix='native-audit-test-') as temp:
            folder=self.fixture(temp)
            p=folder/'raw.npy';pixels=np.load(p);pixels[0,0]^=1;np.save(p,pixels)
            with self.assertRaisesRegex(ValueError,'Pixels/mask changed'):
                audit.load_group(folder)

    def test_changed_uart_crc_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEST_WORKDIR,prefix='native-audit-test-') as temp:
            folder=self.fixture(temp);p=folder/'comparison.json'
            data=audit.read(p);data['crc32'][0]='00000000';p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'CRC differs'):
                audit.load_group(folder)

    def test_outside_workspace_rejected(self):
        with self.assertRaisesRegex(ValueError,'outside workspace'):
            audit.load_group(ROOT.parent/'not-a-project-capture')

if __name__=='__main__':unittest.main()
