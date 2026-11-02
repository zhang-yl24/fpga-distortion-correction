"""New-target facade must not admit old statistics source/report evidence."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_delay_io_cdc as adapter
import prepare_camera720_calibrated as calibrated
import prepare_camera720_stats_delay_shared_source as source

ROOT=Path(__file__).resolve().parents[1]


class DelayTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original=calibrated.render_top((ROOT/'board/camera720_transport_top.v').read_text())
        cls.top=source.render_top(original,'a'*16,'b'*16)
        cls.fdc=source.render_fdc((ROOT/'board/camera720-output-diagnostic.fdc').read_text(),
                                (ROOT/'board/raw_camera_capture_cam2_ref.fdc').read_text())

    def test_exact_new_source_and_129_pins(self):
        value=adapter.source_inventory(self.top,self.fdc)
        self.assertEqual(value['Target'],adapter.TARGET)
        self.assertEqual(value['PortCount'],129)
        self.assertFalse(value['TimingAccepted'])

    def test_old_top_and_multiple_modules_rejected(self):
        for top in (self.top.replace(adapter.TARGET,adapter.base.TARGET),self.top+'\nmodule extra(); endmodule'):
            with self.assertRaises(ValueError):adapter.source_inventory(top,self.fdc)
        self.assertEqual(adapter.base.TARGET,'camera720_calibrated_stats_top')

    def test_old_native_report_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'timing.rtr'
            path.write_text('2023.2-SP3 <build 154097>\n| Design : '+adapter.base.TARGET+'\n')
            with self.assertRaises(ValueError):adapter.collect([], [path])
            path.write_text('2023.2-SP3 <build 154097>\n| Design : '+adapter.TARGET+'\n')
            self.assertEqual(adapter.collect([], [path]),([],[],[]))


if __name__=='__main__':unittest.main()
