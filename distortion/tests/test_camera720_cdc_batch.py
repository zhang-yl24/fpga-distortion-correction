"""Coverage must fail closed when grouped native detail is missing or rebound."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_cdc_batch as batch


def query(source='pipe/meta[0]/CLK',endpoint='pipe/sync[0]/D',cross=False):
    value = {'Label':'test','Source':source,'Endpoint':endpoint}
    if cross:
        value.update(SourceClock='camera_pclk',DestinationClock='board27')
    else:
        value['Clock'] = 'board27'
    return batch.requirements([value],{('camera_pclk','board27'):{'BoundNS':8.0}},
        {('camera_pclk','board27'):0.0},{'camera_pclk':20.833})[0]


def report(q,corner='slow',kind='setup',slack=1.0,arrival=2.0,bound=None):
    is_max = kind in ('setup','max-delay')
    typ = 'max' if is_max else 'min'
    check = 'Setup' if is_max else 'Hold'
    cross = 'Clock' not in q
    clocks = (q['SourceClock'],q['DestinationClock']) if cross else (q['Clock'],q['Clock'])
    exception = ''
    if cross:
        limit = (q['MaximumNS'] if is_max else q['MinimumNS']) if bound is None else bound
        exception = f'Timing Exception : {"Max" if is_max else "Min"}Delay Path {limit:.3f}ns'+(' -datapath_only' if is_max else '')+'\n'
    return (f'Startpoint : {q["Source"]}\nEndpoint : {q["Endpoint"]}\n'
            f'Path Type : {typ} ({corner} corner)\nPath Class : sequential timing path\n'+exception+
            f' Clock {clocks[0]} (rising edge) 0.000 0.000\n'
            f' Data arrival time {arrival:.3f} Logic Levels: 0\n'
            f' Clock {clocks[1]} (rising edge) 0.000 0.000\n'
            f' {check} time 0.100 0.100\n'
            f' Slack ({"MET" if slack >= 0 else "VIOLATED"}) {slack:.3f}\n')


class GroupedCoverageTests(unittest.TestCase):
    def test_one_source_groups_preserve_every_pair_and_bound_detail_budget(self):
        qs = [query(endpoint=f'sync[{i}]/D') for i in range(65)]
        qs += [query(source='other/meta/CLK',endpoint='other/sync/D')]
        bodies,groups = batch.bodies(qs,['IO_1_2'])
        self.assertEqual(len(groups),4)
        self.assertEqual(sum(len(g['ExpectedPairs']) for g in groups),66)
        self.assertTrue(all(len(g['Endpoints'])*8*4 <= 1000 for g in groups))
        self.assertEqual({(p['Source'],p['Endpoint']) for g in groups for p in g['ExpectedPairs']},
                         {(q['Source'],q['Endpoint']) for q in qs})
        self.assertEqual(len(batch.inspect.query_commands(bodies[0])),6)

    def test_many_source_inventory_splits_at_whitelist_limit(self):
        qs = [query(source=f'meta[{i}]/CLK') for i in range(301)]
        bodies,_ = batch.bodies(qs)
        self.assertEqual([len(batch.inspect.query_commands(b)) for b in bodies],[300,1])

    def test_tcl_injection_and_duplicate_pair_are_rejected(self):
        for source in ('bad}; exec x; {','pipe/$env(secret)','pipe\\\nname','pipe;exit'):
            with self.subTest(source=source),self.assertRaises(ValueError):
                batch.bodies([{'Source':source,'Endpoint':'x/D','Clock':'board27'}])
        q = query()
        with self.assertRaisesRegex(ValueError,'duplicate physical'):
            batch.requirements([q,q],{},{},{})

    def test_no_inference_from_top_n_paths_or_other_endpoints(self):
        q1,q2 = query(),query(endpoint='missing/sync/D')
        rows = [batch.parse_record(report(q1,c,k).splitlines(True),'native.rtr',1,q1)
                for c in q1['Corners'] for k in q1['CheckKinds']]
        value = batch.coverage([q1,q2],rows,[])
        self.assertEqual(value['CoveredCases'],4)
        self.assertEqual(len(value['MissingCases']),4)
        self.assertFalse(value['EnumeratedPathsTimingPassed'])
        self.assertEqual({r['Endpoint'] for r in value['MissingCases']},{q2['Endpoint']})

    def test_each_corner_and_kind_are_required_not_path_count(self):
        q = query()
        row = batch.parse_record(report(q).splitlines(True),'native.rtr',1,q)
        result = batch.coverage([q],[row]*1000,[])
        self.assertEqual(result['CoveredCases'],1)
        self.assertEqual(len(result['MissingCases']),3)
        self.assertFalse(result['Complete'])

    def test_complete_pairs_with_any_reported_violation_cannot_pass(self):
        q = query()
        rows = [batch.parse_record(report(q,c,k).splitlines(True),'native.rtr',1,q)
                for c in q['Corners'] for k in q['CheckKinds']]
        result = batch.coverage([q],rows,[{'Error':'additional native variant violated'}])
        self.assertTrue(result['Complete'])
        self.assertFalse(result['EnumeratedPathsTimingPassed'])

    def test_crossing_max_cannot_substitute_for_min(self):
        q = query(cross=True)
        rows = [batch.parse_record(report(q,c,'max-delay').splitlines(True),'native.rtr',1,q)
                for c in q['Corners']]
        result = batch.coverage([q],rows,[])
        self.assertEqual({r['Kind'] for r in result['MissingCases']},{'min-delay'})
        rows += [batch.parse_record(report(q,c,'min-delay').splitlines(True),'native.rtr',1,q)
                 for c in q['Corners']]
        self.assertTrue(batch.coverage([q],rows,[])['EnumeratedPathsTimingPassed'])

    def test_native_violation_bound_or_exception_mismatch_is_rejected(self):
        q = query(cross=True)
        bad = [report(q,kind='max-delay',slack=-0.001),
               report(q,kind='max-delay',bound=20),
               report(q,kind='max-delay',arrival=21),
               report(q,kind='max-delay').replace(' -datapath_only',''),
               report(q,kind='min-delay').replace('Clock camera_pclk','Clock other'),
               report(q,kind='min-delay').replace('Timing Exception : MinDelay Path 0.000ns\n','')]
        for text in bad:
            with self.subTest(text=text),self.assertRaises(ValueError):
                batch.parse_record(text.splitlines(True),'native.rtr',1,q)

    def test_ordinary_paths_need_matching_clocks_edges_and_no_exception(self):
        q = query()
        bad = [report(q).replace('Clock board27','Clock other',1),
               report(q).replace('(rising edge)','(falling edge)',1),
               report(q).replace('Path Class','Timing Exception : False Path\nPath Class'),
               report(q).replace('Setup time','Hold time'),
               report(q).replace(q['Endpoint'],'other/D')]
        for text in bad:
            with self.subTest(text=text),self.assertRaises(ValueError):
                batch.parse_record(text.splitlines(True),'native.rtr',1,q)

    def test_native_file_collection_retains_bad_variant_and_deduplicates(self):
        q = query()
        text = report(q)+report(q)+report(q,slack=-0.001)
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)/'fixture.rtr'; p.write_text(text,encoding='ascii')
            rows,violations = batch.collect([q],[p])
        self.assertEqual(len(rows),1)
        self.assertEqual(len(violations),1)
        self.assertIn('violation',violations[0]['Error'])

    def test_truncated_report_is_rejected(self):
        q = query()
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)/'fixture.rtr'; p.write_text(report(q).split(' Slack')[0],encoding='ascii')
            with self.assertRaisesRegex(ValueError,'truncated native'):
                batch.collect([q],[p])

    def test_only_exact_pair_supplement_or_exact_initial_body_is_allowed(self):
        qs = [query(endpoint='a/D'),query(endpoint='b/D')]
        initial,_ = batch.bodies(qs,['IO_1_2'])
        plan = {'Queries':qs}
        batch.approved_body(initial[0],plan,initial)
        exact,_ = batch.bodies(qs,exact=True)
        batch.approved_body(exact[0],plan,initial)
        grouped,_ = batch.bodies(qs)
        with self.assertRaisesRegex(ValueError,'neither planned batch'):
            batch.approved_body(grouped[0],plan,initial)
        with self.assertRaises(ValueError):
            batch.approved_body('show -dev_instance {UNPLANNED}\n',plan,initial)


class ReceiptBindingTests(unittest.TestCase):
    def bind_mock(self, schema, value, candidate, build='buildsha'):
        value = {'Mode':'query','Target':batch.prep.TARGET,'SourceADF':'candidate.adf',
                 'SourceADFSHA256':'actualsha','BuildPlanSHA256':'buildsha','Command':['pds_shell.exe'],**value}
        watched = {}
        if schema == 'camera720-reset-derived-inspection-v1':
            module = SimpleNamespace(bind_receipt=lambda path,watched:value)
        else:
            module = SimpleNamespace(bind_receipt=lambda path:(value,{}))
        with patch.object(batch,'add',side_effect=lambda watched,path,*args,**kwargs:Path(path)), \
             patch.object(batch,'read',return_value={'Schema':schema}), \
             patch.object(batch.importlib,'import_module',return_value=module), \
             patch.object(batch.structure,'local_helpers',return_value=[]):
            return batch.bind_native('result.json','query',watched,candidate,build)

    def test_all_three_receipt_adapters_reject_wrong_candidate_or_build(self):
        for schema in ('camera720-output-readonly-inspection-v1','camera720-derived-readonly-inspection-v1',
                       'camera720-reset-derived-inspection-v1'):
            candidate = {'Path':'candidate.adf','SHA256':'actualsha'}
            with self.subTest(schema=schema):
                self.assertEqual(self.bind_mock(schema,{},candidate)['SourceADFSHA256'],'actualsha')
                with self.assertRaisesRegex(ValueError,'different actual ADF'):
                    self.bind_mock(schema,{},dict(candidate,SHA256='oldsha'))
                with self.assertRaisesRegex(ValueError,'different actual ADF'):
                    self.bind_mock(schema,{},dict(candidate,Path='another.adf'))
                with self.assertRaisesRegex(ValueError,'different build'):
                    self.bind_mock(schema,{},candidate,'otherbuild')
                with self.assertRaisesRegex(ValueError,'mode/target'):
                    self.bind_mock(schema,{'Mode':'export'},candidate)

    def test_unknown_schema_cannot_bypass_native_binder(self):
        with self.assertRaisesRegex(ValueError,'unsupported actual'):
            self.bind_mock('some-passing-json',{},None)

    def test_sha_change_is_rejected_and_input_not_silently_rebound(self):
        with tempfile.TemporaryDirectory() as root,patch.object(batch.prep,'PROJECT',Path(root)):
            p = Path(root)/'evidence.txt'; p.write_text('a')
            watched = {}; batch.add(watched,p,hashlib.sha256(b'a').hexdigest())
            p.write_text('b')
            with self.assertRaisesRegex(ValueError,'digest differs'):
                batch.add(watched,p,hashlib.sha256(b'a').hexdigest())
            with self.assertRaisesRegex(ValueError,'changed while binding'):
                batch.add(watched,p)

    def test_crossing_without_explicit_bound_must_not_be_queried_as_ordinary(self):
        q = {'Source':'a/CLK','Endpoint':'b/D','SourceClock':'camera_pclk','DestinationClock':'board27'}
        with self.assertRaisesRegex(ValueError,'lacks exact'):
            batch.requirements([q],{}, {},{})


if __name__ == '__main__':
    unittest.main()
