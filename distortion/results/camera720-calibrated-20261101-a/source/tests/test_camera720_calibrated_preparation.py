"""Focused CPU-only preparation checks; no native executor is launched."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_camera720_calibrated as prep
import run_camera720_calibrated_diagnostic as runner
import run_camera720_corrected_system_sim as simulation


def sample_mapping():
    return {'passed':True,'sample_stride':1,'full_requested_frames_checked':True,
        'source_image_size':[1280,720],'output_size':[1280,720],
        'coordinates_checked':921600,'requested_full_frame_coordinates':921600,
        'output_K':[[480.,0.,639.5],[0.,480.,359.5],[0.,0.,1.]],
        'criteria':{'maximum_coordinate_error_px':.25,'minimum_in_bounds_fraction':.99,
                    'arithmetic_invalid_max':0,'folded_samples_max':0,'requires_stride_one':True},
        'integer_config':[163712,92032,163712,92032,81792,81792,2236962,2236962,-674237,121875,-11577,0,0],
        'required_radius_guard_q22_for_checked_rays':11000002,
        'frames':[{'angle_deg':0,'coordinates_checked':921600,'numerical_gates_passed':True,
                   'finite_opencv_reference':True,'fixed_point_invalid_coordinates':0,'reference_folded_samples':0,
                   'fixed_point_folded_samples':0,'maximum_coordinate_error_px':.07,
                   'bilinear_all_neighbours_in_bounds_fraction':1.,'opencv_all_neighbours_in_bounds_fraction':1.,
                   'maximum_normalized_radius_squared_q22':11000000}]}


class PurePreparationTests(unittest.TestCase):
    def test_transport_changes_only_module_and_include(self):
        old=(prep.PROJECT/prep.transport.TOP).read_text(encoding='utf-8')
        new=prep.render_top(old)
        restored=new.replace('module '+prep.TARGET,'module '+prep.transport.TARGET,1).replace(prep.HEADER,prep.transport.HEADER,1)
        self.assertEqual(restored,old)
        self.assertIn('parameter CAMERA_WARMUP_MS=8000',new)
        self.assertIn('.BANK_STRIDE(1048576)',new)

    def test_header_negative_literals_round_trip(self):
        mapping=sample_mapping();config,guard=prep.mapping_parameters(mapping)
        e={'Profile':{'SHA256':'1'*64},'MappingAudit':{'SHA256':'2'*64}}
        text=prep.render_header(config,guard,e).decode()
        self.assertIn("-32'sd674237",text)
        self.assertEqual(simulation.parse_header(text),(config,guard))

    def test_incomplete_or_relaxed_mapping_rejected(self):
        cases=[('sample_stride',2),('coordinates_checked',1000),('output_size',[640,480])]
        for k,v in cases:
            m=sample_mapping();m[k]=v
            with self.subTest(field=k),self.assertRaises(ValueError):prep.mapping_parameters(m)
        m=sample_mapping();m['criteria']['minimum_in_bounds_fraction']=.5
        with self.assertRaisesRegex(ValueError,'budgets'):prep.mapping_parameters(m)

    def test_overflow_fold_radius_and_neighbours_rejected(self):
        for field,value in [('fixed_point_invalid_coordinates',1),('reference_folded_samples',1),
                            ('fixed_point_folded_samples',1),('maximum_coordinate_error_px',.3),
                            ('bilinear_all_neighbours_in_bounds_fraction',.999)]:
            m=sample_mapping();m['frames'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):prep.mapping_parameters(m)
        m=sample_mapping();m['required_radius_guard_q22_for_checked_rays']-=1
        with self.assertRaisesRegex(ValueError,'radius'):prep.mapping_parameters(m)

    def test_signed_widths_and_tangential_change_rejected(self):
        c=sample_mapping()['integer_config']
        for i,v in [(0,1<<23),(8,1<<31),(11,1)]:
            x=c.copy();x[i]=v
            with self.subTest(index=i),self.assertRaises(ValueError):prep.validate_config(x,100)

    def test_firstfit_cannot_substitute_target_report(self):
        with self.assertRaisesRegex(ValueError,'measured target'):prep.validate_profile({}, {'DiagnosticFitWithinDeclaredBudget':True})

    def test_profile_is_exact_fixed_target_without_optical_claim(self):
        identity={'camera_id':'camera','lens_id':'lens','profile_id':'measured-candidate','capture_mode_id':'current720'}
        parameters={'K':[[300.,0,640.],[0,300.,360.],[0,0,1.]],'D':[0.,0.,0.,0.],
                    'projection':'forward_rectilinear','maximum_ray_angle_deg':88.,'inverse_method':'bounded_monotone_bisection_v1'}
        validation={'schema':prep.target.REPORT_SCHEMA,'native_physical_observed_views_passed':True,
                    'coverage_passed':None,'intrinsics_refitted':False,'candidate_parameters':parameters,'target_identity':identity}
        profile={**identity,'model':'fisheye','image_size':[1280,720],'K':parameters['K'],'D':parameters['D'],
                 'model_scope':{k:parameters[k] for k in ('projection','maximum_ray_angle_deg','inverse_method')},
                 'development_only':True,'passed':False,'candidate_ready_for_profile_review':False,'independent_spatial_coverage_passed':False}
        prep.validate_profile(profile,validation)
        for key,value in [('lens_id','different'),('passed',True),('D',[.1,0.,0.,0.])]:
            bad=copy.deepcopy(profile);bad[key]=value
            with self.subTest(field=key),self.assertRaises(ValueError):prep.validate_profile(bad,validation)

    def test_strict_critical_diagnostic_scan_present(self):
        text=Path(runner.__file__).read_text()
        self.assertIn('(?:C:|E:|F:|ERROR:|FATAL:|Traceback)',text)

    def test_request_cannot_supply_unhashed_evidence(self):
        for item in ({'Path':str(prep.SELF)}, {'Path':str(prep.SELF),'SHA256':''}):
            with self.assertRaises(ValueError):prep.bind({},item)


class CompiledRecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prep.WORK.mkdir(parents=True,exist_ok=True)
        cls.temporary=tempfile.TemporaryDirectory(prefix='_ci_',dir=prep.WORK)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.scratch=Path(cls.temporary.name).resolve()
        if cls.scratch.parent!=prep.WORK.resolve():
            raise AssertionError('test fixture escaped calibrated workspace')
        cls.pds=cls.scratch/'pds_shell.exe'
        cls.pds.write_bytes(b'INERT CPU TEST FILE; NEVER EXECUTE\n')
        cls.base_plan,_,_=prep.transport.recipe(
            prep.transport.WORK/'_test_calibrated_baseline',str(cls.pds))
        cls.roles=prep.transport.validate_sources()

    def test_isolated_recipe_and_full_runner_validation(self):
        with tempfile.TemporaryDirectory(prefix='_tcal_',dir=prep.WORK) as directory:
            work=Path(directory).resolve();work.rmdir()
            config,guard=prep.mapping_parameters(sample_mapping())
            evidence={'Profile':{'SHA256':'1'*64},'MappingAudit':{'SHA256':'2'*64},
                      'IntegerConfig':config,'RadiusQ22':guard,'SyntheticTestFixture':True}
            with (mock.patch.object(prep,'calibration',return_value=(evidence,{})),
                 mock.patch.object(prep.transport,'recipe',return_value=(copy.deepcopy(self.base_plan),{},b'')),
                 mock.patch.object(prep.transport,'validate_sources',return_value=copy.deepcopy(self.roles)),
                 mock.patch.object(runner.subprocess,'Popen') as process):
                plan=prep.prepare(prep.SELF,work)
                context=runner.validate_plan(work/'plan.json')
                process.assert_not_called()
                self.assertEqual(context['Plan']['Target'],prep.TARGET)
                self.assertEqual(len(plan['ExplicitDesigns']),31)
                self.assertEqual(sum(Path(p).suffix=='.idf' for p in plan['ExplicitDesigns']),1)
                self.assertFalse(plan['TimingAccepted']);self.assertFalse(plan['FPSParametersChanged'])
                compiled=(work/'compiled'/prep.TOP).read_text()
                self.assertIn((work/'compiled'/prep.HEADER).as_posix(),compiled)
                self.assertNotIn('gen_bit_stream',(work/'timing.tcl').read_text())
                self.assertIn('compile -top_module '+prep.TARGET,(work/'timing.tcl').read_text())
                (work/'source'/prep.HEADER).write_bytes(b'mutated')
                with self.assertRaisesRegex(ValueError,'bytes differ'):runner.validate_plan(work/'plan.json')
                process.assert_not_called()


if __name__=='__main__':unittest.main()
