from pathlib import Path
import copy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
from measurement_report import analyze_run
from fixture_packets import run, signature


class MeasurementReportTests(unittest.TestCase):
    def analyze(self, data):
        return analyze_run(*data)

    def test_counter_time_and_sampled_latency_exclude_UART_wall_time(self):
        r = self.analyze(run())
        self.assertEqual(r['status'], 'PASS_OFFLINE_SYNTHETIC_FIXTURE')
        self.assertEqual(r['core_window']['seconds_nominal'], 20)
        self.assertEqual(r['rates']['processed_new_correction_fps_nominal'], 20)
        self.assertEqual(r['rates']['new_presented_fps_nominal'], 15)
        self.assertEqual(r['rates']['scan_repeat_events_per_second_nominal'], 15)
        self.assertEqual(r['rates']['successful_nonblank_scan_repeat_fraction'], .5)
        s = r['sampled_internal_sourceaccept_to_success']
        self.assertEqual(s['distribution']['cycles']['median'], 6312500)
        self.assertEqual(s['distribution']['seconds_nominal']['median'], .0505)
        self.assertEqual(s['unambiguous_new_completion_samples_inside_window'], 1)
        self.assertEqual(s['sample_coverage_fraction_vs_window_completions'], 1/400)
        self.assertEqual(r['external_E2E'], 'UNMEASURED')

    def test_modulo32_events_sequence_and_low32_tick_carry(self):
        U = 1 << 32
        a = dict(ticks=U-100000000, sequence=U-1, frame_id=2000,
                 counts=(U-199, U-200, U-150, U-200, U-1), raw_cycles=6249999)
        b = dict(ticks=a['ticks']+2500000000, sequence=0, frame_id=2400,
                 counts=(201, 200, 150, 100, 1), raw_cycles=6374999)
        r = self.analyze(run(a, b))
        self.assertEqual(r['core_window']['delta'], dict(captured_frames=400, processed_frames=400,
                        presented_frames=300, scan_repeat_frames=300, dropped_frames=2))
        self.assertEqual(r['rates']['processed_new_correction_fps_nominal'], 20)

    def test_old_epoch_age_does_not_make_wrapped_legacy_cycles_absolute(self):
        U = 1 << 32
        a = dict(ticks=U+100000000, sequence=20, frame_id=2000,
                 counts=(101,100,90,8,0), raw_cycles=6249999)
        b = dict(ticks=a['ticks']+2500000000, sequence=21, frame_id=2001,
                 counts=(102,101,91,9,0), raw_cycles=6374999)
        r = self.analyze(run(a,b))
        s = r['sampled_internal_sourceaccept_to_success']
        self.assertEqual(s['distribution']['count'], 0)
        self.assertEqual(s['unproven_cycle_wrap_samples'], 2)
        self.assertIsNone(s['samples'][-1]['sourceaccept_to_success_seconds_nominal'])
        b.update(frame_id=2002, counts=(103,102,92,10,0))
        r = self.analyze(run(a,b))
        s = r['sampled_internal_sourceaccept_to_success']
        self.assertEqual(s['distribution']['count'], 1)
        self.assertFalse(s['samples'][0]['no_legacy_cycle_wrap_proven'])
        self.assertTrue(s['samples'][1]['no_legacy_cycle_wrap_proven'])

    def test_no_new_completions_cannot_silently_change_cycle_identity(self):
        a = dict(ticks=100000000, sequence=20, frame_id=2000,
                 counts=(101,100,90,8,0), raw_cycles=6249999)
        b = dict(ticks=a['ticks']+125000000, sequence=21, frame_id=2000,
                 counts=a['counts'], raw_cycles=6374999)
        with self.assertRaisesRegex(ValueError, 'tuple changed'):
            self.analyze(run(a,b))
        b['raw_cycles'] = a['raw_cycles']
        r = self.analyze(run(a,b))
        self.assertEqual(r['rates']['processed_new_correction_fps_nominal'], 0)
        self.assertIsNone(r['sampled_internal_sourceaccept_to_success']['sample_coverage_fraction_vs_window_completions'])

    def test_clock_version_nonce_mode_and_intermediate_identity_rejected(self):
        a = dict(ticks=100000000, sequence=20, frame_id=2000,
                 counts=(101,100,90,8,0), raw_cycles=6249999)
        b = dict(ticks=a['ticks']+125000000, sequence=21, frame_id=2002,
                 counts=(103,102,92,10,0), raw_cycles=6374999)
        for change in ({'hz':100000000}, {'version':1}, {'nonce':999}, {'mode':0}, {'flags':0x40}, {'sequence':20}, {'frame_id':1999}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.analyze(run(a,{**b,**change}))

    def test_reset_epoch_load_hash_boundary_CRC_and_full_tick_reset_rejected(self):
        bad_build=list(run());bad_build[1]['firmware_sha256']='NOT_BUILT';bad_build[3]['loaded_firmware_sha256']='NOT_BUILT'
        with self.assertRaisesRegex(ValueError,'built firmware'):
            self.analyze(bad_build)
        for name, value in (('uninterrupted_reset_epoch',False), ('loaded_firmware_sha256','0'*64),
                            ('known_packet_boundary_offset',1), ('boundary_evidence','')):
            data = list(run())
            data[3][name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.analyze(data)
        data = list(run())
        wire = bytearray(data[0]);wire[170] ^= 1;data[0] = bytes(wire)
        import hashlib
        data[4]['raw_sha256'] = hashlib.sha256(data[0]).hexdigest()
        with self.assertRaisesRegex(ValueError, 'CRC'):
            self.analyze(data)
        a = dict(ticks=5000000000, sequence=20, frame_id=2000,counts=(101,100,90,8,0),raw_cycles=6249999)
        b = dict(ticks=100000000, sequence=21, frame_id=2002,counts=(103,102,92,10,0),raw_cycles=6374999)
        with self.assertRaisesRegex(ValueError, 'positive'):
            self.analyze(run(a,b))

    def test_prefix_tail_and_magic_inside_packet_are_not_resynchronized(self):
        data = run(prefix=b'unparsed old partial UART',tail=b'PGSIG001\x01',embedded_magic=True)
        r = self.analyze(data)
        self.assertEqual(r['integrity']['validated_packet_count'], 5)
        self.assertEqual(r['integrity']['retained_tail_bytes'], 9)
        self.assertEqual(r['integrity']['excluded_prefix_bytes'], 25)
        bad = list(copy.deepcopy(data))
        bad[3]['known_packet_boundary_offset'] = 0
        with self.assertRaisesRegex(ValueError, 'boundary'):
            self.analyze(bad)

    def test_old_complete_prefix_is_walked_to_ARMED_without_magic_search(self):
        import hashlib
        data = list(run())
        old = signature(mode=0)
        data[0] = old + data[0]
        data[4].update(raw_sha256=hashlib.sha256(data[0]).hexdigest(),
                       validated_analysis_end_offset=data[4]['validated_analysis_end_offset']+len(old),
                       selected_ack_start_offset=len(old))
        r = self.analyze(data)
        self.assertEqual(r['integrity']['analysis_start_offset'],128)
        self.assertEqual(r['integrity']['strict_parsed_complete_packets_before_selected_ARMED'],1)
        data[4]['selected_ack_start_offset'] = 1
        with self.assertRaisesRegex(ValueError,'strict packet walk'):
            self.analyze(data)

    def test_session_ACK_status_and_exact_prechecked_plan_required(self):
        import hashlib,struct,zlib
        for mutation in ('signature_session','ACK_status'):
            data = list(run());b=bytearray(data[0])
            if mutation=='signature_session':
                struct.pack_into('<I',b,24+16,123)
                struct.pack_into('<I',b,24+120,zlib.crc32(b[24:24+120]))
            else:
                b[5]=3
                struct.pack_into('<I',b,20,zlib.crc32(b[:20]))
            data[0]=bytes(b);data[4]['raw_sha256']=hashlib.sha256(b).hexdigest()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                self.analyze(data)
        data=list(run());data[2]=copy.deepcopy(data[2]);data[2]['Commands'][1]['SHA256']='0'*64
        with self.assertRaisesRegex(ValueError,'exact existing'):
            self.analyze(data)

    def test_technical_window_limit_and_impossible_legacy_duration_rejected(self):
        a=dict(ticks=100000000,sequence=1,frame_id=2000,counts=(101,100,90,8,0),raw_cycles=6249999)
        b=dict(ticks=a['ticks']+(1<<32),sequence=2,frame_id=2002,counts=(103,102,92,10,0),raw_cycles=6374999)
        with self.assertRaisesRegex(ValueError,'shorter'):
            self.analyze(run(a,b))
        a['raw_cycles']=0xffffffff
        b['ticks']=a['ticks']+125000000
        with self.assertRaisesRegex(ValueError,'since-reset'):
            self.analyze(run(a,b))

    def test_exact_transmit_journal_and_request_fences_are_bound(self):
        data=list(run())
        tx=[]
        for index,command in enumerate(data[2]['Commands']):
            tx.append(dict(index=index+1,magic=command['Magic'],ticket=command['Ticket'],nonce=command['Nonce'],
                           hex=command['Hex'],sha256=command['SHA256'],outcome_uncertain=False,
                           disposition='HOST_WRITE_DRAINED',rx_fence_offset=(0,152,364)[index]))
        data[4]['TX_requests']=tx
        self.assertTrue(self.analyze(data)['integrity']['transmit_journal_validated'])
        for change in ({'outcome_uncertain':True},{'rx_fence_offset':365},{'hex':'00'}):
            invalid=copy.deepcopy(data);invalid[4]['TX_requests'][2].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.analyze(invalid)


if __name__ == '__main__':
    unittest.main()
