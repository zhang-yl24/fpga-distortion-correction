"""Reject missing evidence, failed timing, wrong hardware identity or stage order."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import raw_camera_delay_bitstream as bit


class TimingTests(unittest.TestCase):
    def tables(self):
        return {(corner, kind): {('a', 'b'):{'FailingChecks':0,'WorstSlackNS':0.01,'TotalNegativeSlackNS':0}}
                for corner in ('slow','fast') for kind in ('setup','hold','recovery','removal','mpw')}

    def test_missing_corner_table_is_rejected(self):
        tables = self.tables(); del tables[('fast','hold')]
        with patch.object(bit.timing, 'summaries', return_value=(tables, {'clock':1})):
            with self.assertRaisesRegex(ValueError, 'all ten'):
                bit.passed_tables(Path('unused'))

    def test_one_negative_hold_is_rejected(self):
        tables = self.tables(); tables[('fast','hold')][('a','b')]['WorstSlackNS'] = -0.001
        with patch.object(bit.timing, 'summaries', return_value=(tables, {'clock':1})):
            with self.assertRaisesRegex(ValueError, 'must pass'):
                bit.passed_tables(Path('unused'))

    def test_current_ten_tables_pass(self):
        tables = self.tables()
        with patch.object(bit.timing, 'summaries', return_value=(tables, {'clock':1})):
            self.assertEqual(bit.passed_tables(Path('unused'))[0], tables)


class IdentityTests(unittest.TestCase):
    def native_header(self, design=None):
        values = [design or bit.prep.TARGET, 'Logos2-PG2L100H--6-FBG676', '2026/10/31', '23:59:59',
                  'Fabric Compiler', '2023.2-SP3<154097>']
        data = bytes.fromhex('00090ff00ff00ff00ff000') + b'PANGO MICROSYSTEMS, INC.\0\1'
        for tag, value in zip(b'abcdef', values):
            raw = value.encode('ascii') + b'\0'
            data += bytes([tag]) + len(raw).to_bytes(2, 'big') + raw
        return data + b'ghi' + bytes(1000001)

    def test_bit_header_binds_new_target(self):
        self.assertEqual(bit.bit_header(self.native_header())['Design'], bit.prep.TARGET)
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            bit.bit_header(self.native_header('raw_camera_capture_cam2_reset'))

    def test_runtime_gate_must_precede_programming_file_generation(self):
        digest = 'a'*64
        correct = '\n'.join(['Process "Report Timing" started.', 'Process "Report Timing" done.',
                              'RAW_CAMERA_DELAY_GATE_PASS '+digest, 'Process "Generate Bitstream" started.',
                              'Process "Generate Bitstream" done.', bit.COMPLETE])
        self.assertEqual(len(bit.events(correct, digest)), 6)
        wrong = correct.replace('RAW_CAMERA_DELAY_GATE_PASS '+digest+'\n', '') + '\nRAW_CAMERA_DELAY_GATE_PASS '+digest
        with self.assertRaisesRegex(ValueError, 'order differs'):
            bit.events(wrong, digest)

    def test_an_extra_synthesis_stage_is_not_accepted(self):
        with self.assertRaisesRegex(ValueError, 'order differs'):
            bit.events('Process "Synthesize" started.', 'b'*64)


class ProofTests(unittest.TestCase):
    def test_io_query_cannot_inject_fabricated_native_output(self):
        pins = {'PinInventory':[{'Site':'IOLHR_16_294'}]}
        body = 'show -dev_instance {IOLHR_16_294}\n'
        bit.require_io_query_commands(body, pins)
        with self.assertRaisesRegex(ValueError, 'query commands differ'):
            bit.require_io_query_commands(body + 'puts {fabricated native mapping}\n', pins)

    def fixture(self):
        export = {'SourceADFSHA256':'a'*64}
        proof = {'Schema':bit.interfaces.SCHEMA,'Target':bit.prep.TARGET,'StructuralAuditPassed':True,
                 'ScopedDigitalChecksPassed':True,'Blockers':[],'BaselineDiagnosticOnly':False,
                 'CandidateADFSHA256':'a'*64,'ExportReceipt':{'path':'export'},
                 'EffectReceipt':{'Receipt':{'path':'effect'}},'MissingGrayCases':[],
                 'MissingHeldCases':[],'PendingInterstageCases':[],
                 'Pins':{'FinalNativeSiteMappingPassed':True,'FinalFunctionalPadSiteMappingPassed':True}}
        return proof, export

    def check(self, proof, export):
        with patch.object(bit.effect, 'file_binding', side_effect=lambda name: {'path':str(name)}):
            bit.io_flags(proof, Path('export'), export, Path('effect'))

    def test_baseline_cannot_authorize_bit(self):
        proof, export = self.fixture(); proof['BaselineDiagnosticOnly'] = True
        with self.assertRaisesRegex(ValueError, 'complete current'):
            self.check(proof, export)

    def test_missing_interstage_query_cannot_hide_under_pass_flag(self):
        proof, export = self.fixture(); proof['PendingInterstageCases'] = [{'Source':'a','Endpoint':'b'}]
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.check(proof, export)

    def test_missing_actual_pin_query_is_rejected(self):
        proof, export = self.fixture(); proof['Pins']['FinalNativeSiteMappingPassed'] = False
        with self.assertRaisesRegex(ValueError, 'IO mapping missing'):
            self.check(proof, export)

    def test_process_local_cache_is_invalid_after_input_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            request = Path(folder)/'request.json'; request.write_text('{}')
            proof = Path(folder)/'proof.json'; proof.write_text('first')
            watched = {request:bit.sha(request), proof:bit.sha(proof)}
            bit._AUTHORITY_CACHE[str(request)] = {'Watched':watched,'Sentinel':'computed-only'}
            try:
                with patch.object(bit.inspect, 'canonical', return_value=request):
                    self.assertEqual(bit.authority(request)['Sentinel'], 'computed-only')
                    proof.write_text('changed')
                    with patch.object(bit, 'add', side_effect=lambda watched,path,*args: Path(path)):
                        with self.assertRaisesRegex(ValueError, 'exact input-delay bit request'):
                            bit.authority(request)
            finally:
                bit._AUTHORITY_CACHE.pop(str(request), None)


if __name__ == '__main__': unittest.main()
