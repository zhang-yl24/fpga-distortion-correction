"""Reject absent power confirmation and mismatched hardware/capture evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import raw_camera_delay_program as program
import raw_camera_delay_capture_binding as binding


class ProgrammingAuthorizationTests(unittest.TestCase):
    def test_current_power_confirmation_is_required(self):
        with self.assertRaisesRegex(ValueError, 'power must be confirmed'):
            program.execution_authorization(False, True, 90)

    def test_notify_flag_is_required(self):
        with self.assertRaisesRegex(ValueError, 'notify user'):
            program.execution_authorization(True, False, 90)

    def test_integer_truthiness_is_not_confirmation(self):
        with self.assertRaises(ValueError):
            program.execution_authorization(1, True, 90)

    def test_unbounded_or_nonfinite_timeout_is_rejected(self):
        for value in (0, -1, 301, float('inf'), float('nan'), True):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'timeout'):
                program.execution_authorization(True, True, value)

    def test_only_sram_scripts_are_available(self):
        scripts = program.scripts(Path('D:/example/raw_camera_capture_cam2_delay.sbit'))
        self.assertEqual(set(scripts), {'scan','program'})
        self.assertNotIn('flash', '\n'.join(scripts.values()).lower())
        self.assertEqual(scripts['program'].count('cfg_program -device_index 0'), 1)


class BindingDeclarationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'review.json'
        self.review = {'Schema':binding.REVIEW_SCHEMA, 'Target':binding.prep.TARGET, 'Eye':'CAM2',
            'Declarations':{name:True for name in binding.capture.CONNECTION_FIELDS[:-1]},
            'Evidence':{name:'synthetic unit test evidence only' for name in binding.capture.CONNECTION_FIELDS[:-1]}}

    def save_review(self):
        self.path.write_text(json.dumps(self.review), encoding='utf-8')
        return self.path

    def test_declared_review_requires_per_field_evidence(self):
        self.review['Evidence'].pop('power_and_io_verified')
        with self.assertRaisesRegex(ValueError, 'actual review evidence'):
            binding.review_declarations(self.save_review())

    def test_false_review_cannot_be_promoted(self):
        self.review['Declarations']['selected_eye_verified'] = False
        with self.assertRaisesRegex(ValueError, 'three explicit'):
            binding.review_declarations(self.save_review())

    def test_empty_review_evidence_is_rejected(self):
        self.review['Evidence']['power_and_io_verified'] = '  '
        with self.assertRaisesRegex(ValueError, 'actual review evidence'):
            binding.review_declarations(self.save_review())

    def test_another_candidate_review_is_rejected(self):
        self.review['Target'] = 'camera_vga_upright_top'
        with self.assertRaisesRegex(ValueError, 'current CAM2 review'):
            binding.review_declarations(self.save_review())

    def test_identity_template_does_not_copy_hardware_claims(self):
        template = {'schema':1, 'camera_id':'camera', 'lens_id':'lens', 'profile_id':'profile',
            'capture_mode_id':'mode', 'eye':'CAM2', 'image_size':[640,480], 'pixel_format':'RGB565_LE',
            'connection_review':{name:True for name in binding.capture.CONNECTION_FIELDS},
            'build_binding':{'bitstream':{'path':'unrelated','sha256':'0'*64}}}
        identity = binding.identity_from_template(template)
        self.assertNotIn('connection_review', identity)
        self.assertNotIn('build_binding', identity)
        self.assertEqual(identity['eye'], 'CAM2')

    def test_only_vga_cam2_identity_is_supported(self):
        template = {'schema':1, 'camera_id':'camera', 'lens_id':'lens', 'profile_id':'profile',
            'capture_mode_id':'mode', 'eye':'CAM1', 'image_size':[640,480], 'pixel_format':'RGB565_LE'}
        with self.assertRaisesRegex(ValueError, 'only current CAM2 VGA'):
            binding.identity_from_template(template)

    def test_old_program_receipt_rejected_before_native_validation(self):
        path = self.root / 'receipt.json'
        path.write_text(json.dumps({'Schema':'camera-vga-upright-sram-execution-v1','Target':'camera_vga_upright_top'}))
        with patch.object(binding.bit.inspect, 'canonical', return_value=path), \
                patch.object(binding.program, 'validate') as validate:
            with self.assertRaisesRegex(ValueError, 'another candidate'):
                binding.checked_program_receipt(path, self.root, {})
            validate.assert_not_called()

    def test_missing_done_rejected_before_plan_revalidation(self):
        value = {'Schema':'raw-camera-delay-sram-execution-v1', 'Target':binding.prep.TARGET}
        value.update({k:True for k in ('Passed','Executed','HardwareAccessed','ProgrammingAttempted',
            'UserConfirmedBoardPowered','UserNotifiedBeforeExecution','CurrentPowerConfirmationAsserted')})
        value['DoneConfirmed'] = False
        path = self.root / 'receipt.json'; path.write_text(json.dumps(value))
        with patch.object(binding.bit.inspect, 'canonical', return_value=path), \
                patch.object(binding.program, 'validate') as validate:
            with self.assertRaisesRegex(ValueError, 'DoneConfirmed'):
                binding.checked_program_receipt(path, self.root, {})
            validate.assert_not_called()


if __name__ == '__main__': unittest.main()
