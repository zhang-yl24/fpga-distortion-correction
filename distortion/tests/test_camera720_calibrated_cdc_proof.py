"""CPU tests for current candidate, launch filtering and complete evidence."""
from pathlib import Path
import json,sys,tempfile,unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_calibrated_cdc_proof as proof


def query(source='a',output='L5Q',endpoint='x/I0'):
    return {'Source':source+'/CLK','LaunchOutput':source+'/'+output,'Endpoint':endpoint,
            'Clock':'board27','Corners':['slow','fast'],'CheckKinds':['setup','hold'],'LogicalRelationships':[0]}


class CalibratedProofTests(unittest.TestCase):
    def test_independent_destinations_merge(self):
        qs=[query(),query('b',endpoint='y/I0')]
        groups=proof.groups(qs,qs)
        self.assertEqual(len(groups),1)
        self.assertEqual(len(groups[0]['SourceLaunches']),2)

    def test_competing_destinations_never_merge(self):
        qs=[query(),query('b')]
        self.assertEqual(len(proof.groups(qs,qs)),2)

    def test_already_covered_competition_still_prevents_merge(self):
        qs=[query(),query('b',endpoint='y/I0'),query('b')]
        self.assertEqual(len(proof.groups(qs,qs[:2])),2)

    def test_two_q_of_one_clk_never_merge(self):
        qs=[query(),query(output='L6Q',endpoint='y/I0')]
        self.assertEqual(len(proof.groups(qs,qs)),2)

    def test_only_missing_identities_and_bounded_commands(self):
        qs=[query(str(i),endpoint=f'x[{i}]/I0') for i in range(260)]
        groups=proof.groups(qs,qs[:259])
        self.assertEqual([len(g['ExpectedIdentities']) for g in groups],[128,128,3])
        self.assertEqual(len(proof.cdc.bodies(groups,8)),1)
        with self.assertRaises(ValueError):proof.groups(qs,[query('unknown')])

    def query_files(self,tmp,command_transform=lambda s:s):
        qs=[query()];group=proof.groups(qs,qs)[0]
        body=Path(tmp)/'body.tcl';body.write_text(group['PinCommand']+'\n'+group['Command']+'\n')
        log=Path(tmp)/'stdout.log'
        log.write_text("Timing-5001: The pattern '"+group['PinPattern']+"' match 3 objects below: "+' '.join('t:'+p for p in group['Pins'])+'\n')
        relative='report_path_timing/report_path_timing_1/report_timing/report_path_timing_1.rtr'
        report=Path(tmp)/relative;report.parent.mkdir(parents=True)
        report.write_text('| Tcl Command : '+command_transform(group['Command'])+'\n')
        return qs,{'QueryBody':str(body),'Artifacts':{relative:'bound-by-native-receipt'}},report

    def test_exact_native_header_and_pins_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            qs,value,report=self.query_files(tmp)
            reports,issues,_=proof.query_reports(Path(tmp)/'result.json',value,qs)
            self.assertEqual(reports,[report]);self.assertEqual(issues,[])

    def test_native_dropped_through_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            qs,value,_=self.query_files(tmp,lambda s:s.replace(' -through {a/L5Q}',''))
            with self.assertRaises(ValueError):proof.query_reports(Path(tmp)/'result.json',value,qs)

    def test_native_changed_endpoint_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            qs,value,_=self.query_files(tmp,lambda s:s.replace('-to {x/I0}','-to {x/I3}'))
            with self.assertRaises(ValueError):proof.query_reports(Path(tmp)/'result.json',value,qs)

    def test_missing_pin_log_is_not_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            qs,value,_=self.query_files(tmp);(Path(tmp)/'stdout.log').write_text('')
            _,issues,_=proof.query_reports(Path(tmp)/'result.json',value,qs)
            self.assertTrue(issues)

    def test_query_cannot_name_other_candidate_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            qs,value,_=self.query_files(tmp)
            body=Path(value['QueryBody']);body.write_text(body.read_text().replace('x/I0','unexpected/I0'))
            with self.assertRaises(ValueError):proof.query_reports(Path(tmp)/'result.json',value,qs)

    def test_unknown_receipt_schema_is_not_imported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json';path.write_text(json.dumps({'Schema':'raw-other-schema'}))
            with patch.object(proof.importlib,'import_module') as imported,self.assertRaises(ValueError):
                proof.bind_native(path,'query',{})
            imported.assert_not_called()

    def test_native_critical_log_rejected_despite_success_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json';path.write_text(json.dumps({'Schema':'camera720-calibrated-derived-inspection-v1'}))
            value={'Mode':'query','Target':proof.TARGET,'SourceADF':'exact','SourceADFSHA256':'a'*64}
            with patch.object(proof.importlib,'import_module') as imported,patch.object(proof.cdc.inspect,'scan_diagnostics',return_value=['C: STA-3006 invalid pin']):
                imported.return_value.bind_receipt.return_value=(value,{})
                with self.assertRaises(ValueError):proof.bind_native(path,'query',{}, {'Path':'exact','SHA256':'a'*64})

    def test_candidate_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json';path.write_text(json.dumps({'Schema':'camera720-calibrated-derived-inspection-v1'}))
            value={'Mode':'query','Target':proof.TARGET,'SourceADF':'exact','SourceADFSHA256':'b'*64}
            with patch.object(proof.importlib,'import_module') as imported:
                imported.return_value.bind_receipt.return_value=(value,{})
                with self.assertRaises(ValueError):proof.bind_native(path,'query',{}, {'Path':'exact','SHA256':'a'*64})

    def test_reassessed_schema_uses_its_own_full_binder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json';path.write_text(json.dumps({'Schema':'camera720-calibrated-reassessed-inspection-v1'}))
            value={'Mode':'query','Target':proof.TARGET,'SourceADF':'exact','SourceADFSHA256':'a'*64}
            with patch.object(proof.importlib,'import_module') as imported,patch.object(proof.cdc.inspect,'scan_diagnostics',return_value=[]),patch.object(proof.cdc.io.structure,'local_helpers',return_value=[]):
                imported.return_value.bind_receipt.return_value=(value,{})
                self.assertEqual(proof.bind_native(path,'query',{}, {'Path':'exact','SHA256':'a'*64}),value)
                imported.assert_called_once_with('camera720_calibrated_reassessed_inspect')

    def test_final_schema_uses_explicit_sealed_source_binder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json';path.write_text(json.dumps({'Schema':'camera720-calibrated-final-inspection-v1'}))
            value={'Mode':'query','Target':proof.TARGET,'SourceADF':'exact','SourceADFSHA256':'a'*64}
            with patch.object(proof.importlib,'import_module') as imported,patch.object(proof.cdc.inspect,'scan_diagnostics',return_value=[]),patch.object(proof.cdc.io.structure,'local_helpers',return_value=[]):
                imported.return_value.bind_receipt.return_value=(value,{})
                self.assertEqual(proof.bind_native(path,'query',{}, {'Path':'exact','SHA256':'a'*64}),value)
                imported.assert_called_once_with('camera720_calibrated_final_inspect')

    def test_route_role_accepts_final_report_and_query_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'route.json';candidate={'Path':'exact','SHA256':'a'*64}
            for mode in ('query','report'):
                with self.subTest(mode=mode):
                    path.write_text(json.dumps({'Mode':mode}))
                    with patch.object(proof,'bind_native',return_value={'Mode':mode}) as bound:
                        self.assertEqual(proof.bind_route(path,{},candidate),{'Mode':mode})
                        bound.assert_called_once_with(path,mode,{},candidate)
            for mode in ('export','save-reset',None):
                path.write_text(json.dumps({'Mode':mode}))
                with self.subTest(mode=mode),self.assertRaises(ValueError):proof.bind_route(path,{},candidate)

    def test_verify_recomputes_scope_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'native.json';source.write_text('{}')
            native=proof.cdc.ref(source)
            saved={'Schema':proof.SCHEMA,'Target':proof.TARGET,'InputSHA256':{},'ExportReceipt':native,
                   'RouteReceipt':native,'QueryReceipts':[],'ScopedDigitalChecksPassed':True}
            path=Path(tmp)/'proof.json';path.write_text(json.dumps(saved))
            with patch.object(proof,'audit_value',return_value=({**saved,'ScopedDigitalChecksPassed':False},{})),self.assertRaises(ValueError):
                proof.verify(path)


if __name__=='__main__':unittest.main()
