import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_raw_reset_current as current

class CurrentResetTest(unittest.TestCase):
    def value(self):
        return {'Target':current.prep.TARGET,'Mode':'export',
                'SourceADFSHA256':current.SOURCE_SHA,
                'SourceReceipt':{'SHA256':current.APPLICATION_SHA},
                'BuildDiagnosticsCleared':False,'HardwareReleaseAllowed':False}

    def test_exact_b_export_allowed_only_as_diagnostic(self):
        current.exact_export(self.value())

    def test_original_or_other_adf_rejected(self):
        value=self.value();value['SourceADFSHA256']='799296ded7e2fd66969d4cfdf25a9a30e316c2d8ac9c520b659cb83576f8fed7'
        with self.assertRaisesRegex(ValueError,'route-b'):current.exact_export(value)

    def test_receipt_substitution_rejected(self):
        value=self.value();value['SourceReceipt']['SHA256']='0'*64
        with self.assertRaises(ValueError):current.exact_export(value)

    def test_target_mode_and_authority_rejected(self):
        for field,value in [('Target','camera720_transport_top'),('Mode','query'),
                            ('BuildDiagnosticsCleared',True),('HardwareReleaseAllowed',True)]:
            with self.subTest(field=field):
                item=self.value();item[field]=value
                with self.assertRaises(ValueError):current.exact_export(item)

    def test_conflicting_input_union_rejected(self):
        path=Path(__file__).resolve()
        with self.assertRaises(ValueError):current.merge({path:'a'},{path:'b'})

    def test_frozen_targets_unchanged(self):
        target=current.reset.graph.TARGET
        value=self.value();current.exact_export(value)
        self.assertEqual(current.reset.graph.TARGET,target)
        self.assertNotEqual(target,current.prep.TARGET)

if __name__=='__main__':unittest.main()
