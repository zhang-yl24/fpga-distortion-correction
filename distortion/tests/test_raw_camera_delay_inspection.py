"""Independent delay diagnostics must reject old receipts and library substitution."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_raw_camera_delay_inspect as inspect
import audit_raw_camera_delay_reset as audit
import prepare_raw_camera_delay_reset_scope as scope
import audit_raw_camera_delay_reset_netlist as graph


class DelayInspectionTests(unittest.TestCase):
    def setUp(self):
        self.pds = Path('D:/pango/PDS_2023.2/bin/pds_shell.exe')
        self.library = self.pds.parent.parent / 'arch/vendor/pango/logos2/common/lib/gtp_lib.v'
        self.plan = {'PDS': {'Executable':str(self.pds)},
                     'TechnologyPrimitiveSource':inspect.prep.validate_primitive_library(self.library)}

    def test_actual_technology_library_is_watched(self):
        watched = {}
        self.assertEqual(inspect.bind_technology_source(self.plan, watched), self.library)
        self.assertEqual(watched, {self.library:inspect.sha(self.library)})

    def test_another_installed_file_is_not_a_library(self):
        self.plan['TechnologyPrimitiveSource']['Path'] = str(self.pds)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            inspect.bind_technology_source(self.plan, {})

    def test_changed_library_digest_is_rejected(self):
        self.plan['TechnologyPrimitiveSource']['SHA256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'proof differs'):
            inspect.bind_technology_source(self.plan, {})

    def test_mapping_claim_cannot_be_inherited_from_interface_check(self):
        self.plan['TechnologyPrimitiveSource']['NativeMappingVerified'] = True
        with self.assertRaisesRegex(ValueError, 'proof differs'):
            inspect.bind_technology_source(self.plan, {})

    def test_old_reset_receipt_is_rejected(self):
        old = {'Schema':'raw-camera-reset-readonly-inspection-v1',
               'Target':'raw_camera_capture_cam2_reset', 'Mode':'export'}
        with self.assertRaisesRegex(ValueError, 'wrong identity'):
            audit.receipt_status(old, 'export', '0' * 64)

    def test_old_reset_netlist_is_rejected_before_graph_parse(self):
        with self.assertRaisesRegex(ValueError, 'one exact raw-reset module'):
            graph.audit_text('module raw_camera_capture_cam2_reset;\nendmodule\n', [])

    def test_old_reset_report_is_not_relabeled(self):
        text = '| Design : raw_camera_capture_cam2_reset\n'
        with patch.object(Path, 'open', return_value=io.StringIO(text)):
            with self.assertRaisesRegex(ValueError, 'not for raw_camera_capture_cam2_delay'):
                scope.parse_report(Path('unused.rtr'))

    def test_read_only_query_rejects_route_mutation_and_tcl_suffix(self):
        for command in ['save_adif', 'unroute -design_net {_N1;}',
                        'show -design_net {_N1}; save_adif']:
            with self.subTest(command=command):
                with self.assertRaisesRegex(ValueError, 'unsupported read-only query'):
                    inspect.query_commands(command)

    def test_native_query_has_one_sta_initialization(self):
        work = inspect.prep.WORK / 'not-created-by-test'
        body = 'show -design_net {nt_cam_data[2]}'
        text = inspect.render('query', '', work, work, body)
        self.assertEqual(text.count(inspect.INIT), 1)
        self.assertNotIn('save_adif', text)
        self.assertIn(inspect.MARKER, text)


if __name__ == '__main__': unittest.main()
