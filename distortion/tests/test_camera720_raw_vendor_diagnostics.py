"""CPU fault cases for the exact vendor reset and diagnostic disposition scope."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_raw_vendor_basis as basis
import camera720_raw_diagnostics as diag

FIXTURE = Path(__file__).resolve().parent/'fixtures/camera720-raw-vendor-contract.json'


def recorded_fixture():
    # Replay only the parser contracts used here. Production audit_value still
    # requires original build/source hashes and never consumes this fixture.
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class VendorResetContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = recorded_fixture()['Scope']

    def test_actual_placed_graph_contract(self):
        self.assertEqual(len(basis.validate_scope_contract(copy.deepcopy(self.scope))),5)

    def test_other_adf_cannot_inherit_contract(self):
        value=copy.deepcopy(self.scope);value['SourceADFSHA256']='0'*64
        with self.assertRaisesRegex(ValueError,'route-b'):
            basis.validate_scope_contract(value)

    def test_same_count_wrong_family_rejected(self):
        value=copy.deepcopy(self.scope);value['NativeQueries'][1]['Family']='unreviewed_reset'
        with self.assertRaisesRegex(ValueError,'family'):
            basis.validate_scope_contract(value)

    def test_duplicate_target_rejected(self):
        value=copy.deepcopy(self.scope)
        q=next(q for q in value['NativeQueries'] if q['Family']=='dqs_reset')
        q['Targets'][1]=q['Targets'][0]
        with self.assertRaisesRegex(ValueError,'duplicate'):
            basis.validate_scope_contract(value)

    def test_nonsticky_entry_rejected(self):
        value=copy.deepcopy(self.scope);value['StructuralProof']['RegisteredStickyPropertyVerified']=False
        with self.assertRaisesRegex(ValueError,'entry'):
            basis.validate_scope_contract(value)

    def test_first_stage_functional_branch_rejected(self):
        value=copy.deepcopy(self.scope);value['StructuralProof']['FirstStageFunctionalFanout']=2
        with self.assertRaisesRegex(ValueError,'entry'):
            basis.validate_scope_contract(value)

    def test_second_stage_changed_clock_rejected(self):
        value=copy.deepcopy(self.scope);value['StructuralProof']['Stages'][1]['Ports']['CK']='other_clock'
        with self.assertRaisesRegex(ValueError,'two-stage'):
            basis.validate_scope_contract(value)

    def test_preexisting_authority_rejected(self):
        value=copy.deepcopy(self.scope);value['TimingExceptionApproved']=True
        with self.assertRaisesRegex(ValueError,'authority'):
            basis.validate_scope_contract(value)


class DiagnosticDispositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture=recorded_fixture()
        cls.review={'DiagnosticEvents':fixture['DiagnosticEvents']}
        cls.receipt=fixture['Receipt']
        # These validate_events tests must reject an invalid claimed bound
        # before reading a native log or any compiled source.
        cls.lines=[]
        cls.vendor_text='\n'.join(row['Text'] for row in fixture['VendorZeroRows'])

    def test_actual_exact_copies_and_original_vendor_high_bits(self):
        self.assertEqual(sum(diag.validate_diagnostic_copies(self.receipt,self.review['DiagnosticEvents']).values()),60)
        self.assertEqual(len(diag.validate_original_vendor_zeros(self.vendor_text)),9)

    def test_extra_error_rejected(self):
        value=copy.deepcopy(self.receipt);value['Diagnostics'].append('compile/run.log: E: unknown failure')
        with self.assertRaisesRegex(ValueError,'non-reviewed'):
            diag.validate_diagnostic_copies(value,self.review['DiagnosticEvents'])

    def test_missing_log_copy_rejected(self):
        value=copy.deepcopy(self.receipt);value['Diagnostics'].pop()
        with self.assertRaisesRegex(ValueError,'multiset'):
            diag.validate_diagnostic_copies(value,self.review['DiagnosticEvents'])

    def test_changed_width_message_rejected(self):
        value=copy.deepcopy(self.receipt);value['Diagnostics'][0]=value['Diagnostics'][0].replace('16 to 12','16 to 11')
        with self.assertRaisesRegex(ValueError,'multiset'):
            diag.validate_diagnostic_copies(value,self.review['DiagnosticEvents'])

    def test_falsely_clean_receipt_rejected(self):
        value=copy.deepcopy(self.receipt);value['ExecutionCompletedWithoutError']=True
        with self.assertRaisesRegex(ValueError,'failed receipt'):
            diag.validate_diagnostic_copies(value,self.review['DiagnosticEvents'])

    def test_invalid_public_terminal_bound_rejected(self):
        events=copy.deepcopy(self.review['DiagnosticEvents']);events[0]['ReachableMaximum']=4096
        with self.assertRaisesRegex(ValueError,'bound differs'):
            diag.validate_events(events,self.lines,{})

    def test_internal_counter_proof_not_invented(self):
        events=copy.deepcopy(self.review['DiagnosticEvents']);events[13]['RTLBoundProved']=True
        with self.assertRaisesRegex(ValueError,'protected counter'):
            diag.validate_events(events,self.lines,{})

    def test_missing_original_vendor_high_bit_rejected(self):
        text=self.vendor_text.replace('mcdq_dcp_buf/cnt[6]','mcdq_dcp_buf/cnt[5]')
        with self.assertRaisesRegex(ValueError,'high-bit'):
            diag.validate_original_vendor_zeros(text)

    def test_duplicate_original_vendor_high_bit_rejected(self):
        row=diag.validate_original_vendor_zeros(self.vendor_text)[0]['Text']
        with self.assertRaisesRegex(ValueError,'high-bit'):
            diag.validate_original_vendor_zeros(self.vendor_text+'\n'+row)

    def test_duplicate_actual_parameter_block_rejected(self):
        text='I: Module instance {a/u_ddr3_test_h} parameter value:\n    X = 2\n'
        with self.assertRaisesRegex(ValueError,'duplicated'):
            diag.parameter_blocks(text+text)


if __name__=='__main__':
    unittest.main()
