"""Final-C preparation rejects mixed evidence before any native stage exists."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_camera720_stats_delay_final as helper


class FinalCPreparationTests(unittest.TestCase):
    def fixtures(self):
        authority={'Path':str(helper.AUTHORITY),'SHA256':'a'*64}
        export={'Schema':helper.final.SCHEMA,'Target':helper.proof.TARGET,
            'ExecutionPassed':True,'Mode':'export','SourceAuthority':authority,
            'BuildPlanSHA256':helper.BUILD_SHA,'BuildPlan':'current-build',
            'SourceADF':'final.adf','SourceADFSHA256':'b'*64,
            'SourceReceipt':{'Path':'application','SHA256':'c'*64},
            'NativeNetlistWithFFloc':True,'Artifacts':{}}
        route={**deepcopy(export),'Mode':'report','Artifacts':{'route-dump.txt':'d'*64}}
        return export,route,authority

    def test_matched_actual_repaired_final_pair(self):
        helper.same_final_inputs(*self.fixtures())

    def test_original_candidate_or_other_authority_rejected(self):
        for key,value in (('SourceADF','original.adf'),('SourceADFSHA256','e'*64),
                          ('BuildPlanSHA256','f'*64),('SourceAuthority',{}),
                          ('SourceReceipt',{'Path':'other','SHA256':'c'*64})):
            export,route,authority=self.fixtures();route[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                helper.same_final_inputs(export,route,authority)

    def test_failed_wrong_schema_or_missing_export_rejected(self):
        for key,value in (('ExecutionPassed',False),('NativeNetlistWithFFloc',False),
                          ('Schema','camera720-calibrated-stats-delay-readonly-inspection-v1')):
            export,route,authority=self.fixtures();export[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                helper.same_final_inputs(export,route,authority)
        export,route,authority=self.fixtures();route['Artifacts']={}
        with self.assertRaises(ValueError):helper.same_final_inputs(export,route,authority)

    def test_exact_generated_body_names_only(self):
        self.assertEqual(helper.stage_name('query-00.tcl'),'final-cdc-c-00')
        self.assertEqual(helper.stage_name('query-io.tcl'),'final-io-c')
        for name in ('../query-00.tcl','query-other.tcl','query-00.tcl.bak'):
            with self.assertRaises(ValueError):helper.stage_name(name)

    def test_sha_required_even_when_file_absent(self):
        for value in (None,'','ab','A'*64):
            with self.assertRaises(ValueError):helper.exact(Path('missing'),value)


if __name__=='__main__':unittest.main()
