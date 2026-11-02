from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
from measurement_report import analyze_run
from fixture_packets import run

N = 1920 * 1080
U = 1 << 32


def endpoints():
    a = dict(ticks=U-100000000, sequence=17, frame_id=2000,
             counts=(401,400,350,100,2),raw_cycles=6249999,flags=0x12)
    b = dict(ticks=a['ticks']+2500000000,sequence=18,frame_id=2400,
             counts=(801,800,650,400,4),raw_cycles=6374999,flags=0x12)
    return a,b


class V1CounterInvariants(unittest.TestCase):
    def test_native_minimum_rejects_zero_and_below_N_unwrapped_values(self):
        for endpoint in (0,1):
            for raw in (0,N-2):
                a,b=endpoints()
                (a if endpoint==0 else b)['raw_cycles']=raw
                with self.subTest(endpoint=endpoint,raw=raw),self.assertRaisesRegex(ValueError,'coordinate edge lower bound'):
                    analyze_run(*run(a,b))

    def test_N_edges_is_not_rejected_by_a_stronger_guessed_lower_bound(self):
        a,b=endpoints();a['raw_cycles']=N-1;b['raw_cycles']=N-1
        r=analyze_run(*run(a,b))
        self.assertEqual(r['sampled_internal_sourceaccept_to_success']['distribution']['cycles']['min'],N)

    def test_small_residue_with_unproven_wrap_is_retained_not_reported_as_8ns(self):
        a,b=endpoints();a.update(ticks=10*U,raw_cycles=0)
        b.update(ticks=a['ticks']+125000000,frame_id=a['frame_id'],counts=a['counts'],raw_cycles=0)
        r=analyze_run(*run(a,b))
        self.assertEqual(r['sampled_internal_sourceaccept_to_success']['distribution']['count'],0)
        for sample in r['sampled_internal_sourceaccept_to_success']['samples']:
            self.assertEqual(sample['cycles_candidate_raw_plus1'],1)
            self.assertIsNone(sample['sourceaccept_to_success_seconds_nominal'])

    def test_same_completion_keeps_its_earlier_no_wrap_proof_across_tick_carry(self):
        a,b=endpoints();b.update(frame_id=a['frame_id'],counts=a['counts'],raw_cycles=a['raw_cycles'])
        r=analyze_run(*run(a,b))
        samples=r['sampled_internal_sourceaccept_to_success']['samples']
        self.assertTrue(samples[0]['no_legacy_cycle_wrap_proven'])
        self.assertTrue(samples[1]['no_legacy_cycle_wrap_proven'])
        self.assertIn('earlier',samples[1]['no_wrap_evidence'])
        self.assertEqual(r['sampled_internal_sourceaccept_to_success']['distribution']['count'],1)

    def test_902_accepts_and_2_completions_cannot_leave_901_healthy_jobs(self):
        a,b=endpoints();b.update(frame_id=2002,counts=(1303,402,352,102,4))
        with self.assertRaisesRegex(ValueError,'snapshot invariant'):
            analyze_run(*run(a,b))

    def test_processing_flag_must_match_modulo32_outstanding_job(self):
        a,b=endpoints();b['counts']=(800,800,650,400,4)
        with self.assertRaisesRegex(ValueError,'snapshot invariant'):
            analyze_run(*run(a,b))

    def test_drop_changes_do_not_enter_accept_complete_conservation(self):
        # One old active frame and one new frame finish. One new acceptance:
        # dA-dC=-1, ending idle. Granted capture drops are separate events.
        a,b=endpoints();b.update(frame_id=2002,counts=(402,402,352,102,39),flags=0x10)
        r=analyze_run(*run(a,b))
        self.assertEqual(r['core_window']['delta']['captured_frames'],1)
        self.assertEqual(r['core_window']['delta']['processed_frames'],2)
        self.assertEqual(r['core_window']['delta']['dropped_frames'],37)
        self.assertEqual(r['sampled_internal_sourceaccept_to_success']['samples'][1]['accepted_minus_completed'],0)

    def test_idle_to_one_active_frame_and_drop_with_no_completion_is_legal(self):
        a,b=endpoints();a.update(counts=(400,400,350,100,2),flags=0x10)
        b.update(frame_id=2000,counts=(401,400,350,100,8),flags=0x12,raw_cycles=a['raw_cycles'])
        r=analyze_run(*run(a,b))
        self.assertEqual(r['core_window']['delta']['processed_frames'],0)
        self.assertEqual(r['core_window']['delta']['captured_frames'],1)

    def test_native_serial_coordinate_throughput_bound_is_not_one_per_core_edge(self):
        a,b=endpoints();b.update(ticks=a['ticks']+3*N,frame_id=2005,
                                 counts=(406,405,355,100,2),raw_cycles=N-1)
        with self.assertRaisesRegex(ValueError,'coordinate-throughput bound'):
            analyze_run(*run(a,b))


if __name__=='__main__':
    unittest.main()
