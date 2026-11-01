"""Delay-candidate mutation/inspection must not inherit old authority or paths."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_raw_camera_delay_reset_physical as physical
import run_raw_camera_delay_derived_inspect as derived


class ExternalBindingTests(unittest.TestCase):
    def setUp(self):
        self.pds = Path('D:/pango/PDS_2023.2/bin/pds_shell.exe')
        self.library = self.pds.parent.parent / 'arch/vendor/pango/logos2/common/lib/gtp_lib.v'

    def test_exact_pds_and_technology_file_are_watched(self):
        watched = {}
        for path in (self.pds, self.library):
            self.assertEqual(physical.add(watched, path, physical.sha(path), self.pds), path)
        self.assertEqual(set(watched), {self.pds, self.library})

    def test_library_without_bound_pds_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'escapes'):
            physical.add({}, self.library)

    def test_adjacent_installation_file_is_rejected(self):
        unrelated = self.pds.parent.parent / 'doc/Tcl_Command_User_Guide.pdf'
        with self.assertRaisesRegex(ValueError, 'escapes'):
            physical.add({}, unrelated, pds=self.pds)

    def test_non_executable_cannot_establish_external_authority(self):
        with self.assertRaisesRegex(ValueError, 'exact canonical PDS executable'):
            physical.add({}, self.library, pds=self.library)

    def test_changed_library_digest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            physical.add({}, self.library, '0' * 64, self.pds)

    def test_library_interfaces_are_revalidated(self):
        with patch.object(physical.prep, 'validate_primitive_library', side_effect=ValueError('changed interface')):
            with self.assertRaisesRegex(ValueError, 'changed interface'):
                physical.add({}, self.library, pds=self.pds)


class ProofAndStagesTests(unittest.TestCase):
    def graph(self):
        return {'Target':physical.prep.TARGET,
                'HeaderOnlyAdapter':physical.prep.TARGET + ' to board1080_top for strict V_* parsing',
                'TiedInputs':{5:1}, 'RegisteredStickyPropertyVerified':True}

    def test_json_integer_key_roundtrip_preserves_full_graph(self):
        actual = self.graph()
        physical.graph_semantics(actual, json.loads(json.dumps(actual)))

    def test_altered_graph_field_is_rejected(self):
        actual = self.graph(); claimed = json.loads(json.dumps(actual))
        claimed['RegisteredStickyPropertyVerified'] = False
        with self.assertRaisesRegex(ValueError, 'differs from proof'):
            physical.graph_semantics(actual, claimed)

    def test_old_graph_target_is_rejected_even_if_self_consistent(self):
        old = self.graph(); old['Target'] = 'raw_camera_capture_cam2_reset'
        with self.assertRaisesRegex(ValueError, 'current input-delay target'):
            physical.graph_semantics(old, json.loads(json.dumps(old)))

    def test_old_proof_cannot_authorize_new_application(self):
        proof = {'Schema':'raw-camera-reset-proof-v1', 'Target':'raw_camera_capture_cam2_reset', 'Status':'pass'}
        with self.assertRaisesRegex(ValueError, 'proof identity'):
            physical.proof_flags(proof)

    def test_application_has_one_sta_and_only_later_save(self):
        work = physical.prep.WORK / 'not-created-physical-test'
        commands = ['set_false_path -from [get_pins -hierarchical -regexp {^(source/CLK)$}] -to [get_pins -hierarchical -regexp {^(target/CLR)$}]']
        text = physical.render(commands, work)
        self.assertEqual(text.count(physical.INIT), 1)
        self.assertEqual(text.count('save_adif'), 1)
        self.assertLess(text.index(physical.INIT), text.index(commands[0]))
        self.assertLess(text.index(commands[0]), text.index('save_adif'))
        for forbidden in ('manual_route', 'unroute ', 'generate_bitstream', 'programmer'):
            self.assertNotIn(forbidden, text)

    def test_derived_report_is_fresh_read_only_and_one_sta(self):
        work = physical.prep.WORK / 'not-created-derived-test'
        text = derived.render('report', '', work, work)
        self.assertEqual(text.count(derived.inspect.INIT), 1)
        self.assertNotIn('save_adif', text)
        self.assertNotIn('manual_route', text)
        self.assertIn(derived.MARKER, text)

    def test_derived_does_not_accept_old_route_application(self):
        fake = physical.prep.WORK / 'not-created-test/result.json'
        with patch.object(derived.inspect, 'canonical', return_value=fake), patch.object(
                derived, 'read', return_value={'Schema':'raw-camera-route-reset-application-v1'}):
            with self.assertRaisesRegex(ValueError, 'unsupported input-delay mutation'):
                derived.bind_source_receipt(fake, {})

    def test_false_path_command_rejects_unmeasured_target_regex(self):
        row = {'Source':'source/CLK', 'Targets':['target/CLR'], 'ExpectedFromCount':1,
               'ExpectedTargetCount':1, 'ExpectedNativeFromNames':['t:source/CLK'],
               'ExpectedNativeToNames':['t:target/CLR'], 'FromRegex':'^(source/CLK)$', 'ToRegex':'^(.*)$'}
        with self.assertRaisesRegex(ValueError, 'not exact'):
            physical.exact_commands([row])


if __name__ == '__main__': unittest.main()
