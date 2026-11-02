import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_derived_inspect as audit
import camera720_stats_reset_apply as apply
import camera720_stats_final_inspect as final

class StatsDerivedTests(unittest.TestCase):
    def test_exact_receipt_sha_required_before_binding(self):
        with patch.object(audit.prep,'work_path',return_value=Path('D:/stage')),patch.object(audit,'bind_source') as bind:
            for value in (None,'', 'a'*63,'g'*64):
                with self.subTest(value=value),self.assertRaisesRegex(ValueError,'explicit completed'):audit.recipe('receipt',value,Path('D:/stage'),'query')
            bind.assert_not_called()

    def test_rejects_other_target_receipt_schema(self):
        with patch.object(audit.physical,'read',return_value={'Schema':'camera720-calibrated-hold-route-application-v1'}):
            with self.assertRaisesRegex(ValueError,'only exact'):audit.bind_source('receipt',{})

    def test_render_read_only_native_context(self):
        text=audit.render('report','',Path('D:/build'),Path('D:/stage'))
        self.assertEqual(text.count(audit.INIT),1)
        self.assertIn('.switch_db -route',text)
        for bad in ('save_adif','manual_route','set_false_path','bitstream'):
            self.assertNotIn(bad,text)
        for body in ('puts {'+audit.MARKER+'}',):
            with self.assertRaises(ValueError):audit.render('query','',Path('D:/build'),Path('D:/stage'),body)

    def test_recipe_uses_stats_prep_actual_hash_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();build=root/'build';build.mkdir();(build/'timing.tcl').write_text('script')
            plan=build/'plan.json';plan.write_text(json.dumps({'PDS':{'Executable':'pds.exe'}}))
            source=root/'source.adf';source.write_bytes(b'adf');receipt=root/'result.json';receipt.write_text('{}')
            result={'ResultADF':{'Path':str(source)},'BuildPlan':str(plan),'ResultADFSHA256':'a'*64,
                    'SourceADF':'original.adf','SourceADFSHA256':'b'*64,'BuildDiagnosticsReview':None}
            with patch.object(audit.prep,'work_path',return_value=root/'stage'),patch.object(audit,'bind_source',return_value=result),patch.object(audit,'render',return_value='safe script'):
                value,body,_=audit.recipe(receipt,audit.sha(receipt),root/'stage','report')
            self.assertEqual(value['TclSHA256'],hashlib.sha256(b'safe script').hexdigest())
            self.assertEqual(value['Target'],'camera720_calibrated_stats_top')
            self.assertEqual(value['SourceReceipt']['SHA256'],audit.sha(receipt))
            self.assertFalse(value['HardwareAccessed'])
            self.assertFalse(value['TimingAccepted'])


    def test_apply_recipe_uses_actual_stats_prep_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();plan=root/'plan.json';plan.write_text(json.dumps({'PDS':{'Executable':'pds.exe'}}))
            request=root/'request.json';request.write_text('{}')
            facts={'BuildPlan':str(plan),'ExactResetCommands':['exact reset command']}
            with patch.object(apply.prep,'work_path',return_value=root/'stage'),patch.object(apply,'bind_request',return_value=(facts,{})):
                value,body,_=apply.recipe(request,root/'stage')
            self.assertEqual(value['TclSHA256'],hashlib.sha256(body.encode('ascii')).hexdigest())
            self.assertEqual(value['Target'],'camera720_calibrated_stats_top')
            self.assertFalse(value['TimingAccepted'])

    def test_final_recipe_uses_actual_stats_prep_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();build=root/'build';build.mkdir();(build/'timing.tcl').write_text('script')
            plan=build/'plan.json';plan.write_text(json.dumps({'PDS':{'Executable':'pds.exe'}}))
            native=root/'reset';native.mkdir();(native/'result.json').write_text('{}')
            result={'ResultADF':{'Path':str(root/'final.adf')},'BuildPlan':str(plan),'ResultADFSHA256':'a'*64,
                    'SourceADF':'original.adf','SourceADFSHA256':'b'*64,'BuildDiagnosticsReview':None,'WorkDirectory':str(native)}
            with patch.object(final.prep,'work_path',return_value=root/'stage'),patch.object(final,'bind_authority',return_value=(result,{})),patch.object(final,'render',return_value='safe script'):
                value,body,_=final.recipe(root/'authority.json','c'*64,root/'stage','report')
            self.assertEqual(value['TclSHA256'],hashlib.sha256(b'safe script').hexdigest())
            self.assertEqual(value['Target'],'camera720_calibrated_stats_top')
            self.assertFalse(value['TimingAccepted'])


    def test_explicit_near_route_provider_dispatch(self):
        schema='camera720-calibrated-stats-hold-route-near-application-v1'
        called=[]
        provider=SimpleNamespace(SCHEMA=schema,__file__=str(audit.prep.PROJECT/'tools/camera720_stats_hold_route_near.py'),
                                 bind_completed=lambda p,w:called.append((p,w)) or {'ExactBResult':True})
        with patch.object(audit.physical,'read',return_value={'Schema':schema}),patch.dict(sys.modules,{'camera720_stats_hold_route_near':provider}),patch.object(audit.physical,'add') as add:
            self.assertEqual(audit.bind_source('b-receipt',{}),{'ExactBResult':True})
            add.assert_called_once_with({},provider.__file__)
        self.assertEqual(called,[('b-receipt',{})])

    def test_near_route_provider_cannot_shadow_exact_module(self):
        schema='camera720-calibrated-stats-hold-route-near-application-v1'
        provider=SimpleNamespace(SCHEMA=schema,__file__='elsewhere.py',bind_completed=lambda p,w:{'Passed':True})
        with patch.object(audit.physical,'read',return_value={'Schema':schema}),patch.dict(sys.modules,{'camera720_stats_hold_route_near':provider}):
            with self.assertRaisesRegex(ValueError,'provider identity'):audit.bind_source('b-receipt',{})

if __name__=='__main__':unittest.main()
