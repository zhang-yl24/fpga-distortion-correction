"""Exact metadata disposition tests; no native or hardware access."""
import copy
from pathlib import Path
import sys
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_calibrated_route_reassessment as review
import camera720_calibrated_reassessed_inspect as derived


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.a={'ExcludedBlocks':{'FILETABLE':{'Tokens':['(','FILETABLE','(','FILEMAP','2','""',')',')'],
                 'TokenSHA256':'before'}},'SourceAnnotationsOutsideCDBEntries':[
                 {'Tokens':['(','FILEID','11012',')']},{'Tokens':['(','LINENUM','106',')']}]}
        self.b={'ExcludedBlocks':{'FILETABLE':{'Tokens':['(','FILETABLE',')'],'TokenSHA256':'after'}},
                'SourceAnnotationsOutsideCDBEntries':[]}

    def test_only_empty_filename_and_numeric_locations_are_metadata(self):
        value=review.metadata_change(self.a,self.b)
        self.assertTrue(value['ExactEmptyFileMapRemoval'])
        self.assertFalse(value['FunctionalOrTimingExceptionChangePermitted'])
        self.assertEqual(value['RemovedOutsideCDBMetadataCounts'],{'FILEID':1,'LINENUM':1})

    def test_real_filename_or_added_entry_is_not_disposed(self):
        for replacement in ('"camera.v"','"../other.v"','" "'):
            bad=copy.deepcopy(self.a);bad['ExcludedBlocks']['FILETABLE']['Tokens'][5]=replacement
            with self.subTest(filename=replacement),self.assertRaises(ValueError):review.metadata_change(bad,self.b)
        bad=copy.deepcopy(self.b);bad['ExcludedBlocks']['FILETABLE']['Tokens']=self.a['ExcludedBlocks']['FILETABLE']['Tokens']
        with self.assertRaises(ValueError):review.metadata_change(self.a,bad)

    def test_source_payload_or_partial_removal_is_not_disposed(self):
        for tokens in (['(','FILEID','data',')'],['(','INIT','0',')'],['(','LINENUM','-1',')']):
            bad=copy.deepcopy(self.a);bad['SourceAnnotationsOutsideCDBEntries'][0]['Tokens']=tokens
            with self.subTest(tokens=tokens),self.assertRaises(ValueError):review.metadata_change(bad,self.b)
        bad=copy.deepcopy(self.b);bad['SourceAnnotationsOutsideCDBEntries']=self.a['SourceAnnotationsOutsideCDBEntries'][:1]
        with self.assertRaises(ValueError):review.metadata_change(self.a,bad)

    def test_wrong_native_failure_cannot_use_disposition(self):
        for error in ('timeout','ValueError: constraint definitions changed',None):
            value={'Schema':review.original.SCHEMA,'ExecutionPassed':False,'Error':error}
            with self.subTest(error=error),mock.patch.object(review.inspect,'canonical',side_effect=Path), \
                 mock.patch.object(review,'add'),mock.patch.object(review,'read',return_value=value),self.assertRaises(ValueError):
                review.bind_original(Path('result.json'),{})

    def test_new_inspector_accepts_only_new_schema_or_exact_reset_provider(self):
        with mock.patch.object(review,'read',return_value={'Schema':review.SCHEMA}), \
             mock.patch.object(review,'bind_completed',return_value={'ReassessmentPassed':True}) as bound:
            self.assertEqual(derived.bind_source(Path('new.json'),{}),{'ReassessmentPassed':True})
            bound.assert_called_once()
        with mock.patch.object(review,'read',return_value={'Schema':review.original.SCHEMA}),self.assertRaises(ValueError):
            derived.bind_source(Path('old-failed.json'),{})


if __name__=='__main__':unittest.main()
