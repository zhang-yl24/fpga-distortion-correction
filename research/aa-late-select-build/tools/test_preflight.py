#!/usr/bin/env python3
"""Static/negative tests only. Never run vendor tools, RTL simulation or hardware."""
import contextlib, copy, hashlib, io, json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.dont_write_bytecode=True
from preflight import ROOT, TOP, SYSTEM, CACHE, check, sha, resolve_pds
from run_stage import ensure_fresh, validate_predecessor, validate_sta_review

class Gates(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='late-kit-gate-')
        self.r=Path(self.tmp.name)/'kit'
        shutil.copytree(ROOT,self.r,ignore=shutil.ignore_patterns('reports','build-repro','__pycache__'))
    def tearDown(self):self.tmp.cleanup()
    def mutate(self,p,old,new):
        q=self.r/p;s=q.read_text();assert old in s;q.write_text(s.replace(old,new,1))
    def test_01_public_kit_static(self):
        r=check(self.r);self.assertEqual(r['errors'],[]);self.assertEqual(len(r['missing_external_inputs']),77);self.assertFalse(r['eda_launched']);self.assertFalse(r['eda_inputs_checked'])
    def test_02_missing_ip_tool_stop(self):
        r=check(self.r,require_eda=True,pds='/nonexistent/pds_shell');self.assertEqual(r['status'],'STOP');self.assertGreaterEqual(len(r['errors']),80);self.assertFalse((self.r/'build-repro').exists())
    def test_03_candidate_tamper_stop(self):
        self.mutate(SYSTEM,'DISPLAY_SELECT_GRACE_CYCLES=0','DISPLAY_SELECT_GRACE_CYCLES=1');self.assertTrue(check(self.r)['errors'])
    def test_04_top_forward_tamper_stop(self):
        self.mutate(TOP,'.DISPLAY_SELECT_GRACE_CYCLES(DISPLAY_SELECT_GRACE_CYCLES)','.DISPLAY_SELECT_GRACE_CYCLES(0)');self.assertTrue(check(self.r)['errors'])
    def test_05_cache_tamper_stop(self):
        with (self.r/CACHE).open('a') as f:f.write('\n// changed\n')
        self.assertTrue(check(self.r)['errors'])
    def test_06_clock_constraint_tamper_stop(self):
        from preflight import FDC
        self.mutate(FDC,'6.657789','6.734006');self.assertTrue(check(self.r)['errors'])
    def test_07_missing_first_party_stop(self):
        (self.r/'native/source/rtl/mul32_pipe.v').unlink();self.assertTrue(check(self.r)['errors'])
    def test_08_manifest_mutation_stop(self):
        self.mutate('rebuild/design_imports.txt','native/source/rtl/mul32_pipe.v','native/source/rtl/other.v');self.assertTrue(check(self.r)['errors'])
    def test_09_pds_options_tamper_stop(self):
        self.mutate('rebuild/route.tcl','-fix_hold_violation_in_route TRUE','-fix_hold_violation_in_route FALSE');self.assertTrue(check(self.r)['errors'])
    def test_10_existing_stage_refused(self):
        (self.r/'build-repro/map').mkdir(parents=True)
        with self.assertRaises(ValueError):ensure_fresh(self.r,'map')
    def test_11_existing_receipt_refused(self):
        (self.r/'build-repro').mkdir();(self.r/'build-repro/map.receipt.json').write_text('{}')
        with self.assertRaises(ValueError):ensure_fresh(self.r,'map')
    def test_12_symlink_output_refused(self):
        (self.r/'build-repro').symlink_to(self.r.parent/'elsewhere',target_is_directory=True)
        with self.assertRaises(ValueError):ensure_fresh(self.r,'map')
    def test_13_arbitrary_old_adf_refused(self):
        q=self.r.parent/'old_map.adf';q.write_text('old evidence, not a PDS output')
        with self.assertRaises(ValueError):validate_predecessor(self.r,'place',q,self.r/'review.json')
    def test_14_injected_map_adf_refused(self):
        with self.assertRaises(ValueError):validate_predecessor(self.r,'map',self.r/'anything.adf',None)
    def test_15_original_launcher_missing_ip_no_eda(self):
        r=subprocess.run([sys.executable,str(self.r/'rebuild/run_build.py'),'map','--root',str(self.r),'--pds','/nonexistent/pds_shell'],capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        self.assertEqual(r.returncode,2);self.assertIn('No EDA launched',r.stdout);self.assertFalse((self.r/'build-repro').exists())
    def test_16_guarded_launcher_missing_ip_no_eda(self):
        r=subprocess.run([sys.executable,str(self.r/'tools/run_stage.py'),'map','--root',str(self.r),'--pds','/nonexistent/pds_shell','--vendor-receipt',str(self.r/'absent.json'),'--tool-receipt',str(self.r/'absent-tool.json')],capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        self.assertEqual(r.returncode,2);self.assertIn('"eda_launched": false',r.stdout);self.assertFalse((self.r/'build-repro').exists())
    def test_17_no_fake_vendor_closure(self):
        ext=json.loads((self.r/'EXTERNAL_INPUTS.json').read_text())['required']
        for entry in ext:
            p=self.r/entry['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_text('module placeholder; endmodule\n')
        r=check(self.r,require_eda=True,pds='/nonexistent/pds_shell');self.assertEqual(r['status'],'STOP');self.assertFalse(r['eda_launched']);self.assertTrue(any('parameter checker rejected' in e for e in r['errors']))
    def test_18_wrong_tool_version_and_external_receipt(self):
        p=self.r/'bad-tool.json';p.write_text(json.dumps({'schema':1,'product':'PDS','version':'2025.1','fabric_compiler_build':'other','normal_authorized_license_setup':True,'executable_sha256':sha(sys.executable),'version_evidence':'NEGATIVE TEST ONLY'}))
        v=self.r/'bad-ip.json';v.write_text(json.dumps({'schema':1,'authorized_use':False,'placeholder_or_blackbox_inputs':True,'ddr_model':'HMIC_S1.9','ddr_generator':'other','files':[]}))
        r=check(self.r,require_eda=True,pds=sys.executable,vendor_receipt=v,tool_receipt=p);self.assertTrue(any('Tool receipt mismatch: version' in e for e in r['errors']));self.assertTrue(any('External receipt mismatch: ddr_model' in e for e in r['errors']))
    def test_19_symlink_input_refused(self):
        p=self.r/'native/source/rtl/mul32_pipe.v';p.unlink();p.symlink_to(ROOT/'native/source/rtl/mul32_pipe.v')
        with self.assertRaises(ValueError):check(self.r)
    def test_20_changed_prior_adf_refused(self):
        ident=json.loads((self.r/'BUILD_IDENTITY.json').read_text())['build_input_identity'];p=self.r/'build-repro/map/board1080_top_map.adf';p.parent.mkdir(parents=True);p.write_text('fixture not EDA');record={'stage':'map','build_input_identity':ident,'exit_code':0,'output_adfs':[{'path':str(p.relative_to(self.r)),'sha256':'0'*64}]};(self.r/'build-repro/map.receipt.json').write_text(json.dumps(record))
        with self.assertRaises(ValueError):validate_predecessor(self.r,'place',p,self.r/'review.json')

    def test_21_idf_dependency_escape_refused(self):
        from preflight import DDR
        p=self.r/DDR;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text('<ip_inst><file_list><source><file pathname="../../../../../../outside.v"/></source></file_list></ip_inst>')
        r=check(self.r);self.assertTrue(any('dependency outside recorded closure' in e for e in r['errors']))
    def test_22_changed_vendor_receipt_refused(self):
        ident=json.loads((self.r/'BUILD_IDENTITY.json').read_text())['build_input_identity'];p=self.r/'build-repro/map/board1080_top_map.adf';p.parent.mkdir(parents=True);p.write_text('fixture not EDA')
        record={'stage':'map','build_input_identity':ident,'exit_code':0,'vendor_receipt_sha256':'0'*64,'output_adfs':[{'path':str(p.relative_to(self.r)),'sha256':sha(p)}]};(self.r/'build-repro/map.receipt.json').write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError,'Vendor receipt/inputs changed'):validate_predecessor(self.r,'place',p,self.r/'review.json',vendor_receipt_sha256='1'*64)


    def test_23_predecessor_stage_symlink_refused(self):
        outside=self.r.parent/'oldstage';outside.mkdir();p=outside/'board1080_top_map.adf';p.write_text('old not EDA')
        (self.r/'build-repro').mkdir();(self.r/'build-repro/map').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'stage directory escapes'):validate_predecessor(self.r,'place',p,self.r/'review.json')
    def test_24_bitgen_no_sta_review_refused(self):
        with self.assertRaisesRegex(ValueError,'explicit reviewed STA'):validate_sta_review(self.r,self.r/'route.adf',None,'a','b','c')
    def sta_fixture(self):
        ident=json.loads((self.r/'BUILD_IDENTITY.json').read_text())['build_input_identity'];p=self.r/'route.adf';p.write_text('synthetic control-plane fixture; not EDA')
        out=self.r/'build-repro/sta';out.mkdir(parents=True);report=out/'fixture-report.txt';report.write_text('UNIT TEST FIXTURE. Not a timing report.')
        record={'stage':'sta','exit_code':0,'build_input_identity':ident,'input_adf_sha256':sha(p),'vendor_receipt_sha256':'v','tool_receipt_sha256':'t','output_files':[{'path':str(report.relative_to(self.r)),'sha256':sha(report)}]}
        (self.r/'build-repro/sta.receipt.json').write_text(json.dumps(record))
        acceptance={'stage':'sta','build_input_identity':ident,'checkpoint_sha256':sha(p),'vendor_receipt_sha256':'v','tool_receipt_sha256':'t','accepted_for_offline_bitgen':True,'unresolved_cells_or_blackboxes':False,'setup_and_hold_reviewed':True,'unconstrained_and_zero_coverage_reviewed':True,'clock_and_exception_coverage_reviewed':True,'physical_io_and_cdc_limitations_acknowledged':True,'worst_setup_slack_ns':0.1,'worst_hold_slack_ns':0.0,'reviewed_clock_count':10,'unconstrained_path_count':0,'reviewed_reports':[{'path':str(report.relative_to(self.r)),'sha256':sha(report)}]}
        review=self.r/'sta-review.json';review.write_text(json.dumps(acceptance));return ident,p,review,acceptance
    def test_25_sta_exit_zero_without_coverage_review_refused(self):
        ident,p,review,a=self.sta_fixture();a['unconstrained_and_zero_coverage_reviewed']=False;review.write_text(json.dumps(a))
        with self.assertRaisesRegex(ValueError,'unconstrained_and_zero_coverage'):validate_sta_review(self.r,p,review,ident,'v','t')
    def test_26_sta_changed_tool_refused(self):
        ident,p,review,a=self.sta_fixture()
        with self.assertRaisesRegex(ValueError,'tool_receipt_sha256'):validate_sta_review(self.r,p,review,ident,'v','different')
    def test_27_sta_changed_report_refused(self):
        ident,p,review,a=self.sta_fixture();(self.r/a['reviewed_reports'][0]['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'report missing, outside stage or changed'):validate_sta_review(self.r,p,review,ident,'v','t')
    def test_28_sta_control_plane_fixture_only(self):
        ident,p,review,a=self.sta_fixture();validate_sta_review(self.r,p,review,ident,'v','t')


    def test_29_relative_pds_path_bound_before_cwd_change(self):
        caller=self.r.parent/'caller';caller.mkdir();wanted=caller/'pds_shell';wanted.write_text('TEST ONLY, never executed');wanted.chmod(0o700)
        shadow=self.r/'pds_shell';shadow.write_text('SHADOW, never executed');shadow.chmod(0o700)
        old=Path.cwd()
        try:
            os.chdir(caller);resolved=resolve_pds('./pds_shell');os.chdir(self.r)
            self.assertEqual(resolved,wanted.resolve());self.assertNotEqual(resolved,resolve_pds('./pds_shell'));self.assertTrue(resolved.is_absolute())
        finally:os.chdir(old)


    def test_30_injected_unrecorded_sta_report_refused(self):
        ident,p,review,a=self.sta_fixture();injected=self.r/'build-repro/sta/copied-old-report.txt';injected.write_text('old/injected report, not emitted by this stage')
        a['reviewed_reports']=[{'path':str(injected.relative_to(self.r)),'sha256':sha(injected)}];review.write_text(json.dumps(a))
        with self.assertRaisesRegex(ValueError,'not recorded as a generated output'):validate_sta_review(self.r,p,review,ident,'v','t')


    def test_31_vp_plaintext_dependency_not_ignored(self):
        ext=json.loads((self.r/'EXTERNAL_INPUTS.json').read_text())['required'];rel=next(e['path'] for e in ext if e['path'].endswith('.vp'))
        p=self.r/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('`include "unrecorded.vh"\n');(p.parent/'unrecorded.vh').write_text('// synthetic fixture, not vendor IP\n')
        self.assertTrue(any('dependency outside recorded closure' in e for e in check(self.r)['errors']))
    def test_32_macro_include_not_silently_skipped(self):
        p=self.r/'native/source/platform/video_base/ipcore/ddr3_test/ddr3_test.v';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('`define HEADER "unrecorded.vh"\n`include `HEADER\n');(p.parent/'unrecorded.vh').write_text('// synthetic fixture\n')
        self.assertTrue(any('Unsupported nonliteral include' in e for e in check(self.r)['errors']))
    def test_33_falsey_or_nonobject_receipt_rejected(self):
        for value in ({}, [], None, False, 0, '', ['x']):
            p=self.r/'empty-receipt.json';p.write_text(json.dumps(value))
            r=check(self.r,require_eda=True,pds=sys.executable,vendor_receipt=p,tool_receipt=p)
            self.assertEqual(sum('Receipt must be a nonempty JSON object' in e for e in r['errors']),2)


    def test_34_invalid_sta_slack_refused(self):
        ident,p,review,a=self.sta_fixture()
        for field in ('worst_setup_slack_ns','worst_hold_slack_ns'):
            for value in (None,True,False,'0',float('nan'),float('inf'),-float('inf'),-0.001):
                bad=dict(a);bad[field]=value;review.write_text(json.dumps(bad))
                with self.assertRaisesRegex(ValueError,'finite nonnegative numeric'):validate_sta_review(self.r,p,review,ident,'v','t')
    def test_35_empty_clock_coverage_refused(self):
        ident,p,review,a=self.sta_fixture()
        for value in (None,0,-1,True,1.0,'10'):
            bad=dict(a);bad['reviewed_clock_count']=value;review.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'positive integer reviewed_clock_count'):validate_sta_review(self.r,p,review,ident,'v','t')
    def test_36_unconstrained_paths_refused(self):
        ident,p,review,a=self.sta_fixture()
        for value in (None,1,-1,False,0.0,'0'):
            bad=dict(a);bad['unconstrained_path_count']=value;review.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'zero integer unconstrained_path_count'):validate_sta_review(self.r,p,review,ident,'v','t')

if __name__=='__main__':unittest.main(verbosity=2)
