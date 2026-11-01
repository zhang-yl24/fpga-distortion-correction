"""Offline scope/selection regression checks; synthetic evidence only."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import assemble_dataset as assembler


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.nine = [[r, c] for r in range(3) for c in range(3)]
        self.identity = {'camera_id':'test', 'lens_id':'test', 'profile_id':'test',
                         'capture_mode_id':'test', 'eye':'CAM2'}
        self.plan = self.root / 'plan.json'
        self.write(self.plan, {'identity':self.identity, 'image_size':[640,480],
            'required_coverage_cells':self.nine, 'minimum_tool_requirements':{
            'training_corners_per_required_cell':15,'held_out_corners_per_required_cell':3}})
        image = self.root / 'image.png'; image.write_bytes(b'synthetic evidence bytes')
        metadata = self.root / 'meta.json'
        self.write(metadata, {'identity_binding':self.identity, 'width':640,'height':480,
            'geometry_applied':False,'source_kind':'physical_native_camera','hardware_accessed':True,
            'pixel_format':'RGB565_LE','image_path':str(image),'image_sha256':assembler.sha(image)})
        self.scope = {'Schema':'current-vga-physical-visibility-scope-v1',
            'ImageSize':[640,480], 'Identity':self.identity, 'OriginalRequiredCoverageCells':self.nine,
            'RequiredCoverageCells':self.nine[:-1], 'ExcludedCoverageCells':[[2,2]],
            'MinimumTrainingCornersPerRequiredCell':15, 'MinimumHeldCornersPerRequiredCell':3,
            'SessionPlan':self.ref(self.plan),'EvidenceMetadata':self.ref(metadata),
            'EvidenceImage':self.ref(image),'UserReport':'Fixed obstruction', 'Reason':'Fixed hardware',
            'ExcludedCellDefinition':'Conservative lower-right source-image cell', 'Limits':'No full-field claim',
            'OtherQualityThresholdsChanged':False,'RenderingMaskApplied':False,'PixelGeometryChanged':False,
            'FullFrameCoverageClaimAllowed':False,'ExcludedRegionOpticalValidationClaimAllowed':False,
            'DecisionAnnouncedToUser':True}
        self.path = self.root / 'scope.json'
        self.freeze()

    def write(self, path, obj):path.write_text(json.dumps(obj), encoding='utf-8')
    def ref(self, path):return {'Path':str(path),'SHA256':assembler.sha(path)}
    def freeze(self):
        self.write(self.path,self.scope)
        self.progress = {'VisibilityScope':self.ref(self.path)}
    def load(self):
        return assembler.load_visibility_scope(self.path,plan_path=self.plan,progress=self.progress)

    def test_full_record_preserved(self):
        result=self.load()
        self.assertEqual(result['record'],self.scope)
        self.assertEqual(result['source_sha256'],assembler.sha(self.path))
        self.assertFalse(result['record']['FullFrameCoverageClaimAllowed'])

    def test_semantic_rejections_even_with_fresh_hash(self):
        mutations=[('Identity',dict(self.identity,eye='CAM1')),
            ('ExcludedCoverageCells',[[2,2],[2,0]]),('RequiredCoverageCells',self.nine[:-2]),
            ('OriginalRequiredCoverageCells',self.nine[:-1]),
            ('MinimumTrainingCornersPerRequiredCell',14),('MinimumHeldCornersPerRequiredCell',2),
            ('ImageSize',[320,240]),('OtherQualityThresholdsChanged',True),
            ('RenderingMaskApplied',True),('PixelGeometryChanged',True),
            ('FullFrameCoverageClaimAllowed',True),('ExcludedRegionOpticalValidationClaimAllowed',True),
            ('DecisionAnnouncedToUser',False),('Reason','')]
        original=copy.deepcopy(self.scope)
        for key,value in mutations:
            with self.subTest(key=key):
                self.scope=copy.deepcopy(original);self.scope[key]=value;self.freeze()
                with self.assertRaises(ValueError):self.load()

    def test_frozen_scope_hash(self):
        self.scope['Reason']='Different decision';self.write(self.path,self.scope)
        with self.assertRaisesRegex(ValueError,'frozen'):self.load()

    def test_plan_hash(self):
        self.scope['SessionPlan']['SHA256']='0'*64;self.freeze()
        with self.assertRaisesRegex(ValueError,'SHA256'):self.load()

    def test_evidence_tamper(self):
        Path(self.scope['EvidenceImage']['Path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'SHA256'):self.load()

    def test_metadata_binding(self):
        path=Path(self.scope['EvidenceMetadata']['Path'])
        meta=json.loads(path.read_text());meta['image_path']=str(self.root/'different.png')
        self.write(path,meta);self.scope['EvidenceMetadata']=self.ref(path);self.freeze()
        with self.assertRaisesRegex(ValueError,'image path'):self.load()

    def test_selected_attempt_and_warning(self):
        check=self.root/'quality.json'
        report={'manifest_view_candidate':{'view_id':'held-01','split':'held_out'},
                'image_sha256':'a'*64,'warnings':[]}
        self.write(check,report)
        selected={'QualityPath':str(check),'QualitySHA256':assembler.sha(check),
            'ViewID':'held-01','Split':'held_out','ImageSHA256':'a'*64}
        progress={'SelectedViews':[selected]}
        assembler.validate_selected_check(check,report,progress)
        with self.assertRaisesRegex(ValueError,'explicitly selected'):
            assembler.validate_selected_check(check,report,{'SelectedViews':[]})
        report['warnings']=['blur'];self.write(check,report);selected['QualitySHA256']=assembler.sha(check)
        with self.assertRaisesRegex(ValueError,'warnings'):
            assembler.validate_selected_check(check,report,progress)


if __name__=='__main__':unittest.main()
