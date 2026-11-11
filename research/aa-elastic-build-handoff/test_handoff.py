#!/usr/bin/env python3
"""Small first-party synthetic tests only. No private seed, vendor tool or HDL simulation."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import pds_handoff as h

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.out=self.root/'new';self.out.mkdir();self.prepared=self.root/'inputs';self.prepared.mkdir()
        (self.prepared/'native').mkdir()
        (self.prepared/'native/a.fdc').write_text('# [get_ports ignored]\ncreate_clock [get_ports {clk_p}]\nset_x [get_pins {a[0]/p}] [get_clocks {core}]\n')
        self.plan={'imports':[{'path':'fake'+str(i)+'.sv'} for i in range(85)],
          'constraints':[{'origin':'private_seed','path':'a.fdc'} for _ in range(4)],
          'include_paths':['.'],'rom':{'source':'rom'}}
        self.info={'derived':{'rom':b'0123\n'}};self.nonce='a'*32
        self.scripts,self.rows=h.generate(self.info,self.plan,self.prepared,self.out,self.nonce)
        for name,s in self.scripts.items(): (self.out/name).write_text(s)
        (self.out/'CONSTRAINT_QUERY_INVENTORY.json').write_bytes(h.dump(self.rows))
    def tearDown(self):self.tmp.cleanup()
    def config(self):
        return {'prepared':str(self.prepared),'run_id':self.nonce,'project_name':'aa_elastic_'+self.nonce[:12],
                'asset_hashes':h.inventory(self.out)}
    def test_query_parser_bracket_in_braces(self):
        self.assertEqual(len(self.rows),12);self.assertEqual(self.rows[1]['expression'],'get_pins {a[0]/p}')
        self.assertEqual(self.rows[2]['count_api'],'UNVERIFIED; raw Tcl result is NOT a collection count')
    def test_query_parser_fails_unbalanced(self):
        (self.prepared/'native/a.fdc').write_text('x [get_pins {a}\n')
        with self.assertRaises(h.Refusal):h.query_inventory(self.plan,self.prepared)
    def test_script_has_only_allowed_stages(self):
        s=self.scripts['SYNTHESIS.tcl']
        self.assertEqual(s.count('[list add_design '),85)
        self.assertIn(h.ARCH,s);self.assertIn('-top_module '+h.TOP,s)
        for word in ['dev_map','place_design','route_design','report_timing','bitgen','create_project']:self.assertNotIn(word,s)
    def test_changed_asset_and_rewritten_receipt_rejected(self):
        cfg=self.config();(self.out/'SYNTHESIS.tcl').write_text('exit 0\n')
        cfg['asset_hashes']=h.inventory(self.out)
        with self.assertRaises(h.Refusal):h.verify_assets(self.out,cfg,self.info,self.plan)
    def test_wrong_project_rejected(self):
        cfg=self.config();cfg['project_name']='old_project'
        with self.assertRaises(h.Refusal):h.verify_assets(self.out,cfg,self.info,self.plan)
    def test_good_assets(self): h.verify_assets(self.out,self.config(),self.info,self.plan)
    def test_existing_out(self):
        with self.assertRaises(h.Refusal):h.fresh_output(self.out,[])
    def test_protected_out(self):
        with self.assertRaises(h.Refusal):h.fresh_output(self.prepared/'next',[self.prepared])
    def test_symlink(self):
        p=self.root/'link';p.symlink_to(self.prepared,target_is_directory=True)
        with self.assertRaises(h.Refusal):h.path(p)
    def test_path_traversal(self):
        with self.assertRaises(h.Refusal):h.path(self.root/'a/../new')
    def test_duplicate_json(self):
        p=self.root/'a.json';p.write_text('{"x":1,"x":2}')
        with self.assertRaises(h.Refusal):h.load(p)
    def test_missing_run_receipt(self):
        (self.out/'PREPARED.json').write_bytes(h.dump({'out':str(self.out)}))
        with self.assertRaises((h.Refusal,KeyError)):h.collect(self.out)
    @unittest.skipUnless(shutil.which('tclsh'),'existing Tcl interpreter needed')
    def test_tcl_fixture_hooks_and_query_raw_not_counts(self):
        work=self.out/'work';work.mkdir()
        harness='''proc add_design {args} {return 1}
proc add_constraint {args} {return 1}
proc set_arch {args} {return 1}
proc compile {args} {
    set hook [lindex $args [expr {[lsearch $args -pre_tcl]+1}]]
    set here [pwd];file mkdir compile;cd compile;source $hook;cd $here
}
proc synthesize {args} {
    set hook [lindex $args [expr {[lsearch $args -pre_tcl]+1}]]
    set here [pwd];file mkdir synthesize;cd synthesize;source $hook;cd $here
}
proc get_ports {args} {return _opaque_collection_1}
proc get_pins {args} {return _opaque_collection_1}
proc get_clocks {args} {return _opaque_collection_1}
source '''+h.tcl(self.out/'SYNTHESIS.tcl')+'\n'
        p=self.root/'harness.tcl';p.write_text(harness)
        run=subprocess.run(['tclsh',str(p)],cwd=work,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr);self.assertIn('AA_END '+self.nonce,run.stdout)
        self.assertEqual(run.stdout.count('AA_QUERY\t'),12)
        for d in [work,work/'compile',work/'synthesize']:self.assertEqual((d/'run8_intervals_30bit.mem').read_bytes(),b'0123\n')
        # Explicitly verify conflicting content is not overwritten.
        target=work/'run8_intervals_30bit.mem';target.write_bytes(b'BAD')
        probe=self.root/'probe.tcl';probe.write_text('source '+h.tcl(self.out/'rom_bootstrap.tcl')+'\n')
        fail=subprocess.run(['tclsh',str(probe)],cwd=work,capture_output=True,text=True)
        self.assertNotEqual(fail.returncode,0);self.assertEqual(target.read_bytes(),b'BAD')
        # Outside-root hook fails before any destination is created.
        fail=subprocess.run(['tclsh',str(probe)],cwd=self.root,capture_output=True,text=True)
        self.assertNotEqual(fail.returncode,0);self.assertFalse((self.root/'run8_intervals_30bit.mem').exists())
    def synthetic_finished(self):
        import time
        candidate=self.root/'candidate';candidate.mkdir();record=self.root/'record';record.mkdir();native=record/'native';native.mkdir()
        cfg=self.config();cfg.update(out=str(self.out),candidate=str(candidate),native=str(native),
                                    identity={'test':'synthetic'},helper_sha256=h.sha(h.read(h.__file__)))
        (self.out/'PREPARED.json').write_bytes(h.dump(cfg))
        start={'run_id':self.nonce,'start_ns':time.time_ns(),'tool_sha256':h.TOOL_SHA,
               'prepared_sha256':h.sha(h.read(self.out/'PREPARED.json'))}
        (self.out/'EXECUTION_STARTED.json').write_bytes(h.dump(start))
        work=self.out/'work';work.mkdir()
        (work/'synthetic.rpt').write_text('Synthetic report. Not PDS.\n')
        trace=[]
        for phase in ['bootstrap','compile','synthesize']:
            d=work/phase;d.mkdir();r=d/'run8_intervals_30bit.mem';r.write_bytes(b'0123\n')
            trace.append(phase+'\t'+str(d)+'\t'+str(r))
        (self.out/'ROM_WORKDIRS.tsv').write_text('\n'.join(trace)+'\n')
        lines=['AA_RUN_ID '+self.nonce,'AA_SYNTHESIS_COMMAND_RETURNED','AA_END '+self.nonce]
        lines+=['AA_RESULT '+s+' RC=0' for s in ['ARCH','COMPILE','SYNTHESIZE']+[f'IMPORT_{i}' for i in range(85)]+[f'CONSTRAINT_{i}' for i in range(4)]]
        lines+=['AA_QUERY\t'+str(r['id'])+'\t0\t'+b'_opaque_collection_1'.hex() for r in self.rows]
        (self.out/'pds_stdout.log').write_text('\n'.join(lines)+'\n')
        end={'run_id':self.nonce,'returncode':0,'end_ns':time.time_ns(),'input_identity_unchanged':True,
             'outputs':h.inventory(work),'stdout_sha256':h.sha(h.read(self.out/'pds_stdout.log')),
             'rom_trace_sha256':h.sha(h.read(self.out/'ROM_WORKDIRS.tsv'))}
        (self.out/'EXECUTION_FINISHED.json').write_bytes(h.dump(end))
        return cfg,end
    def collect_fixture(self,cfg):
        with patch.object(h,'authenticate',return_value=(self.info,self.plan,cfg['identity'])), patch.object(h,'ROM_SHA',h.sha(b'0123\n')):
            return h.collect(self.out)
    def test_collect_never_accepts_synthetic_success(self):
        cfg,end=self.synthetic_finished();r=self.collect_fixture(cfg)
        self.assertEqual(r['status'],'SYNTHESIS_EXECUTED_REVIEW_REQUIRED')
        self.assertFalse(r['build_accepted']);self.assertFalse(r['no_blackboxes_verified'])
        self.assertFalse(r['constraint_object_counts_verified'])
    def test_collect_rejects_report_drift(self):
        cfg,end=self.synthetic_finished();(self.out/'work/synthetic.rpt').write_text('changed')
        with self.assertRaises(h.Refusal):self.collect_fixture(cfg)
    def test_collect_flags_stale_report(self):
        import os
        cfg,end=self.synthetic_finished();os.utime(self.out/'work/synthetic.rpt',(1,1))
        r=self.collect_fixture(cfg)
        self.assertIn('stale report timestamp: synthetic.rpt',r['findings'])
    def test_collect_flags_blackbox_diagnostic(self):
        cfg,end=self.synthetic_finished();(self.out/'work/synthetic.rpt').write_text('Unresolved blackbox cell.\n')
        end['outputs']=h.inventory(self.out/'work');(self.out/'EXECUTION_FINISHED.json').write_bytes(h.dump(end))
        r=self.collect_fixture(cfg)
        self.assertTrue(r['diagnostic_hits']);self.assertFalse(r['no_blackboxes_verified'])
    def test_collect_flags_missing_rom_phase(self):
        cfg,end=self.synthetic_finished();p=self.out/'ROM_WORKDIRS.tsv'
        p.write_text('\n'.join(p.read_text().splitlines()[:-1])+'\n')
        end['rom_trace_sha256']=h.sha(h.read(p));(self.out/'EXECUTION_FINISHED.json').write_bytes(h.dump(end))
        r=self.collect_fixture(cfg);self.assertIn('ROM phase not observed: synthesize',r['findings'])
    def test_collect_flags_query_error_not_collection_count(self):
        cfg,end=self.synthetic_finished();p=self.out/'pds_stdout.log'
        p.write_text(p.read_text().replace('AA_QUERY\t0\t0\t','AA_QUERY\t0\t1\t',1))
        end['stdout_sha256']=h.sha(h.read(p));(self.out/'EXECUTION_FINISHED.json').write_bytes(h.dump(end))
        r=self.collect_fixture(cfg);self.assertTrue(r['query_errors']);self.assertFalse(r['constraint_object_counts_verified'])
    def test_relocated_config_cannot_overlap_protected_input(self):
        candidate=self.root/'candidate';candidate.mkdir()
        record=self.root/'record';record.mkdir();native=record/'native';native.mkdir()
        nested=record/'nested';nested.mkdir()
        cfg={'out':str(nested),'candidate':str(candidate),'native':str(native),'prepared':str(self.prepared),'helper_sha256':h.sha(h.read(h.__file__))}
        with self.assertRaises(h.Refusal):h.validate_config_paths(nested,cfg)
    def test_path_template_tokens_are_literal(self):
        out=self.root/'@HEX@_@PHASE@_@TRACE@'
        scripts,rows=h.generate(self.info,self.plan,self.prepared,out,self.nonce)
        self.assertIn('set aa_root '+h.tcl(out/'work'),scripts['rom_bootstrap.tcl'])
        self.assertIn('open '+h.tcl(out/'ROM_WORKDIRS.tsv'),scripts['rom_bootstrap.tcl'])
    def test_tcl_quote(self):
        self.assertEqual(h.tcl('a$[b]"c'), '"a\\$\\[b\\]\\"c"')

if __name__=='__main__': unittest.main(verbosity=2)
